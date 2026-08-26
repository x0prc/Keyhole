# Keyhole — 5-Minute Pitch Script

> **Format:** voiceover + screen share. Sections are timed. Keep it conversational — this is a guide, not a teleprompter script.

---

## 0:00–0:30 — The Problem

**Screen:** Razorpay buildathon page, Track 02 highlighted.

**Say:**
> "Fraud is a silent margin killer for merchants. Every chargeback, every stolen card, every abuse ring — the merchant pays. And with AI-generated fraud scaling up, rule-only systems either miss the novel attacks or drown the ops team in false alarms.
>
> So for Track 02, AI Risk Manager, I built **Keyhole** — a real-time fraud spike detector that scores every transaction in under half a second."

---

## 0:30–1:10 — What I Built & Architecture

**Screen:** README architecture diagram (or DESIGN.md open in editor).

**Say:**
> "The pipeline is four Docker containers, one command. Transactions stream through **Kafka**, a detection worker computes features, an **Isolation Forest** scores each one, and alerts fire over **WebSocket** to a live dashboard.
>
> The key decision: instead of synthetic data, I trained and evaluated on the **Kaggle credit card fraud dataset** — 284,807 real transactions, 492 real frauds."

---

## 1:10–2:10 — Honest Evaluation Design

**Screen:** Open `notebooks/keyhole_training.ipynb` — scroll through the train/test split cell.

**Say:**
> "Here's what makes the metrics honest. I split the dataset by **time**, not randomly — the first 80% of the 48-hour window is training data, and I train on **normal transactions only**, which is the standard for anomaly detection. The last 20% is a held-out set the model never saw — that's what streams live in the demo.
>
> The threshold isn't a magic number I hardcoded — it's **calibrated on training scores** to hit a target false-positive rate of half a percent. Judges can verify every number by running this notebook."

---

## 2:10–3:40 — Live Demo

**Screen:** Terminal. Run `docker compose up --build`. Then open the dashboard.

**Say:**
> "One command. Kafka, Redis, and the app come up together. The model artifact is already in the repo, so it skips training and starts streaming the held-out set immediately — compressed 500x, so 48 hours of transactions replay in about six minutes.

**Screen:** Dashboard filling with transactions. Point at a row turning red.

> "Every row is a real transaction — prediction on the left of the verdict, ground truth on the right. When the model flags one, it appears in the alerts pane with its anomaly score and severity… there — a true positive. And this amber one is a false positive — I'm showing those on purpose, because honest false-positive cost is the bar for this track."

**Screen:** Point at the metrics cards updating.

> "Precision, recall, F1 — all computed live from ground truth, not cherry-picked after the fact."

---

## 3:40–4:30 — Results & Trade-offs

**Screen:** Notebook's operating-point sweep table (or README results).

**Say:**
> "On the held-out 73,766 transactions: at a 0.5% false-positive rate, Keyhole catches about **18% of frauds with 98% of alerts worth investigating** — and the sweep table shows the full trade-off: loosen to 5% FPR and recall climbs past 60%.
>
> In production that dial belongs to the merchant — a high-value merchant tolerates more false alarms than a low-margin one. The system exposes it as a single calibrated threshold."

---

## 4:30–5:00 — Wrap

**Screen:** Repo root on GitHub.

**Say:**
> "Everything you saw is in the repo: the streaming pipeline, the calibrated model, the training notebook, the design doc, and a test suite. Defense-only, honest metrics, one command to run.
>
> I built this end to end — data, features, model, infra, frontend — and I'd love to build Razorpay's real risk systems next. Thanks for watching."

---

### Pre-flight checklist

- [ ] `docker compose down && docker compose up --build` works cleanly
- [ ] Dashboard opens at `localhost:8000/dashboard/`
- [ ] Terminal font is large enough for video
- [ ] Close distracting tabs/notifications
- [ ] Do one dry run — the first fraud alert fires within the first minute of streaming
