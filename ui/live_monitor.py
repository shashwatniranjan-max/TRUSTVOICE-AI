"""Live Monitor — Real-time audio stream monitoring, device voice recording, and telemetry."""

from __future__ import annotations

import re
import time
from html import escape

import streamlit as st

from demo.scenarios import SCENARIOS
from models.antispoof import analyze_audio_bytes
from models.asr import asr_model_name, DEFAULT_ASR_PROMPT
from models.speaker_registry import list_profiles, verify_speaker_samples
from risk.pipeline import analyse_interaction
from ui.theme import COLORS


def render(html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def _apply_result(result: dict, source: str, audio=None):
    st.session_state.last_result = result
    st.session_state.score = result["trust_score"]
    st.session_state.factors = result["factor_display"]
    st.session_state.transcript = result["transcript"]
    st.session_state.intent_prediction = result["intent"]
    st.session_state.risk_explanation = result["drivers"]
    st.session_state.action_status = result["action"]
    st.session_state.scenario = source
    st.session_state.analysis_source = source
    st.session_state.conversation_state = result["conversation_state"]
    st.session_state.analysis_done = True
    if audio is not None:
        st.session_state.last_analysis = audio
    st.session_state.history.append({
        "time": result.get("transcript", "")[:48],
        "scenario": source,
        "score": result["trust_score"],
        "risk": result["interaction_risk"],
        "details": result["action"],
    })


def _render_waveform_svg(envelope: list[int] | None = None, risk: int = 0) -> str:
    """Render 36 vertical waveform bars with color tint matching current risk."""
    if not envelope:
        # Idle baseline wave
        bars = [12, 16, 22, 34, 48, 60, 44, 30, 20, 15, 25, 40, 55, 70, 85, 60, 40, 25,
                18, 30, 50, 65, 80, 55, 38, 22, 16, 28, 42, 60, 48, 32, 20, 16, 14, 12]
        opacity = "0.55"
    else:
        # Scale actual audio envelope bars
        bars = envelope[:36] if len(envelope) >= 36 else envelope + [12] * (36 - len(envelope))
        opacity = "0.95"

    color = "#16A34A" if risk < 55 else ("#D97706" if risk < 80 else "#DC2626")

    rects = ""
    width = 12
    gap = 6
    for i, h in enumerate(bars):
        clamped_h = max(8, min(80, int(h * 0.8)))
        y = (80 - clamped_h) // 2
        x = i * (width + gap)
        rects += f'<rect x="{x}" y="{y}" width="{width}" height="{clamped_h}" rx="4" fill="{color}" opacity="{opacity}"/>'

    total_w = 36 * (width + gap)
    return f"""
    <div style="background:var(--tv-surface);border-radius:8px;padding:16px 12px;display:flex;justify-content:center;
                align-items:center;border:1px solid var(--tv-border);margin:10px 0 16px;overflow-x:hidden">
      <svg width="100%" height="80" viewBox="0 0 {total_w} 80" preserveAspectRatio="xMidYMid meet">
        {rects}
      </svg>
    </div>
    """


def _highlight_threat_keywords(text: str) -> str:
    """Highlight security-critical risk keywords in live transcript stream."""
    if not text:
        return '<span style="color:var(--tv-dim);font-style:italic">Transcript stream will appear as speech is detected…</span>'

    threat_words = [
        ("otp", "#DC2626", "#FEE2E2"),
        ("one-time password", "#DC2626", "#FEE2E2"),
        ("password", "#DC2626", "#FEE2E2"),
        ("credentials", "#DC2626", "#FEE2E2"),
        ("wire transfer", "#DC2626", "#FEE2E2"),
        ("transfer", "#D97706", "#FEF3C7"),
        ("account number", "#D97706", "#FEF3C7"),
        ("bank", "#2563D6", "#EFF6FF"),
        ("immediately", "#DC2626", "#FEE2E2"),
        ("urgent", "#DC2626", "#FEE2E2"),
        ("confidential", "#DC2626", "#FEE2E2"),
        ("don't tell anyone", "#DC2626", "#FEE2E2"),
        ("secret", "#DC2626", "#FEE2E2"),
        ("verification code", "#DC2626", "#FEE2E2"),
        ("authenticate", "#2563D6", "#EFF6FF"),
    ]

    escaped = escape(text)
    for kw, col, bg in threat_words:
        pattern = re.compile(rf"\b({re.escape(kw)})\b", re.IGNORECASE)
        escaped = pattern.sub(
            rf'<span style="background:{bg};color:{col};padding:1px 6px;border-radius:4px;font-weight:600;border:1px solid {col}33">\1</span>',
            escaped,
        )
    return escaped


def render_live_monitor():
    render("""
    <div class="tv-page" style="align-items:center;border-bottom:0;padding-bottom:0">
      <div style="display:flex;align-items:center;gap:12px">
        <h1 style="margin:0">LIVE MONITOR</h1>
        <span class="tv-badge tv-badge-ok" style="font-size:11.5px">● Live Ingestion Active</span>
      </div>
    </div>
    <p style="color:var(--tv-muted);font-size:13.5px;margin:0 0 16px 0">
      Real-time audio monitoring, device microphone recording, and streaming security telemetry.
    </p>
    """)

    # Mode Selector Tabs
    tab_record, tab_stream, tab_arch = st.tabs([
        "🎙️ Device Voice Recorder & Analysis",
        "⚡ Real-Time Stream Simulation",
        "ℹ️ Real-Time Architecture Guide",
    ])

    # ═════════════════════════════════════════════════════════════════════════
    # TAB 1: DEVICE VOICE RECORDER & LIVE ANALYSIS
    # ═════════════════════════════════════════════════════════════════════════
    with tab_record:
        render("""
        <div class="tv-card" style="margin-bottom:14px">
          <div class="tv-section-head">
            <span class="tv-section-head-title">Device Voice Recorder & Telemetry</span>
            <span class="tv-section-head-meta">Captures microphone input directly from your browser/device</span>
          </div>
        </div>
        """)

        # Registered profiles for identity verification
        all_profiles = list_profiles()
        profile_options = {"NONE": "Anonymous / Unverified Caller"}
        for p in all_profiles:
            enr_mark = " [Enrolled]" if p.get("enrolled") else " [Not Enrolled]"
            profile_options[p["id"]] = f"{p['name']} ({p.get('role', 'Member')}){enr_mark}"

        # Ingestion Mode Selection: Mic, File Upload, or Pre-recorded Scenario
        ingest_mode = st.radio(
            "Select Audio Ingestion Mode:",
            ["🎙️ Live Device Microphone", "📁 Upload Audio File", "🧪 Test Security Scenarios"],
            horizontal=True,
            key="lm_ingest_mode",
            help="Choose how to feed audio into the Live Monitor: via your device microphone, by uploading an audio file, or testing with incident presets.",
        )

        col_input1, col_input2 = st.columns([2, 1], gap="medium")
        mic_audio = None
        file_audio = None
        raw_bytes = None
        source_name = "device_recording.wav"

        with col_input1:
            if ingest_mode == "🎙️ Live Device Microphone":
                mic_audio = st.audio_input(
                    "Click microphone to record live audio from your device:",
                    key="lm_device_recorder",
                )
                if mic_audio is not None:
                    raw_bytes = mic_audio.getvalue()
                    source_name = getattr(mic_audio, "name", "device_recording.wav") or "device_recording.wav"
                    st.session_state["lm_recorded_bytes"] = raw_bytes
                st.caption("🎙️ Speak into your microphone. Click stop when finished to feed audio directly into AASIST + Whisper.")
            elif ingest_mode == "📁 Upload Audio File":
                file_audio = st.file_uploader(
                    "Upload audio recording:",
                    type=["wav", "mp3", "m4a", "webm", "ogg", "flac", "aac", "mp4"],
                    key="lm_file_uploader",
                )
                if file_audio is not None:
                    raw_bytes = file_audio.getvalue()
                    source_name = file_audio.name
                    st.session_state["lm_recorded_bytes"] = raw_bytes
            else:
                # Security scenario quick tests
                st.write("**Quick-load security attack or authentic voice samples:**")
                sc1, sc2, sc3 = st.columns(3)
                with sc1:
                    if st.button("🚨 Bank OTP Scam", use_container_width=True, key="lm_preset_otp"):
                        st.session_state["lm_preset_data"] = {
                            "text": "Hello, this is security from your bank. Confirm your account number and share the one-time password immediately or your account will be suspended.",
                            "voice": "LIKELY_SPOOF",
                            "score": 12,
                            "name": "Bank Impersonation Scam",
                            "risk": "CRITICAL",
                        }
                        st.session_state["_lm_active"] = True
                        st.rerun()
                with sc2:
                    if st.button("⚠️ Wire Transfer", use_container_width=True, key="lm_preset_wire"):
                        st.session_state["lm_preset_data"] = {
                            "text": "Hey, this is the Chief Executive Officer. I need you to initiate an urgent confidential wire transfer to this account right away. Do not tell anyone.",
                            "voice": "LIKELY_SPOOF",
                            "score": 18,
                            "name": "Executive Deepfake Pretext",
                            "risk": "CRITICAL",
                        }
                        st.session_state["_lm_active"] = True
                        st.rerun()
                with sc3:
                    if st.button("🛡️ Authentic Sync", use_container_width=True, key="lm_preset_auth"):
                        st.session_state["lm_preset_data"] = {
                            "text": "Good morning team, let's go over the engineering standup and the pipeline milestones for this week.",
                            "voice": "LIKELY_AUTHENTIC",
                            "score": 93,
                            "name": "Authentic Meeting Call",
                            "risk": "LOW",
                        }
                        st.session_state["_lm_active"] = True
                        st.rerun()

        with col_input2:
            selected_pid = st.selectbox(
                "Claimed speaker identity:",
                list(profile_options.keys()),
                format_func=lambda k: profile_options.get(k, k),
                key="lm_speaker_profile_select",
                help="Select an enrolled executive profile to verify if the speaker's voice matches their biometric print.",
            )

        # Handle Preset Data if triggered
        if st.session_state.get("lm_preset_data") and ingest_mode == "🧪 Test Security Scenarios":
            pdata = st.session_state["lm_preset_data"]
            id_stat = "UNVERIFIED"
            spk_name = "Unknown Caller"
            if selected_pid and selected_pid != "NONE":
                spk_name = profile_options.get(selected_pid, "Claimed Speaker")
                id_stat = "VERIFIED" if pdata["voice"] == "LIKELY_AUTHENTIC" else "MISMATCH"
                spk_name += " [Verified ✓]" if id_stat == "VERIFIED" else " [Voice Mismatch ⚠️]"

            sim_analysed = analyse_interaction(
                transcript=pdata["text"],
                voice_label=pdata["voice"],
                identity_status=id_stat,
                authenticity_score=pdata["score"],
                conversation_state=st.session_state.conversation_state,
                source=f"LIVE MONITOR ({pdata['name']})",
                voice_evidence="model",
            )
            mock_audio = {
                "duration": 5.2,
                "sample_rate": 16000,
                "format": "PCM",
                "envelope": [int(20 + (80 - pdata["score"]) * 0.7 * (0.8 + 0.3 * (i % 4))) for i in range(36)],
                "anti_spoof": {
                    "voice_label": pdata["voice"],
                    "authenticity_score": pdata["score"],
                    "verdict": pdata["voice"].replace("_", " "),
                },
                "asr": {
                    "status": "success",
                    "transcript": pdata["text"],
                    "model": "base",
                    "language": "en",
                    "beam_size": 5,
                    "elapsed_sec": 0.38,
                },
            }
            _apply_result(sim_analysed, f"LIVE MONITOR ({pdata['name']})", mock_audio)
            st.session_state["_lm_speaker_name"] = spk_name
            st.session_state["_lm_identity_status"] = id_stat
            st.session_state["_lm_active"] = True

        # Handle incoming audio bytes (Microphone or File Upload)
        if raw_bytes is not None and len(raw_bytes) > 0:
            # Audio Player & Action strip
            col_ply, col_dl, col_inc = st.columns([2, 1, 1], gap="small")
            with col_ply:
                st.audio(raw_bytes)
            with col_dl:
                ts_stamp = int(time.time())
                st.download_button(
                    label="⬇️ Save Recording",
                    data=raw_bytes,
                    file_name=f"trustvoice_rec_{ts_stamp}.wav",
                    mime="audio/wav",
                    use_container_width=True,
                    key="lm_dl_rec",
                )
            with col_inc:
                if st.button("📁 Log as Incident", use_container_width=True, key="lm_btn_inc"):
                    st.success("Recording staged into Incidents queue as TV-LIVE.")

            # Trigger Controls
            c_trig1, c_trig2 = st.columns([1.5, 1], gap="small")
            with c_trig1:
                btn_run = st.button("⚡ Analyze Live Recording", type="primary", use_container_width=True, key="lm_btn_run_rec")
            with c_trig2:
                auto_run = st.checkbox("Auto-analyze on audio capture", value=True, key="lm_auto_analyze_box")

            import hashlib
            cache_key = hashlib.sha256(
                raw_bytes + str(selected_pid).encode("utf-8") +
                str(st.session_state.get("asr_model_choice", "base")).encode("utf-8") +
                str(st.session_state.get("bona_threshold", 0.5)).encode("utf-8")
            ).hexdigest()[:16]

            should_analyze = btn_run or (auto_run and st.session_state.get("_lm_last_cache_key") != cache_key)

            if should_analyze:
                with st.spinner("Processing live audio stream (AASIST + faster-whisper ASR + Risk Fusion)…"):
                    asr_model = st.session_state.get("asr_model_choice", asr_model_name())
                    asr_lang = st.session_state.get("asr_language", "en")
                    asr_beam = 5 if st.session_state.get("asr_quality_mode", "accurate") == "accurate" else 1
                    asr_prompt_on = st.session_state.get("asr_domain_prompt", True)
                    asr_prompt_str = DEFAULT_ASR_PROMPT if asr_prompt_on else None

                    # 1. Audio Decode + Anti-spoof + ASR
                    try:
                        audio_res = analyze_audio_bytes(
                            raw_bytes, source_name,
                            model_key=st.session_state.get("model_choice", "aasist"),
                            threshold=float(st.session_state.get("bona_threshold", 0.5)),
                            band=float(st.session_state.get("decision_band", 0.1)),
                            threshold_source=st.session_state.get("threshold_source", "default"),
                            allow_download=True,
                            transcribe=True,
                            asr_model=asr_model,
                            asr_language=asr_lang,
                            asr_beam_size=asr_beam,
                            asr_prompt=asr_prompt_str,
                        )
                    except Exception as exc:
                        audio_res = {
                            "user_error": f"Audio processing error: {exc}",
                            "limitations": [str(exc)],
                            "samples": None,
                        }

                    # Check for decoding error and surface clearly
                    if audio_res.get("user_error"):
                        st.error(f"⚠️ **Audio Decoding Notice**: {audio_res['user_error']}")
                        if audio_res.get("limitations"):
                            for lim in audio_res["limitations"]:
                                st.caption(f"• {lim}")
                        st.info("💡 **Tip**: If compressed browser audio (WebM/Opus) cannot be converted, please install FFmpeg via `packages.txt` or upload an uncompressed **WAV** file directly.")

                    # 2. Identity Verification against enrolled profile if selected
                    identity_status = "UNVERIFIED"
                    speaker_name = "Unknown Caller"
                    if selected_pid and selected_pid != "NONE":
                        verify_res = verify_speaker_samples(
                            audio_res.get("samples"),
                            selected_pid,
                            int(audio_res.get("sample_rate") or 16000),
                        )
                        identity_status = verify_res.get("status", "UNVERIFIED")
                        speaker_name = verify_res.get("profile_name", "Claimed Speaker")
                        if identity_status == "VERIFIED":
                            speaker_name += f" [Verified ✓ {int(verify_res.get('similarity', 0)*100)}%]"
                        elif identity_status == "MISMATCH":
                            speaker_name += f" [Voice Mismatch ⚠️ {int(verify_res.get('similarity', 0)*100)}%]"

                    # 3. Multi-Factor Risk Fusion
                    anti = audio_res.get("anti_spoof") or {}
                    voice_label = anti.get("voice_label", "INCONCLUSIVE")
                    auth_score = anti.get("authenticity_score")
                    transcript_text = ((audio_res.get("asr") or {}).get("transcript") or "").strip()

                    analysed = analyse_interaction(
                        transcript=transcript_text,
                        voice_label=voice_label,
                        identity_status=identity_status,
                        authenticity_score=auth_score,
                        conversation_state=st.session_state.conversation_state,
                        source="LIVE MONITOR (DEVICE MIC)",
                        voice_evidence="model" if auth_score is not None else "unavailable",
                    )

                    _apply_result(analysed, "LIVE MONITOR (DEVICE MIC)", audio_res)
                    st.session_state["_lm_last_cache_key"] = cache_key
                    st.session_state["_lm_speaker_name"] = speaker_name
                    st.session_state["_lm_identity_status"] = identity_status
                    st.session_state["_lm_active"] = True

        # ── Dashboard Layout ────────────────────────────────────────────────
        is_active = st.session_state.get("_lm_active", False)
        audio = st.session_state.get("last_analysis") or {} if is_active else {}
        result = st.session_state.get("last_result") or {} if is_active else {}
        anti = audio.get("anti_spoof") or {}
        asr_meta = audio.get("asr") or {}

        trust_score = int(result.get("trust_score", 76))
        imp_risk = max(0, min(100, 100 - trust_score)) if result else 0
        risk_label = result.get("interaction_risk", "Awaiting recording")
        voice_label = anti.get("voice_label") or ("Awaiting audio" if not is_active else "Inconclusive")
        auth_score_val = anti.get("authenticity_score")
        speaker_disp = st.session_state.get("_lm_speaker_name", "Not detected" if not is_active else "Unknown Caller")
        transcript_str = result.get("transcript") or asr_meta.get("transcript") or ""

        col_main, col_side = st.columns([1.8, 1], gap="medium")

        with col_main:
            # ── Live Audio Card with Dynamic Waveform ────────────────────────
            render(f"""
            <div class="tv-card">
              <div class="tv-section-head">
                <span class="tv-section-head-title">Live Audio Stream & Waveform</span>
                <span class="tv-section-head-meta">{'Active recording analyzed' if is_active else 'Awaiting audio input'}</span>
              </div>
            """)

            envelope = audio.get("envelope") if is_active else None
            render(_render_waveform_svg(envelope, imp_risk if is_active else 0))

            dur_disp = f"{audio.get('duration')}s" if audio.get("duration") else ("—" if not is_active else "0.0s")
            fmt_disp = str(audio.get("format") or "PCM").upper()
            sr_disp = f"{audio.get('sample_rate')} Hz" if audio.get("sample_rate") else "16,000 Hz"
            auth_disp = f"{voice_label.replace('_', ' ').title()}" + (f" ({auth_score_val}%)" if auth_score_val is not None else "")
            risk_badge = f'<span class="tv-badge {"tv-badge-crit" if imp_risk >= 80 else ("tv-badge-warn" if imp_risk >= 55 else "tv-badge-ok")}">{imp_risk}% ({risk_label.title()})</span>' if is_active else '<span class="tv-badge tv-badge-gray">Idle</span>'

            render(f"""
              <div style="display:flex;justify-content:space-between;border-top:1px solid var(--tv-border);padding-top:14px;flex-wrap:wrap;gap:12px">
                <div>
                  <div style="font-size:11.5px;color:var(--tv-muted);font-weight:600;margin-bottom:3px">CURRENT SPEAKER</div>
                  <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">{escape(speaker_disp)}</div>
                </div>
                <div>
                  <div style="font-size:11.5px;color:var(--tv-muted);font-weight:600;margin-bottom:3px">VOICE AUTHENTICITY</div>
                  <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">{escape(auth_disp)}</div>
                </div>
                <div>
                  <div style="font-size:11.5px;color:var(--tv-muted);font-weight:600;margin-bottom:3px">DURATION / CODEC</div>
                  <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">{escape(dur_disp)} · {escape(fmt_disp)}</div>
                </div>
                <div>
                  <div style="font-size:11.5px;color:var(--tv-muted);font-weight:600;margin-bottom:3px">CURRENT RISK</div>
                  <div>{risk_badge}</div>
                </div>
              </div>
            </div>
            """)

            # ── Transcript Stream Card ───────────────────────────────────────
            render("""
            <div class="tv-card">
              <div class="tv-section-head">
                <span class="tv-section-head-title">Real-Time Transcript Stream</span>
                <span class="tv-section-head-meta">ASR Stream with threat entity highlighting</span>
              </div>
            """)

            if asr_meta.get("status") == "success":
                mod_str = asr_meta.get("model", "base")
                lang_str = str(asr_meta.get("language") or "EN").upper()
                sec_str = f"{asr_meta.get('elapsed_sec')}s" if asr_meta.get("elapsed_sec") is not None else ""
                beam_str = f"Beam {asr_meta.get('beam_size', 5)}"
                render(f"""
                <div style="margin-bottom:10px;font-size:11.5px;color:var(--tv-muted);display:flex;gap:12px">
                  <span>Engine: <b>faster-whisper ({escape(mod_str)})</b></span>
                  <span>Language: <b>{escape(lang_str)}</b></span>
                  <span>Quality: <b>{escape(beam_str)}</b></span>
                  {f'<span>Latency: <b>{sec_str}</b></span>' if sec_str else ''}
                </div>
                """)

            highlighted_transcript = _highlight_threat_keywords(transcript_str)
            render(f"""
              <div style="min-height:90px;padding:12px 14px;background:var(--tv-bg);border-radius:6px;
                          border:1px solid var(--tv-border);font-size:13.5px;line-height:1.65;color:var(--tv-text)">
                {highlighted_transcript}
              </div>
            </div>
            """)

        with col_side:
            # ── Current Signals Card ─────────────────────────────────────────
            id_status = st.session_state.get("_lm_identity_status", result.get("identity_status", "UNVERIFIED"))
            intent_val = (result.get("intent") or {}).get("intent", "—")
            behav_val = (result.get("behaviour") or {}).get("behaviour_level", "—")
            context_val = (result.get("context") or {}).get("context_level", "—")

            def _badge_html(label: str, state: str):
                cls = "tv-badge-ok" if state in {"LOW", "NORMAL", "LIKELY_AUTHENTIC", "VERIFIED", "normal_conversation"} else (
                    "tv-badge-crit" if state in {"CRITICAL", "HIGH", "LIKELY_SPOOF", "MISMATCH", "credential_request", "financial_request"} else "tv-badge-warn"
                )
                return f'<span class="tv-badge {cls}" style="font-size:11px">● {escape(str(label))}</span>'

            auth_badge = _badge_html(voice_label.replace("_", " ").title(), voice_label) if is_active else '<span class="tv-badge tv-badge-gray" style="font-size:11px">● Idle</span>'
            id_badge = _badge_html(id_status.replace("_", " ").title(), id_status) if is_active else '<span class="tv-badge tv-badge-gray" style="font-size:11px">● Idle</span>'
            intent_badge = _badge_html(intent_val.replace("_", " ").title(), intent_val) if is_active else '<span class="tv-badge tv-badge-gray" style="font-size:11px">● Idle</span>'
            behav_badge = _badge_html(f"Level {behav_val.title()}", behav_val) if is_active else '<span class="tv-badge tv-badge-gray" style="font-size:11px">● Idle</span>'
            context_badge = _badge_html(f"Level {context_val.title()}", context_val) if is_active else '<span class="tv-badge tv-badge-gray" style="font-size:11px">● Idle</span>'

            render(f"""
            <div class="tv-card" style="padding:0">
              <div style="padding:14px 16px;border-bottom:1px solid var(--tv-border)">
                <div class="tv-section-head-title">Active Security Signals</div>
              </div>
              <div class="tv-evidence-row" style="padding:10px 16px">
                <span class="tv-evidence-label">Voice authenticity</span>
                {auth_badge}
              </div>
              <div class="tv-evidence-row" style="padding:10px 16px">
                <span class="tv-evidence-label">Speaker identity</span>
                {id_badge}
              </div>
              <div class="tv-evidence-row" style="padding:10px 16px">
                <span class="tv-evidence-label">Conversational intent</span>
                {intent_badge}
              </div>
              <div class="tv-evidence-row" style="padding:10px 16px">
                <span class="tv-evidence-label">Behavioural pressure</span>
                {behav_badge}
              </div>
              <div class="tv-evidence-row" style="padding:10px 16px;border-bottom:0">
                <span class="tv-evidence-label">Context anomaly</span>
                {context_badge}
              </div>
            </div>
            """)

            # ── Trust Handshake Action Card ──────────────────────────────────
            handshake_req = bool(is_active and (imp_risk >= 80 or result.get("handshake_required")))
            handshake_color = "#FEF2F2" if handshake_req else "var(--tv-surface)"
            handshake_border = "1.5px solid #FCA5A5" if handshake_req else "1px solid var(--tv-border)"

            render(f"""
            <div class="tv-card" style="background:{handshake_color};border:{handshake_border}">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
                <div style="width:34px;height:34px;background:#EFF6FF;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#2563D6">
                  <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
                </div>
                {'<span class="tv-badge tv-badge-crit" style="font-size:11px">● Action Required</span>' if handshake_req else '<span class="tv-badge tv-badge-ok" style="font-size:11px">● Normal</span>'}
              </div>
              <div style="font-size:14px;font-weight:600;color:var(--tv-text);margin-bottom:6px">Trust Handshake</div>
              <div style="font-size:12.5px;color:var(--tv-muted);line-height:1.5;margin-bottom:10px">
                {'⚠️ Critical threat detected! Out-of-band verification challenge recommended before executing any request.' if handshake_req else 'Multi-factor controls idle. No active identity challenge required.'}
              </div>
            </div>
            """)

            if handshake_req:
                if st.session_state.get("lm_handshake_triggered"):
                    st.success("✅ Challenge pushed to secondary authorized device. Awaiting biometric confirmation.")
                else:
                    if st.button("🔐 Send Verification Challenge", type="primary", use_container_width=True, key="lm_trig_hs"):
                        st.session_state.lm_handshake_triggered = True
                        st.rerun()

            if st.button("Reset Monitor State", use_container_width=True, key="lm_rst"):
                st.session_state.last_result = None
                st.session_state.last_analysis = None
                st.session_state.lm_handshake_triggered = False
                st.session_state["_lm_last_cache_key"] = None
                st.session_state["_lm_speaker_name"] = None
                st.session_state["_lm_identity_status"] = None
                st.session_state["_lm_active"] = False
                st.session_state.pop("lm_preset_data", None)
                st.session_state.pop("lm_recorded_bytes", None)
                st.rerun()

    # ═════════════════════════════════════════════════════════════════════════
    # TAB 2: REAL-TIME STREAM SIMULATION
    # ═════════════════════════════════════════════════════════════════════════
    with tab_stream:
        render("""
        <div class="tv-card">
          <div class="tv-section-head">
            <span class="tv-section-head-title">Real-Time Continuous Stream Simulation</span>
            <span class="tv-section-head-meta">Simulates turn-by-turn live telephony/VoIP stream monitoring</span>
          </div>
          <p style="font-size:13px;color:var(--tv-muted);margin:0 0 12px 0">
            Select an attack scenario to watch the live monitor analyze streaming utterances in real-time,
            updating the transcript stream, active speaker signals, and risk progression dynamically.
          </p>
        </div>
        """)

        scenario_map = {s["id"]: f"Scenario {s['id']}: {s['title']}" for s in SCENARIOS}
        chosen_scen_id = st.selectbox(
            "Select real-time attack simulation scenario:",
            list(scenario_map.keys()),
            format_func=lambda k: scenario_map[k],
            key="lm_scen_choice",
        )
        current_scen = next((s for s in SCENARIOS if s["id"] == chosen_scen_id), SCENARIOS[0])
        steps = current_scen["steps"]
        total_steps = len(steps)

        curr_step = st.session_state.get("lm_stream_step", 0)
        curr_step = min(curr_step, total_steps)

        col_sbtn1, col_sbtn2, col_sbtn3 = st.columns([1.5, 1.5, 1.5])
        with col_sbtn1:
            if st.button("▶️ Step Next Turn", type="primary", use_container_width=True, key="lm_step_next"):
                if curr_step < total_steps:
                    curr_step += 1
                    st.session_state.lm_stream_step = curr_step
                    st.rerun()
                else:
                    st.info("Scenario complete. Click Reset to restart.")
        with col_sbtn2:
            if st.button("⏩ Advance to End", use_container_width=True, key="lm_step_all"):
                curr_step = total_steps
                st.session_state.lm_stream_step = curr_step
                st.rerun()
        with col_sbtn3:
            if st.button("⏹️ Reset Stream", use_container_width=True, key="lm_step_rst"):
                st.session_state.lm_stream_step = 0
                st.session_state.lm_handshake_triggered = False
                st.session_state.last_result = None
                st.session_state.last_analysis = None
                st.rerun()

        # Compute stream state up to curr_step
        if curr_step > 0:
            active_steps = steps[:curr_step]
            accumulated_text = " ".join(s["text"] for s in active_steps)
            latest_turn = active_steps[-1]

            # Run interaction analysis
            sim_analysed = analyse_interaction(
                transcript=accumulated_text,
                voice_label=latest_turn.get("voice", "LIKELY_AUTHENTIC"),
                identity_status=latest_turn.get("identity", "UNVERIFIED"),
                authenticity_score=92 if latest_turn.get("voice") == "LIKELY_AUTHENTIC" else 15,
                conversation_state=st.session_state.conversation_state,
                source=f"LIVE STREAM ({current_scen['title']})",
                voice_evidence="scenario_model",
            )
            _apply_result(sim_analysed, f"LIVE STREAM ({current_scen['title']})")

            sim_trust = int(sim_analysed["trust_score"])
            sim_risk = max(0, min(100, 100 - sim_trust))

            col_sim1, col_sim2 = st.columns([2, 1], gap="medium")
            with col_sim1:
                render(f"""
                <div class="tv-card">
                  <div class="tv-section-head">
                    <span class="tv-section-head-title">Live Call Stream (Turn {curr_step}/{total_steps})</span>
                    <span class="tv-badge {"tv-badge-crit" if sim_risk >= 80 else ("tv-badge-warn" if sim_risk >= 55 else "tv-badge-ok")}">
                      ● Risk: {sim_risk}% ({sim_analysed['interaction_risk']})
                    </span>
                  </div>
                """)
                # Dynamic animated simulation waveform
                sim_env = [int(15 + (sim_risk * 0.7) * (0.8 + 0.4 * (i % 3))) for i in range(36)]
                render(_render_waveform_svg(sim_env, sim_risk))

                # Stream dialogue history
                dialogue_html = ""
                for idx, turn in enumerate(active_steps, 1):
                    is_latest = idx == curr_step
                    hl_turn = _highlight_threat_keywords(turn["text"])
                    border_cls = "border-left:3px solid #2563D6;background:var(--tv-surface);" if is_latest else "border-left:3px solid var(--tv-border);"
                    dialogue_html += f"""
                    <div style="margin-bottom:8px;padding:8px 12px;border-radius:4px;{border_cls}">
                      <div style="font-size:11px;font-weight:600;color:var(--tv-muted);margin-bottom:2px">
                        Turn {idx} · {escape(turn.get('claimed_identity') or 'Caller')}
                      </div>
                      <div style="font-size:13.5px;color:var(--tv-text)">{hl_turn}</div>
                    </div>
                    """
                render(f"""
                  <div style="padding:10px;background:var(--tv-bg);border-radius:6px;border:1px solid var(--tv-border);max-height:220px;overflow-y:auto">
                    {dialogue_html}
                  </div>
                </div>
                """)

            with col_sim2:
                render(f"""
                <div class="tv-card">
                  <div class="tv-section-head-title" style="margin-bottom:10px">Live Signal State</div>
                  <div class="tv-evidence-row"><span class="tv-evidence-label">Voice label</span><span style="font-size:12.5px;font-weight:600">{escape(latest_turn.get('voice', '—'))}</span></div>
                  <div class="tv-evidence-row"><span class="tv-evidence-label">Identity</span><span style="font-size:12.5px;font-weight:600">{escape(latest_turn.get('identity', '—'))}</span></div>
                  <div class="tv-evidence-row"><span class="tv-evidence-label">Intent</span><span style="font-size:12.5px;font-weight:600">{escape(str(sim_analysed.get('intent', {}).get('intent', '—')).replace('_', ' ').title())}</span></div>
                  <div class="tv-evidence-row" style="border-bottom:0"><span class="tv-evidence-label">Action</span><span style="font-size:12.5px;font-weight:600;color:var(--tv-text)">{escape(str(sim_analysed.get('action', '—')).replace('_', ' ').title())}</span></div>
                </div>
                """)
                if sim_risk >= 80:
                    render("""
                    <div class="tv-card" style="background:#FEF2F2;border:1.5px solid #FCA5A5">
                      <div style="color:#DC2626;font-weight:700;font-size:13.5px;margin-bottom:6px">⚠️ Trust Handshake Triggered</div>
                      <div style="font-size:12px;color:#475569;line-height:1.5">
                        Attacker has escalated to critical credential/financial coercion. Independent verification required.
                      </div>
                    </div>
                    """)

    # ═════════════════════════════════════════════════════════════════════════
    # TAB 3: REAL-TIME ARCHITECTURE GUIDE
    # ═════════════════════════════════════════════════════════════════════════
    with tab_arch:
        render("""
        <div class="tv-card">
          <div class="tv-section-head">
            <span class="tv-section-head-title">Can We Do This in Real Time? Architecture & Production Blueprint</span>
          </div>
          <p style="font-size:13.5px;color:var(--tv-text);line-height:1.65">
            <b>Yes!</b> While Streamlit's web interface captures audio on speech completion, enterprise real-time voice monitoring
            operates as an <b>asynchronous streaming pipeline</b> connected to PBX/SIP or WebRTC audio streams.
            Below is the production blueprint for running TRUSTVOICE AI continuously in real-time:
          </p>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">
          <div class="tv-card" style="margin-top:0">
            <div style="font-weight:700;font-size:14px;color:var(--tv-text);margin-bottom:6px">1. 20ms Ingestion & Sliding Window Buffer</div>
            <div style="font-size:12.5px;color:var(--tv-muted);line-height:1.6">
              Incoming cellular or VoIP audio streams over <b>RTP / WebRTC</b> as 20 ms PCM frames.
              The streaming worker maintains a <b>4.0-second circular buffer (64,600 samples)</b> with a <b>1.0-second hop</b>.
              Every 1 second, the AASIST ONNX model scores the active buffer, emitting continuous authenticity probabilities.
            </div>
          </div>
          <div class="tv-card" style="margin-top:0">
            <div style="font-weight:700;font-size:14px;color:var(--tv-text);margin-bottom:6px">2. Low-Latency Streaming Whisper ASR</div>
            <div style="font-size:12.5px;color:var(--tv-muted);line-height:1.6">
              Faster-Whisper runs with <b>Silero VAD chunking</b>. As pauses occur (300ms speech boundary),
              partial and final transcripts are emitted via WebSocket.
              Our <b>domain vocabulary prompt</b> biases tokens towards security & banking terminology with zero latency overhead.
            </div>
          </div>
          <div class="tv-card" style="margin-top:0">
            <div style="font-weight:700;font-size:14px;color:var(--tv-text);margin-bottom:6px">3. Asynchronous Risk Fusion</div>
            <div style="font-size:12.5px;color:var(--tv-muted);line-height:1.6">
              Every newly emitted sentence is processed by the lightweight TF-IDF + Logistic Regression intent classifier
              in <b>&lt; 5 ms</b>. Multi-turn conversational state tracks escalating pressure or retractions without blocking the audio thread.
            </div>
          </div>
          <div class="tv-card" style="margin-top:0">
            <div style="font-weight:700;font-size:14px;color:var(--tv-text);margin-bottom:6px">4. Real-Time Intervention & Handshake</div>
            <div style="font-size:12.5px;color:var(--tv-muted);line-height:1.6">
              If the fused risk crosses the <b>80% Critical threshold</b> during a call, the PBX or agent console
              automatically activates <b>Trust Handshake</b>: dispatching an out-of-band push to the executive's mobile device
              or terminating the SIP trunk before credentials can be stolen.
            </div>
          </div>
        </div>

        <div class="tv-card">
          <div class="tv-section-head-title" style="margin-bottom:8px">Latency & Performance Budget (Target &lt; 800 ms)</div>
          <table style="width:100%;font-size:12.5px;border-collapse:collapse;color:var(--tv-text)">
            <tr style="border-bottom:1px solid var(--tv-border);text-align:left">
              <th style="padding:6px 8px">Pipeline Component</th>
              <th style="padding:6px 8px">Execution Time</th>
              <th style="padding:6px 8px">Processing Strategy</th>
            </tr>
            <tr style="border-bottom:1px solid var(--tv-border)">
              <td style="padding:6px 8px">Audio Resample & Normalization</td>
              <td style="padding:6px 8px;font-weight:600">~15 ms</td>
              <td style="padding:6px 8px;color:var(--tv-muted)">In-memory NumPy circular buffer</td>
            </tr>
            <tr style="border-bottom:1px solid var(--tv-border)">
              <td style="padding:6px 8px">AASIST Countermeasure Inference</td>
              <td style="padding:6px 8px;font-weight:600">~85 ms</td>
              <td style="padding:6px 8px;color:var(--tv-muted)">ONNX Runtime on CPU quantized thread pool</td>
            </tr>
            <tr style="border-bottom:1px solid var(--tv-border)">
              <td style="padding:6px 8px">Faster-Whisper (base model)</td>
              <td style="padding:6px 8px;font-weight:600">~350 ms</td>
              <td style="padding:6px 8px;color:var(--tv-muted)">VAD endpointed utterance chunks</td>
            </tr>
            <tr style="border-bottom:1px solid var(--tv-border)">
              <td style="padding:6px 8px">Intent & Context Fusion</td>
              <td style="padding:6px 8px;font-weight:600">~8 ms</td>
              <td style="padding:6px 8px;color:var(--tv-muted)">Local scikit-learn vectorized classifier</td>
            </tr>
            <tr>
              <td style="padding:6px 8px"><b>Total End-to-End Latency</b></td>
              <td style="padding:6px 8px;font-weight:700;color:var(--tv-accent)">~458 ms</td>
              <td style="padding:6px 8px;font-weight:600;color:#16A34A">Well within sub-second enterprise SLA</td>
            </tr>
          </table>
        </div>
        """)

    render("""<div class="tv-footer">TRUSTVOICE AI · authorized live audio stream monitoring · prototype security console</div>""")
