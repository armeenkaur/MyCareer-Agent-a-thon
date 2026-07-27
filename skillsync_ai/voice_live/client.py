from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
from collections.abc import Callable
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from ..core.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_VOICE_LIVE_URL,
    AZURE_VOICE_LIVE_VOICE,
    AZURE_VOICE_LIVE_VOICE_FALLBACK,
    AZURE_VOICE_LIVE_VOICE_FALLBACK_TYPE,
    AZURE_VOICE_LIVE_VOICE_TYPE,
)
from . import load_prompt, scoring_instruction

log = logging.getLogger("skillsync.voice_live")

VALID_LEVELS = frozenset({"Beginner", "Intermediate", "Proficient", "Advanced"})


def _voice_candidates() -> list[tuple[str, str]]:
    """Female voices only. Hotels primary Diya HD, then Ava/Jenny neural, then OpenAI shimmer/coral."""
    ordered = [
        (AZURE_VOICE_LIVE_VOICE or "en-IN-Diya:DragonHDLatestNeural", AZURE_VOICE_LIVE_VOICE_TYPE or "azure-standard"),
        (
            AZURE_VOICE_LIVE_VOICE_FALLBACK or "en-US-AvaNeural",
            AZURE_VOICE_LIVE_VOICE_FALLBACK_TYPE or "azure-standard",
        ),
        ("en-IN-Diya:DragonHDLatestNeural", "azure-standard"),
        ("en-US-AvaNeural", "azure-standard"),
        ("en-US-JennyNeural", "azure-standard"),
        ("en-IN-NeerjaNeural", "azure-standard"),
        ("shimmer", "openai"),
        ("coral", "openai"),
    ]
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for name, vtype in ordered:
        voice = str(name or "").strip()
        kind = str(vtype or "azure-standard").strip() or "azure-standard"
        if not voice:
            continue
        key = (voice, kind)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out or [("en-US-AvaNeural", "azure-standard")]


def _session_update_payload(kind: str, voice: str, voice_type: str) -> dict[str, Any]:
    # OpenAI voices: {type,name}. Azure TTS: include temperature like Hotels-VoiceBot.
    if voice_type == "openai":
        voice_block: dict[str, Any] = {"type": "openai", "name": voice}
    else:
        voice_block = {
            "type": voice_type or "azure-standard",
            "name": voice,
            "temperature": 0.6,
        }
    return {
        "type": "session.update",
        "session": {
            # This deployment allows only ["audio"] or ["text"], not both.
            "modalities": ["audio"],
            "voice": voice_block,
            "temperature": 0.6,
            "instructions": load_prompt(kind),
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_sampling_rate": 16000,
            "turn_detection": {
                "type": "azure_semantic_vad",
                "threshold": 0.6,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 900,
                "create_response": True,
                "interrupt_response": True,
                "remove_filler_words": True,
            },
        },
    }


def _hello_payload(kind: str) -> dict[str, Any]:
    if kind == "behavioural":
        opening = (
            "Open in English only for this first turn. Stay in character as Sarah Patel. "
            "Do not greet as an assessor or mention roleplay/assessment. "
            "Paraphrase this kick-off opening, then stop and wait for the learner — "
            "one question only, no second question: "
            "Thanks for joining. Before we commit resources, I need more clarity. "
            "The customer has already added new requirements since signing, Engineering is stretched, "
            "and I'm not convinced we've agreed what success looks like. "
            "Can you walk us through how you see this project working?"
        )
    else:
        opening = (
            "Open in English only for this first turn. "
            "Greet briefly and ask ONE short functional skills roleplay question, then stop and wait. "
            "Do not mention language rules. Do not ask a second question."
        )
    return {
        "type": "response.create",
        "response": {
            "modalities": ["audio"],
            "instructions": opening,
        },
    }


def _score_payload(kind: str, *, strict: bool = False) -> dict[str, Any]:
    return {
        "type": "response.create",
        "response": {
            "modalities": ["text"],
            "instructions": scoring_instruction(kind, strict=strict),
        },
    }


def parse_ratings_json(text: str, expected_skills: list[str]) -> dict[str, str]:
    """Extract ratings map from model text; raise ValueError if unusable."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty scoring response.")
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    payload = _first_ratings_object(raw)
    ratings = payload.get("ratings") if isinstance(payload, dict) else None
    if not isinstance(ratings, dict):
        raise ValueError("Scoring JSON missing ratings object.")
    cleaned: dict[str, str] = {}
    for skill in expected_skills:
        level = str(ratings.get(skill) or "").strip()
        if level not in VALID_LEVELS:
            raise ValueError(f"Invalid or missing level for {skill}.")
        cleaned[skill] = level
    return cleaned


def _first_ratings_object(raw: str) -> dict[str, Any]:
    """Parse first JSON object that contains ratings (handles duplicated / trailing junk)."""
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(raw):
        start = raw.find("{", idx)
        if start < 0:
            break
        try:
            obj, end = decoder.raw_decode(raw, start)
        except json.JSONDecodeError:
            idx = start + 1
            continue
        if isinstance(obj, dict) and isinstance(obj.get("ratings"), dict):
            return obj
        idx = end
    raise ValueError("Scoring response was not JSON.")


class AzureVoiceLiveBridge:
    """Async Azure Voice Live session: audio relay + end-of-call score (no tools)."""

    def __init__(
        self,
        kind: str,
        expected_skills: list[str],
        on_event: Callable[[dict[str, Any]], None],
    ) -> None:
        if not AZURE_OPENAI_API_KEY:
            raise RuntimeError("AZURE_OPENAI_API_KEY is not configured.")
        if not AZURE_VOICE_LIVE_URL:
            raise RuntimeError("AZURE_VOICE_LIVE_URL is not configured.")
        self.kind = kind
        self.expected_skills = expected_skills
        self.on_event = on_event
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ws: ClientConnection | None = None
        self._ready = threading.Event()
        self._closed = threading.Event()
        self._error: str | None = None
        self._score_text_parts: list[str] = []
        self._scoring = False
        self._mute_output = False
        self._score_future: asyncio.Future[dict[str, str]] | None = None
        self._score_generation = 0
        self._voice_candidates = _voice_candidates()
        self._voice_index = 0
        self._session_ack = asyncio.Event()
        self._applied_voice: Any = None
        self._hello_sent = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_thread, name="voice-live-azure", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=30):
            raise RuntimeError(self._error or "Timed out connecting to Azure Voice Live.")
        if self._error:
            raise RuntimeError(self._error)

    def _run_thread(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception as exc:  # noqa: BLE001 — surface to callers via _error
            self._error = str(exc)
            log.exception("Azure Voice Live bridge failed")
            self.on_event({"type": "error", "message": str(exc)})
        finally:
            self._ready.set()
            self._closed.set()

    async def _main(self) -> None:
        self._loop = asyncio.get_running_loop()
        headers = {"api-key": AZURE_OPENAI_API_KEY}
        async with websockets.connect(
            AZURE_VOICE_LIVE_URL,
            additional_headers=headers,
            max_size=8 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=20,
        ) as ws:
            self._ws = ws
            await self._configure_voice_and_greet()
            self._ready.set()
            self.on_event({"type": "ready"})
            async for raw in ws:
                if self._closed.is_set():
                    break
                await self._handle_azure_message(raw)

    async def _configure_voice_and_greet(self) -> None:
        """Apply voice, wait for session.updated, then greet — avoids default male alloy."""
        if self._ws is None:
            return
        voice, voice_type = self._voice_candidates[self._voice_index]
        log.info("Voice Live requesting voice=%s type=%s", voice, voice_type)
        self._session_ack = asyncio.Event()
        self._applied_voice = None
        self._hello_sent = False
        await self._ws.send(json.dumps(_session_update_payload(self.kind, voice, voice_type)))
        try:
            await asyncio.wait_for(self._session_ack.wait(), timeout=8)
        except TimeoutError:
            log.warning("No session.updated within 8s; greeting with requested voice=%s anyway", voice)
        log.info("Voice Live applied voice=%s", self._applied_voice)
        if not self._hello_sent:
            await self._ws.send(json.dumps(_hello_payload(self.kind)))
            self._hello_sent = True

    async def _handle_azure_message(self, raw: str | bytes) -> None:
        try:
            event = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
        except (TypeError, ValueError, UnicodeDecodeError):
            return
        etype = str(event.get("type") or "")
        if etype == "session.updated":
            session = event.get("session") or {}
            self._applied_voice = session.get("voice")
            log.info("session.updated voice=%s", self._applied_voice)
            self._session_ack.set()
            return
        if etype == "response.audio.delta":
            delta = event.get("delta") or event.get("audio")
            if delta and not self._scoring and not self._mute_output:
                self.on_event({"type": "audio", "data": delta})
            return
        if etype in {"response.audio_transcript.delta", "response.text.delta"}:
            if self._scoring:
                part = event.get("delta") or ""
                if part:
                    self._score_text_parts.append(str(part))
            return
        if etype in {"response.audio_transcript.done", "response.text.done"}:
            if self._scoring and not self._score_text_parts:
                transcript = event.get("transcript") or event.get("text")
                if transcript:
                    self._score_text_parts.append(str(transcript))
            return
        if etype == "response.done" and self._scoring:
            generation = self._score_generation
            text = "".join(self._score_text_parts).strip()
            if not text:
                text = self._extract_text_from_done(event)
            log.info("Voice score raw text chars=%s preview=%r", len(text), text[:240])
            future = self._score_future
            if not future or future.done() or generation != self._score_generation:
                return
            try:
                ratings = parse_ratings_json(text, self.expected_skills)
                future.set_result(ratings)
            except Exception as exc:  # noqa: BLE001
                log.warning("Voice score parse failed: %s raw=%r", exc, text[:500])
                future.set_exception(exc)
            return
        if etype == "error":
            message = str((event.get("error") or {}).get("message") or event.get("message") or "Azure error")
            log.warning("Azure Voice Live error: %s", message)
            if await self._maybe_fallback_voice(message):
                return
            self.on_event({"type": "error", "message": message})

    async def _maybe_fallback_voice(self, message: str) -> bool:
        """Retry next female voice if Azure rejects the current one."""
        if self._ws is None or self._closed.is_set():
            return False
        lowered = message.lower()
        if "modalit" in lowered:
            return False
        voice_related = any(
            token in lowered
            for token in ("voice", "unsupported", "invalid voice", "not found", "not available", "unknown voice")
        )
        if not voice_related:
            return False
        next_index = self._voice_index + 1
        if next_index >= len(self._voice_candidates):
            return False
        self._voice_index = next_index
        voice, voice_type = self._voice_candidates[self._voice_index]
        log.warning("Voice rejected (%s); falling back to %s (%s)", message[:200], voice, voice_type)
        self.on_event({"type": "status", "message": f"Switching to female voice {voice}…"})
        self._session_ack = asyncio.Event()
        self._applied_voice = None
        self._hello_sent = False
        await self._ws.send(json.dumps(_session_update_payload(self.kind, voice, voice_type)))
        try:
            await asyncio.wait_for(self._session_ack.wait(), timeout=8)
        except TimeoutError:
            log.warning("Fallback voice ack timeout for %s", voice)
        if not self._hello_sent:
            await self._ws.send(json.dumps(_hello_payload(self.kind)))
            self._hello_sent = True
        return True

    @staticmethod
    def _extract_text_from_done(event: dict[str, Any]) -> str:
        response = event.get("response") or {}
        parts: list[str] = []
        for item in response.get("output") or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                text = content.get("text") or content.get("transcript")
                if text:
                    parts.append(str(text))
        return "".join(parts)

    def append_audio(self, pcm16_b64: str) -> None:
        if not pcm16_b64 or self._scoring or self._mute_output or self._closed.is_set():
            return
        payload = json.dumps({"type": "input_audio_buffer.append", "audio": pcm16_b64})
        self._send_raw(payload)

    def stop_speaking(self) -> None:
        """Hard-stop bot audio + mic relay when user ends the session."""
        self._mute_output = True
        self._scoring = True
        self._send_raw(json.dumps({"type": "response.cancel"}))
        self._send_raw(json.dumps({"type": "input_audio_buffer.clear"}))
        self.on_event({"type": "status", "message": "Stopping — scoring…"})

    def request_scores(self, timeout: float = 60.0) -> dict[str, str]:
        if not self._loop or self._closed.is_set():
            raise RuntimeError("Voice session is not connected.")
        future: asyncio.Future[dict[str, str]] = asyncio.run_coroutine_threadsafe(
            self._score_async(), self._loop
        )
        return future.result(timeout=timeout)

    async def _score_async(self) -> dict[str, str]:
        self._scoring = True
        self._mute_output = True
        self._score_text_parts = []
        self._score_generation += 1
        generation = self._score_generation
        loop = asyncio.get_running_loop()
        self._score_future = loop.create_future()
        assert self._ws is not None
        await self._ws.send(json.dumps(_score_payload(self.kind)))
        try:
            return await asyncio.wait_for(self._score_future, timeout=45)
        except Exception:
            if self._score_future and not self._score_future.done() and generation == self._score_generation:
                self._score_future.cancel()
            self._score_text_parts = []
            self._score_generation += 1
            generation = self._score_generation
            self._score_future = loop.create_future()
            await self._ws.send(json.dumps(_score_payload(self.kind, strict=True)))
            return await asyncio.wait_for(self._score_future, timeout=30)

    def _send_raw(self, payload: str) -> None:
        if not self._loop or self._closed.is_set() or not self._ws:
            return

        async def _send() -> None:
            if self._ws and not self._closed.is_set():
                await self._ws.send(payload)

        asyncio.run_coroutine_threadsafe(_send(), self._loop)

    def close(self) -> None:
        self._closed.set()
        self._mute_output = True
        if self._loop and self._ws:
            asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
