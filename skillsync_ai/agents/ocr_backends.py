"""Optional heavy Hugging Face OCR backend. Tesseract remains runtime default."""

from __future__ import annotations

import io
import threading
from typing import Any

QWEN_VL_MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
from ..core.logging_setup import get_logger

log = get_logger("skillsync.ocr.backends")

_lock = threading.Lock()
_model: Any = None
_processor: Any = None
_device: str | None = None
_load_error: str | None = None


def extract_hf(payload: bytes, filename: str) -> dict[str, str]:
    try:
        model, processor, device = _get_hf_model()
    except Exception as exc:  # noqa: BLE001
        log.error("HF OCR load failed: %s", exc)
        return {"text": "", "source": "hf-qwen-vl", "error": str(exc)}

    try:
        from PIL import Image

        image = Image.open(io.BytesIO(payload)).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {
                        "type": "text",
                        "text": (
                            "Transcribe all the text found in this role-play / assessment screenshot accurately. "
                            "Include scores, feedback, strengths, weaknesses, and outcome labels if visible."
                        ),
                    },
                ],
            }
        ]
        text_prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(images=[image], texts=[text_prompt], padding=True, return_tensors="pt")
        inputs = {key: value.to(device) if hasattr(value, "to") else value for key, value in inputs.items()}

        import torch

        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=1024)
        trimmed = [out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs["input_ids"], generated_ids)]
        output_text = processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        text = (output_text[0] if output_text else "").strip()
        log.info("HF OCR ok model=%s chars=%s", QWEN_VL_MODEL_ID, len(text))
        return {"text": text, "source": f"hf:{QWEN_VL_MODEL_ID}", "error": ""}
    except Exception as exc:  # noqa: BLE001
        log.exception("HF OCR failed")
        return {"text": "", "source": "hf-qwen-vl", "error": f"OCR failed: {exc}"}


def _get_hf_model() -> tuple[Any, Any, str]:
    global _model, _processor, _device, _load_error
    with _lock:
        if _model is not None and _processor is not None and _device is not None:
            return _model, _processor, _device
        if _load_error:
            raise RuntimeError(_load_error)
        try:
            import torch
            from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
        except ImportError as exc:
            _load_error = f"Missing HF deps: {exc}"
            raise RuntimeError(_load_error) from exc

        if torch.cuda.is_available():
            device = "cuda"
            dtype = torch.bfloat16
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            device = "mps"
            dtype = torch.float16
        else:
            device = "cpu"
            dtype = torch.float32

        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            QWEN_VL_MODEL_ID,
            torch_dtype=dtype,
            device_map="auto" if device == "cuda" else None,
        )
        if device != "cuda":
            model = model.to(device)
        processor = AutoProcessor.from_pretrained(QWEN_VL_MODEL_ID)
        _model, _processor, _device = model, processor, device
        return _model, _processor, _device
