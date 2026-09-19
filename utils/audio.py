"""Deterministic 16 kHz audio helpers and quality gating."""

from __future__ import annotations

import hashlib
import io
import os
import subprocess
import tempfile
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None

try:
    import librosa
except ImportError:
    librosa = None

AASIST_WINDOW = 64600
AASIST_HOP = 32300
AASIST_MAX_WINDOWS = 7
MAX_INPUT_BYTES = 200 * 1024 * 1024


def speech_ratio(chunk, floor: float = 0.006) -> float:
    if np is None or chunk is None or getattr(chunk, "size", 0) < 400:
        return 0.0
    frame, hop = 400, 160
    n = 1 + (chunk.size - frame) // hop
    strided = np.lib.stride_tricks.as_strided(
        chunk,
        shape=(n, frame),
        strides=(chunk.strides[0] * hop, chunk.strides[0]),
    )
    rms = np.sqrt(np.mean(np.square(strided, dtype=np.float64), axis=1))
    return float(np.mean(rms > floor))


def quality_gate(audio, sample_rate: int) -> dict:
    if np is None:
        return {
            "duration": 0.0, "rms": 0.0, "clipping_ratio": 0.0,
            "speech_activity_ratio": 0.0, "quality": "REVIEW",
            "issues": ["numpy is required for audio quality checks"],
        }
    a = np.asarray(audio, dtype=np.float32).reshape(-1)
    duration = float(len(a) / sample_rate) if sample_rate else 0.0
    rms = float(np.sqrt(np.mean(np.square(a, dtype=np.float64)))) if len(a) else 0.0
    clipping_ratio = float(np.mean(np.abs(a) >= 0.999)) if len(a) else 0.0
    ratio = speech_ratio(np.ascontiguousarray(a), floor=max(0.006, rms * 0.12))

    issues = []
    if a.size == 0:
        issues.append("Corrupted or empty audio")
    if duration < 1.5:
        issues.append("Sample shorter than 1.5 s")
    if rms < 0.003:
        issues.append("Very low signal energy")
    if clipping_ratio > 0.02:
        issues.append("Significant clipping")
    if ratio < 0.15:
        issues.append("Low speech/activity ratio")

    return {
        "duration": round(duration, 3),
        "rms": round(rms, 6),
        "clipping_ratio": round(clipping_ratio * 100, 3),
        "speech_activity_ratio": round(ratio * 100, 2),
        "quality": "GOOD" if not issues else "REVIEW",
        "issues": issues,
    }


def normalize_model_audio(audio, sample_rate: int):
    if np is None:
        raise RuntimeError("numpy is required for anti-spoof inference.")
    if librosa is None:
        raise RuntimeError("librosa is required for audio preprocessing.")

    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if audio.size == 0:
        raise ValueError("No audio samples were decoded.")
    if sample_rate != 16000:
        audio = librosa.resample(
            audio, orig_sr=int(sample_rate), target_sr=16000, res_type="kaiser_best",
        )
        sample_rate = 16000
    audio = np.nan_to_num(
        np.asarray(audio, dtype=np.float32).reshape(-1),
        nan=0.0, posinf=0.0, neginf=0.0,
    )
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1.0:
        audio = audio / peak
    return np.ascontiguousarray(audio, dtype=np.float32), 16000


def fixed_window(audio, length: int = AASIST_WINDOW):
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if audio.size == 0:
        raise ValueError("No audio samples were decoded.")
    if audio.size >= length:
        return np.ascontiguousarray(audio[:length], dtype=np.float32)
    reps = int(np.ceil(length / audio.size))
    return np.ascontiguousarray(np.tile(audio, reps)[:length], dtype=np.float32)


def make_deterministic_windows(
    audio,
    window_len=AASIST_WINDOW,
    hop=AASIST_HOP,
    max_windows=AASIST_MAX_WINDOWS,
):
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if audio.size <= window_len:
        return [fixed_window(audio, window_len)], 0

    starts = list(range(0, audio.size - window_len + 1, hop))
    final_start = audio.size - window_len
    if len(starts) > max_windows:
        idx = np.linspace(0, len(starts) - 1, max_windows).round().astype(int)
        starts = [starts[i] for i in sorted(set(int(v) for v in idx))]
    if final_start not in starts:
        starts.append(final_start)
    if 0 not in starts:
        starts.insert(0, 0)

    candidates = [
        np.ascontiguousarray(audio[s:s + window_len], dtype=np.float32)
        for s in sorted(set(starts))
    ]
    speech_bearing = [w for w in candidates if speech_ratio(w) >= 0.25]
    dropped = len(candidates) - len(speech_bearing)
    if speech_bearing:
        first = fixed_window(audio, window_len)
        if not any(np.array_equal(first, w) for w in speech_bearing):
            speech_bearing.insert(0, first)
            dropped = max(0, dropped - 1)
        return speech_bearing, dropped
    return candidates, 0


def waveform_envelope(audio, bars: int = 48) -> list[int]:
    if np is None or audio is None or getattr(audio, "size", 0) == 0:
        return [12] * bars
    a = np.abs(np.asarray(audio, dtype=np.float32).reshape(-1))
    step = max(1, a.size // bars)
    env = [float(np.mean(a[i:i + step])) for i in range(0, min(a.size, step * bars), step)]
    peak = max(env) or 1.0
    return [int(8 + 90 * (v / peak)) for v in env[:bars]]


def decode_audio_bytes(raw: bytes, filename: str) -> dict:
    original_suffix = Path(filename).suffix.lower()
    result = {
        "file": filename,
        "file_hash": hashlib.sha256(raw).hexdigest()[:16],
        "format": original_suffix.lstrip(".") or "unknown",
        "duration": None, "sample_rate": None, "channels": None,
        "rms": None, "zero_crossing_rate": None, "spectral_centroid": None,
        "analysis_mode": "Metadata / acoustic checks",
        "limitations": [], "anti_spoof": None, "quality_gate": None,
        "envelope": [], "samples": None,
    }
    if len(raw) > MAX_INPUT_BYTES:
        result["limitations"].append(
            f"File exceeds the {MAX_INPUT_BYTES // (1024 * 1024)} MB analysis limit."
        )
        return result
    if np is None or librosa is None:
        result["limitations"].append(
            "numpy and librosa are required. Run: pip install numpy librosa"
        )
        return result

    analysis_raw, analysis_suffix = raw, original_suffix
    if original_suffix in {".mp4", ".webm", ".mov", ".mkv", ".avi"}:
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = Path(tmpdir) / f"input{original_suffix}"
                wav_path = Path(tmpdir) / "extracted_audio.wav"
                input_path.write_bytes(raw)
                proc = subprocess.run(
                    [ffmpeg_exe, "-y", "-i", str(input_path), "-vn", "-ac", "1",
                     "-ar", "16000", "-c:a", "pcm_s16le", str(wav_path)],
                    capture_output=True, text=True, timeout=180,
                )
                if proc.returncode != 0 or not wav_path.exists():
                    raise RuntimeError(
                        proc.stderr.strip()[-500:] or "FFmpeg found no audio track."
                    )
                analysis_raw = wav_path.read_bytes()
                result["analysis_mode"] = "Video audio extraction + canonical 16 kHz preprocessing"
        except Exception as exc:
            result["limitations"].append(
                f"Video audio extraction failed: {exc}. Install imageio-ffmpeg and retry."
            )
            return result

    try:
        y, sr = librosa.load(io.BytesIO(analysis_raw), sr=16000, mono=True)
        y = np.asarray(y, dtype=np.float32).reshape(-1)
        if y.size == 0:
            raise ValueError("Decoded stream contains no samples.")
        result["duration"] = round(float(len(y) / sr), 2)
        result["sample_rate"] = int(sr)
        result["channels"] = 1
        result["quality_gate"] = quality_gate(y, sr)
        result["rms"] = round(float(np.sqrt(np.mean(np.square(y, dtype=np.float64)))), 5)
        result["zero_crossing_rate"] = round(
            float(np.mean(librosa.feature.zero_crossing_rate(y)[0])), 5
        )
        result["spectral_centroid"] = round(
            float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))), 2
        )
        result["input_fingerprint"] = hashlib.sha256(
            y.tobytes() + str(int(sr)).encode("utf-8")
        ).hexdigest()[:16]
        result["envelope"] = waveform_envelope(y)
        result["samples"] = y
    except Exception as exc:
        result["limitations"].append(f"Canonical audio decode failed: {exc}")
    return result
