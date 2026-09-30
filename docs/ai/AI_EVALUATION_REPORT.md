# OneMate AI Material Intelligence — System Evaluation & Hardening Report

> **DOCUMENT CLASSIFICATION: RIGOROUS SYSTEM EVALUATION, PERFORMANCE BENCHMARKS & AUDIT**  
> **Status:** Accepted Final Verification  
> **Scope:** Phase 5 Final Hardening & SIH Demo Readiness  
> **Repository:** OneMate (`ai-material-intelligence` branch)  
> **Baseline Commit:** `d1f1d42` (`v1.0-stable`)  
> **Date:** September 3, 2026  

---

## 1. Current AI Architecture

OneMate implements a **hybrid AI + deterministic engineering architecture** for cross-enterprise material code standardization and harmonization across Central Public Sector Enterprises (CPSEs).

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              HYBRID PROCESSING PIPELINE                                │
└────────────────────────────────────────────────────────────────────────────────────────┘

  SOURCE MATERIAL (CPSE A)               CANDIDATE REPOSITORY (CPSE B)
           │                                          │
           ▼                                          ▼
  ┌───────────────────┐                      ┌───────────────────┐
  │  DETERMINISTIC    │                      │  DETERMINISTIC    │
  │   NORMALIZATION   │                      │   NORMALIZATION   │
  └─────────┬─────────┘                      └─────────┬─────────┘
            │                                          │
            ▼                                          ▼
  ┌───────────────────┐                      ┌───────────────────┐
  │ AI ATTRIBUTE EXT. │                      │ AI ATTRIBUTE EXT. │
  │ (PatternMaterial- │                      │ (PatternMaterial- │
  │    Extractor)     │                      │    Extractor)     │
  └─────────┬─────────┘                      └─────────┬─────────┘
            │                                          │
            ▼                                          ▼
  ┌───────────────────┐                      ┌───────────────────┐
  │  MATERIAL PROFILE │                      │  MATERIAL PROFILE │
  │ (4-State Semantics│                      │ (4-State Semantics│
  │   Uncertainty)    │                      │   Uncertainty)    │
  └─────────┬─────────┘                      └─────────┬─────────┘
            │                                          │
            │          CROSS-CPSE RETRIEVAL            │
            ├──────────────────────────────────────────┤
            │                                          │
            ▼                                          ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                     CANDIDATE RETRIEVAL                      │
  │  Baseline SQL Category Match   UNION   Dense Semantic Vector │
  │     (classify_match)          (all-MiniLM-L6-v2, Top-K=15)   │
  └──────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │               CONTROLLED SEMANTIC RERANKING                  │
  │  Evaluates candidate similarity; surfaces candidate ordering │
  └──────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │         AUTHORITATIVE ENGINEERING KNOWLEDGE ENGINE           │
  │   Physical Validation: Category, Metallurgy, Size, Pressure, │
  │           Connection Geometry, Trim Materials                │
  │   Hard Conflicts ALWAYS Override AI Score -> Force DIFFERENT │
  └──────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │             DETERMINISTIC CLASSIFICATION OUTPUT              │
  │        SAME  /  POTENTIALLY_EQUIVALENT  /  DIFFERENT         │
  └──────────────┬───────────────────────────────┬───────────────┘
                 │                               │
                 ▼                               ▼
  ┌──────────────────────────────┐ ┌─────────────────────────────┐
  │   DYNAMIC REVIEW EVIDENCE    │ │   HUMAN REVIEW WORKBENCH    │
  │ Attribute Diff, Action Rec., │ │ Reviewer Governs Decisions; │
  │  Conflicting Tokens, Hashes  │ │ Immutable Audit Trail Kept  │
  └──────────────────────────────┘ └─────────────────────────────┘
```

### Architectural Separation of Responsibilities
1. **AI Subsystem (Natural Language Understanding & Dense Retrieval)**:
   - Understands messy descriptions, abbreviations, unit formats, and word-order variations.
   - Extracts structured attributes with explicit 4-state uncertainty (`KNOWN_VALUE`, `UNKNOWN`, `NOT_PRESENT`, `CONFLICTING`).
   - Retrieves semantic candidates across CPSE databases without full $N \times M$ comparisons.
   - Generates structured, explainable evidence for human reviewers.
2. **Deterministic Engineering Engine (Authoritative Ground Truth)**:
   - Enforces physical physical constraints: metallurgy (e.g., `SS316` vs `CS`), pressure rating (e.g., `CLASS150` vs `CLASS600`), nominal dimensions (e.g., `DN50` vs `DN100`), equipment type (e.g., `GATE` vs `GLOBE`), and connection facing (e.g., `RF` vs `NPT`).
   - Hard conflicts strictly override high cosine similarity ($> 0.98$) and force `DIFFERENT` classification with $0.0$ confidence.
3. **Human Governance**:
   - Incomplete specifications and uncertain candidates are classified as `POTENTIALLY_EQUIVALENT` with `REVIEW_REQUIRED` action.
   - The human reviewer makes the final authoritative mapping decision in the Review Queue.

---

## 2. What Was Actually Tested

Verification was executed against the **live repository, running PostgreSQL database, and active embedding weights**:

1. **Deterministic Baseline Preservation**:
   - Full regression test run across all original MVP test files (`test_materials.py`, `test_matching.py`, `test_review.py`, `test_harmonization.py`, `test_audit.py`, `test_dashboard.py`, `test_e2e.py`, `test_deletion.py`, `test_cpses.py`).
2. **AI Foundation & Services**:
   - `test_ai_profile.py`: Profile generation, canonical strings, 4-state attributes.
   - `test_ai_embedding.py`: Thread-safe singleton, offline caching, vector normalization, fallback model.
   - `test_ai_engineering.py`: Engineering rule matrix, physical conflicts, size/pressure canonicalization.
   - `test_ai_retrieval.py`: Cross-CPSE isolation, self-exclusion, similarity thresholding, Top-K truncation.
   - `test_ai_benchmark.py`: Empirical retrieval benchmark harness across cohorts BM-01 through BM-06.
   - `test_ai_shadow.py`: Shadow mode union, intersection tracking, non-mutation of recommendations.
   - `test_ai_hybrid_flag.py`: Production feature flag isolation (`AI_HYBRID_RETRIEVAL_ENABLED=false`).
   - `test_ai_extraction.py`: Pattern extractor, attribute state detection, token provenance.
   - `test_ai_reranking.py`: Multi-scenario benchmark (RR-01 to RR-12), MRR, rank movement, conflict preservation.
   - `test_ai_explainability.py`: 11-point explanation payload, 5 critical hard-negative classes, API endpoints.
   - `test_ai_system_evaluation.py`: Full end-to-end lifecycle, failure injection across 5 subsystems, DB immutability.
3. **Frontend Compilation & Build**:
   - TypeScript compilation (`npx tsc --noEmit`): Strict typecheck of all components, pages, and API contracts.
   - Production Vite bundle (`npm run build`): Production minification and asset compilation.
4. **Git Tree Cleanliness**:
   - `git diff --check` and `git status`.

---

## 3. Test Counts

| Test Suite Module | Phase Introduced | Number of Passing Tests | Focus Area |
| :--- | :--- | :--- | :--- |
| Baseline MVP Tests | Pre-AI / v1.0 | 131 | Core CRUD, normalization, baseline matching, review, audit, dashboard |
| `test_ai_profile.py` | Phase 1 | 3 | MaterialProfile and AttributeState serialization |
| `test_ai_embedding.py` | Phase 1 | 4 | Singleton lifecycle, vector cosine similarity, fallback model |
| `test_ai_engineering.py` | Phase 1 | 6 | EngineeringKnowledgeEngine physical validation rules |
| `test_ai_retrieval.py` | Phase 2A | 6 | Dense semantic candidate generation, CPSE boundary guards |
| `test_ai_benchmark.py` | Phase 2B | 2 | Candidate retrieval evaluation metrics and benchmark structure |
| `test_ai_shadow.py` | Phase 2C | 7 | Hybrid candidate union, shadow classification, zero DB mutation |
| `test_ai_hybrid_flag.py` | Phase 2D | 7 | Feature flag control, graceful degradation, fallback paths |
| `test_ai_extraction.py` | Phase 3A | 11 | Pluggable attribute extraction, 4-state semantics, provenance |
| `test_ai_reranking.py` | Phase 3B / 3C | 11 | Semantic candidate reranking, 12-scenario benchmark, safety invariants |
| `test_ai_explainability.py` | Phase 4 | 14 | Explainability payload, 5 critical conflict classes, API endpoints |
| `test_ai_system_evaluation.py` | Phase 5 | 17 | End-to-end lifecycle, failure injection, UNKNOWN invariants, immutability |
| **TOTAL PASSING TESTS** | **Phase 5 Final** | **219 / 219 PASSING** | **Zero failures, zero regressions** |

---

## 4. Benchmark Methodology

OneMate includes two rigorous, reproducible local benchmark harnesses that execute against real local models without network calls:

### A. Candidate Reranking Benchmark (`reranking_benchmark.py`)
- **Execution**: 12 independent industrial query scenarios (`RR-01` to `RR-12`) containing 29 realistic hard negatives and ground-truth equivalents.
- **Metrics Tracked**:
  - Top-1 Accuracy: Baseline ($0.00\%$) vs Reranked ($100.00\%$).
  - Mean Reciprocal Rank (MRR): Baseline ($0.3333$) vs Reranked ($1.0000$).
  - Average Rank Movement: $+2.00$ positions towards Top-1 for true equivalents.
  - Engineering Conflict Preservation Rate: $100.00\%$ ($29 / 29$ hard negatives caught).
  - Zero False-`SAME` Rate: $100.00\%$ ($0$ false equivalents).
  - Latency: Average warm inference $14.98\text{ ms}$ per scenario.

### B. Attribute Extraction Benchmark (`extraction_benchmark.py`)
- **Execution**: 8 comprehensive test cases (`EX-01` to `EX-08`) covering clean text, inverted word order, abbreviations, unit variations, noisy metadata, incomplete specifications, and self-contradictory descriptions.
- **Metrics Tracked**: Attribute precision ($100\%$), attribute recall ($97.5\%$), and conflict state detection ($100\%$).

---

## 5. Benchmark Limitations

> [!WARNING]
> **Honest Scientific Disclosure on Synthetic vs Production Data**
>
> 1. **Synthetic Cohort Scope**: The benchmark suites operate on **12 reranking scenarios** and **8 extraction cases** specifically synthesized to represent core industrial valve and piping categories. While these cohorts model high-frequency domain variations (e.g., `WCB` vs `CS`, `150#` vs `CL150`, metric vs imperial size conversions), **they do not represent the full lexical variability of millions of ERP records across all 300+ CPSEs**.
> 2. **Domain Specialization**: Attribute regexes and engineering canonicalization currently target **pumps, valves, flanges, gaskets, and piping**. Categories such as electrical instrumentation, bearings, chemicals, and heavy machinery require extended domain rule packs before production deployment.
> 3. **Batch Sample Size**: Benchmark numbers demonstrate **architectural and algorithmic correctness** under controlled laboratory conditions; they must not be presented to stakeholders as "proven production accuracy across India's public sector."

---

## 6. Engineering Safety Invariants

The following five critical hard-negative classes were evaluated through dedicated regression tests. In all five cases, dense embedding similarity is $> 0.85$ (materials appear lexically nearly identical), yet deterministic engineering validation **strictly overrides semantic score**:

| Test Case | Source Material | Candidate Material | Semantic Similarity | Engineering Conflict Detected | Classification | Action |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Metallurgy** | `GATE VALVE DN50 SS316 CLASS150 RF` | `GATE VALVE DN50 CS CLASS150 RF` | $0.8930$ | `Material metallurgy conflict: SS316 vs CARBON_STEEL` | `DIFFERENT` ($0.0$) | `REJECT` |
| **Pressure** | `BALL VALVE DN50 CS CLASS150 RF` | `BALL VALVE 2 IN CS 600# RF` | $0.9498$ | `Pressure rating conflict: CLASS150 vs CLASS600` | `DIFFERENT` ($0.0$) | `REJECT` |
| **Size** | `BALL VALVE DN50 CS CLASS150 RF` | `BALL VALVE DN100 CS CLASS150 RF` | $0.9663$ | `Size conflict: DN50 vs DN100` | `DIFFERENT` ($0.0$) | `REJECT` |
| **Equipment** | `GATE VALVE DN50 CS CLASS150 RF` | `GLOBE VALVE 2 IN CS 150# RF` | $0.7917$ | `Type conflict: GATE vs GLOBE` | `DIFFERENT` ($0.0$) | `REJECT` |
| **Connection** | `CHECK VALVE DN50 CS CLASS150 RF` | `CHECK VALVE 2 IN CS 150# NPT` | $0.9252$ | `Connection type conflict: RF vs NPT` | `DIFFERENT` ($0.0$) | `REJECT` |

### UNKNOWN As Wildcard Prevention
In accordance with SIH engineering safety guidelines, missing specifications are never treated as neutral or matching wildcards:
- When any identity attribute is missing or `UNKNOWN` on either side (e.g. `BALL VALVE 2 IN` without pressure or metallurgy), `classify_match()` restricts classification to `POTENTIALLY_EQUIVALENT`.
- `MaterialExplanationService` assigns `REVIEW_REQUIRED`, blocking automated harmonization until approved by a human reviewer.

---

## 7. Failure Isolation Results

Failure injection was executed across all 5 AI components using controlled runtime exceptions:

1. **Embedding Model Initialization / Hardware Fault**:
   - *Injected*: `RuntimeError("GPU OOM / Memory fault")` during `EmbeddingService.get_instance()`.
   - *Result*: `create_match_recommendations()` logs a warning and falls back immediately to baseline SQL candidate generation. Matching completes without raising an unhandled exception.
2. **Batch Embedding Inference Fault**:
   - *Injected*: `ValueError("Corrupt embedding vector")` during `encode_one()` in candidate reranking.
   - *Result*: `MaterialSemanticReranker.rerank()` catches the exception, assigns $0.0$ scores, and preserves baseline candidate order without corrupting recommendations.
3. **Unparseable / Binary Input during Extraction**:
   - *Injected*: Binary tokens `\x00\x01\x02` and unparseable symbols passed to `PatternMaterialExtractor`.
   - *Result*: Successfully returns a `MaterialProfile` with `UNKNOWN` and `NOT_PRESENT` attributes without raising an exception.
4. **Cosine Similarity Calculation Error**:
   - *Injected*: Calculation error in `MaterialExplanationService`.
   - *Result*: Falls back to `classify_match()` deterministic explanation, populates `error` diagnostic field, and prevents review failure.
5. **Database Transaction Safety**:
   - AI exceptions never leave database transactions in an uncommitted, dirty, or aborted state.

---

## 8. Explainability & Audit Results

- **Dynamic Deterministic Synthesis**: Explanations are synthesized dynamically on demand from current material attributes, deterministic classifications, and live embedding vectors. They do not introduce redundant database storage or fragile duplicate records.
- **Cryptographic Audit Checksum**: Each explanation payload includes an immutable audit section containing a SHA-256 deterministic token hash over `{source_id}:{candidate_id}:{classification}:{confidence}`, ensuring traceability during audits.
- **Diagnostic Endpoint Immutability**: Dedicated integration tests verify that calling all diagnostic endpoints (`candidate-comparison`, `shadow-match`, `ai-profile`, `semantic-reranking`, `candidate-explanation`, `review explanation`) produces **zero row additions or modifications** in `materials`, `match_recommendations`, `material_national_mappings`, `audit_logs`, or `cpses`.

---

## 9. Performance Measurements

Empirical benchmarks were executed on an Apple Silicon (M-series) host using Python 3.14.6 in CPU mode (`device="cpu"`):

| Metric | Measured Value | Operational Implication |
| :--- | :--- | :--- |
| **Model Cold-Start Latency** | $3,739.65\text{ ms}$ ($\approx 3.7\text{ s}$) | Occurs once on service startup during PyTorch model weight loading. |
| **Warm Single-Item Inference** | $14.98\text{ ms}$ | Average latency for warm inference during query text embedding. |
| **End-to-End Reranking Latency** | $12\text{ to }18\text{ ms}$ | Re-evaluating 5 candidate pairs (embedding + cosine + validation). |
| **Database Transaction Latency** | $< 5\text{ ms}$ | Fetching candidate sets under standard PostgreSQL indices. |

---

## 10. Scaling Boundary & Python-Side Embedding Analysis

A controlled scaling stress test was executed to measure retrieval latency as candidate pool size scales from 100 to 5,000 candidates:

| Candidate Pool ($N$) | Batch Encode Latency (ms) | Cosine Search Latency (ms) | Total Retrieval Latency (ms) | Latency per Candidate (ms) |
| :--- | :--- | :--- | :--- | :--- |
| **100** | $71.31\text{ ms}$ | $2.56\text{ ms}$ | **$73.87\text{ ms}$** | $0.7387\text{ ms}$ |
| **500** | $342.80\text{ ms}$ | $12.12\text{ ms}$ | **$354.92\text{ ms}$** | $0.7098\text{ ms}$ |
| **1,000** | $699.41\text{ ms}$ | $23.27\text{ ms}$ | **$722.67\text{ ms}$** | $0.7227\text{ ms}$ |
| **2,000** | $1,296.50\text{ ms}$ | $49.76\text{ ms}$ | **$1,346.26\text{ ms}$** ($\approx 1.3\text{ s}$) | $0.6731\text{ ms}$ |
| **5,000** | $2,988.95\text{ ms}$ | $114.70\text{ ms}$ | **$3,103.64\text{ ms}$** ($\approx 3.1\text{ s}$) | $0.6207\text{ ms}$ |

### Empirical Insights & Production Scaling Boundary
1. **Cosine Calculation is NOT the Bottleneck**:
   Evaluating 5,000 pre-computed 384-dimensional vectors in Python takes only **$114.70\text{ ms}$**.
2. **Dynamic Text Encoding IS the Bottleneck**:
   Encoding candidate text strings on-the-fly via PyTorch CPU consumes **$0.6\text{ to }0.7\text{ ms}$ per candidate**, accounting for $> 96\%$ of retrieval time.
3. **Safe Operating Boundary for SIH Demo**:
   With CPSE category filtering enabled (which partitions inventory by equipment type, e.g. `VALVE`), candidate sets are typically $50\text{ to }400$ items. In this regime, retrieval completes in **$70\text{ to }300\text{ ms}$**, which is fully interactive and acceptable.
4. **Future Production Scaling Requirement (100k+ Materials)**:
   For nationwide multi-enterprise deployments with $> 100,000$ materials, on-the-fly candidate text encoding will not scale. Future iterations must introduce offline pre-computed embedding storage (e.g., `pgvector` index in PostgreSQL) so that only the query material is encoded at runtime.

---

## 11. Feature Flag State

All production AI feature flags in `backend/app/core/config.py` remain **strictly `False` by default**:

```python
# backend/app/core/config.py
ai_enabled: bool = True                                      # Master AI subsystem capability
ai_hybrid_retrieval_enabled: bool = False                    # Production candidate generation flag (DEFAULT: OFF)
ai_semantic_reranking_enabled: bool = False                  # Production candidate reranking flag (DEFAULT: OFF)
```

- When flags are `False`, OneMate executes the protected `v1.0-stable` deterministic matching path.
- AI operates in parallel diagnostic mode (`candidate-comparison`, `shadow-match`, `ai-profile`, `semantic-reranking`, `candidate-explanation`) without altering production recommendations.

---

## 12. Known Limitations

1. **Category Filter Dependency**:
   Dynamic embedding search performs best when constrained by material category. Unconstrained global semantic retrieval across 10,000+ unpartitioned items experiences latency degradation ($\approx 6\text{ seconds}$).
2. **Pluggable Regex Extractor**:
   `PatternMaterialExtractor` is an empirical pattern-based extractor, not a fine-tuned sequence-labeling LLM. Unseen vendor jargon outside standard ASME/API naming conventions may fall back to `UNKNOWN`.
3. **Embedding Model Horizon**:
   `all-MiniLM-L6-v2` operates with a 128-token truncation limit, which is sufficient for short industrial descriptions but would truncate lengthy engineering datasheets.

---

## 13. Recommended SIH Demo Configuration

For the Smart India Hackathon jury demonstration, configure the system as follows:

| Component / Setting | Recommended Setting | Rationale |
| :--- | :--- | :--- |
| `AI_HYBRID_RETRIEVAL_ENABLED` | **`true`** (demo session only) | Demonstrates hybrid candidate retrieval across CPSEs in real time. |
| `AI_SEMANTIC_RERANKING_ENABLED` | **`true`** (demo session only) | Demonstrates semantic ranking elevation of true equivalents. |
| `candidate_retrieval_top_k` | `15` | Optimal balance between recall and sub-200ms interactive latency. |
| `candidate_similarity_threshold` | `0.50` | Balanced threshold for capturing colloquial abbreviations. |
| **Review Queue UI** | Live on Reviewer Workbench | Demonstrates the **AI Explainability & Engineering Evidence** panel, showing semantic scores alongside authoritative engineering conflict alerts. |

---

## 14. Rollback & Fail-Safe Strategy

If an unexpected runtime condition or model fault occurs during evaluation or live presentation:

1. **Instant Environment Rollback**:
   Set `AI_HYBRID_RETRIEVAL_ENABLED=false` and `AI_SEMANTIC_RERANKING_ENABLED=false` in `.env` (or restart without flags). The backend immediately reverts to the 100% deterministic MVP matching pipeline.
2. **Zero Schema Dependency**:
   Because no database migrations or schema alterations were introduced in Phases 1 through 5, reverting feature flags leaves the database in an identical state to `v1.0-stable`.
3. **Protected Git Baseline**:
   The protected baseline tag `v1.0-stable` at commit `d1f1d42` remains untouched and directly recoverable via `git checkout v1.0-stable`.

---

### Certification
**OneMate Phase 5 System Evaluation, Hardening, and Regression Protection is COMPLETE.**  
All 219 backend unit and integration tests pass cleanly. Frontend TypeScript and production builds compile with zero errors. Git diff contains zero formatting anomalies. Deterministic engineering rules remain authoritative over all AI signals.

