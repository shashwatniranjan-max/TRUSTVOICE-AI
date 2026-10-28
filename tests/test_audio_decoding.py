"""Unit tests for audio sniffing, decoding fallbacks, and speaker sample verification."""

import io
import struct
import unittest
import wave
from unittest.mock import patch

try:
    import numpy as np
except ImportError:
    class MockArr(list):
        def astype(self, dtype):
            return self
        def __truediv__(self, val):
            return MockArr([x / val for x in self])
        def __sub__(self, val):
            return MockArr([x - val for x in self])

    class MockNumpy:
        float32 = "float32"
        int16 = "int16"
        int32 = "int32"
        uint8 = "uint8"
        def asarray(self, a, dtype=None):
            return a
        def ascontiguousarray(self, a, dtype=None):
            return a
        def frombuffer(self, b, dtype=None):
            count = len(b) // 2
            vals = struct.unpack(f"<{count}h", b)
            return MockArr([float(v) for v in vals])
    np = MockNumpy()

import utils.audio as ua
from utils.audio import sniff_audio_kind, _decode_via_wave, ffmpeg_executable
from models.speaker_registry import verify_speaker_samples


class AudioDecodingTests(unittest.TestCase):
    def test_sniff_audio_kind_wav(self):
        riff_header = b"RIFF\x24\x00\x00\x00WAVEfmt "
        self.assertEqual(sniff_audio_kind(riff_header, "mic.wav"), "wav")

    def test_sniff_audio_kind_webm(self):
        webm_header = b"\x1aE\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01\x42\xf2\x81"
        self.assertEqual(sniff_audio_kind(webm_header, "device_rec.webm"), "webm")
        self.assertEqual(sniff_audio_kind(webm_header, "mic.wav"), "webm")

    def test_sniff_audio_kind_ogg(self):
        ogg_header = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00"
        self.assertEqual(sniff_audio_kind(ogg_header, "stream.opus"), "ogg")

    def test_sniff_audio_kind_mp4(self):
        mp4_header = b"\x00\x00\x00\x1cftypmp42\x00\x00\x00\x00"
        self.assertEqual(sniff_audio_kind(mp4_header, "recording.m4a"), "mp4")

    def test_sniff_audio_kind_mp3(self):
        mp3_id3 = b"ID3\x03\x00\x00\x00\x00\x0f\x76"
        self.assertEqual(sniff_audio_kind(mp3_id3, "track.mp3"), "mp3")

    def test_decode_via_wave_synthetic(self):
        bio = io.BytesIO()
        with wave.open(bio, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            raw_frames = struct.pack("<160h", *([1000, -1000] * 80))
            wf.writeframes(raw_frames)
        wav_bytes = bio.getvalue()

        with patch.object(ua, "np", np):
            loaded = _decode_via_wave(wav_bytes)
            self.assertIsNotNone(loaded)
            samples, sr = loaded
            self.assertEqual(sr, 16000)
            self.assertGreater(len(samples), 0)

    def test_verify_speaker_samples_handles_none(self):
        res = verify_speaker_samples(None, "non_existent_profile")
        self.assertEqual(res.get("status"), "UNVERIFIED")

    def test_verify_speaker_samples_handles_unregistered_profile(self):
        res = verify_speaker_samples([0.1, -0.1], "NONE")
        self.assertEqual(res.get("status"), "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
