"""Local CPU speech-to-text (faster-whisper). Independent of AASIST."""

from __future__ import annotations

import os
import time

DEFAULT_ASR_MODEL = "tiny"
MAX_ASR_SECONDS = float(os.environ.get("TRUSTVOICE_ASR_MAX_SEC", "120"))
ASR_UNAVAILABLE_SERVER = (
    "ASR is unavailable on the server because the ASR runtime dependency could not be loaded."
)
ASR_FAILURE_WARNING = (
    "ASR unavailable/failed. Voice authenticity was analyzed, but conversation "
    "content could not be automatically analyzed."
)

_MODELS: dict = {}


def asr_model_name() -> str:
    name = (os.environ.get("TRUSTVOICE_ASR_MODEL") or DEFAULT_ASR_MODEL).strip()
    return name or DEFAULT_ASR_MODEL


def asr_dependency_status() -> dict:
    try:
        import faster_whisper  # noqa: F401
        return {"ok": True, "error": None}
    except Exception:
        return {"ok": False, "error": ASR_UNAVAILABLE_SERVER}


def _empty_result(**overrides) -> dict:
    out = {
        "transcript": "",
        "status": "error",
        "model": asr_model_name(),
        "language": None,
        "duration": None,
        "elapsed_sec": None,
        "error": None,
        "truncated": False,
    }
    out.update(overrides)
    return out


def get_whisper_model(model_name: str | None = None):
    """Load once per process. CPU quantized by default."""
    name = model_name or asr_model_name()
    cached = _MODELS.get(name)
    if cached is not None:
        return cached
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(ASR_UNAVAILABLE_SERVER) from exc

    threads = int(os.environ.get("TRUSTVOICE_ASR_THREADS", "1"))
    preferred = (os.environ.get("TRUSTVOICE_ASR_COMPUTE") or "").strip()
    compute_types = [preferred] if preferred else []
    for item in ("int8", "int8_float32", "default"):
        if item not in compute_types:
            compute_types.append(item)

    last_error = None
    for compute in compute_types:
        if not compute:
            continue
        try:
            model = WhisperModel(
                name,
                device="cpu",
                compute_type=compute,
                cpu_threads=threads,
            )
            _MODELS[name] = model
            return model
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not initialize ASR model '{name}': {last_error}")


def transcribe_pcm(samples, sample_rate: int = 16000, duration: float | None = None) -> dict:
    """Transcribe 16 kHz mono float PCM. Never raises to the caller."""
    model_id = asr_model_name()
    truncated = False
    dur = duration
    try:
        dep = asr_dependency_status()
        if not dep["ok"]:
            return _empty_result(status="unavailable", error=ASR_UNAVAILABLE_SERVER, duration=dur)

        if samples is None:
            return _empty_result(
                status="decode_failed",
                model=model_id,
                error="No decoded audio samples were available for ASR.",
            )
        n = int(getattr(samples, "size", 0) or len(samples))
        sr = int(sample_rate or 16000)
        actual = (n / float(sr)) if sr else 0.0
        if dur is None:
            dur = round(actual, 3)
        if actual > MAX_ASR_SECONDS and sr:
            samples = samples[: int(MAX_ASR_SECONDS * sr)]
            n = int(getattr(samples, "size", 0) or len(samples))
            truncated = True
            dur = round(n / float(sr), 3)
        if n < int(0.4 * sr):
            return _empty_result(
                status="no_speech",
                model=model_id,
                duration=dur,
                truncated=truncated,
                error="Clip is too short for reliable transcription.",
            )

        started = time.perf_counter()
        model = get_whisper_model(model_id)

        def _run(vad: bool):
            return model.transcribe(
                samples,
                language=None,
                beam_size=1,
                vad_filter=vad,
                condition_on_previous_text=False,
            )

        segments, info = _run(True)
        text = " ".join((getattr(seg, "text", "") or "").strip() for seg in segments).strip()
        if not text:
            segments, info = _run(False)
            text = " ".join((getattr(seg, "text", "") or "").strip() for seg in segments).strip()
        elapsed = round(time.perf_counter() - started, 3)
        language = getattr(info, "language", None) or None
        if language is not None:
            language = str(language).strip() or None
        note = None
        if truncated:
            note = f"Only the first {MAX_ASR_SECONDS:.0f}s were transcribed."
        if not text:
            return _empty_result(
                status="no_speech",
                model=model_id,
                language=language,
                duration=dur,
                elapsed_sec=elapsed,
                truncated=truncated,
                error="ASR returned no speech.",
            )
        return {
            "transcript": text,
            "status": "success",
            "model": model_id,
            "language": language,
            "duration": dur,
            "elapsed_sec": elapsed,
            "error": note,
            "truncated": truncated,
        }
    except Exception as exc:
        message = str(exc)
        unavailable = ASR_UNAVAILABLE_SERVER.lower() in message.lower() or "faster_whisper" in message.lower()
        return _empty_result(
            status="unavailable" if unavailable else "error",
            model=model_id,
            duration=dur,
            truncated=truncated,
            error=ASR_UNAVAILABLE_SERVER if unavailable else f"{type(exc).__name__}: {exc}",
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
        warning = asr.get("error") if asr.get("truncated") else None
        return {
            "text": asr_text,
            "source": "ASR",
            "analyze": True,
            "asr_text": asr_text,
            "warning": warning,
        }

    status = asr.get("status") or "unavailable"
    detail = asr.get("error")
    if status == "unavailable":
        warning = ASR_UNAVAILABLE_SERVER
    elif status == "decode_failed":
        warning = detail or ASR_FAILURE_WARNING
    elif status == "no_speech":
        warning = (
            "Conversation content: unavailable. ASR detected no usable speech. "
            "Voice authenticity may still be available. That is not a benign verdict."
        )
    elif status == "too_long":
        warning = detail or ASR_FAILURE_WARNING
    else:
        warning = ASR_FAILURE_WARNING
        if detail:
            warning = f"{ASR_FAILURE_WARNING} {detail}"

    return {
        "text": "",
        "source": "NONE",
        "analyze": False,
        "asr_text": None,
        "warning": warning,
    }
