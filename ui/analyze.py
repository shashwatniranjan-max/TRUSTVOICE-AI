"""Analyze Audio — expanded technical analysis, risk fusion audit, and deep diagnostics."""

from __future__ import annotations

import json
from html import escape

import streamlit as st

from models.antispoof import analyze_audio_bytes
from models.asr import asr_dependency_status, asr_model_name, get_whisper_model, resolve_live_transcript
from risk.pipeline import analyse_interaction
from ui.theme import COLORS
from utils.audio import DECODE_FORMAT_HELP
from utils.reporting import REPORTLAB_AVAILABLE, build_incident_report, build_incident_report_pdf
from utils.state import new_conversation_state


def render(html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def _cached_asr_model(name: str):
    return get_whisper_model(name)


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


def _pipeline_sidebar_html(audio: dict | None, result: dict | None) -> str:
    """Render the 6-stage analysis pipeline progress panel."""
    anti = (audio or {}).get("anti_spoof")
    decoded = bool((audio or {}).get("duration") is not None)
    fused = bool(result)

    stages = [
        ("1", "Audio Ingestion", decoded, bool((audio or {}).get("user_error"))),
        ("2", "AASIST Countermeasure", bool(anti), not decoded),
        ("3", "Speaker Biometrics", fused, False),
        ("4", "NLP & Behaviour Engine", fused, False),
        ("5", "Risk Fusion & Gates", fused, False),
        ("6", "Trust Handshake", fused and result.get("handshake_required"), False),
    ]
    items = ""
    for num, label, done, _ in stages:
        num_cls = "done" if done else ("active" if decoded and not fused else "")
        items += f"""
        <div class="tv-pipeline-item">
          <div class="tv-pipeline-num {num_cls}">{num}</div>
          <div class="tv-pipeline-label">{escape(label)}</div>
          <div class="tv-pipeline-arrow">↓</div>
        </div>"""
    return items


def render_analyze():
    # ── Header ──────────────────────────────────────────────────────────────
    render("""
    <div class="tv-page">
      <div>
        <h1>ANALYZE AUDIO & INTERACTION</h1>
        <p>Comprehensive multi-factor security evaluation: voice authenticity, biometric identity, intent, behavioural pressure, and contextual anomalies.</p>
      </div>
    </div>
    """)

    dep = asr_dependency_status()
    if not dep.get("ok"):
        st.warning(dep.get("error") or "ASR is unavailable — transcription will be skipped.")

    if "_asr_transcript_pending" in st.session_state:
        st.session_state["analyze_transcript"] = st.session_state.pop("_asr_transcript_pending")

    audio = st.session_state.get("last_analysis") or {}
    result = st.session_state.get("last_result")

    # ── Layout ──────────────────────────────────────────────────────────────
    col_main, col_pipeline = st.columns([2.3, 0.9], gap="medium")

    with col_pipeline:
        pipeline_html = _pipeline_sidebar_html(audio, result)
        render(f"""
        <div class="tv-card">
          <div class="tv-card-title">Analysis Pipeline Status</div>
          {pipeline_html}
          <div style="margin-top:12px;padding:10px;background:var(--tv-surface);border-radius:6px;
            border:1px solid var(--tv-border);font-size:12px;color:var(--tv-muted);line-height:1.55">
            <b>Zero Mocked Metrics</b>: All scores, intermediate logits, and detected cues shown below reflect real execution outputs from the local models.
          </div>
        </div>
        """)

        if result:
            if st.button("→ View in Overview", use_container_width=True, key="az_goto_ov"):
                st.session_state.ui_nav = "Overview"
                st.rerun()

    with col_main:
        # ── Upload zone ──────────────────────────────────────────────────────
        render("""<div class="tv-card">""")
        render("""<div class="tv-card-title">Input Audio or Speech Stream</div>""")

        uploaded = st.file_uploader(
            "Drop audio file here",
            type=["wav", "mp3", "mpeg", "mpga", "m4a", "aac", "ogg", "opus",
                  "oga", "flac", "mp4", "webm", "mov", "3gp", "amr"],
            key="analyze_upload",
            label_visibility="collapsed",
        )
        mic = st.audio_input("Or record live from microphone", key="analyze_mic")

        render(f"""<div class="tv-dim" style="margin:4px 0 10px">
          Supported: WAV · MP3 · M4A · FLAC · OGG · AAC · WebM · 16 kHz Mono Standard
        </div>""")

        if uploaded is not None:
            st.audio(uploaded)
        elif mic is not None:
            st.audio(mic)

        # File metadata strip
        fname = uploaded.name if uploaded else ("live_microphone.wav" if mic else "Not selected")
        raw_bytes = uploaded.getvalue() if uploaded else (mic.getvalue() if mic else None)
        dur = audio.get("duration")
        fmt = audio.get("format")
        dur_str = f"{dur:.2f} s" if dur is not None else "Not available"
        fmt_str = str(fmt).upper() if fmt else "Not available"
        sr_val = audio.get("sample_rate")
        sr_str = f"{sr_val} Hz" if sr_val else "16000 Hz (Resampled)"

        render(f"""
        <div style="display:flex;gap:20px;flex-wrap:wrap;margin:12px 0 4px">
          <div>
            <div style="font-size:11px;color:var(--tv-muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em">Source File</div>
            <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">{escape(fname)}</div>
          </div>
          <div>
            <div style="font-size:11px;color:var(--tv-muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em">Duration</div>
            <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">{escape(dur_str)}</div>
          </div>
          <div>
            <div style="font-size:11px;color:var(--tv-muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em">Audio Format</div>
            <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">{escape(fmt_str)}</div>
          </div>
          <div>
            <div style="font-size:11px;color:var(--tv-muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em">Sampling Rate</div>
            <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">{escape(sr_str)}</div>
          </div>
        </div>
        """)
        render("""</div>""")

        # ── Transcript & identity ────────────────────────────────────────────
        render("""<div class="tv-card">""")
        render("""<div class="tv-card-title">Transcript & Speaker Biometric Context</div>""")

        last_asr = audio.get("asr") or {}
        if last_asr.get("status") == "success" and last_asr.get("transcript"):
            model_disp = escape(str(last_asr.get("model") or "base"))
            lang_disp = escape(str(last_asr.get("language") or "en")).upper()
            prob = last_asr.get("language_probability")
            prob_disp = f" ({int(prob * 100)}%)" if prob else ""
            beam_disp = escape(str(last_asr.get("beam_size") or 5))
            sec_disp = f"{last_asr.get('elapsed_sec')}s" if last_asr.get("elapsed_sec") is not None else ""
            meta_str = f"Model: <b>{model_disp}</b> · Lang: <b>{lang_disp}{prob_disp}</b> · Beam: <b>{beam_disp}</b>"
            if sec_disp:
                meta_str += f" · Latency: <b>{sec_disp}</b>"
            render(f"""
            <div style="margin-bottom:8px;padding:6px 10px;background:var(--tv-surface);border-radius:6px;
                 border:1px solid var(--tv-border);font-size:12px;color:var(--tv-text);display:flex;align-items:center;gap:6px">
              <span style="color:var(--tv-blue);font-weight:600">🎙️ ASR Telemetry</span>
              <span>{meta_str}</span>
            </div>
            """)

        transcript = st.text_area(
            "Transcript",
            height=85,
            key="analyze_transcript",
            placeholder="Type or paste a transcript to analyze directly, or upload audio to transcribe automatically via faster-whisper…",
            label_visibility="collapsed",
        )
        from demo.scenarios import IDENTITY_HELP
        identity = st.selectbox(
            "Speaker Biometric Enrollment Status",
            ["NOT_AVAILABLE", "UNVERIFIED", "VERIFIED", "MISMATCH"],
            help=IDENTITY_HELP.get("NOT_AVAILABLE", ""),
            key="analyze_identity",
            label_visibility="visible",
        )

        c1, c2 = st.columns(2)
        with c1:
            run = st.button("⊕ Run Comprehensive Security Analysis", use_container_width=True,
                            type="primary", key="analyze_run",
                            disabled=(raw_bytes is None and not transcript.strip()))
        with c2:
            clear = st.button("Reset / Clear Session", use_container_width=True, key="analyze_clear")

        if st.session_state.get("live_warning"):
            st.warning(st.session_state.live_warning)

        render("""</div>""")

        # ── Execution Logic ──────────────────────────────────────────────────
        if clear:
            st.session_state.last_result = None
            st.session_state.last_analysis = None
            st.session_state.transcript = ""
            st.session_state.analysis_source = "Idle"
            st.session_state.live_warning = None
            st.session_state.asr_filled_transcript = ""
            st.rerun()

        if run:
            st.session_state.live_warning = None
            fname_run = "typed_transcript.txt"
            if uploaded is not None:
                raw_bytes, fname_run = uploaded.getvalue(), uploaded.name
            elif mic is not None:
                raw_bytes, fname_run = mic.getvalue(), "live_microphone.wav"
            else:
                raw_bytes = None

            audio_result = None
            voice_label = "UNAVAILABLE"
            auth_score = None
            asr_result = None

            if raw_bytes:
                try:
                    status_box = st.status("Executing multi-component security analysis…", expanded=True)

                    def _prog(msg: str):
                        status_box.write(msg)

                    asr_model = st.session_state.get("asr_model_choice", asr_model_name())
                    asr_lang = st.session_state.get("asr_language", "en")
                    asr_beam = 5 if st.session_state.get("asr_quality_mode", "accurate") == "accurate" else 1
                    asr_prompt_on = st.session_state.get("asr_domain_prompt", True)
                    from models.asr import DEFAULT_ASR_PROMPT
                    asr_prompt_str = DEFAULT_ASR_PROMPT if asr_prompt_on else None

                    try:
                        _prog(f"Loading faster-whisper ASR runtime ({asr_model})…")
                        _cached_asr_model(asr_model)
                    except Exception:
                        _prog("Faster-whisper runtime unavailable — skipping automated ASR.")

                    audio_result = analyze_audio_bytes(
                        raw_bytes, fname_run,
                        model_key=st.session_state.model_choice,
                        threshold=float(st.session_state.bona_threshold),
                        band=float(st.session_state.decision_band),
                        threshold_source=st.session_state.threshold_source,
                        allow_download=True,
                        transcribe=True,
                        asr_model=asr_model,
                        asr_language=asr_lang,
                        asr_beam_size=asr_beam,
                        asr_prompt=asr_prompt_str,
                        on_progress=_prog,
                    )
                    if audio_result.get("user_error"):
                        st.session_state.live_warning = audio_result["user_error"]
                    status_box.update(label="Audio & ASR analysis completed", state="complete")
                except Exception as exc:
                    audio_result = {
                        "anti_spoof": None,
                        "asr": {"status": "error", "transcript": "", "error": str(exc)},
                        "user_error": "Audio analysis failed.",
                        "limitations": [str(exc)],
                    }
                    st.session_state.live_warning = audio_result["user_error"]

                st.session_state.last_analysis = audio_result
                asr_result = (audio_result or {}).get("asr")
                if (audio_result or {}).get("limitations") and not (audio_result or {}).get("user_error"):
                    st.warning(" | ".join(audio_result["limitations"]))
                anti_now = (audio_result or {}).get("anti_spoof")
                if anti_now:
                    voice_label = anti_now.get("voice_label", "INCONCLUSIVE")
                    auth_score = anti_now.get("authenticity_score")
                q = (audio_result or {}).get("quality_gate") or {}
                if q.get("quality") == "REVIEW":
                    st.warning("Acoustic quality alert: " + "; ".join(q.get("issues") or []))
            elif not transcript.strip():
                st.warning("Please upload an audio file or enter a transcript.")
            else:
                st.session_state.last_analysis = None

            if raw_bytes or transcript.strip():
                filled = (st.session_state.get("asr_filled_transcript") or "").strip()
                typed = transcript.strip()
                if raw_bytes:
                    manual = typed if typed and typed != filled else ""
                else:
                    manual = typed
                choice = resolve_live_transcript(manual, asr_result)
                st.session_state.transcript_source = choice["source"]
                st.session_state.live_warning = choice["warning"]
                if choice["source"] == "ASR" and choice["text"]:
                    st.session_state["_asr_transcript_pending"] = choice["text"]
                    st.session_state.asr_filled_transcript = choice["text"]
                if choice["analyze"]:
                    with st.spinner("Executing risk fusion and safety gate arbiter…"):
                        analysed = analyse_interaction(
                            transcript=choice["text"],
                            voice_label=voice_label,
                            identity_status=identity,
                            authenticity_score=auth_score,
                            conversation_state=st.session_state.conversation_state,
                            source="LIVE / UPLOADED ANALYSIS",
                            voice_evidence="model" if auth_score is not None else "unavailable",
                        )
                    _apply_result(analysed, "LIVE / UPLOADED ANALYSIS", audio_result)
                elif raw_bytes:
                    st.session_state.analysis_source = "LIVE / UPLOADED ANALYSIS"
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # ── DEEP TECHNICAL RESULTS SECTION (FULL WIDTH) ─────────────────────────
    # ══════════════════════════════════════════════════════════════════════════
    if result:
        anti = (audio or {}).get("anti_spoof") or {}
        quality = (audio or {}).get("quality_gate") or {}
        asr_data = (audio or {}).get("asr") or {}
        trust = int(result.get("trust_score", 0))
        prelim = result.get("fused_uncapped", trust)
        risk_label = result.get("interaction_risk", "—")
        action_code = result.get("action", "CONTINUE")
        action_detail = result.get("action_detail", "")
        drivers = result.get("drivers") or []
        fusion_audit = result.get("fusion_audit") or {}
        signals_summary = result.get("signals_summary") or {}
        cat_entities = result.get("categorized_entities") or {}
        diagnostics = result.get("diagnostics") or {}
        conv_state = st.session_state.get("conversation_state") or result.get("conversation_state") or {}
        turn_history = conv_state.get("turn_history", [])

        # Color mapping
        badge_cls = "tv-badge-crit" if risk_label == "CRITICAL" else ("tv-badge-warn" if risk_label == "HIGH" else ("tv-badge-blue" if risk_label == "ELEVATED" else "tv-badge-ok"))
        delta_val = fusion_audit.get("delta", 0)
        delta_str = f"{delta_val:+d} pts" if delta_val != 0 else "0 pts (Unmodified)"
        gate_status_str = "Score Capped by Safety Policy" if fusion_audit.get("gate_modified") else "Standard Linear Fusion"

        render("<div style='margin-top:10px'></div>")

        # ── 1. Overall Trust Assessment ──────────────────────────────────────
        render(f"""
        <div class="tv-card" style="border-left: 4px solid {'#DC2626' if risk_label == 'CRITICAL' else ('#D97706' if risk_label == 'HIGH' else '#2563D6')}">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:10px">
            <div>
              <div style="font-size:11.5px;font-weight:700;color:var(--tv-muted);text-transform:uppercase;letter-spacing:.06em">
                TrustVoice Risk Engine · Overall Trust Assessment
              </div>
              <div style="display:flex;align-items:baseline;gap:10px;margin-top:4px">
                <span style="font-size:40px;font-weight:800;color:var(--tv-text)">{trust}</span>
                <span style="font-size:18px;font-weight:600;color:var(--tv-muted)">/ 100</span>
                <span class="tv-badge {badge_cls}" style="font-size:12.5px;padding:3px 10px">{risk_label} RISK</span>
                <span class="tv-badge tv-badge-blue" style="font-size:12.5px;padding:3px 10px">{action_code}</span>
              </div>
            </div>
            <div style="text-align:right;background:var(--tv-surface);padding:8px 14px;border-radius:6px;border:1px solid var(--tv-border)">
              <div style="font-size:12px;color:var(--tv-text)">Preliminary Weighted Score: <b>{prelim}/100</b></div>
              <div style="font-size:12px;color:var(--tv-text)">Policy Gate Adjustment: <b>{delta_str}</b></div>
              <div style="font-size:12px;color:var(--tv-muted)">Arbitration Status: <b>{gate_status_str}</b></div>
            </div>
          </div>

          <div style="background:var(--tv-surface);padding:10px 14px;border-radius:6px;border:1px solid var(--tv-border);margin-bottom:12px">
            <div style="font-size:12px;font-weight:700;color:var(--tv-text);margin-bottom:2px">Recommended Protocol: {escape(action_code)}</div>
            <div style="font-size:12.5px;color:var(--tv-muted);line-height:1.5">{escape(action_detail)}</div>
          </div>

          <div style="display:flex;gap:20px;flex-wrap:wrap;padding-top:4px;border-top:1px solid var(--tv-border);font-size:12px;color:var(--tv-muted)">
            <span>Active Threat Signals: <b style="color:var(--tv-text)">{signals_summary.get('active_threats_count', 0)}</b></span>
            <span>High-Severity Cues: <b style="color:{'#DC2626' if signals_summary.get('high_severity_count', 0) > 0 else 'var(--tv-text)'}">{signals_summary.get('high_severity_count', 0)}</b></span>
            <span>Dimensions Affected: <b style="color:var(--tv-text)">{signals_summary.get('dimensions_affected_count', 0)} / 5</b></span>
            <span>Hard Safety Gates Fired: <b style="color:var(--tv-text)">{fusion_audit.get('active_gate_count', 0)}</b></span>
          </div>
        </div>
        """)

        # ── 2. Five-Dimension Safety Breakdown ───────────────────────────────
        dims = fusion_audit.get("dimensions") or {}
        v_d = dims.get("voice_authenticity", {})
        s_d = dims.get("speaker_identity", {})
        i_d = dims.get("intent_safety", {})
        b_d = dims.get("behaviour_safety", {})
        c_d = dims.get("context_safety", {})

        def _dim_card(title, weight_pct, raw_score, weighted_pts, rating, extra_pill):
            col = "#16A34A" if raw_score >= 80 else ("#D97706" if raw_score >= 55 else "#DC2626")
            return f"""
            <div style="background:var(--tv-surface);border:1px solid var(--tv-border);border-radius:8px;padding:12px 14px;flex:1;min-width:170px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                <span style="font-size:12px;font-weight:700;color:var(--tv-text)">{escape(title)}</span>
                <span style="font-size:11px;font-weight:600;color:var(--tv-muted)">{weight_pct}</span>
              </div>
              <div style="display:flex;align-items:baseline;gap:6px;margin-bottom:4px">
                <span style="font-size:24px;font-weight:800;color:{col}">{raw_score}</span>
                <span style="font-size:12px;color:var(--tv-muted)">/ 100</span>
              </div>
              <div style="font-size:11.5px;color:var(--tv-muted);margin-bottom:6px">
                Contributes: <b>{weighted_pts} pts</b>
              </div>
              <div style="font-size:11px;padding:2px 6px;border-radius:4px;background:{col}18;color:{col};font-weight:600;display:inline-block">
                {escape(extra_pill)}
              </div>
            </div>
            """

        dim_cards_html = f"""
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px">
          {_dim_card("1. Voice Authenticity", "15%", v_d.get("raw_score", 0), v_d.get("weighted_points", 0), v_d.get("rating", ""), str(result.get('voice_display', '—'))[:20])}
          {_dim_card("2. Speaker Identity", "10%", s_d.get("raw_score", 0), s_d.get("weighted_points", 0), s_d.get("rating", ""), str(result.get('identity_status', '—')))}
          {_dim_card("3. Intent Safety", "30%", i_d.get("raw_score", 0), i_d.get("weighted_points", 0), i_d.get("rating", ""), str((result.get('intent') or {}).get('intent', '—')).replace('_', ' ').title()[:18])}
          {_dim_card("4. Behaviour Safety", "25%", b_d.get("raw_score", 0), b_d.get("weighted_points", 0), b_d.get("rating", ""), f"{len(result.get('behaviour_signals', []))} cues detected")}
          {_dim_card("5. Context Safety", "20%", c_d.get("raw_score", 0), c_d.get("weighted_points", 0), c_d.get("rating", ""), f"{len(result.get('context_signals', []))} anomalies")}
        </div>
        """
        render(dim_cards_html)

        # ── 3. Tabs for Deep Inspection ──────────────────────────────────────
        tab_fusion, tab_signals, tab_voice, tab_intent, tab_history, tab_diagnostics = st.tabs([
            "🧮 Mathematical Risk Fusion & Gates",
            "🚨 Signal Inventory & Evidence",
            "🎙️ Voice Authenticity & ASR",
            "🧠 Intent & Redacted Entities",
            "🔄 Multi-Turn History",
            "⚙️ Diagnostics & Export Report",
        ])

        # ── TAB 1: Fusion & Gates ────────────────────────────────────────────
        with tab_fusion:
            st.markdown("### Step-by-Step Risk Fusion Calculation")
            st.caption("Linear 5-dimension weighted summation followed by non-linear policy gate arbitration.")

            # Dimension math table
            fusion_rows = []
            for k in ["voice_authenticity", "speaker_identity", "intent_safety", "behaviour_safety", "context_safety"]:
                d = dims.get(k, {})
                fusion_rows.append({
                    "Dimension": d.get("label", k),
                    "Configured Weight": d.get("weight_pct", "0%"),
                    "Raw Score (0-100)": d.get("raw_score", 0),
                    "Weighted Contribution": f"{d.get('weighted_points', 0):.2f} pts",
                    "Safety Evaluation": d.get("rating", "Standard"),
                })
            st.table(fusion_rows)

            st.markdown(f"""
            **Preliminary Mathematical Score**: `{v_d.get('weighted_points', 0):.2f} + {s_d.get('weighted_points', 0):.2f} + {i_d.get('weighted_points', 0):.2f} + {b_d.get('weighted_points', 0):.2f} + {c_d.get('weighted_points', 0):.2f} = {fusion_audit.get('preliminary_exact', prelim)} pts` (Rounded to **{prelim} / 100**)
            """)

            st.markdown("---")
            st.markdown("### Safety Gates Audit (Policy Constraint Matrix)")
            st.caption("Hard safety gates prevent weighted averaging from diluting high-severity threats (e.g., direct OTP solicitation under urgency).")

            gates_eval = fusion_audit.get("gates_evaluated") or []
            if gates_eval:
                gate_display_table = []
                for g in gates_eval:
                    status_str = "🚨 TRIGGERED" if g.get("triggered") else "⚪ INACTIVE"
                    gate_display_table.append({
                        "Gate Name": g.get("name"),
                        "Status": status_str,
                        "Max Score Cap": f"≤ {g.get('cap')}",
                        "Forced Risk": g.get("forced_risk") or "—",
                        "Condition Evaluated": g.get("condition_desc"),
                        "Operational Rationale": g.get("rationale"),
                        "Score Impact": g.get("effect"),
                    })
                st.dataframe(gate_display_table, use_container_width=True)

            if fusion_audit.get("gate_modified"):
                st.error(f"⚠️ Policy Gate Active: Score capped from {prelim} to {trust} ({delta_str}) to enforce safety floor.")
            else:
                st.success("✅ No hard safety gates triggered. Final Trust Score matches the linear weighted sum.")

        # ── TAB 2: Signal Inventory & Evidence ───────────────────────────────
        with tab_signals:
            st.markdown("### Comprehensive Risk Signal Inventory")
            st.caption("Inventory of all acoustic, biometric, conversational, behavioural, and contextual signals evaluated.")

            c_s1, c_s2, c_s3, c_s4 = st.columns(4)
            c_s1.metric("Total Signals Evaluated", signals_summary.get("total_signals_recorded", 0))
            c_s2.metric("Active Threat Cues", signals_summary.get("active_threats_count", 0))
            c_s3.metric("High-Severity Signals", signals_summary.get("high_severity_count", 0))
            c_s4.metric("Dimensions Affected", f"{signals_summary.get('dimensions_affected_count', 0)} / 5")

            inv = signals_summary.get("inventory") or []
            if inv:
                st.dataframe([
                    {
                        "Category": s["category"],
                        "Signal Name": s["name"],
                        "Status": s["status"],
                        "Severity": s["severity"],
                        "Dimension Affected": s["dimension"],
                        "Evidence / Source": s["evidence"],
                        "Impact on Decision": s["impact"],
                    }
                    for s in inv
                ], use_container_width=True)

            st.markdown("---")
            st.markdown("### Social-Engineering Behavioural Cues Matrix")
            st.caption("Observable psychological indicators detected via regex and temporal pattern recognition.")
            b_indicators = (result.get("behaviour") or {}).get("indicators") or []
            if b_indicators:
                st.table([
                    {
                        "Indicator": bi["label"],
                        "Status": "DETECTED" if bi["detected"] else "NOT DETECTED",
                        "Severity": bi["severity"],
                        "Penalty Deducted": f"-{bi['penalty']} pts" if bi["penalty"] > 0 else "0 pts",
                        "Matched Excerpt": f'"{bi["evidence"]}"' if bi.get("evidence") else "—",
                        "Behavioral Significance": bi["explanation"],
                    }
                    for bi in b_indicators
                ])

        # ── TAB 3: Voice & ASR ───────────────────────────────────────────────
        with tab_voice:
            st.markdown("### AASIST Voice Authenticity Countermeasure Telemetry")
            st.caption("Raw ONNX inference metrics from the AASIST anti-spoofing neural network.")

            if anti:
                col_a1, col_a2, col_a3, col_a4 = st.columns(4)
                col_a1.metric("Authenticity Score", f"{anti.get('authenticity_score', 0)} / 100")
                col_a2.metric("Bona-Fide Probability", f"{anti.get('bona_fide_probability', 0)}%")
                col_a3.metric("Spoof Probability", f"{anti.get('spoof_probability', 0)}%")
                col_a4.metric("Pooled CM Score", f"{anti.get('cm_score', 0):.4f}")

                st.json({
                    "Verdict": anti.get("verdict"),
                    "Pooled CM Logit": anti.get("cm_score"),
                    "Worst-Window CM Logit": anti.get("worst_window_cm"),
                    "Confidence Spread (StdDev)": anti.get("confidence_spread"),
                    "Repeatability Delta": anti.get("repeatability_delta"),
                    "Engine Determinism Stable": anti.get("engine_stable"),
                    "Speech Windows Used": anti.get("windows_used"),
                    "Silent Windows Dropped": anti.get("windows_dropped_silent"),
                    "Audio Quality Assessment": quality.get("quality", "REVIEW"),
                    "Acoustic Clipping Ratio": f"{quality.get('clipping_ratio', 0)}%",
                    "Speech Activity Ratio": f"{quality.get('speech_activity_ratio', 0)}%",
                    "RMS Signal Energy": quality.get("rms", 0),
                    "Model Specification": anti.get("model"),
                    "Threshold Used": f"{anti.get('threshold_used')} ± {anti.get('decision_band')} ({anti.get('threshold_source')})",
                })
                st.info(f"ℹ️ {anti.get('score_note', '')}")
            else:
                st.warning("AASIST voice authenticity was not executed for this input (manual text input or audio decode failed).")

            st.markdown("---")
            st.markdown("### Faster-Whisper Speech Recognition Details")
            st.caption("Acoustic transcription, language identification, and word timestamp boundaries.")

            if asr_data:
                col_w1, col_w2, col_w3, col_w4 = st.columns(4)
                col_w1.metric("ASR Status", asr_data.get("status", "unknown").upper())
                col_w2.metric("Model Architecture", asr_data.get("model", "base"))
                col_w3.metric("Detected Language", str(asr_data.get("language", "en")).upper())
                col_w4.metric("Inference Latency", f"{asr_data.get('elapsed_sec', 0)} s")

                # Timestamped segments
                segments = asr_data.get("segments") or []
                if segments:
                    st.markdown("**Timestamped Utterance Segments**:")
                    st.table([
                        {
                            "Start Time": f"{s.get('start', 0):.2f} s",
                            "End Time": f"{s.get('end', 0):.2f} s",
                            "Transcribed Speech": s.get("text", ""),
                        }
                        for s in segments
                    ])
                else:
                    st.text_area("Full Transcript", value=asr_data.get("transcript", ""), height=70, disabled=True)
            else:
                st.info("No ASR telemetry recorded.")

        # ── TAB 4: Intent & Entities ─────────────────────────────────────────
        with tab_intent:
            st.markdown("### Intent Classification & Linguistic Guards")
            st.caption("TF-IDF n-grams + Logistic Regression with rule-based false-positive suppression.")

            intent_info = result.get("intent") or {}
            c_i1, c_i2, c_i3 = st.columns(3)
            c_i1.metric("Predicted Intent", intent_info.get("intent", "unknown").replace("_", " ").title())
            c_i2.metric("Classifier Confidence", f"{intent_info.get('confidence', 0)}%")
            c_i3.metric("Engine", "TF-IDF + Logistic Regression")

            # Class probabilities distribution
            probs = intent_info.get("probabilities") or {}
            if probs:
                st.markdown("**Alternative Class Probability Distribution**:")
                for cls_name, cls_pct in probs.items():
                    st.progress(cls_pct / 100.0, text=f"{cls_name.replace('_', ' ').title()}: {cls_pct}%")

            # Linguistic guards explanation
            guards = intent_info.get("linguistic_guards") or {}
            if intent_info.get("override") or guards.get("notes"):
                st.markdown("---")
                st.markdown("#### 🛡️ False-Positive Suppression & Linguistic Rules")
                if intent_info.get("override"):
                    st.info(f"**Classification Override Applied**: {intent_info['override']}")
                for gn in guards.get("notes") or []:
                    st.write(f"• {gn}")

            st.markdown("---")
            st.markdown("### Categorized Entity Extraction (PII Redacted)")
            st.caption("Regex entity extraction with automatic PII masking to protect sensitive customer data.")

            cats = cat_entities.get("categories") or []
            if cats:
                for c in cats:
                    if c["detected"]:
                        with st.expander(f"📁 {c['title']} ({c['count']} detected) — Risk: {c['highest_risk']}", expanded=True):
                            st.caption(c["description"])
                            st.table([
                                {
                                    "Entity Type": item["type"],
                                    "Masked Display Value": item["redacted_value"],
                                    "Risk Relevance": item["risk_relevance"],
                                    "Matched In Transcript": item.get("matched_text", item["value"]),
                                }
                                for item in c["items"]
                            ])
            else:
                st.info("No sensitive entities extracted from the current transcript.")

        # ── TAB 5: Multi-Turn History ────────────────────────────────────────
        with tab_history:
            st.markdown("### Multi-Turn Conversation Progression")
            st.caption("Turn-by-turn state tracking across multi-utterance interactions.")

            if turn_history:
                init_score = turn_history[0].get("trust_score", 0)
                curr_score = turn_history[-1].get("trust_score", 0)
                tot_delta = curr_score - init_score

                c_h1, c_h2, c_h3, c_h4 = st.columns(4)
                c_h1.metric("Total Turns Analyzed", len(turn_history))
                c_h2.metric("Initial Trust Score", f"{init_score} / 100")
                c_h3.metric("Current Trust Score", f"{curr_score} / 100", f"{tot_delta:+d} pts")
                first_crit = conv_state.get("first_critical_risk_turn") or conv_state.get("first_high_risk_turn")
                c_h4.metric("Escalation Turn", f"Turn #{first_crit}" if first_crit else "None (Safe)")

                # Turn history table
                turn_rows = []
                for t in turn_history:
                    turn_rows.append({
                        "Turn #": f"#{t.get('turn_index')}",
                        "Transcript Excerpt": (t.get("transcript") or "")[:45] + "…",
                        "Intent": str(t.get("intent", "—")).replace("_", " ").title(),
                        "Prelim Score": t.get("preliminary_score"),
                        "Final Trust Score": t.get("trust_score"),
                        "Risk Band": t.get("interaction_risk"),
                        "Action": t.get("action"),
                        "Score Change": f"{t.get('score_change', 0):+d} pts",
                        "Progression Explanation": t.get("change_explanation"),
                    })
                st.dataframe(turn_rows, use_container_width=True)

                # Turn detail inspector
                chosen_turn_idx = st.selectbox(
                    "Select Turn to Inspect Deep Snapshot:",
                    range(1, len(turn_history) + 1),
                    format_func=lambda idx: f"Turn #{idx}: {turn_history[idx-1].get('transcript', '')[:40]}…",
                    key="az_turn_inspector",
                )
                if chosen_turn_idx:
                    snap = turn_history[chosen_turn_idx - 1]
                    st.json({
                        "Turn Index": snap.get("turn_index"),
                        "Transcript": snap.get("transcript"),
                        "Intent": snap.get("intent"),
                        "Trust Score": snap.get("trust_score"),
                        "Preliminary Score": snap.get("preliminary_score"),
                        "Score Change": snap.get("score_change"),
                        "Safety Gates Triggered": snap.get("gates"),
                        "Newly Detected Signals": snap.get("newly_detected_signals"),
                        "Persistent Signals": snap.get("persistent_signals"),
                        "Explanation": snap.get("change_explanation"),
                    })
            else:
                st.info("Single turn recorded. Run additional turns to visualize multi-turn progression.")

        # ── TAB 6: Diagnostics & Export Report ────────────────────────────────
        with tab_diagnostics:
            st.markdown("### Technical System Audit & Subsystem Diagnostics")
            st.caption("Verification of component execution for competition judges and security auditors.")

            stages = diagnostics.get("pipeline_stages") or {}
            if stages:
                st.table([
                    {"Pipeline Subsystem": name, "Execution State": status}
                    for name, status in stages.items()
                ])

            st.markdown("---")
            st.markdown("### Export Analysis Report")
            st.caption("Download comprehensive security audit reports in standard JSON and PDF formats.")

            # Build report dictionary
            report_dict = build_incident_report(st.session_state)
            report_json = json.dumps(report_dict, indent=2, default=str)

            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                st.download_button(
                    label="📥 Download Analysis Report (JSON)",
                    data=report_json,
                    file_name="trustvoice_analysis_report.json",
                    mime="application/json",
                    use_container_width=True,
                    key="az_download_json",
                )

            with col_exp2:
                if REPORTLAB_AVAILABLE:
                    try:
                        pdf_data = build_incident_report_pdf(report_dict)
                        st.download_button(
                            label="📄 Download Security Audit Report (PDF)",
                            data=pdf_data,
                            file_name="trustvoice_security_report.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="az_download_pdf",
                        )
                    except Exception as exc:
                        st.warning(f"PDF generation error: {exc}")
                else:
                    st.caption("ReportLab library not detected. PDF export disabled.")

            with st.expander("🔍 Complete Raw Analysis Result (JSON Inspector)", expanded=False):
                st.json(report_dict)

    render("""<div class="tv-footer">TRUSTVOICE AI · local CPU processing · zero external telemetry</div>""")
