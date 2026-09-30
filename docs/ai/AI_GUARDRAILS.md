# OneMate AI Guardrails: Non-Negotiable System Invariants

> **DOCUMENT CLASSIFICATION: MANDATORY SECURITY & SAFETY POLICY**  
> **Status:** Active Standard / Immutable Invariants  
> **Authority:** Lead AI Systems Architect  
> **Applicability:** All AI, NLP, Matching, Harmonization, and Review Operations

---

## 1. The Cardinal Law of OneMate

```text
╔═════════════════════════════════════════════════════════════════════════════════╗
║                             THE CARDINAL LAW                                    ║
║                                                                                 ║
║   AI semantic similarity MUST NEVER override a hard engineering conflict.      ║
║                                                                                 ║
║   No matter how high the embedding cosine similarity (even 0.999),             ║
║   if an irreconcilable physical engineering difference exists,                 ║
║   the match verdict is unconditionally DIFFERENT.                               ║
╚═════════════════════════════════════════════════════════════════════════════════╝
```

---

## 2. Five Pillars of Guardrails

```text
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│     DATA        │ │      AI         │ │    MATCHING     │ │   GOVERNANCE    │ │   DEVELOPMENT   │
│  GUARDRAILS     │ │   GUARDRAILS    │ │   GUARDRAILS    │ │   GUARDRAILS    │ │   GUARDRAILS    │
├─────────────────┤ ├─────────────────┤ ├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│• Immutable raw  │ │• Genuine models │ │• No self match  │ │• Review queue   │ │• No test deletes│
│• Provenance     │ │• No fake scores │ │• No same CPSE   │ │• Idempotent     │ │• Clean diffs    │
│• Namespace isol │ │• No hallucinate │ │• Hard conflicts │ │• Block conflicts│ │• No silent drift│
│• No fabrication │ │• Traceable ver  │ │• UNKNOWN ≠ wild │ │• Audit every act│ │• Monolith bound │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## 3. Pillar I: Data Guardrails

1. **Raw Source Immutability**:
   - The database fields `Material.source_material_code`, `Material.source_description`, `Material.source_uom`, and `Material.raw_source_data` are **write-once, immutable records**.
   - Under no circumstances may an AI service, normalization function, or database migration alter, overwrite, or truncate raw uploaded enterprise data.
2. **Zero Attribute Fabrication**:
   - The AI system must **never invent, synthesize, or hallucinate** an engineering attribute.
   - If a source description reads `"GATE VALVE 2 IN CS"`, the trim material is `None` (UNKNOWN). The AI is strictly forbidden from guessing `SS316` or `SS304` merely because it is common or would facilitate a match.
3. **Strict CPSE Namespace Isolation**:
   - Every material record belongs permanently to its parent CPSE (`Material.cpse_id`). Materials from one CPSE cannot be reassigned or blended into another CPSE namespace.
4. **Preservation of Enterprise Material Codes**:
   - Harmonization creates a link (`MaterialNationalMapping`) to a `NationalMaterial`. It **never** replaces, renames, or deletes the original CPSE item code.

---

## 4. Pillar II: AI & Model Integrity Guardrails

1. **Genuine Model Outputs Only (Zero Fake AI)**:
   - Every semantic similarity score and vector embedding must be calculated by an actual executing neural network (e.g. `sentence-transformers/all-MiniLM-L6-v2`).
   - Hardcoded similarity floats, simulated scores, random number generators, and mocked AI responses are **strictly prohibited** in production code.
2. **Zero Unsupported AI Claims**:
   - Documentation, logs, and code comments must never claim a model is "fine-tuned" unless actual fine-tuning was performed, evaluated, and versioned.
   - The current embedding model must be explicitly declared as:
     `Pre-trained sentence-transformers/all-MiniLM-L6-v2`.
3. **Model Traceability & Versioning**:
   - Every calculated vector embedding and match recommendation must record the exact model identifier and timestamp:
     `{"model": "all-MiniLM-L6-v2", "version": "v2.2.0", "engine": "cpu-onnx"}`.
4. **Explicit Uncertainty Representation**:
   - When an AI model encounters ambiguous text, low token confidence, or conflicting tokens, it must explicitly output `UNKNOWN` or flag `CONFLICTING`.
   - Low model confidence must lower the overall recommendation score and route the material to human review.

---

## 5. Pillar III: Matching & Safety Guardrails

### Concrete Engineering Invariants (Absolute Incompatibilities)

The following attribute mismatches constitute **hard engineering conflicts** and unconditionally produce `DIFFERENT`:

| Attribute Category | Source Specification | Candidate Specification | Verdict | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **Pressure Rating** | `CLASS150` (150#) | `CLASS300` (300#) | **DIFFERENT** | Severe overpressure failure hazard |
| **Pressure Rating** | `3000PSI` | `6000PSI` | **DIFFERENT** | Incompatible pressure boundary |
| **Nominal Size** | `DN50` (2") | `DN100` (4") | **DIFFERENT** | Physical piping dimensional incompatibility |
| **Functional Category** | `VALVE` | `PUMP` | **DIFFERENT** | Categorical equipment difference |
| **Valve Type** | `BALL VALVE` | `GATE VALVE` | **DIFFERENT** | Different flow mechanics and application |
| **Body Metallurgy** | `CARBON_STEEL` (WCB)| `SS316` (Stainless) | **DIFFERENT** | Corrosion resistance / metallurgy conflict |
| **Trim Metallurgy** | `SS304` | `SS316` | **DIFFERENT** | Pitting and sour-service resistance difference |
| **Connection Face** | `RF` (Raised Face) | `SOCKET_WELD` | **DIFFERENT** | Mechanical joint vs welded joint mismatch |

### Invariant Checks

1. **Self-Match Prohibition**:
   $$\forall m \in \text{Materials}: \quad \text{candidate}(m) \ne m \quad (\text{i.e. } \text{cand.id} \ne \text{src.id})$$
2. **Same-CPSE Prohibition**:
   $$\forall m_{src}, m_{cand}: \quad \text{cand.cpse\_id} \ne \text{src.cpse\_id}$$
3. **UNKNOWN Is Not A Wildcard**:
   - `UNKNOWN` represents a missing specification.
   - `UNKNOWN` $\ne$ `KNOWN_VALUE`.
   - `UNKNOWN` $\ne$ `UNKNOWN` (two materials with missing trim cannot be presumed identical).
4. **No Semantic Monarchy**:
   - High vector similarity ($S_{sem} \ge 0.95$) provides **zero authorization** to waive missing attributes or override hard conflicts.

---

## 6. Pillar IV: Governance & Review Guardrails

1. **Human Review for Uncertainty**:
   - Any match exhibiting missing attributes or moderate confidence ($0.50 \le \text{Score} < 0.88$) must be classified as `POTENTIALLY_EQUIVALENT` and placed in the Review Queue. It can never be auto-harmonized.
2. **Idempotent Human Acceptance**:
   - If an operator clicks `ACCEPT` on a recommendation that is already active, the backend returns a successful idempotent response without creating duplicate mapping rows or duplicate audit logs.
3. **Conflicting Remap Prevention**:
   - A material can have at most **one active mapping** (`status = 'ACTIVE'`).
   - If material $M_1$ is actively mapped to National Material $NM_1$, an attempt to accept recommendation $R_2$ pointing to $NM_2$ is blocked with HTTP 400.
   - The operator must explicitly execute `UNMAP` or `OVERRIDE`.
4. **Controlled Unmapping**:
   - The `UNMAP` action marks the active mapping `INACTIVE` and generates an audit record. The material can subsequently be accepted into a new mapping.
5. **Traceable Override**:
   - The `OVERRIDE` action allows authorized reviewers to link a material to an explicit `NationalMaterial`, automatically archiving the previous mapping with a detailed audit justification.
6. **Immutable Audit Trail**:
   - Every review action (`ACCEPT`, `REJECT`, `MARK_DIFFERENT`, `UNMAP`, `OVERRIDE`) must capture the reviewer token/actor, timestamp, before state, after state, and operator reason.

---

## 7. Pillar V: Development & Engineering Guardrails

1. **Test Preservation**:
   - Future AI developers are strictly forbidden from deleting, disabling (`@pytest.mark.skip`), or weakening any of the 131 existing baseline tests.
2. **No Silent Threshold Drift**:
   - Matching thresholds (`SCORE_THRESHOLD_SAME = 0.88`, `SCORE_THRESHOLD_POTENTIAL = 0.45`) are core business logic. They must not be adjusted without documented evaluation on benchmark datasets.
3. **No Uncontrolled Dependencies**:
   - Adding new Python packages requires explicit justification, memory impact assessment, and architecture approval.
4. **Modular Monolith Discipline**:
   - AI code must live cleanly inside `app/services/ai/`. Do not pollute API route handlers or database models with transformer code.

---

## 8. Failure Modes Catalog & Defenses

| Failure Mode | Root Cause | Detection Mechanism | System Defense & Fallback | User-Visible Behavior | Test Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Hallucinated Attributes** | Regex/LLM over-generalizes unstated details | Cross-validation against raw source tokens | Strip ungrounded attributes; set to `UNKNOWN` | Attribute marked as missing in UI | Test ungrounded description extraction |
| **Semantic False Positive** | High cosine similarity between different items (e.g. Ball vs Gate valve) | Stage 7 Deterministic Engineering Gate | Hard conflict detected; classification forced to `DIFFERENT` | Badge shows `DIFFERENT` with red conflict alert | Pairwise conflict test suite |
| **Semantic False Negative** | Unfamiliar phrasing yields low vector similarity | Attribute match score vs vector score divergence | Attribute match elevates score into `POTENTIALLY_EQUIVALENT` | Surfaced in Review Queue for human validation | Word-order permutation tests |
| **Abbreviation Ambiguity** | Token with multiple meanings (e.g. "CI" = Cast Iron vs Compression Ignition) | Contextual token window analysis | Require category confirmation before resolving ambiguous tokens | Leaves ambiguous token in explanation | Ambiguous abbreviation fixtures |
| **Unit Inconsistency** | Mix of inches, mm, and DN sizes | Regex unit detector | Canonicalize all linear dimensions to `DN` integers | Standardized DN display (e.g. `DN50 (2")`) | Size conversion unit tests |
| **Model Cold-Start Timeout**| Transformer weights loading on first request | FastAPI Lifespan singleton preloading | Model loaded at server launch before traffic acceptance | Instant API response; no request-time lag | Health check warmup test |
| **Memory Exhaustion (OOM)** | Transformer model exceeds worker RAM ceiling | Model weight quantization (ONNX / MiniLM) | 22M parameter ceiling; max batch size = 32 | Server stays well within 512MB RAM | Process memory profiling test |
| **Missing Model File** | Network down or HuggingFace unreachable | Local disk cache verification on startup | Fall back gracefully to `v1.0-stable` deterministic matching | Matching continues; warning logged in health check | Offline mode initialization test |

