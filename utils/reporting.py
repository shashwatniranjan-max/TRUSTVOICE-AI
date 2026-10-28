"""Incident report JSON + PDF. Prototype estimates are not labelled as probabilities."""

from __future__ import annotations

import io
from datetime import datetime
from html import escape

from models.intent import describe_intent
from risk.config import FUSION_WEIGHTS

try:
    from reportlab.lib import colors as pdf_colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def build_incident_report(session: dict) -> dict:
    result = session.get("last_result") or {}
    last_analysis = session.get("last_analysis") or {}
    conv_state = session.get("conversation_state") or result.get("conversation_state") or {}

    return {
        "report_id": f"TV-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": session.get("analysis_source", result.get("source", "LIVE")),
        "scenario": session.get("scenario", "Conversation analysis"),
        "trust_score": result.get("trust_score", session.get("score")),
        "preliminary_score": result.get("fused_uncapped"),
        "interaction_risk": result.get("interaction_risk"),
        "voice_authenticity": result.get("voice_display"),
        "identity_status": result.get("identity_status"),
        "intent": result.get("intent"),
        "entities": result.get("entities"),
        "categorized_entities": result.get("categorized_entities"),
        "behaviour_signals": result.get("behaviour_signals"),
        "context_signals": result.get("context_signals"),
        "decision_drivers": result.get("drivers"),
        "recommended_action": result.get("action"),
        "action_detail": result.get("action_detail"),
        "handshake_required": result.get("handshake_required"),
        "handshake": session.get("handshake_result"),
        "audio_quality": last_analysis.get("quality_gate"),
        "model": (last_analysis.get("anti_spoof") or {}).get("model"),
        "threshold_information": {
            "threshold": session.get("bona_threshold"),
            "decision_band": session.get("decision_band"),
            "source": session.get("threshold_source"),
        },
        "evaluation": session.get("accuracy_eval") if (session.get("accuracy_eval") or {}).get("n") else None,
        "risk_factors": result.get("factor_display") or session.get("factors"),
        "fusion_weights": FUSION_WEIGHTS,
        "fusion_audit": result.get("fusion_audit"),
        "signals_summary": result.get("signals_summary"),
        "diagnostics": result.get("diagnostics"),
        "turn_history": conv_state.get("turn_history", []),
        "transcript": result.get("transcript") or session.get("transcript"),
        "last_analysis": last_analysis,
        "prototype_note": (
            "Dynamic Trust Score is a prototype decision-support value, not a probability. "
            "Countermeasure scores are uncalibrated unless the evaluation lab has fitted a threshold. "
            "This report is not a certified fraud verdict."
        ),
    }


def build_incident_report_pdf(rep: dict) -> bytes:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("PDF generation requires reportlab. Install it with: pip install reportlab")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=f"TRUSTVOICE AI Incident Report {rep.get('report_id', '')}",
        author="TRUSTVOICE AI",
    )
    ink = pdf_colors.HexColor("#12151a")
    muted = pdf_colors.HexColor("#5c6570")
    line = pdf_colors.HexColor("#d0d5db")
    wash = pdf_colors.HexColor("#f3f5f7")
    accent = pdf_colors.HexColor("#2f6fed")
    danger = pdf_colors.HexColor("#dc2626")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TVTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                                 fontSize=16, leading=20, textColor=ink, spaceAfter=4)
    sub_style = ParagraphStyle("TVSub", parent=styles["Normal"], fontSize=8.5, leading=12,
                               textColor=muted, spaceAfter=10)
    section_style = ParagraphStyle("TVSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
                                   fontSize=10, leading=13, textColor=ink, spaceBefore=10, spaceAfter=6)
    body_style = ParagraphStyle("TVBody", parent=styles["BodyText"], fontSize=8.7, leading=13,
                                textColor=ink, spaceAfter=5)
    small_style = ParagraphStyle("TVSmall", parent=styles["BodyText"], fontSize=7.5, leading=10.5,
                                 textColor=muted)
    white_small = ParagraphStyle("TVWhiteSmall", parent=small_style, textColor=pdf_colors.white)
    white_body = ParagraphStyle("TVWhiteBody", parent=body_style, textColor=pdf_colors.white)
    center_small = ParagraphStyle("TVCenterSmall", parent=small_style, alignment=TA_CENTER)

    def safe(value):
        return escape(str(value if value is not None else "—"))

    score = int(rep.get("trust_score", 0) or 0)
    prelim = rep.get("preliminary_score")
    score_label = f"{score} / 100"
    if prelim is not None and int(prelim) != score:
        score_label += f" (Prelim: {prelim})"

    story = []
    header = Table([[
        Paragraph("TRUSTVOICE AI", ParagraphStyle("Brand", parent=title_style,
                                                  textColor=pdf_colors.white, fontSize=15)),
        Paragraph("CONVERSATION SECURITY & RISK FUSION REPORT", ParagraphStyle("HeaderRight", parent=white_small,
                                                                               alignment=2, fontSize=8.5)),
    ]], colWidths=[105 * mm, 70 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ink),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
        ("LINEBELOW", (0, -1), (-1, -1), 2, accent),
    ]))
    story += [header, Spacer(1, 7)]
    story.append(Paragraph(
        f"Report ID: <b>{safe(rep.get('report_id'))}</b> &nbsp;&nbsp; Generated: {safe(rep.get('generated_at'))} "
        f"&nbsp;&nbsp; Source: {safe(rep.get('source'))}",
        sub_style,
    ))

    summary = Table([
        [Paragraph("TRUST SCORE", center_small), Paragraph("INTERACTION RISK", center_small),
         Paragraph("VOICE AUTHENTICITY", center_small), Paragraph("RECOMMENDED ACTION", center_small)],
        [Paragraph(score_label, ParagraphStyle("ss", parent=body_style, alignment=TA_CENTER,
                                              fontSize=13, fontName="Helvetica-Bold")),
         Paragraph(safe(rep.get("interaction_risk")), ParagraphStyle("sr", parent=body_style,
                                                                     alignment=TA_CENTER, fontName="Helvetica-Bold")),
         Paragraph(safe(rep.get("voice_authenticity")), ParagraphStyle("sv", parent=body_style,
                                                                       alignment=TA_CENTER, fontName="Helvetica-Bold")),
         Paragraph(safe(rep.get("recommended_action")), ParagraphStyle("sa", parent=body_style,
                                                                       alignment=TA_CENTER, fontSize=8))],
    ], colWidths=[43 * mm, 43 * mm, 44 * mm, 44 * mm])
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), wash),
        ("BOX", (0, 0), (-1, -1), 0.6, line),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, line),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [summary, Spacer(1, 6)]

    # 5-Dimension Safety Breakdown
    story.append(Paragraph("FIVE-DIMENSION SAFETY BREAKDOWN & MATHEMATICAL FUSION", section_style))
    fusion = rep.get("fusion_audit") or {}
    dims = fusion.get("dimensions") or {}
    factor_rows = [["Dimension", "Weight", "Raw Score", "Contribution", "Safety Rating"]]

    labels = [
        ("Voice Authenticity", "voice_authenticity"),
        ("Speaker Identity", "speaker_identity"),
        ("Intent Safety", "intent_safety"),
        ("Behaviour Safety", "behaviour_safety"),
        ("Context Safety", "context_safety"),
    ]
    factors = rep.get("risk_factors") or {}
    for label, key in labels:
        d_info = dims.get(key) or {}
        raw = d_info.get("raw_score", factors.get(label, factors.get(key, "—")))
        w_str = d_info.get("weight_pct", f"{FUSION_WEIGHTS.get(key, 0):.0%}")
        pts = f"{d_info.get('weighted_points', '—')} pts" if "weighted_points" in d_info else "—"
        rating = d_info.get("rating", "Standard")
        factor_rows.append([label, w_str, str(raw), pts, rating])

    # Formula row
    if fusion.get("preliminary_score") is not None:
        factor_rows.append(["Preliminary Weighted Score", "100%", str(fusion.get("preliminary_score")), f"{fusion.get('preliminary_exact', '')} pts", "Before Safety Gates"])
        if fusion.get("delta"):
            factor_rows.append(["Hard Safety Gate Adjustments", "—", f"{fusion.get('delta'):+d} pts", "—", "Score Capped by Policy"])
        factor_rows.append(["Final Trust Score", "—", str(score), "—", safe(rep.get("interaction_risk"))])

    table = Table(factor_rows, colWidths=[55 * mm, 20 * mm, 28 * mm, 32 * mm, 39 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ink),
        ("TEXTCOLOR", (0, 0), (-1, 0), pdf_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, line),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [pdf_colors.white, wash]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

    # Active Safety Gates
    triggered_gates = fusion.get("gates_triggered") or []
    if triggered_gates:
        story.append(Spacer(1, 4))
        story.append(Paragraph("ACTIVE HARD SAFETY GATES", section_style))
        gate_rows = [["Gate Identifier", "Cap", "Forced Risk", "Condition & Rationale"]]
        for g in triggered_gates:
            gate_rows.append([
                g.get("name", g.get("id")),
                f"≤ {g.get('cap')}",
                str(g.get("forced_risk") or "—"),
                f"{g.get('rationale')} ({g.get('condition_desc')})",
            ])
        gate_table = Table(gate_rows, colWidths=[50 * mm, 16 * mm, 26 * mm, 82 * mm], repeatRows=1)
        gate_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), danger),
            ("TEXTCOLOR", (0, 0), (-1, 0), pdf_colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.4, line),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [pdf_colors.white, wash]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(gate_table)

    story.append(Paragraph("INTELLIGENCE: IDENTITY, INTENT & REDACTED ENTITIES", section_style))
    story.append(Paragraph(f"Identity status: <b>{safe(rep.get('identity_status'))}</b>", body_style))
    story.append(Paragraph(f"Intent classification: {safe(describe_intent(rep.get('intent')))}", body_style))

    # Entities with redaction
    ents = rep.get("entities") or []
    if ents:
        ent_strs = []
        for e in ents:
            redacted = e.get("redacted_value", e.get("value"))
            ent_strs.append(f"<b>{e.get('type')}</b>: {redacted} [{e.get('risk_relevance', 'INFO')}]")
        story.append(Paragraph("Extracted entities (masked): " + ", ".join(ent_strs), body_style))
    else:
        story.append(Paragraph("Entities: None detected", body_style))

    story.append(Paragraph(
        "Behaviour signals: " + (", ".join(rep.get("behaviour_signals") or []) or "None"),
        body_style,
    ))
    story.append(Paragraph(
        "Context signals: " + (", ".join(rep.get("context_signals") or []) or "None"),
        body_style,
    ))

    if rep.get("decision_drivers"):
        story.append(Paragraph("DECISION DRIVERS", section_style))
        for item in rep["decision_drivers"]:
            story.append(Paragraph(f"&bull; {safe(item)}", body_style))

    story.append(Paragraph("RECOMMENDED ACTION & INTERVENTION", section_style))
    action_table = Table([[Paragraph(
        f"<b>{safe(rep.get('recommended_action'))}</b><br/>{safe(rep.get('action_detail'))}",
        ParagraphStyle("Action", parent=white_body, fontSize=9, leading=13),
    )]], colWidths=[174 * mm])
    action_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ink),
        ("BOX", (0, 0), (-1, -1), 1, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(action_table)

    hs = rep.get("handshake")
    story.append(Paragraph("TRUST HANDSHAKE VERIFICATION", section_style))
    if rep.get("handshake_required"):
        story.append(Paragraph(
            "<b>Intervention Required</b>: Voice biometric identity alone is not sufficient authorization for this action.",
            body_style,
        ))
    if hs:
        status = safe(hs.get("status")) if isinstance(hs, dict) else safe(hs)
        msg = safe(hs.get("message", "")) if isinstance(hs, dict) else ""
        story.append(Paragraph(f"Status: <b>{status}</b> — {msg} (demo / simulated unless integrated).", body_style))
    else:
        story.append(Paragraph("No handshake recorded for this session.", body_style))

    if rep.get("transcript"):
        story.append(Paragraph("CONVERSATION TRANSCRIPT", section_style))
        t = Table([[Paragraph(safe(rep["transcript"]), white_body)]], colWidths=[174 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ink),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(t)

    # Technical diagnostics
    story.append(Paragraph("TECHNICAL DIAGNOSTICS & SYSTEM AUDIT", section_style))
    technical = [["Subsystem / Field", "Status / Measurement"]]
    diag = rep.get("diagnostics") or {}
    stages = diag.get("pipeline_stages") or {}
    for stg, sval in stages.items():
        technical.append([stg, safe(sval)])

    quality = rep.get("audio_quality") or {}
    if quality:
        technical.append(["Audio Quality Assessment", safe(quality.get("quality"))])
        if quality.get("issues"):
            technical.append(["Acoustic Quality Gate Issues", safe("; ".join(quality["issues"]))])

    last = rep.get("last_analysis") if isinstance(rep.get("last_analysis"), dict) else None
    if last:
        for key in ["file", "duration", "sample_rate"]:
            if last.get(key) is not None:
                technical.append([key.replace("_", " ").title(), safe(last.get(key))])
        anti = last.get("anti_spoof") or {}
        for key in ["verdict", "authenticity_score", "cm_score", "windows_used", "engine_stable"]:
            if key in anti:
                technical.append([key.replace("_", " ").title(), safe(anti.get(key))])

    tech_table = Table(technical, colWidths=[65 * mm, 109 * mm], repeatRows=1)
    tech_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ink),
        ("TEXTCOLOR", (0, 0), (-1, 0), pdf_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.4, line),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [pdf_colors.white, wash]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tech_table)

    story.append(Spacer(1, 8))
    story.append(Paragraph(safe(rep.get("prototype_note")), small_style))
    story.append(Paragraph(
        "TRUSTVOICE AI prototype architecture. Processing is local to the runtime environment. "
        "Sensitive entity fields have been redacted in accordance with PII protection standards.",
        small_style,
    ))

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(accent)
        canvas.setLineWidth(0.6)
        canvas.line(15 * mm, 10 * mm, 195 * mm, 10 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(muted)
        canvas.drawString(15 * mm, 6 * mm, "TRUSTVOICE AI · Enterprise Risk Intelligence")
        canvas.drawRightString(195 * mm, 6 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
