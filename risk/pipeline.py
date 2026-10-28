"""End-to-end interaction analysis used by the UI and tests."""

from __future__ import annotations

import re

from models.entities import categorized_entity_inventory, extract_entities
from models.intent import classify_intent, intent_safety_score
from risk.behaviour import analyse_behaviour
from risk.config import FUSION_WEIGHTS, FUSION_WEIGHTS_NOTE
from risk.context import analyse_context
from risk.fusion import (
    apply_safety_gates,
    authenticity_display,
    compute_fused_score,
    evaluate_safety_gates_detailed,
    explain_fusion_calculation,
    identity_safety_from_status,
    recommended_action,
    trust_band,
    voice_safety_from_label,
)
from utils.state import new_conversation_state, update_conversation_state

SENSITIVE_INTENTS = {
    "credential_request",
    "financial_request",
    "sensitive_data_request",
    "personal_information_request",
}

PRESSURE_ONLY = re.compile(
    r"\b(immediately|right now|do it|don't tell anyone|blocked|hurry)\b",
    re.I,
)


def compile_signals_inventory(
    voice_label: str,
    authenticity_score: int | None,
    identity_status: str,
    intent: dict,
    behaviour: dict,
    context: dict,
    entities: list[dict],
    components: dict,
    caps: list[str],
) -> dict:
    """Build a comprehensive, categorized inventory of all real signals evaluated in this turn."""
    signals_list = []

    # 1. Voice Signals
    if voice_label == "LIKELY_SPOOF":
        signals_list.append({
            "category": "Voice Authenticity",
            "name": "Synthetic Speech Artifacts Detected",
            "status": "ACTIVE_THREAT",
            "severity": "CRITICAL",
            "dimension": "Voice Authenticity",
            "evidence": f"AASIST countermeasure score {authenticity_score if authenticity_score is not None else 'low'}/100 indicative of synthetic/cloned speech",
            "impact": "Suppresses Voice Authenticity dimension to 18 pts; triggers deepfake safety gates if paired with sensitive requests",
        })
    elif voice_label in ("INCONCLUSIVE", "INCONCLUSIVE_QUALITY"):
        signals_list.append({
            "category": "Voice Authenticity",
            "name": "Acoustic Authenticity Inconclusive",
            "status": "UNCERTAIN",
            "severity": "INFORMATIONAL",
            "dimension": "Voice Authenticity",
            "evidence": "Audio quality or acoustic variance does not permit definitive classification; not treated as malicious",
            "impact": "Maintains neutral score (74 pts); does not penalize innocent conversation",
        })
    elif voice_label == "LIKELY_AUTHENTIC":
        signals_list.append({
            "category": "Voice Authenticity",
            "name": "Organic Human Voice Verified",
            "status": "BENIGN",
            "severity": "INFORMATIONAL",
            "dimension": "Voice Authenticity",
            "evidence": f"AASIST countermeasure score {authenticity_score if authenticity_score is not None else 'high'}/100 confirms natural speech spectral distribution",
            "impact": "Contributes full positive weight (up to 96 pts) to Trust Score",
        })
    else:
        signals_list.append({
            "category": "Voice Authenticity",
            "name": "Voice Authenticity Unavailable",
            "status": "NOT_AVAILABLE",
            "severity": "INFORMATIONAL",
            "dimension": "Voice Authenticity",
            "evidence": "No raw audio was provided for countermeasure inference",
            "impact": "Defaults to baseline score (72 pts)",
        })

    # 2. Identity Signals
    if identity_status == "MISMATCH":
        signals_list.append({
            "category": "Speaker Identity",
            "name": "Biometric Voiceprint Mismatch",
            "status": "ACTIVE_THREAT",
            "severity": "CRITICAL",
            "dimension": "Speaker Identity",
            "evidence": "Extracted speaker embedding distance exceeds threshold from enrolled voice profile",
            "impact": "Drops identity safety to 12 pts; activates hard impersonation gate",
        })
    elif identity_status == "UNVERIFIED":
        signals_list.append({
            "category": "Speaker Identity",
            "name": "Unverified Caller Identity",
            "status": "UNVERIFIED",
            "severity": "ELEVATED",
            "dimension": "Speaker Identity",
            "evidence": "Caller is not enrolled in the trusted speaker gallery; identity cannot be confirmed",
            "impact": "Restricts identity safety to 72 pts; acts as compounding factor in safety gates",
        })
    elif identity_status == "VERIFIED":
        signals_list.append({
            "category": "Speaker Identity",
            "name": "Biometric Voice Identity Confirmed",
            "status": "BENIGN",
            "severity": "INFORMATIONAL",
            "dimension": "Speaker Identity",
            "evidence": "Cosine similarity with enrolled speaker profile exceeds verification threshold",
            "impact": "Provides 92 pts in identity dimension (note: identity alone is not authorization)",
        })

    # 3. Intent Signals
    intent_name = intent.get("intent", "unknown")
    if intent_name in SENSITIVE_INTENTS:
        signals_list.append({
            "category": "Intent Safety",
            "name": f"High-Sensitivity Request: {intent_name.replace('_', ' ').title()}",
            "status": "ACTIVE_THREAT",
            "severity": "CRITICAL" if intent_name in ("credential_request", "financial_request") else "HIGH",
            "dimension": "Intent Safety",
            "evidence": f"Classifier predicted '{intent_name}' with {intent.get('confidence', 0)}% confidence; riskiest phrase: \"{intent.get('riskiest_utterance', '')}\"",
            "impact": "Significantly penalizes Intent Safety dimension; unlocks hard safety caps",
        })
    elif intent.get("override"):
        signals_list.append({
            "category": "Intent Safety",
            "name": "Linguistic Guard / False Positive Suppression",
            "status": "BENIGN",
            "severity": "INFORMATIONAL",
            "dimension": "Intent Safety",
            "evidence": intent["override"],
            "impact": "Prevents benign discussion, security awareness, or past reports from being falsely flagged as an attack",
        })

    # 4. Behaviour Signals
    indicators = behaviour.get("indicators") or []
    for ind in indicators:
        if ind["detected"]:
            signals_list.append({
                "category": "Behavioural Threat",
                "name": ind["label"],
                "status": "ACTIVE_THREAT",
                "severity": ind["severity"],
                "dimension": "Behavioural Safety",
                "evidence": f"Detected matching phrase: \"{ind.get('evidence', '')}\"",
                "impact": f"Deducts {ind.get('penalty', 0)} pts from Behavioural Safety; contributes to coercive pressure combination",
            })

    # 5. Context Signals
    for sig in context.get("signals") or []:
        sig_title = sig.replace("_", " ").title()
        signals_list.append({
            "category": "Context Anomaly",
            "name": sig_title,
            "status": "ACTIVE_THREAT",
            "severity": "HIGH",
            "dimension": "Contextual Safety",
            "evidence": f"Contextual violation: {sig}",
            "impact": "Reduces Context Safety score; indicates protocol or channel anomaly",
        })

    # Metrics
    active_threats = [s for s in signals_list if s["status"] == "ACTIVE_THREAT"]
    high_sev = [s for s in signals_list if s["severity"] in ("CRITICAL", "HIGH")]
    uncertain = [s for s in signals_list if s["status"] in ("UNCERTAIN", "NOT_AVAILABLE")]
    affected_dims = [k for k, v in components.items() if v < 80]

    return {
        "inventory": signals_list,
        "total_signals_recorded": len(signals_list),
        "active_threats_count": len(active_threats),
        "high_severity_count": len(high_sev),
        "uncertain_signals_count": len(uncertain),
        "dimensions_affected_count": len(affected_dims),
        "dimensions_affected": affected_dims,
    }


def analyse_interaction(
    transcript: str = "",
    voice_label: str = "UNAVAILABLE",
    identity_status: str = "NOT_AVAILABLE",
    authenticity_score: int | None = None,
    conversation_state: dict | None = None,
    claimed_identity: str | None = None,
    source: str = "LIVE",
    voice_evidence: str = "unavailable",
) -> dict:
    """
    Analyse one utterance (and accumulated conversation state).

    Voice authenticity and interaction risk are computed separately, then
    combined only at the fusion / gate layer.
    """
    if source == "DEMO SCENARIO" and voice_evidence == "unavailable":
        voice_evidence = "illustrative"
    state = conversation_state or new_conversation_state()
    intent = classify_intent(transcript)
    guards = intent.get("linguistic_guards") or {}
    prior_action = state.get("requested_action")
    continuation = (
        intent.get("intent") in {"normal_conversation", "unknown"}
        and prior_action in SENSITIVE_INTENTS
        and not guards.get("last_utterance_retracts")
        and PRESSURE_ONLY.search(transcript or "")
    )
    if continuation:
        intent = dict(intent)
        intent["intent"] = prior_action
        intent["override"] = (
            "Current turn continues an earlier sensitive request under pressure "
            "(history used as context, not as a permanent verdict)"
        )

    entities = extract_entities(transcript)
    categorized_entities = categorized_entity_inventory(entities)
    behaviour = analyse_behaviour(transcript, intent.get("intent"))
    context = analyse_context(
        transcript, intent.get("intent"), identity_status, entities, state,
    )

    voice_safety = voice_safety_from_label(voice_label)
    if authenticity_score is not None and voice_label == "LIKELY_AUTHENTIC":
        voice_safety = int(max(voice_safety, min(96, authenticity_score)))
    if authenticity_score is not None and voice_label == "LIKELY_SPOOF":
        voice_safety = int(min(voice_safety, max(4, authenticity_score)))

    identity_safety = identity_safety_from_status(identity_status)
    intent_safety = intent_safety_score(intent)

    components = {
        "voice_authenticity": voice_safety,
        "speaker_identity": identity_safety,
        "intent_safety": intent_safety,
        "behaviour_safety": behaviour["Behaviour Safety"],
        "context_safety": context["Context Safety"],
    }
    fused = compute_fused_score(components)
    evidence = {
        "intent": intent.get("intent"),
        "behaviour_signals": behaviour["signals"],
        "context_signals": context["signals"],
        "identity_status": identity_status,
        "voice_label": voice_label,
        "off_channel": context.get("off_channel"),
        "new_destination": context.get("new_destination"),
    }
    gated, caps, forced_risk, gates_evaluated = evaluate_safety_gates_detailed(fused, evidence)

    if guards.get("last_utterance_retracts") and intent.get("intent") not in SENSITIVE_INTENTS:
        # Clarification / advice can lower risk; keep a small residual note only.
        forced_risk = None
        caps = [c for c in caps if "credential" not in c.lower()]
        residual = 6 if state.get("active_concern") else 0
        gated = int(min(96, gated + (8 if residual else 0)))
        if residual:
            caps.append("Earlier turn raised a concern; current turn appears to retract or clarify it")

    risk, action_code = trust_band(gated)
    if forced_risk:
        rank = {"LOW": 0, "ELEVATED": 1, "HIGH": 2, "CRITICAL": 3}
        if rank.get(forced_risk, 0) > rank.get(risk, 0):
            risk = forced_risk
            action_code = {
                "HIGH": "VERIFY",
                "CRITICAL": "CRITICAL INTERVENTION",
                "ELEVATED": "WARN",
            }.get(risk, action_code)

    action_code, action_detail = recommended_action(risk, voice_label, identity_status)
    drivers = _decision_drivers(
        risk, intent, behaviour, context, caps, voice_label, identity_status,
    )

    fusion_audit = explain_fusion_calculation(
        components=components,
        preliminary_score=fused,
        final_score=gated,
        gates_evaluated=gates_evaluated,
        forced_risk=forced_risk,
    )

    signals_summary = compile_signals_inventory(
        voice_label=voice_label,
        authenticity_score=authenticity_score,
        identity_status=identity_status,
        intent=intent,
        behaviour=behaviour,
        context=context,
        entities=entities,
        components=components,
        caps=caps,
    )

    diagnostics = {
        "source": source,
        "voice_evidence": voice_evidence,
        "is_demo_replay": source == "DEMO SCENARIO" or voice_evidence == "illustrative",
        "pipeline_stages": {
            "Audio Ingestion & Quality Gate": "COMPLETE" if voice_evidence != "unavailable" else "SKIPPED",
            "AASIST Countermeasure Inference": "COMPLETE" if voice_label not in ("UNAVAILABLE", "ERROR") else ("ILLUSTRATIVE" if source == "DEMO SCENARIO" else "SKIPPED"),
            "Faster-Whisper Speech Recognition": "COMPLETE" if transcript else "SKIPPED",
            "Intent Classifier (TF-IDF + LR)": "COMPLETE",
            "Regex Entity Extractor": "COMPLETE",
            "Behavioural Threat Engine": "COMPLETE",
            "Context Anomaly Engine": "COMPLETE",
            "Dynamic Trust Score Fusion Arbiter": "COMPLETE",
            "Safety Gate Enforcement Engine": "COMPLETE",
        },
        "gates_evaluated_count": len(gates_evaluated),
        "gates_triggered_count": len(fusion_audit["gates_triggered"]),
        "dimensions_affected_count": signals_summary["dimensions_affected_count"],
    }

    result = {
        "source": source,
        "transcript": transcript,
        "intent": intent,
        "entities": entities,
        "categorized_entities": categorized_entities,
        "behaviour": behaviour,
        "context": context,
        "components": components,
        "factor_display": {
            "Voice Authenticity": components["voice_authenticity"],
            "Speaker Identity": components["speaker_identity"],
            "Intent Safety": components["intent_safety"],
            "Behaviour Safety": components["behaviour_safety"],
            "Context Safety": components["context_safety"],
        },
        "trust_score": gated,
        "fused_uncapped": fused,
        "interaction_risk": risk,
        "voice_label": voice_label,
        "voice_display": authenticity_display(voice_label, evidence_kind=voice_evidence, source=source),
        "identity_status": identity_status,
        "action": action_code,
        "action_detail": action_detail,
        "gates": caps,
        "drivers": drivers,
        "handshake_required": risk == "CRITICAL" or action_code == "CRITICAL INTERVENTION",
        "fusion_weights": dict(FUSION_WEIGHTS),
        "fusion_note": FUSION_WEIGHTS_NOTE,
        "claimed_identity": claimed_identity,
        "behaviour_signals": behaviour["signals"],
        "context_signals": context["signals"],
        "fusion_audit": fusion_audit,
        "signals_summary": signals_summary,
        "diagnostics": diagnostics,
    }
    result["conversation_state"] = update_conversation_state(state, result)
    return result


def _decision_drivers(risk, intent, behaviour, context, caps, voice_label, identity_status):
    drivers = []
    if risk == "LOW":
        drivers.append("No sensitive request detected" if intent.get("intent") in {
            "normal_conversation", "security_support", "unknown", "unavailable",
        } else f"Intent labelled {intent.get('intent')}")
        if not behaviour["signals"]:
            drivers.append("No urgency, secrecy, or verification-bypass combination")
        if context.get("context_level") == "NORMAL":
            drivers.append("No unusual destination or role/action mismatch")
        if voice_label == "LIKELY_AUTHENTIC":
            drivers.append("Voice signal appears authentic (countermeasure estimate)")
        elif voice_label in {"INCONCLUSIVE", "INCONCLUSIVE_QUALITY"}:
            drivers.append("Voice authenticity is inconclusive and was not treated as an attack")
        if identity_status in {"UNVERIFIED", "NOT_AVAILABLE"}:
            drivers.append("Identity is unverified — not interpreted as malicious by itself")
    else:
        drivers.extend(caps)
        drivers.extend(behaviour.get("notes") or [])
        drivers.extend(context.get("notes") or [])
        if intent.get("override"):
            drivers.append(intent["override"])
        if intent.get("linguistic_guards", {}).get("notes"):
            drivers.extend(intent["linguistic_guards"]["notes"])
    # de-dupe
    seen = []
    for item in drivers:
        if item and item not in seen:
            seen.append(item)
    return seen[:8]
