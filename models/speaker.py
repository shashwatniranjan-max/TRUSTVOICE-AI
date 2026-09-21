"""Registered-speaker enrollment and similarity search.

Prototype implementation: uses a pretrained Resemblyzer speaker encoder when
available. Audio samples are converted to 16 kHz mono and stored locally as
speaker embeddings; raw audio is not required after enrollment.

Important: speaker similarity is identity evidence, not proof of identity, and
must be fused with the existing anti-spoofing signal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np

try:
    from resemblyzer import VoiceEncoder, preprocess_wav
except ImportError:  # pragma: no cover - optional runtime dependency
    VoiceEncoder = None
    preprocess_wav = None

from utils.audio import decode_audio_bytes

STORE_DIR = Path(__file__).resolve().parents[1] / "data" / "speakers"
METADATA_PATH = STORE_DIR / "registry.json"
_ENCODER = None


def dependency_status() -> dict:
    if VoiceEncoder is None or preprocess_wav is None:
        return {
            "ok": False,
            "error": "Speaker encoder unavailable. Install the resemblyzer dependency to enable speaker enrollment.",
        }
    return {"ok": True, "error": None}


def _ensure_store() -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    if not METADATA_PATH.exists():
        METADATA_PATH.write_text("{}", encoding="utf-8")


def _load_registry() -> dict:
    _ensure_store()
    try:
        value = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_registry(registry: dict) -> None:
    _ensure_store()
    METADATA_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def _encoder():
    global _ENCODER
    if VoiceEncoder is None:
        raise RuntimeError(dependency_status()["error"])
    if _ENCODER is None:
        _ENCODER = VoiceEncoder()
    return _ENCODER


def _embedding_from_pcm(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    if preprocess_wav is None:
        raise RuntimeError(dependency_status()["error"])
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    if samples.size == 0:
        raise ValueError("Audio sample is empty.")
    # preprocess_wav performs resampling and normalization expected by the
    # pretrained speaker encoder.
    wav = preprocess_wav(samples, source_sr=int(sample_rate))
    if len(wav) < 16000:
        raise ValueError("Voice sample is too short. Use at least about one second of speech.")
    emb = np.asarray(_encoder().embed_utterance(wav), dtype=np.float32)
    norm = float(np.linalg.norm(emb))
    if norm <= 0:
        raise ValueError("Speaker encoder returned an invalid embedding.")
    return emb / norm


def embedding_from_audio_bytes(raw: bytes, filename: str) -> np.ndarray:
    decoded = decode_audio_bytes(raw, filename)
    samples = decoded.get("samples")
    if samples is None:
        raise ValueError(decoded.get("user_error") or "; ".join(decoded.get("limitations") or []) or "Could not decode audio.")
    return _embedding_from_pcm(samples, int(decoded.get("sample_rate") or 16000))


def list_speakers() -> list[dict]:
    registry = _load_registry()
    return sorted(registry.values(), key=lambda item: item.get("name", "").lower())


def enroll_speaker(name: str, role: str, samples: Iterable[tuple[bytes, str]]) -> dict:
    name = name.strip()
    role = role.strip()
    if not name:
        raise ValueError("Speaker name is required.")

    embeddings = []
    for raw, filename in samples:
        embeddings.append(embedding_from_audio_bytes(raw, filename))
    if len(embeddings) < 3:
        raise ValueError("Enroll at least 3 voice samples for a more stable speaker profile.")

    matrix = np.vstack(embeddings)
    centroid = np.mean(matrix, axis=0)
    centroid /= max(float(np.linalg.norm(centroid)), 1e-12)

    speaker_id = name.lower().replace(" ", "_")
    safe_id = "".join(ch for ch in speaker_id if ch.isalnum() or ch in "_-" ) or "speaker"
    registry = _load_registry()
    existing = registry.get(safe_id, {})
    version = int(existing.get("version", 0)) + 1

    embedding_path = STORE_DIR / f"{safe_id}.npz"
    np.savez_compressed(
        embedding_path,
        centroid=centroid.astype(np.float32),
        samples=matrix.astype(np.float32),
    )
    record = {
        "id": safe_id,
        "name": name,
        "role": role,
        "sample_count": len(embeddings),
        "version": version,
        "embedding_file": embedding_path.name,
    }
    registry[safe_id] = record
    _save_registry(registry)
    return record


def _load_embeddings(record: dict) -> np.ndarray:
    path = STORE_DIR / record["embedding_file"]
    data = np.load(path)
    return np.asarray(data["samples"], dtype=np.float32)


def match_embedding(embedding: np.ndarray, top_k: int = 3) -> list[dict]:
    query = np.asarray(embedding, dtype=np.float32).reshape(-1)
    query /= max(float(np.linalg.norm(query)), 1e-12)
    matches = []
    for record in list_speakers():
        try:
            samples = _load_embeddings(record)
        except Exception:
            continue
        sims = samples @ query
        similarity = float(np.max(sims))
        matches.append({
            "speaker_id": record["id"],
            "name": record["name"],
            "role": record.get("role", ""),
            "similarity": round(similarity * 100, 2),
            "sample_count": record.get("sample_count", len(samples)),
        })
    return sorted(matches, key=lambda item: item["similarity"], reverse=True)[:max(1, top_k)]


def match_audio_bytes(raw: bytes, filename: str, top_k: int = 3) -> list[dict]:
    return match_embedding(embedding_from_audio_bytes(raw, filename), top_k=top_k)
