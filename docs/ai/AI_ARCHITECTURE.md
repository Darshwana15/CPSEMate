# OneMate AI Architecture: Technical Specification

> **DOCUMENT CLASSIFICATION: DETAILED SYSTEM DESIGN**  
> **Status:** Architecture Freeze / Pre-Implementation  
> **Author:** Lead AI Systems Architect  
> **Target Version:** OneMate v2.0 (AI-Driven Material Intelligence)  
> **Architecture Pattern:** Modular Monolith (FastAPI + PyTorch/ONNX CPU Engine)

---

## 1. Architectural Overview & System Topology

OneMate v2.0 maintains a clean, robust **Modular Monolith** architecture. We deliberately avoid distributed microservices, network serialization overhead, message broker complexities (Kafka/RabbitMQ), and asynchronous worker nodes (Celery).

All AI components reside as high-performance, in-process Python services within the existing FastAPI backend, executing CPU-optimized vectorized inference and leveraging PostgreSQL for persistence.

```text
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FASTAPI APPLICATION CORE                                │
│                                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │                               REST API ENDPOINTS (/api/v1)                        │  │
│  │    cpses/  │  materials/  │  reviews/  │  national-materials/  │  audit/  │  dash │  │
│  └─────────────────────────────────────────┬─────────────────────────────────────────┘  │
│                                            │                                            │
│  ┌─────────────────────────────────────────▼─────────────────────────────────────────┐  │
│  │                               BUSINESS SERVICE LAYER                              │  │
│  │                                                                                   │  │
│  │   ┌────────────────────────┐                   ┌──────────────────────────────┐   │  │
│  │   │  normalization.py      │                   │  matching.py                 │   │  │
│  │   │  • Orchestration       │                   │  • Orchestration             │   │  │
│  │   │  • Audit event emitter │                   │  • Classification threshold  │   │  │
│  │   └───────────┬────────────┘                   │  • Recommendation factory    │   │  │
│  │               │                                └──────────────┬───────────────┘   │  │
│  │               │                                               │                   │  │
│  │  ┌────────────▼───────────────────────────────────────────────▼────────────────┐  │  │
│  │  │                   NEW: AI SUBSYSTEM (app/services/ai/)                      │  │  │
│  │  │                                                                             │  │  │
│  │  │   ┌─────────────────────┐  ┌────────────────────┐  ┌─────────────────────┐  │  │  │
│  │  │   │ profiling.py        │  │ embedding.py       │  │ retrieval.py        │  │  │  │
│  │  │   │ • Token parsing     │  │ • all-MiniLM-L6-v2 │  │ • Vector similarity │  │  │  │
│  │  │   │ • Attribute profile │  │ • Singleton loader │  │ • Top-K cross-CPSE  │  │  │  │
│  │  │   │ • Provenance map    │  │ • In-memory cache  │  │ • Candidate pruning │  │  │  │
│  │  │   └─────────────────────┘  └────────────────────┘  └─────────────────────┘  │  │  │
│  │  │                                                                             │  │  │
│  │  │   ┌──────────────────────────────────────────────────────────────────────┐  │  │  │
│  │  │   │ validation.py: ENGINEERING KNOWLEDGE & VALIDATION ENGINE             │  │  │  │
│  │  │   │ • Authoritative hard engineering conflict diagnosis                  │  │  │  │
│  │  │   │ • Physical attribute equivalence rules (size, class, metallurgy)     │  │  │  │
│  │  │   │ • Asymmetric missing attribute evaluation                            │  │  │  │
│  │  │   │ • Structured comparison evidence generator                           │  │  │  │
│  │  │   └──────────────────────────────────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                                   │  │
│  │   ┌────────────────────────┐                   ┌──────────────────────────────┐   │  │
│  │   │  harmonization.py      │                   │  review.py                   │   │  │
│  │   │  • Deterministic ID key│                   │  • Governance state machine  │   │  │
│  │   │  • Safe AUTO_SAME      │                   │  • ACCEPT/REJECT/OVERRIDE    │   │  │
│  │   └────────────────────────┘                   └──────────────────────────────┘   │  │
│  └─────────────────────────────────────────┬─────────────────────────────────────────┘  │
│                                            │                                            │
│  ┌─────────────────────────────────────────▼─────────────────────────────────────────┐  │
│  │                                DATA PERSISTENCE LAYER                             │  │
│  │   SQLAlchemy 2.0 ORM  ──►  PostgreSQL (Supabase compatible)                       │  │
│  │   [material, cpse, national_material, match_recommendation, mapping, audit_log]   │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Target Decision Flow

The OneMate material intelligence architecture executes in a strict, audited 10-stage decision pipeline where AI language comprehension is paired with an authoritative engineering gate:

```text
       RAW MATERIAL DESCRIPTION
                  ↓
    AI/NLP MATERIAL UNDERSTANDING
                  ↓
     STRUCTURED MATERIAL PROFILE
                  ↓
         SEMANTIC EMBEDDING
                  ↓
   CROSS-CPSE CANDIDATE RETRIEVAL
                  ↓
  AI SEMANTIC RERANKING / COMPARISON
                  ↓
ENGINEERING KNOWLEDGE & VALIDATION ENGINE
                  ↓
      SAME / POTENTIAL / DIFFERENT
                  ↓
    HUMAN REVIEW FOR UNCERTAINTY
                  ↓
          NATIONAL MATERIAL
                  ↓
           IMMUTABLE AUDIT
```

---

## 3. Detailed Stage Specifications

### Stage 1: Ingestion Input
- **Input**: Raw uploaded file payload (CSV / XLSX) containing `source_material_code`, `source_description`, `source_uom`, and optional `source_specifications`.
- **Output**: Persisted `Material` record with unmodified source columns and `raw_source_data` (JSONB).
- **Responsibility**: Ingestion validation, duplicate check within CPSE, file size checks.
- **Service Boundary**: `app/services/ingestion.py`.
- **Authority**: Authoritative.
- **Failure Mode**: Rejection with clear HTTP 400 validation error (e.g. unsupported file format or missing required columns).

---

### Stage 2: AI/NLP Text Parsing & Normalization
- **Input**: `Material.source_description` and `Material.source_specifications`.
- **Output**: Normalized tokens, resolved abbreviations, standardized casing and units.
- **Responsibility**:
  - Convert disparate abbreviation tokens to standard technical expressions (`"WCB"` $\to$ `"CARBON_STEEL"`, `"316SS"` $\to$ `"SS316"`, `"6000#"` / `"6000PSI"` $\to$ `"6000PSI"`, `"2 IN"` / `"2\""` $\to$ `"DN50"`).
  - Multi-category entity classification (VALVE, PUMP, GASKET, FLANGE, BEARING, FASTENER).
- **Service Boundary**: `app/services/ai/profiling.py`.
- **Authority**: Advisory (produces normalized text for profile extraction).
- **Failure Mode**: Falls back to raw cleaned source text without failing the transaction.

---

### Stage 3: Structured Material Profile
- **Input**: Parsed token stream from Stage 2.
- **Output**: Canonical `MaterialProfile` dataclass and JSONB payload stored in `Material.normalized_attributes`.
- **Responsibility**:
  - Populate structured attributes: `category`, `sub_type`, `size`, `body_material`, `pressure_class`, `connection_type`, `trim_material`, `normalized_uom`.
  - Maintain the **Four-State Value Representation** (see Section 4).
- **Service Boundary**: `app/services/ai/profiling.py`.
- **Authority**: Advisory until verified by engineering rules.
- **Failure Mode**: Inability to identify an attribute marks it explicitly as `NOT_PRESENT` or `UNKNOWN`. It **never** guesses an attribute to force a match.

---

### Stage 4: Dense Semantic Embedding
- **Input**: Canonical description string generated from the material profile:
  `"{category} {sub_type} {size} {body_material} {pressure_class} {connection_type} {trim_material}"`.
- **Output**: 384-dimensional dense vector of 32-bit floats ($\mathbb{R}^{384}$).
- **Responsibility**: High-dimensional semantic representation capturing conceptual equivalence regardless of word order.
- **Service Boundary**: `app/services/ai/embedding.py`.
- **Authority**: Advisory.
- **Failure Mode**: If the transformer fails to load or infer, log an error and fall back to lexical matching (`difflib`) without halting system operation.

---

### Stage 5: Dense Vector Candidate Retrieval (Top-$K$)
- **Input**: Source material vector $\mathbf{v}_{src} \in \mathbb{R}^{384}$ and source `cpse_id`.
- **Output**: List of at most $K$ candidates (default $K=15$) from other CPSEs whose cosine similarity exceeds the candidate threshold ($\tau_{cand} \ge 0.60$).
- **Responsibility**: Prune the candidate search space from $O(N \times M)$ down to $O(N \times K)$, preventing review queue explosion.
- **Enforced SQL Filtering**:
  ```sql
  WHERE candidate.id != :source_id
    AND candidate.cpse_id != :source_cpse_id
    AND candidate.category = :source_category
  ```
- **Service Boundary**: `app/services/ai/retrieval.py`.
- **Authority**: Advisory (filters candidates for engineering review).
- **Failure Mode**: If no vectors are present in the catalog, falls back to deterministic candidate retrieval.

---

### Stage 6: AI Reranking & Comparison Scoring
- **Input**: Source `Material` and retrieved candidate `Material`.
- **Output**: Continuous semantic similarity score $S_{sem} \in [0.0, 1.0]$.
- **Responsibility**: Compute exact cosine similarity:
  $$S_{sem} = \frac{\mathbf{v}_{src} \cdot \mathbf{v}_{cand}}{\|\mathbf{v}_{src}\| \|\mathbf{v}_{cand}\|}$$
- **Service Boundary**: `app/services/ai/retrieval.py`.
- **Authority**: Advisory.
- **Failure Mode**: Default to 0.0 if vectors are missing.

---

### Stage 7: Engineering Knowledge & Validation Engine (Authoritative Deterministic Gate)
- **Input**: Source profile, candidate profile, and AI semantic score $S_{sem}$.
- **Output**: Boolean `is_safe`, list of `hard_conflicts`, list of `matching_attributes`, list of `missing_attributes`.
- **Responsibility**:
  - The **Sole Authoritative Gate** for physical engineering equivalence.
  - Enforces physical engineering equivalence rules:
    - Metallurgy / grade conflicts: `SS316 != Carbon Steel`, `SS304 != SS316`.
    - Dimensional conflicts: `DN50 (2 IN) != DN100 (4 IN)`.
    - Pressure rating conflicts: `150 PSI != 6000 PSI`, `CLASS150 != CLASS300`.
    - Category / functional conflicts: `BALL VALVE != GATE VALVE`, `VALVE != PUMP`.
    - Connection conflicts: `NPT != FLANGED` when defined as incompatible by piping standards.
  - **Invariants**:
    - `UNKNOWN`/`NULL` is NOT a wildcard.
    - AI must NEVER invent a missing engineering attribute.
    - AI similarity MUST NEVER override a deterministic hard conflict.
- **Service Boundary**: `app/services/ai/validation.py`.
- **Authority**: **AUTHORITATIVE**. Overrides all AI scores unconditionally.
- **Failure Mode**: Any validation exception or unresolvable conflict results in `DIFFERENT`.

---

### Stage 8: Three-Way Classification Engine
- **Input**: Safety evaluation from Stage 7 and semantic score $S_{sem}$.
- **Output**: Match classification: `SAME`, `POTENTIALLY_EQUIVALENT`, or `DIFFERENT`, with confidence score $\in [0.0, 1.0]$ and structured explanation.
- **Decision Logic**:
  ```python
  if hard_conflicts:
      classification = "DIFFERENT"
      confidence = 0.0
      explanation = f"Hard engineering conflicts detected: {'; '.join(hard_conflicts)}."
  else:
      # Attribute agreement weight (0.60) + Semantic similarity weight (0.40)
      composite_score = (attribute_score * 0.60) + (S_sem * 0.40)

      if attribute_score == 1.0 and S_sem >= 0.85:
          classification = "SAME"
          confidence = max(composite_score, 0.90)
          explanation = "Exact technical match across all engineering attributes with high semantic similarity."
      elif composite_score >= 0.50:
          classification = "POTENTIALLY_EQUIVALENT"
          confidence = composite_score
          explanation = f"Plausible equivalent with missing or unconfirmed attributes ({', '.join(missing_attrs)})."
      else:
          classification = "DIFFERENT"
          confidence = composite_score
          explanation = "Low semantic and attribute correlation."
  ```
- **Service Boundary**: `app/services/matching.py`.
- **Authority**: Authoritative recommendation output.
- **Failure Mode**: On error, defaults to `POTENTIALLY_EQUIVALENT` for human review.

---

### Stage 9: Harmonization & Human Review
- **Input**: `MatchRecommendation` record.
- **Output**: If `SAME` and complete $\to$ Automated harmonization via `harmonize_material`. If `POTENTIALLY_EQUIVALENT` or `DIFFERENT` $\to$ Available in Review Queue.
- **Responsibility**: Governed review operations (`ACCEPT`, `REJECT`, `MARK_DIFFERENT`, `UNMAP`, `OVERRIDE`).
- **Service Boundary**: `app/services/harmonization.py` and `app/services/review.py`.
- **Authority**: Authoritative.
- **Failure Mode**: Atomic database rollback on conflict.

---

### Stage 10: National Material Catalog
- **Input**: Confirmed match or authorized override.
- **Output**: Persisted `NationalMaterial` and active `MaterialNationalMapping`.
- **Responsibility**: Canonical registry maintenance, deduplication via unique `identity_key`.
- **Service Boundary**: `app/services/harmonization.py`.
- **Authority**: Authoritative.

---

### Stage 11: Immutable Audit Trail
- **Input**: Every state transition event across normalization, matching, review, and mapping.
- **Output**: Permanent `AuditLog` row with actor, action, before_state, after_state, and reason.
- **Responsibility**: Legal compliance, audit trail, government traceability.
- **Service Boundary**: `app/models.py:AuditLog`.
- **Authority**: Authoritative and append-only.

---

## 4. The Canonical Material Profile Schema

To avoid loss of engineering precision, the AI system introduces a structured intermediate representation:

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List

class AttributeState(str, Enum):
    KNOWN_VALUE = "KNOWN_VALUE"           # Explicitly specified and recognized
    UNKNOWN = "UNKNOWN"                   # Explicitly stated as unknown/unspecified in source text
    NOT_PRESENT = "NOT_PRESENT"           # Completely omitted from source text
    CONFLICTING_VALUE = "CONFLICTING"     # Text contains self-contradictory claims (e.g. "DN50 4 IN")

@dataclass
class ProfileAttribute:
    value: Optional[str]                  # Standardized canonical value (e.g. "DN50", "SS316")
    raw_token: Optional[str]              # Verbatim token from text (e.g. "2 INCH", "316SS")
    state: AttributeState                 # Four-state discriminator
    confidence: float                     # Extraction confidence [0.0 - 1.0]

@dataclass
class MaterialProfile:
    category: ProfileAttribute
    sub_type: ProfileAttribute            # e.g. valve_type, pump_type, flange_type
    size: ProfileAttribute
    body_material: ProfileAttribute
    pressure_class: ProfileAttribute
    connection_type: ProfileAttribute
    trim_material: ProfileAttribute
    normalized_uom: ProfileAttribute
    additional_attributes: Dict[str, ProfileAttribute] = field(default_factory=dict)
    extraction_confidence: float = 0.0
    provenance_tokens: List[str] = field(default_factory=list)
```

### Four-State Value Handling Rules
1. `KNOWN_VALUE`: Participates directly in identity calculation and conflict checking.
2. `UNKNOWN`: Explicitly unassigned. Can never match a `KNOWN_VALUE`. Does not conflict with another `UNKNOWN`, but produces `POTENTIALLY_EQUIVALENT` instead of `SAME`.
3. `NOT_PRESENT`: Missing information. Handled as unknown. Cannot be used to declare equivalence.
4. `CONFLICTING_VALUE`: Immediate internal contradiction flag. Blocks automated harmonization.

---

## 5. Deep Technical Evaluation of `all-MiniLM-L6-v2`

| Characteristic | Specification / Metric | System Impact |
| :--- | :--- | :--- |
| **Model Name** | `sentence-transformers/all-MiniLM-L6-v2` | Hosted on HuggingFace Hub; cacheable locally |
| **Parameters** | 22,713,216 parameters (~22.7 M) | Lightweight, fits easily in low-tier RAM |
| **Embedding Dimensions** | 384 dimensions (float32) | $384 \times 4 \text{ bytes} = 1.536 \text{ KB}$ per vector |
| **Storage for 100K Items**| $100,000 \times 1.536 \text{ KB} \approx 150 \text{ MB}$ | Easily fits entirely in memory |
| **Disk Size** | 80–90 MB | Negligible container image footprint |
| **CPU Inference Latency** | Single item: 12–18 ms; Batch of 32: 85–110 ms | Fast enough for real-time synchronous UI requests |
| **Process Memory (RAM)** | ~180 MB RSS | Safe for Render free/hobby tiers (512MB limit) |
| **Cold Start Overhead** | 1.2 to 1.8 seconds on application startup | Loaded once via FastAPI lifespan singleton |
| **Runtime Dependency** | `sentence-transformers` OR pure `onnxruntime` | Pure ONNX runtime option reduces dependencies by 70% |

### In-Process Singleton & Thread Safety
The model is loaded **once** at server startup using FastAPI Lifespan management:

```python
# Conceptual Architecture for app/services/ai/embedding.py
class EmbeddingService:
    _instance = None
    _model = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def encode(self, texts: List[str]) -> List[List[float]]:
        if self._model is None:
            self.initialize()
        return self._model.encode(texts, batch_size=32, normalize_embeddings=True).tolist()
```

---

## 6. Attribute Extraction Options & Architecture Decision

### Option A: Enhanced Rule-Based Parser (Enhanced Baseline)
- **Mechanism**: Expanded regex tables with complete engineering dictionaries (ANSI sizes, PSI/PN pressure, exotic alloys, NPT/SW connections).
- **Pros**: 0ms latency, zero memory, 100% deterministic, 0 dependencies.
- **Cons**: Still misses completely irregular or unmodeled phrasing.

### Option B: Local Transformer NER (e.g. Spacy / RoBERTa-NER)
- **Mechanism**: Sequence labeling token-by-token.
- **Pros**: Good at finding entities in novel sentence structures.
- **Cons**: Heavy memory usage (+400MB), requires manual training and annotated tokens, unpredictable edge-case outputs.

### Option C: External LLM API (e.g. Gemini 1.5 Flash / OpenAI GPT-4o-mini)
- **Mechanism**: Zero-shot prompt requesting JSON profile.
- **Pros**: Extremely high linguistic comprehension of messy descriptions.
- **Cons**: Network dependency, 1000ms+ latency, financial API costs, data privacy issues with government records, potential for hallucinated attributes.

### Option D: The Hybrid Architecture (SELECTED)
- **Phase 1-3 Execution**: High-coverage deterministic parser (handles 90% of materials deterministically in $<2$ms) + `all-MiniLM-L6-v2` dense semantic embeddings.
- **Optional Fallback**: Pluggable LLM interface reserved solely for complex unparsed strings, guarded by strict schema validation.
- **Benefit**: Ensures the system remains 100% operable offline, deterministic, and lightning-fast, with no cloud dependencies required to pass all tests.

---

## 7. AI Evidence Structure

The Review Queue UI requires clear, explainable diagnostic evidence:

```json
{
  "semantic_similarity": 0.942,
  "attribute_summary": {
    "category": { "source": "VALVE", "candidate": "VALVE", "match": true },
    "valve_type": { "source": "NEEDLE", "candidate": "NEEDLE", "match": true },
    "size": { "source": "DN15", "candidate": "DN15", "match": true },
    "body_material": { "source": "SS316", "candidate": "SS316", "match": true },
    "pressure_class": { "source": "6000PSI", "candidate": "6000PSI", "match": true },
    "connection_type": { "source": "NPT", "candidate": "NPT", "match": true },
    "trim": { "source": "SS316", "candidate": "SS316", "match": true }
  },
  "conflicts": [],
  "missing_attributes": [],
  "verdict": {
    "classification": "SAME",
    "confidence": 0.965,
    "rationale": "Identical engineering attributes and high semantic vector similarity (0.942)."
  }
}
```

