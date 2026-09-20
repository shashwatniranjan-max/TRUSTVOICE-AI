"""ASR wiring tests. Whisper weights are mocked — no fabricated inference."""

import io
import unittest
import wave
from unittest.mock import patch

import numpy as np

from models.asr import (
    ASR_UNAVAILABLE_SERVER,
    MAX_ASR_SECONDS,
    resolve_live_transcript,
    transcribe_pcm,
)
from models.antispoof import analyze_audio_bytes
from risk.pipeline import analyse_interaction
from ui.console import consume_pending_transcript
from utils.audio import DECODE_FORMAT_HELP, decode_audio_bytes, sniff_audio_kind


class FakeSegment:
    def __init__(self, text):
        self.text = text


class FakeInfo:
    language = "en"
    language_probability = 0.92


class FakeModel:
    def transcribe(self, audio, **kwargs):
        return iter([FakeSegment("  Please send me the OTP you just received.  ")]), FakeInfo()


class EmptyModel:
    def transcribe(self, audio, **kwargs):
        return iter([]), FakeInfo()


def _pcm16_wav_bytes(samples: np.ndarray, sr: int = 16000) -> bytes:
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(pcm.tobytes())
    return buf.getvalue()


class AsrIntegrationTests(unittest.TestCase):
    def test_text_only_analysis_still_works(self):
        r = analyse_interaction("Hey, are we still meeting at five?")
        self.assertEqual(r["intent"]["intent"], "normal_conversation")
        self.assertEqual(r["interaction_risk"], "LOW")

    def test_asr_transcript_feeds_existing_pipeline(self):
        choice = resolve_live_transcript("", {
            "status": "success",
            "transcript": "Please send me the OTP you just received.",
        })
        self.assertTrue(choice["analyze"])
        self.assertEqual(choice["source"], "ASR")
        r = analyse_interaction(choice["text"])
        self.assertEqual(r["intent"]["intent"], "credential_request")
        self.assertIn(r["interaction_risk"], {"HIGH", "CRITICAL"})

    def test_asr_failure_does_not_crash_or_score_empty_text(self):
        with patch("models.asr.asr_dependency_status", return_value={"ok": True, "error": None}):
            out = transcribe_pcm(None, 16000)
        self.assertEqual(out["status"], "decode_failed")
        choice = resolve_live_transcript("", out)
        self.assertFalse(choice["analyze"])
        self.assertEqual(choice["source"], "NONE")

    def test_asr_unavailable_uses_server_message(self):
        with patch("models.asr.asr_dependency_status", return_value={"ok": False, "error": ASR_UNAVAILABLE_SERVER}):
            out = transcribe_pcm(np.zeros(16000, dtype=np.float32), 16000, duration=1.0)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["error"], ASR_UNAVAILABLE_SERVER)
        choice = resolve_live_transcript("", out)
        self.assertFalse(choice["analyze"])
        self.assertIn("runtime dependency could not be loaded", choice["warning"])
        self.assertNotIn("pip install", choice["warning"].lower())

    def test_empty_or_no_speech_is_not_treated_as_benign(self):
        choice = resolve_live_transcript("", {
            "status": "no_speech",
            "transcript": "",
            "error": "ASR returned no speech.",
        })
        self.assertFalse(choice["analyze"])
        self.assertIn("unavailable", choice["warning"].lower())
        self.assertEqual(choice["text"], "")

    def test_manual_transcript_overrides_asr(self):
        choice = resolve_live_transcript(
            "Hey, are we still meeting at five?",
            {
                "status": "success",
                "transcript": "Give me your OTP immediately.",
            },
        )
        self.assertEqual(choice["source"], "MANUAL")
        self.assertTrue(choice["analyze"])
        r = analyse_interaction(choice["text"])
        self.assertEqual(r["intent"]["intent"], "normal_conversation")
        self.assertEqual(r["interaction_risk"], "LOW")

    def test_security_advice_still_not_a_credential_attack(self):
        choice = resolve_live_transcript("", {
            "status": "success",
            "transcript": "The bank will never ask you for your OTP.",
        })
        r = analyse_interaction(choice["text"])
        self.assertNotEqual(r["intent"]["intent"], "credential_request")

    def test_transcribe_pcm_duration_limit_truncates(self):
        y = np.zeros(int((MAX_ASR_SECONDS + 8) * 16000), dtype=np.float32)
        with patch("models.asr.asr_dependency_status", return_value={"ok": True, "error": None}):
            with patch("models.asr.get_whisper_model", return_value=FakeModel()):
                out = transcribe_pcm(y, 16000)
        self.assertEqual(out["status"], "success")
        self.assertTrue(out.get("truncated"))

    def test_transcribe_pcm_model_error_is_structured(self):
        y = np.zeros(16000, dtype=np.float32)
        with patch("models.asr.asr_dependency_status", return_value={"ok": True, "error": None}):
            with patch("models.asr.get_whisper_model", side_effect=RuntimeError("oom")):
                out = transcribe_pcm(y, 16000, duration=1.0)
        self.assertEqual(out["status"], "error")
        self.assertIn("oom", out["error"] or "")

    def test_transcribe_pcm_mocked_success_does_not_invent_weights(self):
        y = np.zeros(16000, dtype=np.float32)
        with patch("models.asr.asr_dependency_status", return_value={"ok": True, "error": None}):
            with patch("models.asr.get_whisper_model", return_value=FakeModel()):
                out = transcribe_pcm(y, 16000, duration=1.0)
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["transcript"], "Please send me the OTP you just received.")
        self.assertEqual(out["language"], "en")
        choice = resolve_live_transcript("", out)
        r = analyse_interaction(choice["text"])
        self.assertEqual(r["intent"]["intent"], "credential_request")

    def test_mocked_no_speech_status(self):
        y = np.zeros(16000, dtype=np.float32)
        with patch("models.asr.asr_dependency_status", return_value={"ok": True, "error": None}):
            with patch("models.asr.get_whisper_model", return_value=EmptyModel()):
                out = transcribe_pcm(y, 16000, duration=1.0)
        self.assertEqual(out["status"], "no_speech")
        self.assertFalse(resolve_live_transcript("", out)["analyze"])

    def test_pending_console_transcript_applied_before_widget(self):
        state = {"pending_console_transcript": "Share the OTP."}
        consume_pending_transcript(state)
        self.assertEqual(state["console_transcript"], "Share the OTP.")
        self.assertNotIn("pending_console_transcript", state)
        consume_pending_transcript(state)
        self.assertEqual(state["console_transcript"], "Share the OTP.")

    def test_wav_decode_is_16k_mono(self):
        tone = 0.1 * np.sin(2 * np.pi * 440.0 * np.arange(16000) / 16000.0).astype(np.float32)
        decoded = decode_audio_bytes(_pcm16_wav_bytes(tone), "clip.wav")
        self.assertIsNotNone(decoded.get("samples"))
        self.assertEqual(decoded["sample_rate"], 16000)
        self.assertEqual(decoded["channels"], 1)
        self.assertGreater(decoded["duration"], 0.5)

    def test_corrupt_audio_has_user_facing_error(self):
        decoded = decode_audio_bytes(b"this is not audio", "note.txt")
        self.assertIsNone(decoded.get("samples"))
        self.assertEqual(decoded.get("user_error"), DECODE_FORMAT_HELP)

    def test_mpeg_sniff_and_ffmpeg_normalize(self):
        self.assertEqual(sniff_audio_kind(b"ID3\x03" + b"\x00" * 20, "voice.mpeg"), "mp3")
        fake_wav = _pcm16_wav_bytes(0.05 * np.ones(8000, dtype=np.float32))
        with patch("utils.audio._ffmpeg_to_wav16k", return_value=(fake_wav, None)):
            decoded = decode_audio_bytes(b"ID3" + b"\x00" * 64, "call.mp3")
        self.assertIsNotNone(decoded.get("samples"))
        self.assertEqual(decoded.get("decode_path"), "ffmpeg")
        self.assertEqual(decoded["sample_rate"], 16000)

    def test_normalized_pcm_reused_for_aasist_and_asr(self):
        samples = np.zeros(16000, dtype=np.float32)
        decoded = {
            "file": "a.wav",
            "limitations": [],
            "samples": samples,
            "sample_rate": 16000,
            "duration": 1.0,
            "quality_gate": {"issues": [], "quality": "GOOD"},
            "analysis_mode": "test",
            "envelope": [],
        }
        progress = []
        with patch("models.antispoof.decode_audio_bytes", return_value=dict(decoded)):
            with patch("models.antispoof.run_antispoof_scores", return_value={
                "authenticity_score": 80,
                "worst_window_bona_fide": 80,
                "confidence_spread": 1.0,
                "engine_stable": True,
                "voice_label": "LIKELY_AUTHENTIC",
            }) as anti:
                with patch("models.asr.transcribe_pcm") as asr:
                    asr.return_value = {"status": "success", "transcript": "hello", "error": None}
                    analyze_audio_bytes(b"x", "a.wav", transcribe=True, allow_download=False,
                                        on_progress=progress.append)
        self.assertTrue(anti.called)
        self.assertIs(anti.call_args[0][0], samples)
        self.assertTrue(asr.called)
        self.assertIs(asr.call_args[0][0], samples)
        self.assertIn("Decoding audio...", progress)
        self.assertIn("Running voice authenticity analysis...", progress)
        self.assertIn("Transcribing conversation...", progress)


if __name__ == "__main__":
    unittest.main()
