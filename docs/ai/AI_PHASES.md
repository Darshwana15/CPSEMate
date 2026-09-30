# OneMate AI Implementation Roadmap: Structured Phases & Test Gates

> **DOCUMENT CLASSIFICATION: PHASED IMPLEMENTATION & VERIFICATION PLAN**  
> **Status:** Active Execution Plan  
> **Author:** Lead AI Systems Architect  
> **Baseline Recovery:** `v1.0-stable` (`d1f1d42`)  
> **Enforcement:** Strict Sequential Progression via Mandatory Test Gates

---

## 1. Roadmap Architecture & Execution Principles

To guarantee that the working MVP is never destabilized, the AI upgrade is partitioned into **seven discrete, strictly gated phases** (Phases 0 through 6).

```text
Phase 0: Architecture Freeze & Safety Guardrails (CURRENT)
   ↓ [TEST GATE 0: All docs approved, 131 tests pass]
Phase 1: Semantic Embeddings & Offline Material Profiling
   ↓ [TEST GATE 1: Vector generation & profile unit tests pass]
Phase 2: Dense Vector Candidate Retrieval (Top-K)
   ↓ [TEST GATE 2: Candidate search reduces pairwise volume >= 80%]
Phase 3: Deep Attribute Extraction & Semantic Reranking
   ↓ [TEST GATE 3: Word-order invariance verified, safety gate intact]
Phase 4: Structured AI Evidence & Review Queue Integration
   ↓ [TEST GATE 4: Frontend renders evidence matrix, 0 UI regressions]
Phase 5: Golden Benchmark Evaluation & Threshold Calibration
   ↓ [TEST GATE 5: 0.00% safety conflict override rate on golden suite]
Phase 6: Performance Optimization, In-Memory Caching & Production Hardening
   ↓ [TEST GATE 6: CPU inference latency < 15ms, memory < 250MB]
PRODUCTION RELEASE (v2.0-ai)
```

> [!IMPORTANT]
> **THE MANDATORY TEST GATE RULE**  
> No coding agent or engineer may begin work on Phase $N+1$ until all acceptance criteria and automated tests for Phase $N$ have passed with 100% verification.

---

## 2. Phase 0: Architecture Freeze & Safety Guardrails (CURRENT)

- **Objective**: Establish the complete architectural specification, safety guardrails, baseline verification, and development protocol before modifying any code.
- **Scope**:
  - Author `BASELINE.md`, `AI_UPGRADE_PLAN.md`, `AI_ARCHITECTURE.md`, `AI_GUARDRAILS.md`, `AI_CODING_RULES.md`, `AI_EVALUATION.md`, `AI_PHASES.md`.
  - Verify baseline working tree cleanliness on branch `ai-material-intelligence`.
- **Affected Files**: Documentation files in `docs/` and `docs/ai/` only.
- **Dependencies**: None.
- **Non-Goals**: No code changes, no dependency additions, no database alterations.
- **Test Gate 0**:
  1. All 7 documentation files exist and pass architectural review.
  2. Baseline tests pass: `pytest -v` $\to$ 131 passed.
  3. `git diff --check` passes with zero errors.
  4. Git status shows zero uncommitted application code modifications.

---

## 3. Phase 1: Semantic Embeddings & Offline Material Profiling

- **Objective**: Implement the core vector embedding service (`all-MiniLM-L6-v2`) and the structured `MaterialProfile` schema in isolation.
- **Scope**:
  - Add approved dependencies (`sentence-transformers>=2.7.0`, `numpy>=1.26.0`) to `backend/pyproject.toml`.
  - Create `backend/app/services/ai/embedding.py` with singleton model management and lifespan initialization.
  - Create `backend/app/services/ai/profiling.py` implementing the 4-state `MaterialProfile` and canonical text construction.
  - Unit-test vector generation, determinism, and normalization profile extraction without touching existing endpoints.
- **Files Likely Affected**:
  - `backend/pyproject.toml`
  - `backend/app/main.py` (lifespan model warmup)
  - `backend/app/services/ai/__init__.py`
  - `backend/app/services/ai/embedding.py` (NEW)
  - `backend/app/services/ai/profiling.py` (NEW)
  - `backend/tests/test_ai_embedding.py` (NEW)
  - `backend/tests/test_ai_profiling.py` (NEW)
- **Non-Goals**: Do not alter `matching.py` or `review.py`. Do not alter database tables.
- **Test Gate 1**:
  1. `pytest tests/test_ai_embedding.py`: Vector dimensions are exactly 384; normalized vectors have unit length ($\|\mathbf{v}\| = 1.0 \pm 10^{-5}$).
  2. `pytest tests/test_ai_profiling.py`: Extracts 4-state profiles across VALVE, PUMP, GASKET, FLANGE, BEARING, FASTENER.
  3. All 131 baseline tests continue to pass without modification.
  4. Server startup time overhead is $< 2.5$ seconds.

---

## 4. Phase 2: Dense Vector Candidate Retrieval (Top-K)

- **Objective**: Replace the unconstrained $O(N \times M)$ SQL candidate query with intelligent Top-$K$ dense vector retrieval, solving Review Queue combinatorial explosion.
- **Scope**:
  - Implement `backend/app/services/ai/retrieval.py`.
  - Compute candidate cosine similarity across pre-embedded materials.
  - Enforce cross-CPSE isolation (`cand.cpse_id != src.cpse_id`) and self-match exclusion (`cand.id != src.id`) in the vector retrieval filter.
  - Configure candidate cutoff threshold ($\tau_{cand} \ge 0.60$) and limit to top $K=15$ candidates.
  - Integrate retrieval service into `matching.generate_candidates()`.
- **Files Likely Affected**:
  - `backend/app/services/ai/retrieval.py` (NEW)
  - `backend/app/services/matching.py`
  - `backend/tests/test_ai_retrieval.py` (NEW)
  - `backend/tests/test_matching.py`
- **Non-Goals**: Do not change final classification formulas or thresholds yet.
- **Test Gate 2**:
  1. `pytest tests/test_ai_retrieval.py`: Verifies that vector retrieval returns top-$K$ cross-CPSE items.
  2. Verified reduction: Generated match recommendations decrease by $\ge 80\%$ on multi-material ingestion.
  3. Self-matching and same-CPSE matching remain 100% blocked.
  4. All existing matching regression tests pass.

---

## 5. Phase 3: Deep Attribute Extraction & Semantic Reranking

- **Objective**: Replace character-level `difflib.SequenceMatcher` with multi-token semantic similarity, and connect the deterministic engineering safety gate.
- **Scope**:
  - Implement `backend/app/services/ai/validation.py` containing explicit conflict checks (size, pressure, material, valve type, connection, trim).
  - Update `classify_match` in `backend/app/services/matching.py` to combine:
    - Attribute match score (weight: 0.60).
    - Dense vector semantic similarity $S_{sem}$ (weight: 0.40).
  - Enforce the **Cardinal Law**: Any hard conflict from `validation.py` overrides $S_{sem}$ and sets classification to `DIFFERENT` with confidence 0.0.
  - Enhance normalization parser with expanded engineering dictionary (PSI/PN pressure ratings, NPT/SW connections, exotic alloys).
- **Files Likely Affected**:
  - `backend/app/services/ai/validation.py` (NEW)
  - `backend/app/services/matching.py`
  - `backend/app/services/normalization.py`
  - `backend/tests/test_ai_validation.py` (NEW)
  - `backend/tests/test_normalization.py`
  - `backend/tests/test_matching.py`
- **Non-Goals**: No frontend changes yet.
- **Test Gate 3**:
  1. Word-order invariance test: `"BALL VALVE DN50 CS CL150 RF SS304"` vs `"VALVE, BALL, DN50, 150#, RF, CS, 304SS"` scores $S_{sem} \ge 0.90$ and classifies as `SAME`.
  2. Hard conflict test: `"BALL VALVE DN50 CL150 CS"` vs `"BALL VALVE DN50 CL300 CS"` receives $S_{sem} > 0.85$ but unconditionally classifies as `DIFFERENT`.
  3. All 131 baseline tests pass.

---

## 6. Phase 4: Structured AI Evidence & Review Queue Integration

- **Objective**: Expose multi-dimensional AI diagnostic evidence in the REST API and render it clearly in the Review Queue UI.
- **Scope**:
  - Update `MatchRecommendation.evidence` schema to store structured comparison JSON:
    - Semantic similarity float.
    - Pairwise attribute comparison matrix.
    - Explicit conflict list.
    - Missing attribute diagnostics.
  - Update `ReviewPage.tsx` to render the AI diagnostic card:
    - Semantic similarity gauge/badge.
    - Attribute match breakdown.
    - Conflict diagnostic warning.
  - Update `MatchingPage.tsx` to display vector scores alongside lexical attributes.
- **Files Likely Affected**:
  - `backend/app/schemas/material.py`
  - `backend/app/services/review.py`
  - `frontend/src/types/api.ts`
  - `frontend/src/pages/ReviewPage.tsx`
  - `frontend/src/pages/MatchingPage.tsx`
  - `frontend/src/components/matching/AttributeComparisonTable.tsx`
- **Non-Goals**: Do not turn UI into a consumer chatbot. Maintain high-density, professional engineering layout.
- **Test Gate 4**:
  1. Frontend typecheck passes: `npx tsc --noEmit`.
  2. Production build succeeds: `npm run build`.
  3. Review Queue renders side-by-side CPSE comparison, semantic score, and attribute breakdown cleanly without UI regressions.
  4. Human review actions (`ACCEPT`, `REJECT`, `MARK_DIFFERENT`, `UNMAP`, `OVERRIDE`) function flawlessly with audit trail.

---

## 7. Phase 5: Golden Benchmark Evaluation & Threshold Calibration

- **Objective**: Validate the complete end-to-end system against the Golden Benchmark Suite (True Positives, Hard Negatives, Asymmetric Incompletes, Disjoint Categories).
- **Scope**:
  - Create automated benchmark test script: `backend/tests/test_ai_golden_benchmarks.py`.
  - Evaluate accuracy, recall@15, precision on `SAME`, and noise reduction rate.
  - Calibrate classification thresholds ($\tau_{same} = 0.88$, $\tau_{pot} = 0.50$, $\tau_{cand} = 0.60$) based on empirical benchmark results.
- **Files Likely Affected**:
  - `backend/tests/test_ai_golden_benchmarks.py` (NEW)
  - `backend/app/services/matching.py` (threshold constants)
- **Non-Goals**: No model fine-tuning on synthetic data.
- **Test Gate 5**:
  1. **Conflict Override Rate is exactly 0.00%** across all hard negatives.
  2. Recall on true technical equivalents $\ge 95\%$.
  3. Total recommendations generated reduced by $\ge 80\%$ relative to `v1.0-stable`.
  4. 100% pass rate on all backend tests.

---

## 8. Phase 6: Performance Optimization, In-Memory Caching & Production Hardening

- **Objective**: Ensure lightning-fast execution, low memory footprint, and production robustness on Render and cloud platforms.
- **Scope**:
  - Add in-memory LRU embedding cache (avoids re-encoding identical material descriptions).
  - Profile resident memory (RSS) to guarantee $< 250\text{ MB}$ footprint.
  - Benchmark batch ingestion of 100 materials: must complete embedding + retrieval + matching in $< 10$ seconds on CPU.
  - Document deployment parameters for Render and verify pre-deploy migrations.
- **Files Likely Affected**:
  - `backend/app/services/ai/embedding.py`
  - `backend/app/core/config.py`
  - `docs/ai/AI_EVALUATION.md` (record benchmark numbers)
- **Non-Goals**: No distributed cache (Redis) required unless catalog exceeds 500,000 items.
- **Test Gate 6**:
  1. End-to-end pipeline benchmark passes performance requirements.
  2. Memory footprint remains safely below 512MB limit.
  3. Render build and start commands execute cleanly.

---

## 9. Database & Schema Policy

The AI upgrade is architected to **minimize database schema alterations**:
1. **Leveraging Existing JSONB Columns**:
   - `Material.normalized_attributes` already exists in `v1.0-stable` models as a `JSONB` column. The structured `MaterialProfile` will be persisted directly inside this column without requiring a database migration!
   - `MatchRecommendation.evidence` already exists as a `JSONB` column. The new structured AI evidence matrix will be persisted directly inside this column!
2. **Vector Storage Strategy**:
   - For Phase 1–5 (MVP scale: catalogs $< 10,000$ items), vector embeddings are cached in-memory and serialized as standard JSON arrays in `Material.normalized_attributes["embedding"]`.
   - If dedicated vector indexing (e.g. `pgvector`) is desired in Phase 6, it will be introduced via a dedicated, tested Alembic migration with an explicit downgrade script.

---

## 10. Rollback & Recovery Strategy

If an unforeseen defect occurs during any phase, recovery to `v1.0-stable` is instantaneous:

```bash
# Emergency rollback to known-good baseline:
git checkout v1.0-stable
cd backend && pytest -v
cd ../frontend && npm run build
```

Because all AI components are encapsulated in `app/services/ai/`, individual phases can also be reverted cleanly using Git without affecting the core database schema or baseline business logic.

