# OneMate AI Coding Rules & Development Guidelines

> **DOCUMENT CLASSIFICATION: MANDATORY DEVELOPER & AGENT STANDARD**  
> **Status:** Active Standard  
> **Target Audience:** All Software Engineers and AI Coding Agents Working on OneMate  
> **Enforcement:** Automated Pre-Commit Gates & Peer Review

---

## 1. Developer & Agent Standard Operating Procedure (SOP)

Every coding agent or developer contributing to OneMate must strictly follow this **13-Step Workflow**:

```text
  [1] Read AI Architecture & Guardrail Docs
          ↓
  [2] Inspect Relevant Existing Code
          ↓
  [3] Explicitly Identify Target Files
          ↓
  [4] State Proposed Change & Rationale
          ↓
  [5] Implement Smallest Coherent Diff
          ↓
  [6] Author Unit / Regression Tests
          ↓
  [7] Run Focused Pytest on New Tests
          ↓
  [8] Run Complete 131+ Backend Pytest Suite
          ↓
  [9] Run Frontend Typecheck & Build (if UI touched)
          ↓
  [10] Execute git diff --check (Whitespace/Formatting)
          ↓
  [11] Inspect git diff for Accidental Changes
          ↓
  [12] Formulate Precise Verification Report
          ↓
  [13] STOP. Do NOT Commit/Push Without Instruction.
```

---

## 2. Core Architectural & Code Hygiene Rules

### Rule 1: Preserve Baseline Contracts & Invariants
- Existing API route signatures (`/api/v1/...`), request schemas, and response formats must remain backward-compatible with `v1.0-stable`.
- Never alter the behavior of existing working endpoints without explicit architectural authorization.
- Never weaken or bypass the **Cardinal Law** (engineering conflicts unconditionally override AI similarity).

### Rule 2: Service Layer Separation (The Modular Monolith)
- AI functionality must reside within the dedicated package: `backend/app/services/ai/`.
  - `embedding.py`: Vector generation and model lifecycle.
  - `retrieval.py`: Vector similarity, indexing, and candidate filtering.
  - `profiling.py`: NLP tokenization, entity parsing, and material profile construction.
  - `validation.py`: Deterministic engineering validation and conflict detection.
- Core business orchestration remains in:
  - `normalization.py`: Orchestrates ingestion normalization and audit emission.
  - `matching.py`: Orchestrates candidate retrieval, scoring, and classification.
  - `harmonization.py`: Manages national catalog deduplication and mapping.
  - `review.py`: Governs human reviewer state transitions and audit logging.
- **Never** put transformer loading code, neural network inference, or vector math directly into FastAPI endpoint files (`app/api/v1/endpoints/*.py`) or database models (`app/models.py`).

### Rule 3: Singleton Model Management (No Per-Request Loading)
- Transformer models (`all-MiniLM-L6-v2`) must be initialized **exactly once** at application startup or via a thread-safe singleton.
- **NEVER** instantiate `SentenceTransformer(...)` inside an API endpoint, loop, or request handler. Instantiating a model per request introduces 1.5s+ latency and quickly exhausts server memory.

### Rule 4: Graceful Degradation & Failure Isolation
- AI services must be wrapped in structured try/except blocks.
- If the embedding model fails to infer or a vector search encounters an issue, the system must **gracefully degrade** to the deterministic baseline matching logic without throwing an unhandled HTTP 500 error.
- All AI failures must be logged via Python's standard `logging` module with stack traces.

### Rule 5: Strict Typing & Documentation Standards
- Every new Python function and class must include complete type annotations:
  ```python
  from typing import List, Optional, Tuple, Dict, Any

  def compute_similarity(
      source_vector: List[float],
      candidate_vectors: List[List[float]]
  ) -> List[float]:
      """Computes cosine similarity between source and candidates."""
      ...
  ```
- Docstrings must clearly specify: Purpose, Parameters, Returns, Raises, and Complexity.

### Rule 6: Zero Fake AI
- Absolute zero tolerance for fabricated AI metrics:
  - No `random.uniform(0.85, 0.99)` to simulate confidence.
  - No hardcoded similarity floats passed off as neural network outputs.
  - No claiming a model is "fine-tuned" when using off-the-shelf pre-trained weights.
  - If a model output is unavailable, return `None` or an explicit `confidence: 0.0`.

### Rule 7: Backend Authority
- The backend is the sole authority for:
  - Similarity scores
  - Matching classifications
  - Confidence levels
  - National Material code generation
  - Governance decisions
- The frontend is an **operational display and command interface**. The client must never calculate matching scores, invent national codes, or dictate classification thresholds.

---

## 3. Dependency Management Protocol

Every new dependency added to `backend/pyproject.toml` incurs maintenance overhead, container size expansion, and memory usage.

### Adding a Dependency Requires:
1. **Clear Justification**: Why built-in Python or existing packages cannot accomplish the task.
2. **Resource Footprint**: Disk size, transitive dependencies, and resident memory impact.
3. **Pinned Specification**: Exact version constraints (`>= X.Y.Z, < A.B.C`).
4. **License Compatibility**: Permissive open-source license (MIT, Apache 2.0, BSD).

### Approved AI Dependencies:
- `sentence-transformers>=2.7.0` (or pure `onnxruntime>=1.18.0` + `tokenizers>=0.19.0` for ultra-lean deployment).
- `numpy>=1.26.0` (for vectorized cosine similarity).

### Prohibited Dependencies:
- Unnecessary full-stack frameworks (e.g. LangChain, LlamaIndex) that obscure low-level control.
- Heavy distributed orchestrators (Celery, Ray, Spark) for MVP scope.
- Cloud vector database SDKs (Pinecone, Weaviate) when PostgreSQL or in-memory search suffices.

---

## 4. Testing & Verification Gates

### Test-Driven Development (TDD) Required
1. For every AI feature or bugfix, author a corresponding test file in `backend/tests/`:
   - Unit tests for token parsing (`test_ai_profiling.py`).
   - Unit tests for vector embedding and cosine similarity (`test_ai_embedding.py`).
   - Integration tests for candidate retrieval and engineering safety (`test_ai_matching.py`).
2. **Never delete or comment out existing tests**.
3. All 131 baseline tests must pass without exception:
   ```bash
   cd backend && pytest -v
   ```
4. Frontend integrity must be validated whenever UI files are touched:
   ```bash
   cd frontend && npx tsc --noEmit && npm run build
   ```
5. Clean code formatting:
   ```bash
   git diff --check
   ```

---

## 5. Security & Privacy Guardrails

1. **No Secrets in Code**: API keys, database credentials, and reviewer tokens must load via `pydantic-settings` from environment variables.
2. **No Data Leakage**: Sensitive CPSE financial terms or supplier proprietary details in `raw_source_data` must not be logged to application standard out.
3. **Deterministic Query Parameters**: All database interactions must use SQLAlchemy ORM or parameterized queries to prevent SQL injection.

