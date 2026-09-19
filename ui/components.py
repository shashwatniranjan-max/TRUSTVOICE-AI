"""Small HTML fragments. Color is never the only signal."""

from html import escape

from ui.theme import COLORS, status_color


def render(st, html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def meter(value: int, color: str | None = None) -> str:
    width = max(2, min(100, int(value)))
    c = color or COLORS["accent"]
    return f'<div class="tv-bar"><i style="width:{width}%;background:{c}"></i></div>'


def decision_block(result: dict) -> str:
    score = int(result.get("trust_score") or 0)
    risk = result.get("interaction_risk") or "—"
    action = result.get("action") or "—"
    voice = result.get("voice_display") or "UNAVAILABLE"
    identity = result.get("identity_status") or "NOT_AVAILABLE"
    rc = status_color(risk)
    return f"""
    <div class="tv-panel">
      <div class="tv-kicker">Current decision</div>
      <div class="tv-value">{score} <span class="tv-muted">/ 100</span></div>
      {meter(score, rc)}
      <div class="tv-label" style="color:{rc}">{escape(str(risk))} RISK · {escape(str(action))}</div>
      <div class="tv-row"><span>Voice authenticity</span><span>{escape(str(voice))}</span></div>
      <div class="tv-row"><span>Identity</span><span>{escape(str(identity).replace('_', ' '))}</span></div>
      <div class="tv-muted" style="margin-top:8px">Dynamic Trust Score is a decision-support value, not a probability.</div>
    </div>
    """


def signal_rows(factors: dict) -> str:
    labels = [
        ("Voice Authenticity", "Voice Authenticity"),
        ("Speaker Identity", "Speaker Identity"),
        ("Intent Safety", "Intent Safety"),
        ("Behaviour Safety", "Behaviour Safety"),
        ("Context Safety", "Context Safety"),
    ]
    rows = []
    for title, key in labels:
        raw = factors.get(key, "—")
        if isinstance(raw, (int, float)):
            val = int(raw)
            bar = meter(val, COLORS["accent"] if val >= 70 else (COLORS["amber"] if val >= 40 else COLORS["red"]))
            right = f"{val}"
        else:
            bar = meter(0, COLORS["gray"])
            right = escape(str(raw))
        rows.append(
            f'<div class="tv-row"><span>{title}</span><span>{right}</span></div>{bar}'
        )
    return '<div class="tv-panel">' + "".join(rows) + "</div>"


def entity_lines(entities) -> str:
    if not entities:
        return "None"
    return "<br>".join(
        f"{escape(e.get('type','?'))} → {escape(str(e.get('value','')))}" for e in entities
    )


def waveform(envelope) -> str:
    bars = envelope or [16, 28, 22, 40, 18, 36, 24]
    html = "".join(f'<i style="height:{int(h)}px"></i>' for h in bars)
    return f'<div class="tv-wave">{html}</div>'
