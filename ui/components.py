"""Small HTML fragments. Color is never the only signal."""

import re
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


def analysis_mode(source: str | None) -> str:
    s = (source or "Idle").upper()
    if s.startswith("DEMO"):
        return "DEMO"
    if s.startswith("LIVE"):
        return "LIVE"
    return "IDLE"


def decision_block(result: dict) -> str:
    score = int(result.get("trust_score") or 0)
    risk = result.get("interaction_risk") or "—"
    action = result.get("action") or "—"
    source = result.get("source") or "—"
    rc = status_color(risk)
    return f"""
    <div class="tv-decision">
      <div>
        <div class="tv-section" style="margin-top:0">Trust score</div>
        <div class="tv-value">{score} <span class="tv-muted">/ 100</span></div>
        {meter(score, rc)}
      </div>
      <div>
        <div class="tv-decision-risk" style="color:{rc}">{escape(str(risk))}</div>
        <div class="tv-decision-action">{escape(str(action))}</div>
        <div class="tv-note">Mode {escape(analysis_mode(str(source)))}. Decision support, not a probability. Voice authenticity is not identity or authorization.</div>
      </div>
    </div>
    """


def idle_decision() -> str:
    return """
    <div class="tv-decision">
      <div>
        <div class="tv-section" style="margin-top:0">Trust score</div>
        <div class="tv-value tv-muted">—</div>
      </div>
      <div>
        <div class="tv-decision-risk">Awaiting analysis</div>
        <div class="tv-decision-action">Upload audio for anti-spoof and local ASR, or type a transcript.</div>
      </div>
    </div>
    """


def signal_rows(factors: dict | None, identity_status: str | None = None) -> str:
    labels = [
        ("Voice Authenticity", "Voice Authenticity"),
        ("Speaker Identity", "Speaker Identity"),
        ("Intent", "Intent Safety"),
        ("Behaviour", "Behaviour Safety"),
        ("Context", "Context Safety"),
    ]
    if not factors:
        cells = "".join(
            f'<div class="tv-signal"><div class="name">{title}</div>'
            f'<div class="val tv-muted">—</div></div>'
            for title, _ in labels
        )
        return f'<div class="tv-signals">{cells}</div>'

    cells = []
    for title, key in labels:
        raw = factors.get(key, "—")
        if isinstance(raw, (int, float)):
            val = int(raw)
            color = COLORS["accent"] if val >= 70 else (COLORS["amber"] if val >= 40 else COLORS["red"])
            extra = ""
            if title == "Speaker Identity" and identity_status:
                extra = f' · {escape(str(identity_status).replace("_", " "))}'
            cells.append(
                f'<div class="tv-signal"><div class="name">{title}</div>'
                f'<div class="val">{val}{extra}</div>{meter(val, color)}</div>'
            )
        else:
            cells.append(
                f'<div class="tv-signal"><div class="name">{title}</div>'
                f'<div class="val">{escape(str(raw))}</div>{meter(0, COLORS["gray"])}</div>'
            )
    return f'<div class="tv-signals">{"".join(cells)}</div>'


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


def utterances_from_transcript(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def conversation_timeline(utterances: list[str], speaker: str = "Caller") -> str:
    if not utterances:
        return '<div class="tv-muted">No conversation yet.</div>'
    rows = []
    for i, line in enumerate(utterances, start=1):
        rows.append(
            f'<div class="tv-utt"><div class="who"><span class="step">{i:02d}</span>'
            f'{escape(speaker)}</div><div class="said">“{escape(line)}”</div></div>'
        )
    return f'<div class="tv-timeline">{"".join(rows)}</div>'


def why_this_risk(drivers: list | None) -> str:
    items = drivers or ["No analysis yet"]
    lis = "".join(f"<li>{escape(str(d))}</li>" for d in items)
    return f'<div class="tv-why"><ul>{lis}</ul></div>'


def handshake_block(detail: str) -> str:
    return f"""
    <div class="tv-handshake">
      <h3>Critical intervention</h3>
      <div class="tv-label" style="margin-top:6px">Independent verification required</div>
      <p class="tv-muted" style="margin:6px 0">Caller identity alone is not sufficient authorization.</p>
      <div class="tv-section" style="margin-top:12px">Trust handshake</div>
      <p class="tv-muted">Did you initiate this request?</p>
      <p class="tv-note">{escape(detail or "")} Verification is simulated in this prototype — it does not contact a phone, bank, or device service.</p>
    </div>
    """


def score_trail(scores: list[int]) -> str:
    if not scores:
        return ""
    joined = " <span>→</span> ".join(str(int(s)) for s in scores)
    return (
        f'<div class="tv-section">Illustrative scenario progression</div>'
        f'<div class="tv-trail">{joined}</div>'
        f'<div class="tv-note">Not a measured model accuracy or probability.</div>'
    )


def scenario_choice(letter: str, title: str, subtitle: str, active: bool) -> str:
    cls = "tv-choice active" if active else "tv-choice"
    return f"""
    <div class="{cls}">
      <div class="id">[{escape(letter)}]</div>
      <div class="title">{escape(title)}</div>
      <div class="sub">{escape(subtitle)}</div>
    </div>
    """
