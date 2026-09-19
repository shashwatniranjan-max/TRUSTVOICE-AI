"""Local CPU speech-to-text (faster-whisper). Independent of AASIST."""

from __future__ import annotations

import os
import time

DEFAULT_ASR_MODEL = "tiny"
MAX_ASR_SECONDS = float(os.environ.get("TRUSTVOICE_ASR_MAX_SEC", "180"))
ASR_FAILURE_WARNING = (
    "ASR unavailable/failed. Voice authenticity was analyzed, but conversation "
    "content could not be automatically analyzed."
)

_MODELS: dict = {}


def asr_model_name() -> str:
    name = (os.environ.get("TRUSTVOICE_ASR_MODEL") or DEFAULT_ASR_MODEL).strip()
    return name or DEFAULT_ASR_MODEL


def _empty_result(**overrides) -> dict:
    out = {
        "transcript": "",
        "status": "error",
        "model": asr_model_name(),
        "language": None,
        "duration": None,
        "elapsed_sec": None,
        "error": None,
    }
    out.update(overrides)
    return out


def get_whisper_model(model_name: str | None = None):
    """Load once per process. CPU int8 by default."""
    name = model_name or asr_model_name()
    cached = _MODELS.get(name)
    if cached is not None:
        return cached
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        ) from exc

    last_error = None
    for compute in ("int8", "default"):
        try:
            model = WhisperModel(
                name,
                device="cpu",
                compute_type=compute,
                cpu_threads=int(os.environ.get("TRUSTVOICE_ASR_THREADS", "1")),
            )
            _MODELS[name] = model
            return model
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not load ASR model '{name}': {last_error}")


def transcribe_pcm(samples, sample_rate: int = 16000, duration: float | None = None) -> dict:
    """Transcribe 16 kHz mono float PCM. Never raises to the caller."""
    model_id = asr_model_name()
    dur = duration
    try:
        if samples is None:
            return _empty_result(
                status="decode_failed",
                model=model_id,
                error="No decoded audio samples were available for ASR.",
            )
        n = int(getattr(samples, "size", 0) or len(samples))
        sr = int(sample_rate or 16000)
        if dur is None and sr:
            dur = round(n / float(sr), 3)
        if dur is not None and dur > MAX_ASR_SECONDS:
            return _empty_result(
                status="too_long",
                model=model_id,
                duration=float(dur),
                error=(
                    f"Audio is {dur:.1f}s; ASR is limited to {MAX_ASR_SECONDS:.0f}s "
                    "for this deployment. Trim the clip or set TRUSTVOICE_ASR_MAX_SEC."
                ),
            )
        if n < int(0.4 * sr):
            return _empty_result(
                status="no_speech",
                model=model_id,
                duration=dur,
                error="Clip is too short for reliable transcription.",
            )

        started = time.perf_counter()
        model = get_whisper_model(model_id)
        segments, info = model.transcribe(
            samples,
            language=None,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = " ".join((getattr(seg, "text", "") or "").strip() for seg in segments).strip()
        elapsed = round(time.perf_counter() - started, 3)
        language = getattr(info, "language", None) or None
        if language is not None:
            language = str(language).strip() or None
        if not text:
            return _empty_result(
                status="no_speech",
                model=model_id,
                language=language,
                duration=dur,
                elapsed_sec=elapsed,
                error="ASR returned no speech.",
            )
        return {
            "transcript": text,
            "status": "success",
            "model": model_id,
            "language": language,
            "duration": dur,
            "elapsed_sec": elapsed,
            "error": None,
        }
    except Exception as exc:
        return _empty_result(
            status="unavailable" if "not installed" in str(exc).lower() else "error",
            model=model_id,
            duration=dur,
            error=f"{type(exc).__name__}: {exc}",
        )


def resolve_live_transcript(manual: str, asr: dict | None) -> dict:
    """Choose the text that feeds the existing interaction engine."""
    manual_text = (manual or "").strip()
    asr = asr or {}
    asr_text = (asr.get("transcript") or "").strip()
    asr_ok = asr.get("status") == "success" and bool(asr_text)

    if manual_text:
        return {
            "text": manual_text,
            "source": "MANUAL",
            "analyze": True,
            "asr_text": asr_text or None,
            "warning": None,
        }
    if asr_ok:
        return {
            "text": asr_text,
            "source": "ASR",
            "analyze": True,
            "asr_text": asr_text,
            "warning": None,
        }

    status = asr.get("status") or "unavailable"
    if status == "too_long":
        warning = asr.get("error") or ASR_FAILURE_WARNING
    elif status in {"unavailable", "error", "decode_failed"}:
        warning = ASR_FAILURE_WARNING
        if asr.get("error"):
            warning = f"{ASR_FAILURE_WARNING} ({asr['error']})"
    elif status == "no_speech":
        warning = (
            "ASR detected no usable speech. Voice authenticity may still be available. "
            "Conversation content was not automatically analyzed — that is not a benign verdict. "
            "Type a transcript to run interaction analysis."
        )
    else:
        warning = ASR_FAILURE_WARNING

    return {
        "text": "",
        "source": "NONE",
        "analyze": False,
        "asr_text": None,
        "warning": warning,
    }
