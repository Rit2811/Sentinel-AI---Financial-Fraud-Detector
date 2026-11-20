# 🛡️ Sentinel AI — Evaluator Presentation & Live Simulation Guide
**Project:** Sentinel AI — Enterprise Financial Fraud Detection & Prevention Platform  
**Target Environment:** Docker Microservices, Heterogeneous Hybrid Ensemble, Redis Streams, React 19  
**Patent Reference:** IDF Sharda University — Dynamic Class-Imbalance & Multi-Learner Stream Innovations (Claims 1–6)  

---

## 📌 Executive Summary & 30-Second Elevator Pitch

> *"Sentinel AI is a bank-grade, real-time financial fraud detection and stream prevention platform. Unlike traditional black-box fraud systems, Sentinel AI integrates a **Heterogeneous Hybrid Ensemble** combining tree-based, margin-based, distance-based, and linear models with **Dynamic Class-Imbalance calibration**, **Balance Inconsistency tracking**, and **Concept Drift detection**. Every payment authorization is scored in sub-15ms, verified across strict PCI-DSS tokenization safeguards, audited via Redis Streams with 100% event receipts, and supported by a dual-custody human review workflow."*

```mermaid
flowchart TD
    subgraph ClientLayer["1. Client & Ingestion Layer"]
        UserCard["💳 3D Interactive Card Simulator<br/>(Front & Back View)"] --> Tokenizer["🔐 PCI-DSS Tokenizer<br/>(PAN & CVV Masking)"]
        Tokenizer --> API["⚡ Express API Gateway<br/>(:18000 / :8000)"]
    end

    subgraph StreamingLayer["2. Telemetry & Streaming Layer"]
        API --> RedisStream["🌊 Redis Streams<br/>(authorization.events.v1)"]
        RedisStream --> Publisher["📡 Stream Publisher<br/>(Batching & Telemetry)"]
        Publisher --> PostgresDB[("🗄️ PostgreSQL Ledger<br/>(Audit Trails & Health)")]
    end

    subgraph MLEngineLayer["3. Patent Hybrid Ensemble & Scoring"]
        API --> ScoringService["🧠 Multi-Learner Engine<br/>(Logit & Feature Fusion)"]
        ScoringService --> RF["🌲 Random Forest (Tree Ensemble)"]
        ScoringService --> SVM["📐 SVM (Hyperplane Separation)"]
        ScoringService --> KNN["📍 KNN (Instance Distance)"]
        ScoringService --> LR["📈 Logistic Regression (Sigmoid)"]
        RF & SVM & KNN & LR --> PolicyGate{"⚖️ Policy Gate Thresholds"}
    end

    subgraph DecisionLayer["4. Decision & Review Workflow"]
        PolicyGate -->|p < 0.10| Approved["🟢 Pass / Approved"]
        PolicyGate -->|0.10 <= p < 0.25| Review["🟡 Review / Dual Custody"]
        PolicyGate -->|p >= 0.25| Blocked["🔴 Block / Dangerous"]
        Review --> AnalystUI["👤 Fraud Analyst Resolution<br/>(Allow / Reject)"]
    end

    subgraph VisualizationLayer["5. Frontend Presentation Layer (:15173)"]
        Approved & Review & Blocked & AnalystUI --> Dashboard["📊 Real-time Dashboard & Gauge"]
    end
```

---

## 🏛️ Patent Claims Architecture & Innovations Deep-Dive

When the evaluator asks about the theoretical and intellectual contributions of this project, present these **6 Core Patent Claims**:

| Patent Claim | Innovation Name | Technical & Mathematical Implementation in Sentinel AI |
|---|---|---|
| **Claim 1** | **Real-Time Transaction Scoring Engine** | Sub-15ms latency inference scoring using vectorized feature extractors across 21 behavioral dimensions (amount, hour, velocity, channel, merchant tier). |
| **Claim 2** | **Balance Inconsistency Score** | Real-time calculation of balance deviation:$$\Delta_{inconsistency} = |Balance_{expected} - Balance_{actual}|$$Large anomalous spikes trigger immediate policy reviews before ledger persistence. |
| **Claim 3** | **Dynamic Class-Imbalance Calibration** | Real-world fraud represents only **0.16%** of transactions vs **99.84%** legitimate. Sentinel AI applies an adaptive sliding window with probability calibration to eliminate false-positive explosion. |
| **Claim 4** | **Heterogeneous Hybrid Ensemble Fusion** | Fuses 4 fundamentally distinct mathematical learners:<ul><li>**Random Forest:** Non-linear feature interactions and bagging.</li><li>**SVM (RBF Kernel):** Maximum-margin boundary separation.</li><li>**KNN (Euclidean Distance):** Instance-based metric similarity.</li><li>**Logistic Regression:** Calibrated log-odds prior probability baseline.</li></ul> |
| **Claim 5** | **Concept Drift Monitoring** | Continuously evaluates population feature drift index ($\text{Nominal} = 0.024$). Detects fraud syndicate pattern migrations without destructive live retraining. |
| **Claim 6** | **Stream Processing & Immutable Audit Receipts** | Full Redis Stream event receipts (`receiptId`, `partitionKey`, `ackToken`) with 100% delivery guarantee, zero data loss, and dual-custody resolution logging. |

---

## 🎬 Evaluator Live Demonstration Walkthrough (Step-by-Step Script)

Follow this structured script when demonstrating the platform. Each step includes **what to do**, **what happens under the hood**, and **what to say to the evaluator**.

---

### Step 0: Pre-Flight System Health Check
**Action:** Open terminal and run:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/teammate.ps1 health
```
**What the Evaluator Sees:**
```text
Infrastructure: HTTP 200
Dashboard: HTTP 200
Dashboard data: HTTP 200
```
**What to Say:**
> *"Before starting, we verify that our local multi-container microservices stack is fully operational. All six containers—PostgreSQL 16, Redis 7 Streams, Express API, Stream Publisher, React 19 Dashboard, and our isolated Scoring Worker—are healthy and communicating over internal Docker virtual networks."*

---

### Step 1: Launch the Interactive Workbench & 3D Card Visualizer
**Action:** Navigate to `http://localhost:15173`.
1. Point to the **3D Interactive Credit Card** on the left panel.
2. Click the **🔄 View Back Side (CVV & Magnetic Stripe)** button (or click the card).
3. The card performs a realistic 3D flip revealing the magnetic stripe, signature panel, dynamic 3-digit CVV, and EMV watermark.
4. Click again to return to the front view.

**What to Say:**
> *"Here is our payment simulation workbench. We feature a fully interactive 3D card element supporting EMV chip, contactless NFC, and magnetic stripe fallback. Flipping the card displays the dynamic CVV and security strip. Notice that card numbers are automatically masked according to PCI-DSS standards, ensuring PAN data is never exposed in the presentation layer."*

---

### Step 2: Scenario 1 — Everyday Safe Purchase (Approved / Pass)
**Action:**
1. Click the preset: **Normal Everyday Purchase**.
2. Form fields populate: `$14.50` at `Trader Joe's Market #104`, category `grocery_pos`, entry mode `chip`, hour `10:00 AM`.
3. Click **Authorize Payment**.

**What Happens:**
- The card status turns **emerald green** (`credit-card--approved`).
- Radial Gauge settles at **Low Risk** (~5.0%).
- Assessment Banner indicates **00 - TRANSACTION APPROVED**.
- The **Patent Ensemble Panel** updates with all 4 model outputs:
  - Random Forest: `5.1%`
  - SVM: `4.8%`
  - KNN: `5.3%`
  - Logistic Regression: `4.7%`
- The **Reasoning Narrative** breaks down negative risk factors:
  - `Low-Risk Category: Essential Grocery (-8%)`
  - `Micro-Transaction Tier (< $30.00) (-6%)`
  - `Hardware Cryptographic Verification (EMV Chip) (-8%)`
  - `Normal Daylight Hours (-3%)`

**What to Say:**
> *"Our first test evaluates a legitimate baseline. The consumer is purchasing morning groceries for $14.50 using a physical EMV chip. Notice how the AI reasoning engine explains why this was approved: essential category, daylight hours, cryptographic chip verification, and micro-transaction bounds reduce the logit score to approximately 5%. All four models in the patent ensemble agree, yielding an immediate Pass decision."*

---

### Step 3: Scenario 2 — Suspicious Online Order (Flagged for Review & Analyst Override)
**Action:**
1. Click the preset: **Suspicious Spike / Online Electronics**.
2. Form populates: `$420.00` at `MegaTech Electronics Direct`, category `shopping_net`, hour `19:00`.
3. Click **Authorize Payment**.
4. The card turns **amber/yellow** with banner **01 - SUSPICIOUS TRANSACTION: FLAGGED FOR HUMAN FRAUD REVIEW**.
5. The **Dual-Custody Review Resolution Box** appears.
6. Click the green button: **Allow & Approve**.

**What Happens:**
- Probability crosses the review threshold ($0.10 \le p < 0.25$, ~14.8%).
- Risk factors highlighted:
  - `Large Purchase Amount ($750 tier)`
  - `Card-Not-Present Remote Channel`
  - `Spending Volatility relative to cardholder 24h baseline`
- The system places the transaction in `pending_review`.
- Clicking **Allow & Approve** executes an authenticated API patch to `/api/v1/simulate/review`, updating PostgreSQL with the analyst identity and timestamp, and transitioning the state to `allowed`.

**What to Say:**
> *"In Scenario 2, we simulate an order of $420 on an online electronics site. This crosses our policy review threshold of 10%. Instead of blindly declining a potentially good customer, Sentinel AI routes this to the Dual-Custody Review Queue. Here, a fraud analyst can inspect the evidence and choose 'Allow & Approve' or 'Reject & Confirm Fraud'. As I click Allow, the transaction updates in the database and enters the audit trail with analyst verification."*

---

### Step 4: Scenario 3 — Midnight High-Risk Anomaly (Automated Block)
**Action:**
1. Click the preset: **High-Risk Midnight Anomaly**.
2. Form populates: `$3,850.00` at `Global Vault FX & Luxury`, country `NG`, entry mode `manual`, hour `03:00 AM`.
3. Click **Authorize Payment**.

**What Happens:**
- Card turns **crimson red** (`credit-card--dangerous`).
- Radial Gauge spikes to **Severe Risk** (~82.4%).
- Assessment Banner displays: **05 - TRANSACTION DECLINED: DANGEROUS FRAUD PATTERN BLOCKED**.
- Patent Metrics highlight:
  - `Balance Inconsistency Score: 0.85 (High Anomaly)`
  - Risk factors: `Cryptocurrency Exchange (+28%)`, `Exceptional Dollar Value > $2,500 (+26%)`, `Off-Hours 03:00 AM (+15%)`, `Manual Keyed Entry (+14%)`, `Cross-Border Settlement NG (+12%)`.

**What to Say:**
> *"Now we test an aggressive fraud attack: an un-tokenized manual entry of $3,850 for overseas crypto at 3:30 AM. Multiple critical risk vectors compound simultaneously: high dollar value, off-hours timing, cross-border jurisdiction, and manual entry. The fused risk score jumps above our 25% hard-block threshold to 82%, instantly declining the transaction before any fund movement occurs."*

---

### Step 5: Scenario 4 — Security Test: PCI-DSS Prohibited Field Leak (Quarantine)
**Action:**
1. Click the preset: **Security Test: PCI Prohibited Field Leak**.
2. Click **Authorize Payment**.

**What Happens:**
- Card turns **purple** (`credit-card--quarantined`).
- Assessment Banner flashes: **PCI-DSS QUARANTINE: UNENCRYPTED PAN/CVV DETECTED**.
- Transmission is intercepted and dropped by the client/API gateway before entering the scoring pipeline or database.

**What to Say:**
> *"A hallmark of production enterprise systems is compliance defense. In this scenario, raw card data is injected without prior hardware tokenization. Sentinel AI immediately isolates and quarantines the payload under PCI-DSS Requirement 3.4. Unencrypted account numbers never reach the database or logging pipeline."*

---

### Step 6: Step-by-Step Transaction Lifecycle & Stream Processing Verification
**Action:**
1. Scroll down to the **6-Step Transaction Lifecycle Timeline**.
2. Walk the evaluator through the 6 visual stages:
   - `1. Ingestion` → `2. Tokenization` → `3. Feature Extraction` → `4. Ensemble Scoring` → `5. Policy Decision` → `6. Stream Receipt`.
3. Switch to the second top tab: **Ingestion & Stream Dashboard**.
4. Observe the live stream metrics:
   - `49/49 events processed (100.0% completion rate)`
   - `0 dead-letter backlog`
   - Real-time event timeline and distribution charts.

**What to Say:**
> *"Under the hood, every transaction flows through a 6-stage lifecycle pipeline. When we switch to the Ingestion & Stream Dashboard, you can see live telemetry from our Redis stream consumer groups. In our load tests, 49 out of 49 stream events were processed with a 100% completion rate, zero dead-letter queue spillover, and complete audit receipt generation."*

---

### Step 7: History Ledger & Compliance CSV Export
**Action:**
1. Switch back to the **Credit Card Simulator** tab.
2. In the **Simulation History** section:
   - Click the **Approved** filter button.
   - Click the **Blocked** filter button.
   - Click the **All** filter button.
3. Click the **Export CSV** button. The browser downloads `sentinel_audit_ledger.csv`.

**What to Say:**
> *"Finally, every simulated event is recorded in an immutable ledger. Fraud teams can filter by decision state and export the entire audit trail to CSV for regulatory compliance, banking audits, and model performance backtesting."*

---

## 💡 Evaluator Q&A Defense Guide (The Hard Questions)

Be prepared to answer these challenging questions from the evaluator with confidence:

### Q1: *"Why use a Heterogeneous Hybrid Ensemble instead of a single Deep Learning model like LSTM or Transformer?"*
> **Answer:**  
> *"In real-time banking authorizations, latency, explainability, and regulatory compliance are paramount. A deep transformer typically incurs 50–200ms latency and operates as an unexplainable black box under GDPR/FCRA adverse action notice rules. Our hybrid ensemble fuses Random Forest (for non-linear multi-split interactions), SVM (for max-margin boundary optimization), KNN (for instance similarity), and Logistic Regression (for calibrated log-odds baseline). This achieves sub-15ms inference while providing transparent mathematical factor breakdowns for every decision."*

### Q2: *"How do you handle extreme class imbalance where 99.8% of transactions are legitimate?"*
> **Answer:**  
> *"Standard classifiers trained on raw banking data suffer from accuracy paradox—predicting all legitimate yields 99.8% accuracy but catches 0% fraud. Sentinel AI implements Patent Claim 3: an adaptive sliding window with synthetic minority oversampling (SMOTE) during training, paired with post-scoring Platt/Isotonic probability calibration. This ensures the output risk score represents true empirical fraud likelihood rather than prior class frequency."*

### Q3: *"How does the system prevent model degradation when fraudsters change their tactics (Concept Drift)?"*
> **Answer:**  
> *"That is addressed directly in Patent Claim 5. Sentinel AI continuously monitors a Population Stability Index (PSI) and Wasserstein drift distance against the baseline feature distributions (currently nominal at 0.024). When velocity, amounts, or merchant categories shift past the drift threshold, the system flags a Concept Drift alert to the risk team without triggering untested automated retraining that could destabilize production."*

### Q4: *"What prevents credential leakage or data poisoning across distributed teammate machines?"*
> **Answer:**  
> *"The repository adheres to strict zero-leak principles. Teammates generate their own cryptographic secrets locally via `new-teammate-env.ps1`. The model package is frozen and signed with SHA-256 manifests (`1e421627...`). The scoring worker refuses to start unless the package checksum matches the pre-approved evaluation gate report (`abdffc8e...`). No passwords, databases, or training logs are ever transmitted."*

---

## 📊 Summary Checklist for Presentation Day

- [x] Docker Desktop is running and healthy.
- [x] All 6 containers started (`scripts/teammate.ps1 start -Scoring`).
- [x] Teammate health check returns HTTP 200 (`scripts/teammate.ps1 health`).
- [x] Frontend loaded at `http://localhost:15173`.
- [x] 3D Card flips to show backside (CVV and magnetic stripe).
- [x] Tested all 4 presets (Normal, Suspicious Review, Midnight Block, PCI Quarantine).
- [x] Verified Dual-Custody analyst override (`Allow & Approve`).
- [x] Inspected Ingestion & Stream Dashboard tab.
- [x] Downloaded sample CSV audit ledger.
- [x] Ready to answer patent and architectural questions.
