"""Main conversation security console."""

from html import escape

import streamlit as st

from demo.scenarios import BENIGN_EXAMPLES, IDENTITY_HELP, SCENARIO_A, SCENARIO_B
from models.antispoof import MODEL_REGISTRY, analyze_audio_bytes
from models.intent import intent_display_name
from risk.pipeline import analyse_interaction
from ui.components import decision_block, entity_lines, meter, render, signal_rows, waveform
from ui.theme import COLORS, status_color
from utils.state import new_conversation_state


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


def render_topbar():
    spec = MODEL_REGISTRY.get(st.session_state.model_choice, {})
    source = st.session_state.get("analysis_source") or "Idle"
    render(st, f"""
    <div class="tv-top">
      <div class="tv-brand">TRUSTVOICE AI
        <span>Conversation Security Console</span>
      </div>
      <div class="tv-status"><span class="tv-dot"></span>Analysis engine online</div>
      <div class="tv-meta">
        Model · {escape(str(spec.get('label', 'AASIST')))}<br>
        Mode · {escape(str(source))}
      </div>
    </div>
    """)


def render_console():
    render_topbar()
    result = st.session_state.get("last_result")
    audio = st.session_state.get("last_analysis") or {}
    anti = (audio or {}).get("anti_spoof") or {}
    quality = (audio or {}).get("quality_gate") or {}

    render(st, '<div class="tv-section">Call / audio analysis</div>')
    left, mid, right = st.columns([1.1, 1.2, 1.1], gap="small")

    with left:
        uploaded = st.file_uploader(
            "Audio or video",
            type=["wav", "mp3", "m4a", "ogg", "flac", "mp4", "webm", "mov"],
            key="console_upload",
        )
        mic = st.audio_input("Microphone capture", key="console_mic")
        transcript = st.text_area(
            "Transcript (ASR is not bundled; paste text or type)",
            value=st.session_state.get("transcript_input", ""),
            height=90,
            key="console_transcript",
        )
        identity = st.selectbox(
            "Speaker identity (prototype — not an enrolled user directory)",
            ["NOT_AVAILABLE", "UNVERIFIED", "VERIFIED", "MISMATCH"],
            help=IDENTITY_HELP["NOT_AVAILABLE"],
        )
        st.caption(IDENTITY_HELP.get(identity, ""))
        run = st.button("Run live analysis", use_container_width=True)

        if run:
            raw = None
            fname = "typed_transcript.txt"
            if uploaded is not None:
                raw, fname = uploaded.getvalue(), uploaded.name
            elif mic is not None:
                raw, fname = mic.getvalue(), "live_microphone.wav"

            audio_result = None
            voice_label = "UNAVAILABLE"
            auth_score = None
            if raw:
                with st.spinner("Decoding audio and running countermeasure…"):
                    audio_result = analyze_audio_bytes(
                        raw, fname,
                        model_key=st.session_state.model_choice,
                        threshold=float(st.session_state.bona_threshold),
                        band=float(st.session_state.decision_band),
                        threshold_source=st.session_state.threshold_source,
                        allow_download=True,
                    )
                st.session_state.last_analysis = audio_result
                if audio_result.get("limitations"):
                    st.warning(" | ".join(audio_result["limitations"]))
                anti_now = audio_result.get("anti_spoof")
                if anti_now:
                    voice_label = anti_now.get("voice_label", "INCONCLUSIVE")
                    auth_score = anti_now.get("authenticity_score")
                else:
                    st.info(
                        "Anti-spoof model unavailable. Interaction analysis can still run, "
                        "but voice authenticity cannot be established."
                    )
                q = audio_result.get("quality_gate") or {}
                if q.get("quality") == "REVIEW":
                    st.warning(
                        "Audio quality insufficient for reliable authenticity analysis. "
                        + "; ".join(q.get("issues") or [])
                    )
            elif not transcript.strip():
                st.warning("Provide audio and/or a transcript. Nothing was analysed.")
            else:
                st.session_state.last_analysis = None

            text = transcript.strip()
            if not text and not raw:
                pass
            else:
                if not text:
                    st.info("Transcript unavailable. Audio authenticity analysis can still run.")
                analysed = analyse_interaction(
                    transcript=text,
                    voice_label=voice_label,
                    identity_status=identity,
                    authenticity_score=auth_score,
                    conversation_state=st.session_state.conversation_state,
                    source="LIVE / UPLOADED ANALYSIS",
                )
                _apply_result(analysed, "LIVE / UPLOADED ANALYSIS", audio_result)
                st.rerun()

    with mid:
        env = audio.get("envelope") if audio else None
        render(st, f"""
        <div class="tv-panel">
          <div class="tv-kicker">Waveform</div>
          {waveform(env)}
          <div class="tv-muted">
            Duration {escape(str(audio.get('duration', '—')))} s ·
            Quality {escape(str(quality.get('quality', '—')))}
          </div>
        </div>
        """)
        if anti:
            render(st, f"""
            <div class="tv-panel" style="margin-top:10px">
              <div class="tv-kicker">Voice authenticity</div>
              <div class="tv-value small">{int(anti.get('authenticity_score', 0))} / 100</div>
              {meter(int(anti.get('authenticity_score', 0)), status_color(anti.get('verdict')))}
              <div class="tv-label">{escape(str(anti.get('verdict', 'UNAVAILABLE')))}</div>
              <div class="tv-muted">Model confidence is an estimate from the selected countermeasure and is not a guarantee of authenticity.</div>
            </div>
            """)
        else:
            render(st, '<div class="tv-panel" style="margin-top:10px"><div class="tv-muted">No live countermeasure result. Upload audio or use a demo scenario.</div></div>')

    with right:
        if result:
            render(st, decision_block(result))
            qlabel = (quality or {}).get("quality") or "—"
            render(st, f'<div class="tv-muted" style="margin-top:8px">Audio quality · {escape(str(qlabel))}</div>')
        else:
            render(st, '<div class="tv-panel"><div class="tv-kicker">Current decision</div><div class="tv-muted">Awaiting analysis. Live uploads use the real pipeline; demo scenarios are labelled separately.</div></div>')

    render(st, '<div class="tv-section">Risk signals</div>')
    factors = (result or {}).get("factor_display") or st.session_state.factors
    id_status = (result or {}).get("identity_status") or "NOT_AVAILABLE"
    # Speaker identity row should show status text, not a fake enrollment score alone
    display_factors = dict(factors)
    render(st, signal_rows(display_factors))
    st.caption(
        f"Speaker identity status: {id_status.replace('_', ' ')}. "
        + IDENTITY_HELP.get(id_status, "")
    )

    render(st, '<div class="tv-section">Conversation analysis</div>')
    c1, c2 = st.columns(2, gap="small")
    transcript_show = (result or {}).get("transcript") or st.session_state.transcript
    intent = (result or {}).get("intent") or {}
    behaviour = (result or {}).get("behaviour") or {}
    context = (result or {}).get("context") or {}
    entities = (result or {}).get("entities") or []
    with c1:
        render(st, f"""
        <div class="tv-panel">
          <div class="tv-kicker">Transcript</div>
          <div style="font-size:13px;line-height:1.6;margin-top:8px">{escape(str(transcript_show or '—'))}</div>
        </div>
        """)
    with c2:
        render(st, f"""
        <div class="tv-panel">
          <div class="tv-row"><span>Intent</span><span>{escape(intent_display_name(intent.get('intent','—')))}</span></div>
          <div class="tv-row"><span>Entities</span><span>{entity_lines(entities)}</span></div>
          <div class="tv-row"><span>Behaviour</span><span>{escape(str(behaviour.get('behaviour_level', 'LOW')))} · {escape(str(behaviour.get('disclaimer', '')))}</span></div>
          <div class="tv-row"><span>Observed signals</span><span>{escape(', '.join(behaviour.get('signals') or []) or 'None')}</span></div>
          <div class="tv-row"><span>Context</span><span>{escape(str(context.get('context_level', 'NORMAL')))}</span></div>
        </div>
        """)

    render(st, '<div class="tv-section">Decision explanation</div>')
    drivers = (result or {}).get("drivers") or ["No analysis yet"]
    items = "".join(f"<div class='tv-row'><span>•</span><span>{escape(str(d))}</span></div>" for d in drivers)
    render(st, f'<div class="tv-panel">{items}<div class="tv-muted" style="margin-top:8px">{escape(str((result or {}).get("action_detail") or ""))}</div></div>')

    if result and result.get("handshake_required"):
        render(st, '<div class="tv-section">Trust handshake</div>')
        render(st, f"""
        <div class="tv-alert">
          <div class="tv-kicker">Trust handshake required · demo / simulated</div>
          <div class="tv-label">Voice identity alone is not sufficient authorization for this action.</div>
          <div class="tv-muted" style="margin-top:6px">{escape(result.get('action_detail', ''))}</div>
          <div class="tv-muted">Verification request sent to registered device (simulated — this prototype does not contact a telecom or device service).</div>
        </div>
        """)
        h1, h2 = st.columns(2)
        with h1:
            if st.button("Confirm request", use_container_width=True):
                st.session_state.handshake_result = {
                    "status": "CONFIRMED",
                    "message": "Demo confirmation on a trusted channel.",
                }
                st.success("Demo handshake confirmed.")
        with h2:
            if st.button("Deny request", use_container_width=True):
                st.session_state.handshake_result = {
                    "status": "DENIED",
                    "message": "Demo denial on a trusted channel.",
                }
                st.error("Demo handshake denied. Sensitive action should remain blocked.")
        if st.session_state.handshake_result:
            st.info(
                f"{st.session_state.handshake_result['status']}: "
                f"{st.session_state.handshake_result['message']}"
            )

    with st.expander("Advanced diagnostics"):
        if anti:
            st.write({
                "model": anti.get("model"),
                "sample_rate": anti.get("sample_rate_used"),
                "window_count": anti.get("windows_used"),
                "cm_score": anti.get("cm_score"),
                "threshold": anti.get("threshold_used"),
                "decision_band": anti.get("decision_band"),
                "threshold_source": anti.get("threshold_source"),
                "audio_quality": quality,
                "speech_activity": quality.get("speech_activity_ratio"),
                "repeatability": anti.get("engine_stable"),
                "inference_status": anti.get("verdict"),
                "authenticity_score": anti.get("authenticity_score"),
            })
            st.caption(anti.get("score_note", ""))
        else:
            st.write("No countermeasure diagnostics. Live audio has not been scored, or the model is unavailable.")
        st.caption(
            "Prototype processing is local to the application environment. "
            "Voice/audio data should be treated as sensitive and retained only as long as necessary. "
            "No compliance certification is claimed."
        )


def render_demo():
    render_topbar()
    st.caption("Demo scenarios use the interaction engine on scripted dialogue. They are not live anti-spoof measurements.")
    a, b, c = st.columns(3)
    with a:
        run_a = st.button("Scenario A · unknown caller", use_container_width=True)
    with b:
        run_b = st.button("Scenario B · verified + dangerous request", use_container_width=True)
    with c:
        reset = st.button("Reset session", use_container_width=True)

    if reset:
        st.session_state.conversation_state = new_conversation_state()
        st.session_state.last_result = None
        st.session_state.last_analysis = None
        st.session_state.transcript = ""
        st.session_state.analysis_source = "Idle"
        st.session_state.handshake_result = None
        st.session_state.history = []
        st.rerun()

    slot = st.empty()
    if run_a:
        _run_scenario(SCENARIO_A, slot)
    if run_b:
        _run_scenario(SCENARIO_B, slot)

    render(st, '<div class="tv-section">Benign / contrast examples</div>')
    st.caption("These buttons run the live interaction pipeline on fixed sentences so judges can see false-positive behaviour.")
    for i, (kind, text) in enumerate(BENIGN_EXAMPLES):
        if st.button(f"{kind}: {text}", key=f"ex_{i}", use_container_width=True):
            analysed = analyse_interaction(
                transcript=text,
                voice_label="LIKELY_AUTHENTIC",
                identity_status="UNVERIFIED",
                source="LIVE / UPLOADED ANALYSIS",
                conversation_state=new_conversation_state(),
            )
            _apply_result(analysed, "LIVE / UPLOADED ANALYSIS")
            st.rerun()

    if st.session_state.get("last_result"):
        render(st, decision_block(st.session_state.last_result))


def _run_scenario(spec, slot):
    state = new_conversation_state()
    combined = []
    last = None
    for step in spec["steps"]:
        combined.append(step["text"])
        last = analyse_interaction(
            transcript=" ".join(combined),
            voice_label=step["voice"],
            identity_status=step["identity"],
            claimed_identity=step.get("claimed_identity"),
            conversation_state=state,
            source="DEMO SCENARIO",
        )
        state = last["conversation_state"]
        slot.markdown(
            f"**{spec['title']}** — {step['text']} → trust {last['trust_score']} · "
            f"{last['interaction_risk']} · {last['action']}"
        )
    if last:
        last = dict(last)
        last["transcript"] = " ".join(s["text"] for s in spec["steps"])
        _apply_result(last, "DEMO SCENARIO")
        st.session_state.last_analysis = None
        st.info(spec["note"])
        st.rerun()
