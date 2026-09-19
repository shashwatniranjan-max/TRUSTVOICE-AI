# TRUSTVOICE AI

SIH (Smart India Hackathon) prototype for **AI-powered conversation security**:
voice authenticity, speaker identity *status*, intent, social-engineering
indicators, and context are analysed separately and fused into a
**Dynamic Trust Score** (decision support, not a probability).

Core idea: **a real voice is not a safe conversation.**

This is a local prototype, not a production security product. It does **not**
intercept ordinary cellular calls, enroll a real user gallery, or claim
calibrated detector accuracy.

## Capabilities

- **Anti-spoofing:** optional AASIST / W2V2-AASIST ONNX countermeasures
  (`models/aasist.onnx` is the small default). Output is an *authenticity
  score* plus LIKELY AUTHENTIC / LIKELY SPOOF / INCONCLUSIVE, with an
  uncertainty band. Poor audio is inconclusive, not an alarm.
- **Interaction analysis:** TF-IDF + logistic regression intent classifier,
  regex entities, behavioural cues, context anomalies, conversation state.
- **Fusion:** prototype weights in `risk/config.py`. Hard gates require
  *combinations* (for example OTP solicitation + pressure + unverified
  identity), not a single keyword.
- **Trust Handshake:** simulated independent verification UI when interaction
  risk is CRITICAL. Buttons do not contact a device or telecom service.
- **Evaluation lab:** metrics (accuracy, precision, recall, F1, FAR, FRR, EER,
  confusion matrix) appear **only** when you upload labelled `REAL_` / `SPOOF_`
  files. No placeholder numbers.

## Not implemented / not claimed

- No in-house Whisper or ASR training. Paste a transcript for text analysis.
- No live speaker enrollment. Identity is `VERIFIED` / `UNVERIFIED` /
  `NOT_AVAILABLE` / `MISMATCH` for the demo — unavailable is not “malicious”.
- No telecom, SS7, or cellular tap.
- Raw countermeasure scores are **not** calibrated probabilities unless you
  fit a threshold in the evaluation lab.

## Run

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Optional PDF reports: `python -m pip install reportlab`

Place a larger W2V2-AASIST ONNX file in `models/` or set `TRUSTVOICE_MODEL_PATH`
to run a different checkpoint. First-run download is attempted only if the
file is missing.

## Live analysis vs demo scenarios

| Mode | What it is |
| --- | --- |
| **LIVE / UPLOADED ANALYSIS** | Real audio pipeline (if a file is provided) plus the interaction engine on the transcript. |
| **DEMO SCENARIO** | Scripted dialogue run through the *same* interaction engine. Voice labels in the script are illustrative, not live AASIST measurements. |

Do not mix the two when presenting scores.

## Demo scenarios

- **A — unknown caller:** Hello → bank pretext → account number → OTP → urgency/threat. Trust should fall.
- **B — verified identity:** greeting → employee database → personal email → secrecy. Trust should fall even though identity is verified (identity ≠ authorization).

There is also a **benign / contrast** button list (meetings, security advice, credential asks) so judges can see that ordinary language does not automatically become CRITICAL.

## Evaluate anti-spoofing

In **Evaluation**, upload files named `REAL_…` and `SPOOF_…`. If both classes
are present, EER and a suggested threshold can be derived. If not, the UI
states that the threshold is the prototype default.

## Tests

```bash
python -m unittest tests.test_pipeline
```

## Layout

```
app.py                 Streamlit entry
ui/                    SOC-style console, demo, evaluation, reports, settings
models/                anti-spoof, intent, entities
risk/                  behaviour, context, fusion, pipeline
demo/                  scripted scenarios
utils/                 audio, state, evaluation, reporting
```

## Privacy

Prototype processing is local to the application environment. Voice/audio
data should be treated as sensitive and retained only as long as necessary.
No compliance certification is claimed.
