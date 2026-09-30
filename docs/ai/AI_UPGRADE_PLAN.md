# OneMate AI Upgrade Plan: Material Intelligence & Semantic Harmonization

> **DOCUMENT CLASSIFICATION: ARCHITECTURAL STRATEGY & ROADMAP**  
> **Status:** Architecture Freeze / Pre-Implementation  
> **Author:** Lead AI Systems Architect  
> **Target Version:** OneMate v2.0 (AI-Driven Material Intelligence)  
> **Baseline Recovery:** `v1.0-stable` (`d1f1d42`)

---

## 1. Context & Motivation

In the Indian public sector, Central Public Sector Enterprises (CPSEs)—ranging from upstream oil exploration (e.g. ONGC, OIL) to refining and petrochemicals (e.g. IOCL, BPCL, HPCL, CPCL) and heavy engineering (e.g. BHEL)—procure millions of engineering components independently.

The same physical engineering component is routinely recorded under completely disparate descriptions, abbreviations, word orders, and internal item codes:

```text
CPSE 1: "VALVE, NEEDLE, 1/2 INCH, SS316, 6000PSI, NPT"
CPSE 2: "NEEDLE VALVE 1/2 IN SS316 6000PSI NPT"
CPSE 3: "15MM 6000# NPT NEEDLE VLV BODY/TRIM 316SS"
```

To an experienced piping engineer, these three descriptions identify an identical physical component. However, the existing deterministic parser and substring matcher struggle:
- Lexical similarity algorithms (`difflib.SequenceMatcher`) fail when tokens are permuted or abbreviated.
- Regex-based extractors drop unmodeled parameters (e.g., `6000PSI` or `NPT` become `None`/`UNKNOWN`).
- Coarse database candidate selection retrieves hundreds of unrelated valves, creating combinatorial clutter in the Review Queue.

The **OneMate AI Upgrade** evolves OneMate from a purely rule-based system into a hybrid **Material Intelligence Platform**.

---

## 2. The Core Philosophy

```text
┌────────────────────────────────────────────────────────┐
│               THE ONEMATE AI TRIAD                     │
│                                                        │
│   "AI understands language.                            │
│    Engineering rules enforce correctness.              │
│    Humans govern uncertainty."                         │
└────────────────────────────────────────────────────────┘
```

The upgrade does **not** hand authoritative decision-making to an unconstrained neural network or LLM. AI is employed where machine learning excels: **semantic language comprehension, abbreviation resolution, vector embedding, and high-dimensional similarity retrieval**. Deterministic code remains strictly in charge of **engineering validation, conflict detection, database integrity, and governance**.

---

## 3. Current System vs. Target AI System

| Dimension | Current System (`v1.0-stable`) | Target AI System (`v2.0-ai`) |
| :--- | :--- | :--- |
| **Description Ingestion** | Regex string cleaning + uppercase | NLP tokenization, domain normalization, semantic embedding |
| **Attribute Extraction** | Brittle regex with hardcoded keyword lists | Hybrid extractor: High-coverage regex fast-path + NLP entity extraction + structured profile |
| **Attribute Coverage** | 14 fractional sizes, CLASS ratings, basic CS/SS/CI | Full ANSI/DIN/JIS sizes, PSI/PN/Bar pressure, exotic alloys, diverse connection geometries |
| **Semantic Representation**| None (raw string only) | Dense vector embedding (384-dimensional `all-MiniLM-L6-v2`) |
| **Candidate Retrieval** | Coarse SQL: `category = X AND (type = Y OR type IS NULL)` | Top-$K$ Dense Vector Search filtered by CPSE boundary and coarse family |
| **Pairwise Comparisons** | $O(N \times M)$ pairwise explosion across entire category | Filtered Top-$K$ candidates ($K=10\text{--}20$) per source material |
| **Text Similarity** | Character-level `difflib.SequenceMatcher` | Dense cosine similarity in semantic vector space |
| **Matching Engine** | Static linear weighting of regex attributes + difflib | Multi-stage: Vector candidate retrieval $\to$ Semantic reranking $\to$ Deterministic engineering gate |
| **Review Queue Volume** | Bloated with irrelevant pairs ($100\times$ catalog size) | Focused, high-precision recommendations ($5\times\text{--}10\times$ catalog size) |
| **Explainability** | Hardcoded template string ("Same valve type and size") | Multi-dimensional structured evidence: Attribute match matrix + Semantic score + Conflict diagnosis |

---

## 4. Division of Responsibilities

To maintain absolute reliability and safety, boundaries between AI, deterministic software, and human operators are rigidly enforced:

```text
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│     AI LAYER            │     │   DETERMINISTIC LAYER   │     │      HUMAN LAYER        │
│   (Semantic Advisory)   │     │  (Engineering Authority)│     │  (Governance Authority) │
├─────────────────────────┤     ├─────────────────────────┤     ├─────────────────────────┤
│ • Messy text parsing    │     │ • Hard conflict checks  │     │ • Review uncertain cases│
│ • Abbreviation mapping  │     │ • Cross-CPSE isolation  │     │ • Validate POTENTIAL rec│
│ • Word-order invariance │     │ • Self-match prevention │     │ • Execute OVERRIDE      │
│ • Dense embeddings      │     │ • Category constraints  │     │ • Execute UNMAP         │
│ • Cosine similarity     │     │ • Identity key hashing  │     │ • Resolve edge cases    │
│ • Top-K candidate search│     │ • Unique active mapping │     │ • Provide domain reasons│
│ • Semantic reranking    │     │ • Audit log persistence │     │ • Audit oversight       │
│ • Similarity evidence   │     │ • DB transaction safety │     │                         │
└─────────────────────────┘     └─────────────────────────┘     └─────────────────────────┘
```

### 4.1 What AI Handles
- **Language Understanding**: Resolves syntactic variations (e.g. `"BALL VLV DN50"` vs `"VALVE, BALL, 2 IN"`).
- **Domain Synonymy**: Maps abbreviations (`SS`, `C.S.`, `WCB`, `NPT`, `SW`, `150#`) to semantic concepts.
- **Semantic Similarity**: Calculates dense cosine similarity capturing engineering proximity even with varied vocabulary.
- **Candidate Filtering**: Quickly surfaces the top 10–20 most plausible cross-CPSE candidates from thousands of catalog items.
- **Ranking**: Sorts candidate materials by multi-token semantic affinity.

### 4.2 What Deterministic Software Handles
- **Hard Engineering Invariants**: Evaluates whether pressure ratings (150# vs 300#), sizes (DN50 vs DN100), body metallurgy (Carbon Steel vs SS316), or functional categories conflict.
- **Safety Gate**: Any detected technical conflict **instantly forces the classification to `DIFFERENT`**, overriding any AI similarity score, no matter how high.
- **Identity & Provenance**: Generates immutable `identity_key` strings and national codes.
- **Enterprise Isolation**: Guarantees that `candidate.id != source.id` and `candidate.cpse_id != source.cpse_id`.
- **State Integrity**: Enforces that each material has at most one active mapping, records complete before/after audit states, and guarantees transaction rollback on errors.

### 4.3 What Humans Handle
- **Review Queue Resolution**: Inspects recommendations classified as `POTENTIALLY_EQUIVALENT` (e.g., complete specifications on one material but missing trim on another).
- **Governance Actions**: Authorizes `ACCEPT`, `REJECT`, `MARK_DIFFERENT`, `UNMAP`, or `OVERRIDE` with mandatory structured reasoning.

---

## 5. Solving the Review Queue Combinatorial Explosion

### 5.1 The Root Cause in v1.0-stable
In the current deterministic implementation, `generate_candidates` queries:
```python
query = db.query(Material).filter(
    Material.id != source.id,
    Material.cpse_id != source.cpse_id,
    Material.category == source.category
)
if source.valve_type:
    query = query.filter((Material.valve_type == source.valve_type) | (Material.valve_type.is_(None)))
```
When an enterprise ingests 100 valves into a database with 1,000 existing valves from other CPSEs, the system generates up to:
$$100 \times 1000 = 100,000 \text{ pairwise comparisons!}$$

Even when 95% are classified as `DIFFERENT`, hundreds of tenuous or incomplete items flood the Review Queue as `POTENTIALLY_EQUIVALENT`, making human verification overwhelming.

### 5.2 The AI Solution: Dense Vector Candidate Retrieval
The target AI pipeline introduces a two-tier retrieval architecture:
1. **Tier 1: Dense Vector Retrieval (Top-$K$)**:
   - Each material has a pre-computed 384-dimensional vector embedding.
   - When a material is matched, a fast vector similarity search identifies only the top $K$ candidates (default $K=15$) from other CPSEs with cosine similarity above a candidate threshold ($\tau_{cand} \ge 0.60$).
   - This cuts candidate generation from $O(N \times M)$ down to $O(N \times K)$, reducing candidate volume by **95% to 98%**.
2. **Tier 2: AI-Assisted Reranking & Engineering Gate**:
   - Only the retrieved top-$K$ candidates are passed to the engineering validation engine.
   - Irrelevant pairs (e.g. 1/2" needle valve vs 24" gate valve) are pruned in Tier 1 before ever generating a database recommendation.
   - The Review Queue contains only genuine potential equivalents and actionable comparisons.

---

## 6. Model Strategy & Technical Feasibility

### 6.1 Semantic Embedding: `sentence-transformers/all-MiniLM-L6-v2`

The system selects `all-MiniLM-L6-v2` as the primary dense semantic embedding model.

#### Technical Specifications
- **Architecture**: 6-layer MiniLM transformer with 384-dimensional output embeddings.
- **Parameters**: 22.7 Million parameters.
- **Model Size on Disk**: ~80 MB (PyTorch / ONNX format).
- **Max Sequence Length**: 256 tokens (ample for material descriptions, which average 10–35 tokens).
- **Execution Environment**: 100% CPU inference; no GPU or CUDA required.
- **Inference Latency**: ~15ms per description on standard x86/ARM CPU cores; ~100ms for a batch of 32 items.
- **Process Memory Footprint**: ~180MB RAM when loaded as a singleton.
- **Determinism**: Produces identical floating-point vectors for identical inputs across runs.

#### Domain Feasibility & Limitations
- **General Strengths**: Excellent sentence-level semantic understanding, word-order invariance, handling of punctuation and word permutations.
- **Domain Limitations**: It is pre-trained on general English corpora (MS MARCO, SNLI, Wikipedia, Reddit). It does **not** inherently know that "WCB" is cast carbon steel or that "NPT" is an American National Standard Taper Pipe Thread.
- **Engineering Mitigation**: Raw descriptions are pre-processed by a domain-aware normalizer before embedding (e.g. expanding known abbreviations in an embedding input string: `"VALVE NEEDLE 1/2 IN SS316 6000PSI NPT (STAINLESS STEEL, THREADED CONNECTION)"`), ensuring high semantic vector alignment without requiring expensive fine-tuning.

### 6.2 Attribute Extraction Strategy: Hybrid Approach

We evaluated four options for technical attribute extraction:

| Approach | Latency | Dependency Footprint | Accuracy on Slang | Failure Mode | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Pure Regex** | $< 1$ms | Zero | Low (fails on new patterns) | Silent missing data | **Baseline (v1.0)** |
| **B. Local NLP / Spacy NER** | $15\text{--}30$ms | Medium (~150MB) | Moderate | Misclassification | **Considered** |
| **C. External LLM (API)** | $800\text{--}2500$ms| Low code, High runtime | High | API timeout / Network break / Cost | **Optional Fallback Only** |
| **D. Hybrid (Enhanced Rule + Local Embeddings + Pluggable LLM fallback)** | $2\text{--}20$ms | Controlled (~200MB) | High | Graceful degradation to deterministic baseline | **SELECTED STRATEGY** |

#### Why the Hybrid Architecture Wins
1. **Speed & Determinism**: 90% of industrial descriptions follow common patterns and can be extracted deterministically in $<2$ms.
2. **Offline & Self-Contained**: The core system runs locally and in air-gapped test environments without cloud API keys.
3. **Pluggable Architecture**: An optional, provider-agnostic LLM interface (e.g., supporting Google Gemini, OpenAI, or local Ollama) can be configured for complex unparsed strings, while never becoming a single point of failure.

---

## 7. No Premature Machine Learning Classifier

> [!WARNING]
> **ARCHITECTURAL BAN: DO NOT TRAIN OR FINE-TUNE CLASSIFIERS AT THIS STAGE**

We explicitly forbid training custom ML models (e.g. XGBoost, Random Forest, or fine-tuning transformer weights) on the current synthetic demo dataset.

### Why This is an Engineering Rule:
1. **Severe Dataset Scarcity**: The demo dataset contains synthetic records designed for functional testing, not statistical model training.
2. **Spurious Correlations**: A classifier trained on small datasets memorizes arbitrary artifacts (e.g. associating the string `CPSE-A` with specific labels) rather than learning general engineering principles.
3. **Loss of Explainability**: A black-box classifier cannot provide the strict legal and audit guarantees required by government procurement oversight.
4. **The Proper Path**: Custom fine-tuning will only be considered in Phase 6 after hundreds of authentic human reviewer decisions have been logged in `AuditLog` to form an authenticated ground-truth corpus.

---

## 8. Success Criteria

### Quantitative Metrics
1. **Candidate Volume Reduction**: Reduce generated match recommendations per import by $\ge 80\%$ compared to the $O(N \times M)$ baseline.
2. **Review Queue Precision**: At least 80% of recommendations in the Review Queue represent genuine semantic candidates rather than totally unrelated items.
3. **Harmonization Recall**: 100% of exact technical equivalents (identical physical attributes with scrambled text) must achieve $\ge 0.88$ confidence and qualify for `SAME`.
4. **Zero Safety Overrides**: 0.00% rate of hard engineering conflicts classified as `SAME`.
5. **Inference Latency**: Batch vector embedding and matching of 100 materials must complete in $< 10$ seconds on CPU.

### Qualitative Metrics
- **Reviewer Trust**: Human operators can clearly understand *why* materials were paired via the structured evidence view.
- **Zero Regressions**: 100% pass rate on all 131 baseline tests in `v1.0-stable`.

---

## 9. Non-Goals (Strictly Excluded from Scope)

To maintain focus and avoid scope creep, the following are explicitly declared non-goals:
- **No SAP / ERP Connectors**: We do not build BAPI, RFC, or live ERP integration pipelines.
- **No Chatbots / Conversational UIs**: OneMate is an operational data catalog, not a conversational assistant.
- **No Heavy Distributed Infrastructure**: No Kubernetes clusters, no Kafka brokers, no Celery task workers, no Redis clusters for this MVP phase.
- **No Vendor Lock-in**: No proprietary vector databases (e.g. Pinecone). Vector operations run in-process or via standard PostgreSQL extensions.

---

## 10. Upgrade Roadmap Summary

```text
Phase 0: Architecture Freeze & Safety Guardrails (CURRENT)
   ↓
Phase 1: Semantic Embedding & Offline Profiling Engine
   ↓
Phase 2: Dense Vector Candidate Retrieval (Top-K)
   ↓
Phase 3: Deep Attribute Extraction & Semantic Reranking
   ↓
Phase 4: Structured AI Evidence & Review Queue Integration
   ↓
Phase 5: Golden Benchmark Evaluation & Threshold Calibration
   ↓
Phase 6: Performance Optimization, In-Memory Caching & Production Hardening
```

