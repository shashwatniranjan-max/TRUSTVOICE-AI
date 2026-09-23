"""Live Monitor — prototype monitoring page."""

from __future__ import annotations

from html import escape

import streamlit as st

from ui.theme import COLORS


def render(html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def render_live_monitor():
    render("""
    <div class="tv-page">
      <div>
        <h1>LIVE MONITOR</h1>
        <p>Real-time voice security monitoring — prototype status.</p>
      </div>
    </div>
    """)

    col1, col2 = st.columns([1.4, 1], gap="medium")

    with col1:
        render("""
        <div class="tv-card">
          <div class="tv-card-title">Monitor status</div>
          <div class="tv-evidence-row">
            <span class="tv-evidence-label">Live call interception</span>
            <span class="tv-badge tv-badge-gray">Not implemented</span>
          </div>
          <div class="tv-evidence-row">
            <span class="tv-evidence-label">Analysis engine</span>
            <span class="tv-badge tv-badge-ok">● Ready</span>
          </div>
          <div class="tv-evidence-row" style="border-bottom:0">
            <span class="tv-evidence-label">Prototype mode</span>
            <span style="font-size:13px;color:#182235;font-weight:500">Upload / manual analysis</span>
          </div>
        </div>

        <div class="tv-card" style="margin-top:0">
          <div class="tv-card-title">About live monitoring</div>
          <div class="tv-muted" style="line-height:1.65">
            TRUSTVOICE does not intercept ordinary cellular calls. This prototype
            analyses audio files and manual transcripts submitted through the
            Analyze Audio page. A live monitoring integration would require explicit
            integration with a telephony provider and is outside the current scope.
          </div>
        </div>
        """)

        # Last analysis quick summary
        result = st.session_state.get("last_result")
        if result:
            trust = int(result.get("trust_score", 50))
            imp_risk = max(0, min(100, 100 - trust))
            band = result.get("interaction_risk", "LOW")
            badge_cls = "tv-badge-crit" if imp_risk >= 80 else ("tv-badge-warn" if imp_risk >= 55 else "tv-badge-ok")
            render(f"""
            <div class="tv-card" style="border-left:3px solid #2563D6">
              <div class="tv-card-title">Last analysis</div>
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
                <span style="font-size:28px;font-weight:700;color:#182235">{imp_risk}</span>
                <span style="font-size:15px;color:#64748B">/ 100</span>
                <span class="tv-badge {badge_cls}">{escape(band.replace('_', ' ').title())}</span>
              </div>
              <div class="tv-note">{escape(str(result.get('action_detail') or result.get('action') or ''))}</div>
            </div>
            """)

    with col2:
        render("""
        <div class="tv-card">
          <div class="tv-card-title">Analysis methods</div>
          <div class="tv-pipeline-item">
            <div class="tv-pipeline-num done">✓</div>
            <div class="tv-pipeline-label">File upload analysis</div>
          </div>
          <div class="tv-pipeline-item">
            <div class="tv-pipeline-num done">✓</div>
            <div class="tv-pipeline-label">Microphone recording</div>
          </div>
          <div class="tv-pipeline-item">
            <div class="tv-pipeline-num done">✓</div>
            <div class="tv-pipeline-label">Manual transcript</div>
          </div>
          <div class="tv-pipeline-item">
            <div class="tv-pipeline-num">—</div>
            <div class="tv-pipeline-label" style="color:#94A3B8">Live call integration</div>
          </div>
          <div class="tv-pipeline-item" style="border-bottom:0">
            <div class="tv-pipeline-num">—</div>
            <div class="tv-pipeline-label" style="color:#94A3B8">Real-time stream</div>
          </div>
        </div>
        """)

        if st.button("→ Go to Analyze Audio", use_container_width=True, type="primary", key="lm_goto_analyze"):
            st.session_state.ui_nav = "Analyze Audio"
            st.rerun()

    render("""<div class="tv-footer">TRUSTVOICE AI · does not intercept cellular calls · prototype only</div>""")
