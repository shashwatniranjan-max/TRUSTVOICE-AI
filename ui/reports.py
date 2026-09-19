"""Incident report generation."""

import json

import streamlit as st

from ui.components import render
from ui.console import render_topbar
from utils.reporting import REPORTLAB_AVAILABLE, build_incident_report, build_incident_report_pdf


def render_reports():
    render_topbar()
    render(st, '<div class="tv-section">Reports</div>')
    if st.button("Generate incident report", use_container_width=True):
        try:
            report = build_incident_report(st.session_state)
            st.session_state.incident_report = report
            if REPORTLAB_AVAILABLE:
                st.session_state.incident_report_pdf = build_incident_report_pdf(report)
                st.session_state.incident_report_filename = (
                    f"{report.get('report_id', 'trustvoice_incident_report')}.pdf"
                )
            else:
                st.session_state.incident_report_pdf = None
                st.warning("PDF generator unavailable. Install reportlab to enable PDF reports.")
        except Exception as exc:
            st.error(f"Report generation failed: {type(exc).__name__}: {exc}")

    rep = st.session_state.get("incident_report")
    if not rep:
        st.info("Run an analysis, then generate a report from the latest result.")
        return

    render(st, f"""
    <div class="tv-panel">
      <div class="tv-kicker">{rep.get('report_id','')}</div>
      <div class="tv-row"><span>Trust score</span><span>{rep.get('trust_score')}</span></div>
      <div class="tv-row"><span>Interaction risk</span><span>{rep.get('interaction_risk')}</span></div>
      <div class="tv-row"><span>Voice authenticity</span><span>{rep.get('voice_authenticity')}</span></div>
      <div class="tv-row"><span>Identity</span><span>{rep.get('identity_status')}</span></div>
      <div class="tv-row"><span>Action</span><span>{rep.get('recommended_action')}</span></div>
      <div class="tv-row"><span>Handshake</span><span>{'required' if rep.get('handshake_required') else 'not required'}</span></div>
      <div class="tv-muted" style="margin-top:8px">{rep.get('prototype_note','')}</div>
    </div>
    """)

    with st.expander("Technical JSON"):
        st.code(json.dumps(rep, indent=2, default=str), language="json")

    d1, d2 = st.columns(2)
    with d1:
        if st.session_state.get("incident_report_pdf"):
            st.download_button(
                "Download PDF",
                st.session_state.incident_report_pdf,
                st.session_state.get("incident_report_filename", "trustvoice_incident_report.pdf"),
                "application/pdf",
                use_container_width=True,
            )
    with d2:
        st.download_button(
            "Download JSON",
            json.dumps(rep, indent=2, default=str),
            "trustvoice_incident_report.json",
            "application/json",
            use_container_width=True,
        )
