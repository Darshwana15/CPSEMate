# OneMate AI Evaluation Framework: Benchmarks, Metrics & Safety

> **DOCUMENT CLASSIFICATION: RIGOROUS EVALUATION & BENCHMARKING PROTOCOL**  
> **Status:** Active Standard  
> **Author:** Lead AI Systems Architect  
> **Target Version:** OneMate v2.0 (AI-Driven Material Intelligence)

---

## 1. Evaluation Philosophy & Principles

In industrial procurement, a false positive (declaring two incompatible items as `SAME`) is catastrophic. For example, installing a **Class 150** valve on a **Class 300** high-pressure steam line causes catastrophic mechanical blowout, loss of containment, and severe human casualty.

Therefore, the OneMate evaluation framework prioritizes:
1. **Safety First**: Zero tolerance for hard engineering conflict overrides ($0.00\%$ allowed error rate).
2. **Precision over Recall**: Better to route an uncertain item to human review as `POTENTIALLY_EQUIVALENT` than to auto-harmonize an invalid item as `SAME`.
3. **Noise Reduction**: Success is measured by reducing combinatorial clutter in the Review Queue while maximizing true-positive retrieval.

---

## 2. Quantitative Metric Formulations

We evaluate the AI material intelligence system across **four distinct dimensions**:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          FOUR-DIMENSIONAL EVALUATION MATRIX                            │
├─────────────────────────┬─────────────────────────┬────────────────────────────────────┤
│ 1. MATERIAL PARSING     │ 2. CANDIDATE RETRIEVAL  │ 3. CLASSIFICATION & NOISE          │
│ • Attribute Precision   │ • Recall@10, Recall@20  │ • Precision / Recall on SAME       │
│ • Attribute Recall      │ • Mean Reciprocal Rank  │ • Review Queue Reduction (%)       │
│ • UNKNOWN Correctness   │ • Cosine Discrimination │ • Human Review Efficiency          │
├─────────────────────────┴─────────────────────────┴────────────────────────────────────┤
│ 4. CRITICAL SAFETY GATE: Hard Conflict Override Rate (Target: Exactly 0.00%)          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Dimension 1: Material Understanding & Extraction Accuracy
Evaluates the accuracy of structured attribute extraction from messy text:
- **Slot Precision ($P_{slot}$)**: Proportion of extracted attribute values that match the physical specification.
- **Slot Recall ($R_{slot}$)**: Proportion of unstated/present physical attributes correctly identified.
- **Slot $F_1$ Score**:
  $$F_1 = 2 \times \frac{P_{slot} \times R_{slot}}{P_{slot} + R_{slot}}$$
- **UNKNOWN / NULL Correctness**:
  $$\text{Acc}_{null} = \frac{\text{Correctly Unassigned Attributes}}{\text{Total Truly Omitted Attributes}}$$
  *Requirement: Must be 100%. If an attribute is missing from text, the AI must NOT invent a value.*

### Dimension 2: Dense Semantic Retrieval Quality
Evaluates the capability of `all-MiniLM-L6-v2` dense vectors to find equivalent materials across CPSEs without evaluating all $N \times M$ pairs:
- **Recall@$K$ ($K=10, 20$)**:
  $$\text{Recall@}K = \frac{|\{\text{True Equivalent Candidates}\} \cap \{\text{Top-}K \text{ Retrieved Candidates}\}|}{|\{\text{True Equivalent Candidates}\}|}$$
  *Target: $\ge 95\%$ for $K=15$.*
- **Mean Reciprocal Rank (MRR)**:
  $$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$
  where $\text{rank}_i$ is the position of the first true equivalent item in candidate search results.

### Dimension 3: Final Classification & Noise Reduction
- **Precision on `SAME`**:
  $$\text{Precision}_{SAME} = \frac{\text{True } SAME}{\text{Total Recommended } SAME}$$
  *Target: $\ge 98\%$.*
- **Review Queue Clutter Reduction**:
  $$\text{Noise Reduction Rate} = 1.0 - \left( \frac{\text{Total Recommendations Generated (v2.0)}}{\text{Total Recommendations Generated (v1.0 Baseline)}} \right)$$
  *Target: $\ge 80\%$ reduction in generated match recommendation rows.*

### Dimension 4: Engineering Safety Gate (The 0.00% Rule)
Evaluates whether any hard technical conflict is ever misclassified as `SAME`:
$$\text{Conflict Override Rate} = \frac{\text{Pairs with Hard Conflicts Classified as SAME}}{\text{Total Pairs with Hard Conflicts}}$$
**MANDATORY THRESHOLD: EXACTLY 0.00%. ANY VALUE GREATER THAN ZERO FAILS THE BUILD.**

---

## 4. Benchmark Golden Dataset Architecture

To evaluate the system objectively, we establish a **Golden Benchmark Suite** containing 5 distinct test cohorts:

```text
Cohort A: True Positives (Exact Technical Equivalents, Lexical Divergence)
  Example 1: "BALL VALVE 2\" CL150 RF CS SS304"  vs  "VALVE, BALL, DN50, 150#, RAISED FACE, WCB/304SS"
  Expected: Classification = SAME, Confidence >= 0.90, Conflicts = None

Cohort B: Hard Negatives (Identical in 5 Attributes, Conflicting in 1)
  Example 1: "GATE VALVE DN50 CLASS150 RF CS SS316"  vs  "GATE VALVE DN50 CLASS300 RF CS SS316" (Pressure conflict)
  Example 2: "BALL VALVE DN50 CLASS150 RF CS SS316"  vs  "GATE VALVE DN50 CLASS150 RF CS SS316" (Valve type conflict)
  Example 3: "BALL VALVE DN50 CLASS150 RF CS SS304"  vs  "BALL VALVE DN50 CLASS150 RF CS SS316" (Trim conflict)
  Example 4: "BALL VALVE DN50 CLASS150 RF CS SS316"  vs  "BALL VALVE DN100 CLASS150 RF CS SS316" (Size conflict)
  Expected: Classification = DIFFERENT, Confidence = 0.0, Conflicts Detected = Explicitly Named

Cohort C: Asymmetric Incomplete Pairs (One Complete, One Incomplete)
  Example 1: "BALL VALVE DN50 CLASS150 RF CS" (Trim omitted)  vs  "BALL VALVE DN50 CLASS150 RF CS SS316"
  Expected: Classification = POTENTIALLY_EQUIVALENT, Routed to Review Queue, Auto-Harmonization Blocked

Cohort D: Cross-Enterprise Category Disjoint Pairs
  Example 1: "CENTRIFUGAL PUMP 50M3/HR CS"  vs  "WELD NECK FLANGE DN50 CL150 CS"
  Expected: Filtered at Retrieval Stage (never enters candidate comparison)

Cohort E: Ambiguous & Informal Abbreviations
  Example 1: "VLV NDL 1/2IN 6000PSI NPT 316SS"  vs  "NEEDLE VALVE DN15 6000# SCREWED SS316"
  Expected: Classification = SAME, Attributes successfully extracted across both
```

---

## 5. Why NOT to Train an ML Classifier Prematurely

An inexperienced ML engineer might propose training an XGBoost classifier or fine-tuning a BERT classifier on the current demo dataset. **We explicitly reject this approach at this stage.**

### Rigorous Architectural Justification:

1. **Severe Small-Sample Bias ($N < 500$)**:
   - The demo dataset contains dozens, not millions, of materials.
   - Deep neural networks or gradient-boosted trees trained on small datasets suffer from extreme variance and memorization.
2. **Spurious Feature Correlation**:
   - Classifiers latch onto non-engineering features. If synthetic data happens to have all `CPSE-A` items in uppercase and `CPSE-B` items with commas, a trained model learns to predict equivalence based on punctuation patterns rather than pressure ratings.
3. **Loss of Safety Determinism**:
   - A statistical classifier outputs probabilities (e.g. $P(SAME) = 0.94$). If a tiny permutation of words drops the probability from 0.94 to 0.49, the system behaves unpredictably.
   - Deterministic engineering rules provide $100\%$ guarantees that `CLASS150 != CLASS300`.
4. **Legal & Procurement Auditability**:
   - When public sector auditors ask why two material codes were merged, OneMate can point to exact attribute matching and human approval. A black-box classifier score cannot be legally defended.

---

## 6. The Human-in-the-Loop Feedback Loop

Rather than training on synthetic data, OneMate builds its ground truth organically from real human operator actions:

```text
  [1] AI surfaces POTENTIALLY_EQUIVALENT in Review Queue
                           │
                           ▼
  [2] Human Reviewer evaluates technical specifications
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
       Action: ACCEPT              Action: REJECT / MARK_DIFF
             │                           │
             └─────────────┬─────────────┘
                           ▼
  [3] System records immutable AuditLog event:
      • Source Material ID & Description
      • Candidate Material ID & Description
      • AI Confidence & Evidence
      • Human Action, Decision & Justification Reason
                           │
                           ▼
  [4] Audit logs are periodically compiled into Verified Evaluation Sets
                           │
                           ▼
  [5] Future Model Fine-Tuning & Threshold Calibration (Phase 6)
```

By grounding future training exclusively on verified human audit logs, OneMate ensures continuous learning without sacrificing safety.

