"""Main conversation security console."""

from html import escape

import streamlit as st

from demo.scenarios import BENIGN_EXAMPLES, IDENTITY_HELP, SCENARIO_A, SCENARIO_B, SCENARIO_C
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
    source = st.session_state.get("analysis_source") or "Idle"
    if source.startswith("DEMO"):
        st.info("DEMO SCENARIO — scripted transcript and illustrative voice labels. Not a live AASIST verdict.")
    elif source.startswith("LIVE"):
        st.info("LIVE / MANUAL ANALYSIS — anti-spoofing runs on uploaded/microphone audio when provided. Transcript is typed (ASR is not bundled).")
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
                    source="LIVE / MANUAL ANALYSIS",
                    voice_evidence="model" if auth_score is not None else "unavailable",
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
          <div class="tv-kicker">Simulated Trust Handshake</div>
          <div class="tv-label">Voice identity alone is not sufficient authorization for this action.</div>
          <div class="tv-muted" style="margin-top:6px">{escape(result.get('action_detail', ''))}</div>
          <div class="tv-muted">Verification request sent to registered device — simulated. This prototype does not contact a phone, bank, telecom provider, or device service. YES continues, NO stops, no response keeps the action blocked.</div>
        </div>
        """)
        h1, h2, h3 = st.columns(3)
        with h1:
            if st.button("Confirm request (simulated YES)", use_container_width=True):
                st.session_state.handshake_result = {
                    "status": "CONFIRMED",
                    "message": "Simulated confirmation on a trusted channel. Sensitive action may continue.",
                }
        with h2:
            if st.button("Deny request (simulated NO)", use_container_width=True):
                st.session_state.handshake_result = {
                    "status": "DENIED",
                    "message": "Simulated denial. Sensitive action remains blocked.",
                }
        with h3:
            if st.button("No response (remain blocked)", use_container_width=True):
                st.session_state.handshake_result = {
                    "status": "NO_RESPONSE",
                    "message": "No independent confirmation. Sensitive action remains blocked pending manual verification.",
                }
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
    st.caption(
        "Each button below is a different scripted call. Voice labels are illustrative — "
        "not live AASIST output. Reset clears this page and the shared analysis session."
    )
    a, b, c, d = st.columns(4)
    with a:
        run_a = st.button("Run Scenario A", key="demo_run_a", use_container_width=True)
    with b:
        run_b = st.button("Run Scenario B", key="demo_run_b", use_container_width=True)
    with c:
        run_c = st.button("Run Scenario C", key="demo_run_c", use_container_width=True)
    with d:
        reset = st.button("Reset session", key="demo_reset", use_container_width=True)

    if reset:
        _reset_demo_session()
        st.rerun()

    if run_a:
        _run_scenario(SCENARIO_A)
    elif run_b:
        _run_scenario(SCENARIO_B)
    elif run_c:
        _run_scenario(SCENARIO_C)

    selected = (st.session_state.get("demo_view") or {}).get("id")
    p1, p2, p3 = st.columns(3)
    with p1:
        _scenario_script_card(SCENARIO_A, selected == "A")
    with p2:
        _scenario_script_card(SCENARIO_B, selected == "B")
    with p3:
        _scenario_script_card(SCENARIO_C, selected == "C")

    demo = st.session_state.get("demo_view")
    edge = st.session_state.get("edge_case_view")
    if demo:
        _render_demo_progression(demo)
    elif edge:
        _render_edge_case_result(edge)
    else:
        render(st, """
        <div class="tv-panel">
          <div class="tv-kicker">No demo running</div>
          <div class="tv-muted">Click Run Scenario A, B, or C. The conversation for that script only will appear here. Console uploads are not shown on this page.</div>
        </div>
        """)

    edge_open = bool(st.session_state.get("edge_case_view"))
    with st.expander("Additional edge-case tests (not part of A / B / C)", expanded=edge_open):
        st.caption(
            "Each click scores that one sentence and shows the result in the panel above. "
            "These are not the scripts for Scenarios A–C."
        )
        for i, (kind, text) in enumerate(BENIGN_EXAMPLES):
            if st.button(f"{kind}: {text}", key=f"ex_{i}", use_container_width=True):
                analysed = analyse_interaction(
                    transcript=text,
                    voice_label="UNAVAILABLE" if kind == "SPOOF-NOTE" else "LIKELY_AUTHENTIC",
                    identity_status="UNVERIFIED",
                    source="LIVE / MANUAL ANALYSIS",
                    voice_evidence="illustrative",
                    conversation_state=new_conversation_state(),
                )
                st.session_state.demo_view = None
                st.session_state.edge_case_view = {
                    "kind": kind,
                    "text": text,
                    "result": analysed,
                }
                _apply_result(analysed, "LIVE / MANUAL ANALYSIS")
                st.rerun()


def _scenario_script_card(spec: dict, active: bool):
    lines = "".join(
        f'<div class="tv-muted">{i}. {escape(step["text"])}</div>'
        for i, step in enumerate(spec["steps"], start=1)
    )
    border = "border-color:#3d8bfd" if active else ""
    kicker = "SELECTED" if active else f"SCENARIO {spec['id']}"
    render(st, f"""
    <div class="tv-panel" style="{border}">
      <div class="tv-kicker">{kicker}</div>
      <div class="tv-label">{escape(spec["title"])}</div>
      <div class="tv-muted" style="margin:6px 0 8px">{escape(spec["note"])}</div>
      {lines}
    </div>
    """)


def _reset_demo_session():
    st.session_state.conversation_state = new_conversation_state()
    st.session_state.last_result = None
    st.session_state.last_analysis = None
    st.session_state.transcript = ""
    st.session_state.analysis_source = "Idle"
    st.session_state.handshake_result = None
    st.session_state.history = []
    st.session_state.demo_view = None
    st.session_state.edge_case_view = None
    st.session_state.analysis_done = False
    st.session_state.intent_prediction = None
    st.session_state.risk_explanation = []
    st.session_state.score = None
    st.session_state.scenario = "Awaiting analysis"


def _render_edge_case_result(edge: dict):
    result = edge.get("result") or {}
    render(st, f"""
    <div class="tv-section">Edge-case test result</div>
    <div class="tv-panel">
      <div class="tv-kicker">{escape(str(edge.get("kind", "TEST")))}</div>
      <div class="tv-label">{escape(str(edge.get("text", "")))}</div>
      <div class="tv-muted" style="margin-top:8px">
        This is a single-sentence check, not Scenario A/B/C.
        Intent: {escape(str(((result.get("intent") or {}).get("intent") or "—")).replace("_", " "))}
      </div>
    </div>
    """)
    render(st, decision_block(result))


def _render_demo_progression(demo: dict):
    title = escape(str(demo.get("title", "Demo scenario")))
    note = escape(str(demo.get("note", "")))
    rows = []
    for i, turn in enumerate(demo.get("turns") or [], start=1):
        rows.append(
            f'<div class="tv-row"><span>Turn {i}</span>'
            f'<span>{escape(str(turn["text"]))}</span></div>'
            f'<div class="tv-muted" style="padding:0 0 8px 0">'
            f'Trust {int(turn["trust_score"])} / 100 · {escape(str(turn["risk"]))} · '
            f'{escape(str(turn["action"]))}</div>'
        )
    render(st, f"""
    <div class="tv-section">Running now · Scenario {escape(str(demo.get("id", "")))}</div>
    <div class="tv-panel">
      <div class="tv-kicker">DEMO SCENARIO · {escape(str(demo.get("id", "")))} only</div>
      <div class="tv-label">{title}</div>
      <div class="tv-muted" style="margin:6px 0 12px">{note}</div>
      {"".join(rows)}
    </div>
    """)
    if st.session_state.get("last_result"):
        render(st, '<div class="tv-section">Final decision for this scenario</div>')
        render(st, decision_block(st.session_state.last_result))


def _run_scenario(spec):
    _reset_demo_session()
    state = new_conversation_state()
    combined = []
    last = None
    turns = []
    for step in spec["steps"]:
        combined.append(step["text"])
        last = analyse_interaction(
            transcript=" ".join(combined),
            voice_label=step["voice"],
            identity_status=step["identity"],
            claimed_identity=step.get("claimed_identity"),
            conversation_state=state,
            source="DEMO SCENARIO",
            voice_evidence="illustrative",
        )
        state = last["conversation_state"]
        turns.append({
            "text": step["text"],
            "trust_score": last["trust_score"],
            "risk": last["interaction_risk"],
            "action": last["action"],
        })
    if last:
        last = dict(last)
        last["transcript"] = " ".join(s["text"] for s in spec["steps"])
        st.session_state.demo_view = {
            "id": spec.get("id"),
            "title": spec.get("title"),
            "note": spec.get("note"),
            "turns": turns,
        }
        _apply_result(last, "DEMO SCENARIO")
        st.session_state.last_analysis = None
        st.session_state.edge_case_view = None
        st.rerun()
