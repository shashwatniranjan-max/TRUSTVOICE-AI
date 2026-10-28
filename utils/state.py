"""Conversation-level state for TRUSTVOICE with multi-turn progression tracking."""

from __future__ import annotations

from copy import deepcopy

EMPTY_CONVERSATION = {
    "claimed_identity": None,
    "identity_status": "NOT_AVAILABLE",
    "voice_authenticity": "UNAVAILABLE",
    "intents": [],
    "entities": [],
    "requested_action": None,
    "destinations": [],
    "behavioural_signals": [],
    "context_signals": [],
    "previous_events": [],
    "current_risk": "LOW",
    "trust_scores": [],
    "active_concern": False,
    "turn_history": [],
    "first_high_risk_turn": None,
    "first_critical_risk_turn": None,
}


def new_conversation_state() -> dict:
    return deepcopy(EMPTY_CONVERSATION)


def update_conversation_state(state: dict | None, utterance: dict) -> dict:
    state = deepcopy(state or new_conversation_state())
    intent = (utterance.get("intent") or {}).get("intent")
    if intent:
        state["intents"].append(intent)
    for ent in utterance.get("entities") or []:
        state["entities"].append(ent)
        if ent.get("type") in {"DESTINATION", "EMAIL"}:
            dest = ent.get("value")
            if dest and dest not in state["destinations"]:
                state["destinations"].append(dest)

    current_turn_behaviour = list(utterance.get("behaviour_signals") or [])
    current_turn_context = list(utterance.get("context_signals") or [])

    for sig in current_turn_behaviour:
        if sig not in state["behavioural_signals"]:
            state["behavioural_signals"].append(sig)
    for sig in current_turn_context:
        if sig not in state["context_signals"]:
            state["context_signals"].append(sig)

    if utterance.get("identity_status"):
        state["identity_status"] = utterance["identity_status"]
    if utterance.get("voice_label"):
        state["voice_authenticity"] = utterance["voice_label"]
    if utterance.get("claimed_identity"):
        state["claimed_identity"] = utterance["claimed_identity"]

    state["requested_action"] = intent or state.get("requested_action")
    risk = utterance.get("interaction_risk", state.get("current_risk"))
    state["current_risk"] = risk
    score = utterance.get("trust_score")
    state["trust_scores"].append(score)

    retracting = bool(
        (utterance.get("intent") or {}).get("linguistic_guards", {}).get("last_utterance_retracts")
    )
    if retracting and intent in {
        "normal_conversation", "security_support", "account_information",
    }:
        state["requested_action"] = intent
        state["active_concern"] = False
    elif intent in {
        "credential_request", "financial_request", "sensitive_data_request",
        "personal_information_request",
    }:
        state["active_concern"] = True

    # Legacy event entry
    state["previous_events"].append({
        "transcript": utterance.get("transcript", ""),
        "intent": intent,
        "trust_score": score,
        "interaction_risk": risk,
    })

    # Detailed turn-by-turn history
    turn_history = state.get("turn_history", [])
    turn_idx = len(turn_history) + 1
    prev_turn = turn_history[-1] if turn_history else None

    # Track signals delta
    curr_signals = set(current_turn_behaviour + current_turn_context)
    prev_signals = set((prev_turn.get("behaviour_signals", []) + prev_turn.get("context_signals", []))) if prev_turn else set()
    newly_detected = sorted(list(curr_signals - prev_signals))
    persistent = sorted(list(curr_signals & prev_signals))

    score_change = (score - prev_turn["trust_score"]) if (prev_turn and prev_turn.get("trust_score") is not None and score is not None) else 0

    # Build change explanation
    caps = utterance.get("gates") or []
    if prev_turn is None:
        explanation = f"Initial turn established baseline Trust Score of {score}/100 ({risk})."
    else:
        if score_change < 0:
            reasons = []
            if newly_detected:
                reasons.append(f"new risk signals: {', '.join(newly_detected)}")
            if caps:
                reasons.append(f"safety gate triggered ({caps[0]})")
            if not reasons:
                reasons.append("intent/context shift")
            explanation = f"Trust Score declined by {abs(score_change)} pts ({prev_turn['trust_score']} → {score}) due to {'; '.join(reasons)}."
        elif score_change > 0:
            explanation = f"Trust Score recovered by {score_change} pts ({prev_turn['trust_score']} → {score}) following clarification or benign context."
        else:
            explanation = f"Trust Score remained steady at {score}/100."

    # Track escalation markers
    if risk in ("HIGH", "CRITICAL") and state.get("first_high_risk_turn") is None:
        state["first_high_risk_turn"] = turn_idx
    if risk == "CRITICAL" and state.get("first_critical_risk_turn") is None:
        state["first_critical_risk_turn"] = turn_idx

    turn_entry = {
        "turn_index": turn_idx,
        "transcript": utterance.get("transcript", ""),
        "intent": intent or "unknown",
        "entities": utterance.get("entities") or [],
        "behaviour_signals": current_turn_behaviour,
        "context_signals": current_turn_context,
        "components": dict(utterance.get("components") or {}),
        "preliminary_score": utterance.get("fused_uncapped"),
        "trust_score": score,
        "interaction_risk": risk,
        "action": utterance.get("action", "CONTINUE"),
        "action_detail": utterance.get("action_detail", ""),
        "gates": list(caps),
        "newly_detected_signals": newly_detected,
        "persistent_signals": persistent,
        "score_change": score_change,
        "change_explanation": explanation,
    }
    state["turn_history"].append(turn_entry)

    return state


def reset_conversation_state() -> dict:
    return new_conversation_state()
