# OneMate Baseline (v1.0-stable)

> **RECOVERY BASELINE DECLARATION**
> This document describes the recovery baseline for AI development.
> Stable tag: `v1.0-stable` · Stable commit: `d1f1d42` · Branch: `ai-material-intelligence`
> The baseline represents the known-good, fully verified deterministic OneMate implementation.
> All future AI enhancements must preserve the invariants, governance behaviors, and test baselines defined here.

---

## 1. Executive Summary

OneMate is an enterprise platform developed for **Smart India Hackathon 2026 (SIH26099)**:
*AI-Driven Standardization & Harmonization of Material Codes Across CPSEs*.

The platform harmonizes fragmented material catalogs from multiple Central Public Sector Enterprises (CPSEs) into a unified, canonical **National Material Catalog** while preserving original source provenance, deterministic engineering safety, human governance decisions, and an immutable audit trail.

As of `v1.0-stable` (commit `d1f1d42`), OneMate functions as a robust, fully deterministic modular monolith. The system enforces strict engineering rules, isolates CPSE namespaces, prevents self- and same-CPSE matching, provides complete review workflows, and passes 100% of automated backend and frontend quality checks.

---

## 2. Current Architecture & Tech Stack

### 2.1 Technology Stack

| Layer | Component | Version / Specification |
| :--- | :--- | :--- |
| **Backend Framework** | FastAPI | `>= 0.115.0` (Python 3.12) |
| **ASGI Server** | Uvicorn (Standard) | `>= 0.30.0` |
| **Database & ORM** | PostgreSQL / SQLAlchemy | PostgreSQL 15+, SQLAlchemy `>= 2.0.30` |
| **Database Migrations** | Alembic | `>= 1.13.0` |
| **Data Validation** | Pydantic / Pydantic-Settings | Pydantic `>= 2.7.0` |
| **Data Ingestion** | Pandas / OpenPyXL | Pandas `>= 2.2.0`, OpenPyXL `>= 3.1.0` |
| **Testing Suite** | Pytest / HTTPX | Pytest `>= 8.2.0`, HTTPX `>= 0.27.0` |
| **Frontend Framework** | React + TypeScript | React 18, TypeScript 5.5, Vite 5 |
| **Styling & Icons** | Tailwind CSS / Lucide React | Tailwind 3.4, Lucide React |

### 2.2 Repository Layout

```text
onemate/
├── backend/
│   ├── alembic/
│   │   ├── versions/           # Schema migration history
│   │   └── env.py
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py         # DB session, reviewer token dependencies
│   │   │   └── v1/
│   │   │       ├── api.py      # Router aggregation
│   │   │       └── endpoints/  # cpses, materials, reviews, national_materials, audit, dashboard
│   │   ├── core/
│   │   │   └── config.py       # Pydantic Settings, DB URLs, Reviewer tokens
│   │   ├── db/
│   │   │   ├── base.py         # Declarative Base
│   │   │   └── session.py      # Engine and SessionLocal
│   │   ├── models.py           # SQLAlchemy entity definitions
│   │   ├── schemas/            # Pydantic request/response models
│   │   └── services/           # Business logic: ingestion, normalization, matching, harmonization, review
│   ├── pyproject.toml          # Dependency declarations and build configuration
│   └── tests/                  # 131 automated unit and integration tests
├── frontend/
│   ├── src/
│   │   ├── api/client.ts       # Typed API client
│   │   ├── components/         # Shared UI, modal, and table components
│   │   ├── context/            # CpseContext enterprise state
│   │   ├── pages/              # Dashboard, Materials, Matching, Review, NationalCatalog, Audit
│   │   └── types/api.ts        # TypeScript API interfaces
│   ├── package.json
│   └── vite.config.ts
└── docs/                       # Architectural specifications and scope documents
```

---

## 3. Current Verified Capabilities

### 3.1 Backend Functionality

1. **CPSE Management**:
   - Create, list, retrieve, and delete CPSE namespaces.
   - Strict foreign key isolation preventing orphan records.

2. **Material Ingestion**:
   - Multi-format ingestion (`.csv` and `.xlsx`) with strict 5MB payload limit.
   - Dual-layer storage: Original source code, description, specifications, and UOM are preserved verbatim alongside full `raw_source_data` (JSONB).

3. **Deterministic Normalization**:
   - Rule-based text cleaning: uppercase conversion, whitespace collapse, punctuation handling.
   - Deterministic UOM normalization (`EA`, `NOS`, `PCS` → `EACH`).
   - Category detection across 6 supported industrial categories: `VALVE`, `PUMP`, `GASKET`, `FLANGE`, `BEARING`, `FASTENER`.
   - Explicit valve attribute extraction via regex:
     - `valve_type`: BALL, GATE, GLOBE, BUTTERFLY, CHECK, NEEDLE, PLUG, DIAPHRAGM.
     - `size`: Standardized to DN notation (e.g., 2" → DN50, 50MM → DN50).
     - `body_material`: Standardized to CARBON_STEEL, STAINLESS_STEEL, SS304, SS316, CAST_IRON.
     - `pressure_class`: Standardized to CLASS150, CLASS300, CLASS600, etc.
     - `connection_type`: RF, SOCKET_WELD, BUTT_WELD, THREADED, FLANGED.
     - `trim`: Explicit SS304, SS316, Stellite extraction; isolates trim from body material.
   - Missing attributes remain strictly `None` (NULL) — `UNKNOWN` is never treated as a wildcard.
   - Normalization creates an immutable `AuditLog` entry detailing before/after state.

4. **Global Cross-CPSE Matching**:
   - Candidate Generation (`generate_candidates`):
     - Explicitly excludes self-matching (`candidate.id != source.id`).
     - Explicitly excludes same-CPSE matching (`candidate.cpse_id != source.cpse_id`).
     - Matches across identical categories.
   - Comparison Engine (`classify_match`):
     - Hard technical conflict detection across primary attributes (size, pressure, material, valve type, connection, trim).
     - Text similarity scoring via `difflib.SequenceMatcher` (weight: 0.28).
     - Attribute match scoring (weight: 0.12 per matching attribute).
     - Three-way classification:
       - `SAME`: Score $\ge 0.88$ AND zero missing attributes AND zero conflicts.
       - `POTENTIALLY_EQUIVALENT`: Score $\ge 0.45$ with non-conflicting missing attributes.
       - `DIFFERENT`: Hard conflict detected OR score $< 0.45$.

5. **Harmonization & National Catalog Creation**:
   - Safe `AUTO_SAME` mapping for complete, unconflicted `SAME` matches.
   - Deterministic `identity_key` construction (`CATEGORY|TYPE|SIZE|BODY|CLASS|CONN|TRIM|UOM`).
   - Re-use before create: Existing National Materials sharing the deterministic `identity_key` are reused.
   - Enforces unique active mapping per material (`status = 'ACTIVE'`).

6. **Human Review Governance**:
   - Role-protected review queue authenticated via `X-Reviewer-Token`.
   - Actions: `ACCEPT`, `REJECT`, `MARK_DIFFERENT`, `UNMAP`, `OVERRIDE`.
   - Idempotent `ACCEPT` on already active mappings for the same recommendation.
   - Hard conflict blocking on `ACCEPT` (e.g. attempting to accept DN50 vs DN80 is rejected with HTTP 400).
   - Asymmetric missing attribute blocking on `ACCEPT` (requires explicit `OVERRIDE`).
   - Controlled `UNMAP` endpoint and action marking mappings `INACTIVE` with audit trail.
   - `OVERRIDE` cleanly supersedes previous active mappings.

7. **Audit Trail & Observability**:
   - Centralized, immutable `audit_log` table tracking: `actor`, `action`, `entity_type`, `entity_id`, `before_state`, `after_state`, `reason`, `created_at`.
   - Operational dashboard tracking total materials, CPSEs, mapped rates, pending reviews, and CPSE breakdown.

### 3.2 Frontend Functionality

- **Dashboard**: High-level KPI strip, CPSE breakdown, operational throughput.
- **Material Explorer**: Enterprise catalog browsing, row inspector, per-material/batch normalization.
- **Matcher**: Single-item matching playground, candidate comparison, raw JSON payload inspection.
- **Review Queue**: Side-by-side comparison cards displaying clear CPSE identity badges (`CPSE-A` vs `CPSE-B`), attribute diff table, action modals with mandatory reason logging.
- **National Registry**: Canonical material catalog viewing and mapping history inspection.
- **Audit Viewer**: Chronological log of all administrative, automated, and reviewer actions.

---

## 4. Verification Baseline

As of commit `d1f1d42`, the repository satisfies all quality gates:

```text
============================= test session starts ==============================
platform darwin -- Python 3.12.x, pytest-8.2.x
rootdir: /Users/rohinishsingh/onemate/backend
collected 131 items

tests/test_audit.py ..............                                       [ 10%]
tests/test_cpse.py ...............                                       [ 22%]
tests/test_dashboard.py ........                                         [ 28%]
tests/test_e2e.py .                                                      [ 29%]
tests/test_harmonization.py ............                                 [ 38%]
tests/test_ingestion.py .................                                [ 51%]
tests/test_matching.py ....................                              [ 66%]
tests/test_national_materials.py .........                               [ 73%]
tests/test_normalization.py ......................                       [ 90%]
tests/test_review.py .............                                       [100%]

======================== 131 passed, 1 warning in 14.82s ========================
```

Frontend Quality Baseline:
- `npx tsc --noEmit`: 0 errors (100% type-safe).
- `npm run build`: Production bundle generated without warnings or circular dependencies.
- `git diff --check`: 0 whitespace or formatting errors.

---

## 5. Protected Invariants (Non-Negotiable)

The following architectural invariants are permanently established and must never be broken by future AI enhancements:

1. **Self-Match Prohibition**: A material must NEVER be matched against itself (`candidate.id != source.id`).
2. **Same-CPSE Prohibition**: Materials from the same CPSE must NEVER be matched against each other (`candidate.cpse_id != source.cpse_id`).
3. **Engineering Conflict Primacy**: Hard technical attribute conflicts (e.g. CLASS150 vs CLASS300, DN50 vs DN100, SS304 vs SS316, BALL vs GATE) unconditionally produce `DIFFERENT`. Semantic text similarity can NEVER override a hard conflict.
4. **Missing Information Discipline**: `NULL` or missing values represent unknown specifications, NOT wildcards. Incomplete materials can never be auto-harmonized as `SAME`.
5. **Source Immutability**: Uploaded raw data (`source_material_code`, `source_description`, `source_uom`, `raw_source_data`) must NEVER be overwritten or mutated.
6. **Unique Active Mapping**: A material may have at most ONE active mapping (`status = 'ACTIVE'`) to a National Material at any time.
7. **Audit Immutability**: All state transitions (normalization, mapping, review actions, unmapping) must generate permanent, append-only `AuditLog` records.
8. **Recommendation-Specific Review State**: Review queue mappings are strictly tied to specific recommendations (`recommendation_id`).
9. **Review Idempotency & Conflict Guard**: Re-accepting an active recommendation is an idempotent no-op; accepting a conflicting recommendation without unmapping is rejected.
10. **Backend Decision Authority**: The backend alone determines scores, classifications, identity keys, national codes, and governance actions. The frontend and AI layers are advisory.

---

## 6. Current Technical Limitations (Why AI is Needed)

While the `v1.0-stable` baseline is deterministic, safe, and robust, it possesses inherent mechanical limitations that motivate the AI upgrade:

### 6.1 Normalization & Attribute Extraction Bottlenecks

1. **Brittle Regex Pattern Matching**:
   - The regex engine expects predictable phrasing. Minor token reorderings or informal descriptions cause extraction failures.
   - Example: `"VALVE, NEEDLE, 1/2 INCH, SS316, 6000PSI, NPT"` fails to parse pressure (`6000PSI`) and connection (`NPT`) because the regex only recognizes `CLASS/CL` and `RF/SW/BW/THREADED`.
2. **Incomplete Engineering Lexicon**:
   - Size parsing only handles 14 hardcoded fractional inches. Unlisted sizes (`1/4"`, `3/8"`, `5/16"`, `1-1/4"`, `3-1/2"`) become `None`.
   - Pressure parsing does not support imperial PSI ratings (`3000PSI`, `6000PSI`, `10000PSI`) or metric PN ratings (`PN16`, `PN40`, `PN100`).
   - Connection types miss standard piping terms: `NPT`, `BSPT`, `BSPP`, `RTJ`, `WAFER`, `LUG`.
   - Material grades only cover basic carbon steel, cast iron, and 300-series stainless. Exotic alloys (`Monel 400`, `Inconel 625`, `Hastelloy C276`, `Duplex 2205`, `Super Duplex 2507`, `Alloy 20`, `PTFE`, `Bronze`) are missed.
3. **Category Attribute Depth**:
   - Categories outside `VALVE` (PUMP, GASKET, FLANGE, BEARING, FASTENER) only have shallow attribute extraction.
4. **Underutilized Model Storage**:
   - The `Material.normalized_attributes` JSONB column exists in the database schema but is completely unused.

### 6.2 Matching & Candidate Generation Bottlenecks

1. **Review Queue Combinatorial Explosion**:
   - `generate_candidates` performs a coarse database query: all materials with matching category and matching/null valve type.
   - In a catalog with 1,000 valves, a single upload can match 800+ candidates. Evaluating every pair produces an explosion of `MatchRecommendation` rows ($O(N \times M)$ pairwise comparison), cluttering the Review Queue with irrelevant noise.
2. **Shallow Lexical Similarity (`difflib.SequenceMatcher`)**:
   - Text similarity is measured using character-level Gestalt pattern matching.
   - Highly sensitive to word order: `"BALL VALVE DN50 CS"` and `"CS DN50 BALL VALVE"` receive degraded similarity scores despite describing the identical physical item.
   - Incapable of recognizing domain abbreviations or synonyms (e.g. `VLV` = `VALVE`, `HEX HD SCR` = `HEXAGON HEAD SCREW`, `NPT` = `NATIONAL PIPE TAPER`).
3. **Templated Explanations**:
   - Explanations are simple string concatenations of matching and missing attribute names, lacking deep engineering context or semantic justification.

---

## 7. Baseline Integrity Assurance

To recover the exact `v1.0-stable` baseline at any point during AI development:

```bash
# Verify current working directory
cd /Users/rohinishsingh/onemate

# Check baseline commit
git checkout v1.0-stable
# (Commit hash: d1f1d42)

# Verify backend tests
cd backend && pytest -v

# Verify frontend
cd ../frontend && npx tsc --noEmit && npm run build
```

This baseline represents the bedrock upon which the AI upgrade will be built.

