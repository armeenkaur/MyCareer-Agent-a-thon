from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from wsproto import ConnectionType, WSConnection
from wsproto.events import (
    AcceptConnection,
    CloseConnection,
    Ping,
    Request,
    TextMessage,
)

from ..backend import BackendError
from . import ROLEPLAY_BUCKETS
from .client import AzureVoiceLiveBridge

log = logging.getLogger("skillsync.voice_live.ws")


def _flush(handler: Any, ws: WSConnection, event: Any) -> None:
    """wsproto 1.3+: Connection.send() returns bytes to write (no bytes_to_send)."""
    payload = ws.send(event)
    if payload:
        handler.connection.sendall(payload)


def handle_voice_roleplay_ws(handler: Any, backend: Any) -> None:
    """Upgrade HTTP connection and proxy browser PCM ↔ Azure Voice Live."""
    parsed = urlparse(handler.path)
    query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
    token = str(query.get("token") or "").strip()
    session_id = str(query.get("session_id") or "").strip()
    if not token:
        auth = str(handler.headers.get("Authorization") or "")
        if auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ").strip()
    try:
        user = backend.user_for_token(token)
        if user.get("role") != "employee":
            raise BackendError("Employee access required.", "forbidden", 403)
        ticket = backend.voice_roleplay_ticket(session_id, user)
    except BackendError as exc:
        _reject_http(handler, exc.status, exc.message)
        return
    except Exception as exc:  # noqa: BLE001
        log.exception("Voice WS auth failed")
        _reject_http(handler, 401, str(exc))
        return

    if str(handler.headers.get("Upgrade") or "").lower() != "websocket":
        _reject_http(handler, 426, "WebSocket upgrade required.")
        return

    ws = WSConnection(ConnectionType.SERVER)
    try:
        headers = [(name.encode("latin-1"), value.encode("latin-1")) for name, value in handler.headers.items()]
        ws.initiate_upgrade_connection(headers, parsed.path)
        accepted = False
        for event in ws.events():
            if isinstance(event, Request):
                _flush(handler, ws, AcceptConnection())
                accepted = True
                break
        if not accepted:
            _reject_http(handler, 400, "Invalid WebSocket handshake.")
            return
    except Exception as exc:  # noqa: BLE001
        log.exception("WebSocket handshake failed")
        _reject_http(handler, 400, f"WebSocket handshake failed: {exc}")
        return

    outbound: queue.Queue[dict[str, Any] | None] = queue.Queue()
    kind = ticket["kind"]
    skills = ROLEPLAY_BUCKETS[kind]
    bridge: AzureVoiceLiveBridge | None = None
    stop = threading.Event()

    def on_azure_event(event: dict[str, Any]) -> None:
        outbound.put(event)

    writer = threading.Thread(
        target=_writer_loop,
        args=(handler, ws, outbound, stop),
        name="voice-ws-writer",
        daemon=True,
    )
    writer.start()

    try:
        bridge = AzureVoiceLiveBridge(kind, skills, on_azure_event)
        bridge.start()
        _reader_loop(handler, ws, bridge, outbound, stop, backend, ticket, session_id)
    except Exception as exc:  # noqa: BLE001
        log.exception("Voice WS session failed session_id=%s", session_id)
        outbound.put({"type": "error", "message": str(exc)})
        try:
            backend.fail_voice_roleplay(session_id, str(exc))
        except Exception:  # noqa: BLE001
            pass
    finally:
        stop.set()
        outbound.put(None)
        if bridge:
            bridge.close()
        try:
            _flush(handler, ws, CloseConnection(0, "done"))
        except Exception:  # noqa: BLE001
            pass
        writer.join(timeout=3)


def _reject_http(handler: Any, status: int, message: str) -> None:
    body = json.dumps({"error": {"code": "voice_ws", "message": message}}).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _writer_loop(
    handler: Any,
    ws: WSConnection,
    outbound: queue.Queue[dict[str, Any] | None],
    stop: threading.Event,
) -> None:
    while not stop.is_set():
        try:
            item = outbound.get(timeout=0.5)
        except queue.Empty:
            continue
        if item is None:
            break
        try:
            _flush(handler, ws, TextMessage(json.dumps(item)))
        except Exception:  # noqa: BLE001
            break


def _reader_loop(
    handler: Any,
    ws: WSConnection,
    bridge: AzureVoiceLiveBridge,
    outbound: queue.Queue[dict[str, Any] | None],
    stop: threading.Event,
    backend: Any,
    ticket: dict[str, Any],
    session_id: str,
) -> None:
    sock = handler.connection
    sock.settimeout(1.0)
    scored = False
    while not stop.is_set():
        try:
            data = sock.recv(65536)
        except TimeoutError:
            continue
        except OSError:
            break
        if not data:
            break
        ws.receive_data(data)
        for event in ws.events():
            if isinstance(event, CloseConnection):
                stop.set()
                return
            if isinstance(event, Ping):
                _flush(handler, ws, event.response())
                continue
            if isinstance(event, TextMessage):
                text = event.data if isinstance(event.data, str) else event.data.decode("utf-8")
                try:
                    message = json.loads(text)
                except json.JSONDecodeError:
                    continue
                mtype = str(message.get("type") or "")
                if mtype == "audio":
                    bridge.append_audio(str(message.get("data") or ""))
                elif mtype == "end" and not scored:
                    scored = True
                    bridge.stop_speaking()
                    outbound.put({"type": "status", "message": "Ending and scoring…"})
                    try:
                        ratings = bridge.request_scores()
                        result = backend.complete_voice_roleplay(session_id, ticket["employee_code"], ratings)
                        # Never send proficiency ratings to the employee client.
                        outbound.put(
                            {
                                "type": "complete",
                                "lattice_unlocked": result.get("lattice_unlocked", False),
                                "sessions": result.get("sessions", []),
                            }
                        )
                    except Exception as exc:  # noqa: BLE001
                        log.exception("Voice scoring failed session_id=%s", session_id)
                        outbound.put({"type": "error", "message": str(exc)})
                        backend.fail_voice_roleplay(session_id, str(exc))
                    stop.set()
                    return
                elif mtype == "ping":
                    outbound.put({"type": "pong"})
