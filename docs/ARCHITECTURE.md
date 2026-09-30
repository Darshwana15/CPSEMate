# SIH26099 — Backend Architecture

**Project:** AI-Driven Standardization and Harmonization of Material Codes Across CPSEs

**Problem Statement:** SIH26099

**Organization:** Ministry of Petroleum & Natural Gas
**Department:** Chennai Petroleum Corporation Limited (CPCL)

**Architecture Status:** LOCKED
**Document Status:** Approved for MVP implementation

---

# 1. Project Goal

Build an AI-powered National Unified Material Master platform that can
analyze material master records from multiple CPSEs and identify:

- identical materials
- duplicate materials
- near-duplicate materials
- potentially functionally equivalent materials

The platform should normalize and standardize material information,
recommend a Common/National Material Code, maintain mappings between
CPSE material codes and the national material, and provide governance,
auditability, and human override.

The MVP is a prototype of this workflow, not a production national
infrastructure platform.

---

# 2. Core Product Principle

## AI-first, human-governed

The system should automate material harmonization wherever confidence
and business rules permit it.

Humans should NOT be required to approve every AI decision.

AI recommendations are advisory. Authorized human reviewers have final
authority over the resulting canonical state, including classification,
harmonization, mappings, derived canonical data, and National Material
Specification assignment.

Instead:

- High-confidence SAME matches may be automatically accepted.
- Uncertain SAME matches enter review.
- POTENTIALLY_EQUIVALENT matches enter review.
- Strong DIFFERENT decisions may be automatically marked different.
- Authorized humans can inspect and intervene in ANY decision at any
  later time.

Human intervention must never silently overwrite the original AI
decision.

All important decisions and state changes must remain auditable.

Core principle:

> Automate by default. Review by exception. Override at any time.
> Never lose history.

---

# 3. Architecture Principles

The backend is a:

> Simple modular monolith.

Technology stack:

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Pydantic
- Alembic
- pytest
- FastAPI TestClient
- Pandas
- openpyxl

Additional AI/NLP dependencies may be introduced later when required
by the matching implementation.

## Do not introduce prematurely

The MVP must NOT introduce:

- microservices
- Redis
- Celery
- Kafka
- Kubernetes
- distributed job queues
- background-worker infrastructure
- unnecessary repository/service abstractions
- vector databases before they are actually required
- production SSO
- live SAP integration

Prefer simple, readable, maintainable code.

---

# 4. Architecture Change Policy

This document is the approved source of truth for backend architecture
and domain decisions.

Codex must NOT silently redesign the architecture.

If implementation reveals a genuine technical contradiction:

1. Stop implementation of the affected feature.
2. Explain the contradiction.
3. Identify the architectural decision affected.
4. Propose the smallest possible change.
5. Wait for approval before changing the architecture.

Do not introduce new infrastructure or abstractions merely because
they appear architecturally "cleaner."

---

# 5. Core Data Principle

## SOURCE DATA != DERIVED DATA

Original CPSE material data is immutable.

For example:

```text
SOURCE DATA

CPSE: CPCL
Material Code: CP00182
Description: BALL VALVE 2" CS 300# RF
UOM: EA
Specifications: 300# RF
````

The system may create derived information:

```text
DERIVED DATA

normalized_description:
BALL VALVE 50 MM CARBON STEEL CLASS 300 RF

normalized_attributes:
{
    "category": "BALL_VALVE",
    "size": "50 MM",
    "material": "CARBON_STEEL",
    "pressure_class": "CLASS_300",
    "connection_type": "RF"
}
```

Derived data must never overwrite the original CPSE source data.

Corrections to the original CPSE master belong to the upstream ERP
system.

---

# 6. Core Domain Entities

The approved MVP domain contains these concepts:

1. CPSE
2. User
3. MaterialImport
4. Material
5. NationalMaterialFamily
6. NationalMaterialSpecification
7. MatchRecommendation
8. GovernanceDecision
9. MaterialNationalMapping
10. AuditEvent
11. MatchingRun

These entities should remain minimal and should not be split into
additional abstractions unless required.

---

# 7. CPSE

Represents an organization contributing material master data.

Example:

```text
CPCL
IOCL
BPCL
HPCL
```

A CPSE owns its source material codes.

Important principle:

> CPSE material codes remain valid identifiers within their originating
> organization even after national harmonization.

---

# 8. User

Represents a system user/reviewer.

Roles required for the MVP:

* REVIEWER
* ADMIN

Production SSO is out of scope.

Authentication must have a replaceable boundary:

```text
get_current_user()
        ↓
User
        ↓
role
```

Development authentication may use seeded development users.

Business logic must depend on the authentication boundary, not on
hard-coded usernames.

The client must never be trusted to provide:

* user identity
* role
* reviewer identity
* authorization
* approval state

---

# 9. MaterialImport

Represents an ingestion operation for a CPSE material file.

Supported MVP formats:

* CSV
* XLSX

Required source fields:

* Material Code
* Description
* UOM

Optional:

* Specifications

Other source columns should be preserved as raw source data where
appropriate.

The import should track useful ingestion metadata such as:

* CPSE
* original filename
* import time
* number of records
* validation/error information
* import status

Imported source material records remain immutable.

---

# 10. Material

Represents an individual CPSE-owned material record.

Conceptually:

```text
Material
├── CPSE
├── source_material_code
├── source_version
├── is_current_source_version
├── supersedes_material_id
├── source_description
├── source_uom
├── source_specifications
├── raw_source_data
├── normalized_description
├── normalized_uom
├── normalized_attributes
├── normalization_version
└── timestamps
```

Important distinction:

```text
source_*       = immutable CPSE data

normalized_*   = system-derived data
```

The system must preserve both.

If a later CPSE import provides changed source values for the same CPSE
material code, it creates a new immutable source-data version rather than
overwriting the earlier record. The current/latest source version is
identified separately, and source history remains auditable. A changed
source version triggers mapping-validity evaluation: an existing mapping
may remain active only when still technically valid; otherwise matching is
rerun and any new automatic mapping must independently satisfy the normal
server-owned `AUTO_SAME` policy. Unsafe remapping is never implicit.

Source-version lifecycle rule:

```text
OLD SOURCE VERSION
      ↓
EXISTING ACTIVE MAPPING
      ↓
MAPPING VALIDITY EVALUATION
      ↓
┌─────────────────────────────┐
│ Still technically valid?   │
└─────────────────────────────┘
      │
   YES│
      ↓
Keep existing mapping active
```

If the old mapping is no longer technically valid:

```text
OLD SOURCE VERSION
      ↓
OLD ACTIVE MAPPING
      ↓
Mark old mapping INACTIVE / SUPERSEDED
      ↓
Re-run matching against the new source version
      ↓
┌──────────────────────────────────────────┐
│ Matching result                          │
└──────────────────────────────────────────┘
      │
      ├── SAME + normal AUTO_ACCEPT policy
      │       ↓
      │   create new AUTO_SAME mapping
      │
      ├── SAME but automation policy not met
      │       ↓
      │   QUEUE_FOR_REVIEW
      │
      ├── POTENTIALLY_EQUIVALENT
      │       ↓
      │   QUEUE_FOR_REVIEW
      │
      ├── DIFFERENT / no valid match
      │       ↓
      │   remain UNMAPPED unless a later
      │   authorized human decision creates
      │   a mapping
      │
      └── HUMAN REVIEW
              ↓
          ACCEPT / OVERRIDE / REMAP / UNMAP
          according to existing governance rules
```

The CPSE material code remains the same logical identity across source
versions. For example, `CPCL-001` with version 1 and version 2 is still
the same material code, but each source version is an immutable source-data
record. Mapping validity is evaluated against the current source version,
never by implicitly carrying forward the old mapping. Version 1 is never
overwritten or replaced by version 2; it remains historical source data.
The backend, not the frontend, decides whether the old mapping remains
valid for the new current source version.

---

# 11. Material Classification

The AI matching system uses exactly three classifications.

## SAME

Two material records represent the same material/specification despite
differences such as:

* naming
* formatting
* abbreviations
* spelling
* unit representation
* ordering of attributes

Example:

```text
BALL VALVE 2" CS 300# RF

50MM CARBON STEEL BALL VALVE CLASS 300 RF
```

may be classified as SAME if the relevant technical attributes agree.

Important:

> Semantic similarity alone must never establish SAME.

Structured technical attributes must be considered whenever available.

---

## POTENTIALLY_EQUIVALENT

The records may serve the same function or may be technically
interchangeable, but the available evidence is insufficient to safely
establish SAME.

These require human review.

POTENTIALLY_EQUIVALENT must NEVER automatically create a National
Material Specification mapping.

---

## DIFFERENT

The materials/specifications should not be treated as equivalent.

Strong DIFFERENT decisions may be automatically marked different.

A human may later override/review the decision.

---

# 12. Matching Architecture

Matching is:

> Pair-based AI recommendations + National Material Family/Specification
> mappings.

The AI operates primarily on pairs:

```text
Material A ↔ Material B
```

Example:

```text
CPCL-001 ↔ IOCL-002
```

The resulting harmonized group is represented by a National Material
Family containing technically distinct National Material Specifications:

```text
VALVE
└── BALL VALVE FAMILY
    ├── NMMC-VAL-000041: DN50 / CS / CLASS 150 / RF
    └── NMMC-VAL-000042: DN50 / CS / CLASS 300 / RF
```

Do NOT make a material cluster the primary AI recommendation entity.

A material can participate in many pairwise recommendations but can
have only one active National Material Specification mapping. Family-level
similarity does not imply specification-level identity.

---

# 13. Cross-CPSE Matching

Matching should primarily compare materials across CPSEs:

```text
CPCL ↔ IOCL
CPCL ↔ BPCL
IOCL ↔ BPCL
```

Unnecessary same-CPSE comparisons should be avoided.

The system must not perform unrestricted all-pairs comparison.

Instead:

```text
All materials
     ↓
Candidate retrieval
     ↓
Bounded candidate set
     ↓
Detailed comparison
```

Candidate retrieval is the coarse first layer of matching. The bounded
candidates then proceed to structured technical comparison and only then
to semantic/AI reasoning and final classification.

---

# 14. Matching Pipeline

The approved conceptual pipeline is:

```text
Raw Material
     ↓
Normalization
     ↓
Attribute Extraction
     ↓
Candidate Generation
     ↓
Lexical/Fuzzy Similarity
     ↓
Structured Attribute Comparison
     ↓
Semantic Similarity
     ↓
Hybrid Score
     ↓
Classification
     ↓
Automation Policy
     ↓
Governance Decision
     ↓
National Material Specification Mapping
```

The matching layers are ordered by technical safety:

1. candidate retrieval and coarse filtering;
2. structured technical comparison; and
3. normalized-description and semantic/AI reasoning.

Structured technical attributes have priority over semantic similarity.
Semantic similarity must never override an explicit hard engineering
conflict.

The actual AI implementation must remain replaceable.

Initial implementation may use:

```text
Normalization
+
Rules
+
Fuzzy/lexical matching
+
Structured attribute comparison
```

Then embeddings may be added.

LLM-assisted extraction/explanation may be added later.

The database/domain model must NOT depend on a specific AI provider,
model, or API.

---

# 15. Matching Service Boundary

Conceptually:

```text
Matching Service
       │
       ├── Candidate Retrieval
       │
       └── Comparison Engine
                │
                ├── lexical comparison
                ├── semantic similarity
                ├── structured attribute comparison
                ├── hybrid scoring
                ├── classification
                └── explanation
```

The comparison engine should be replaceable.

AI/ML may recommend classification, confidence, extracted attributes,
comparison evidence, and explanations. It does not authoritatively control
National Material Code generation, identity, mapping state, authorization,
governance state, or audit state; those remain backend-enforced concerns.

For example:

```text
Rules + fuzzy matching
        ↓
Rules + embeddings
        ↓
Rules + embeddings + LLM
```

without requiring a database redesign.

---

# 16. Automation Policy

The automation policy is server-owned.

The frontend must never provide:

* confidence thresholds
* scores
* classifications
* AI configuration
* automation decisions

Matching is conservative because a false positive can incorrectly
harmonize technically different materials. A hard conflict prevents
`AUTO_ACCEPT`/`AUTO_SAME`, regardless of semantic score. Missing or
ambiguous critical identity attributes also cannot produce automatic
`SAME`.

Default behavior:

```text
SAME + high confidence
        ↓
AUTO_ACCEPT

SAME + insufficient confidence
        ↓
QUEUE_FOR_REVIEW

POTENTIALLY_EQUIVALENT
        ↓
QUEUE_FOR_REVIEW

DIFFERENT + strong evidence
        ↓
AUTO_MARK_DIFFERENT
```

Only high-confidence SAME recommendations are eligible for automatic
harmonization.

POTENTIALLY_EQUIVALENT always requires human review.

For a category, hard/identity attributes must agree for `SAME`.
Secondary attributes may require additional comparison or human review.
For the initial VALVE category, hard attributes include valve type, size,
body material, pressure class, connection type, trim, and normalized UOM.
For `VALVE_V1`, different trim values such as `SS304` and `SS316` define
different Specifications. Service conditions, standards, certifications,
manufacturer, and model are not universally identity-defining; their
treatment is category/schema specific.

Examples of hard technical conflicts include `GATE` versus `BALL`, `50 MM`
versus `80 MM`, `CLASS 150` versus `CLASS 300`, incompatible body materials,
and `RF` versus `SOCKET_WELD`. Such conflicts classify the pair as
`DIFFERENT` for matching purposes and can never result in `AUTO_SAME`.

The category schema distinguishes identity attributes from secondary
attributes and context/compliance attributes. Manufacturer and
manufacturer model do not automatically define a Specification when the
technical identity is otherwise the same. Standards or certifications,
such as API 6D, ISO 14313, or fire-safe requirements, become
identity-defining only when the category schema explicitly requires it;
otherwise they remain secondary/compliance information and may require
human review.

Missing data is not conflicting data. `UNKNOWN` trim must remain unknown;
it must not be inferred to match `SS304`. Whether a missing attribute
blocks `SAME` depends on the category identity schema and automation
policy. UOM normalization is likewise rule-based: `EA`, `NOS`, and `PCS`
may normalize to `EACH` only through an approved equivalence rule; AI may
not infer equivalence. Incompatible UOMs such as `EA` and `KG` do not
match without a valid category-appropriate conversion/equivalence rule.

---

# 17. MatchRecommendation

Represents the immutable AI finding for a material pair.

It should preserve:

* source_material_id
* candidate_material_id
* canonical_material_low_id
* canonical_material_high_id
* canonical_pair_key
* matching_run_id
* semantic similarity
* lexical similarity
* attribute similarity
* overall confidence
* AI classification
* explanation/reasons
* generator version
* normalization version
* creation timestamp

Each recommendation also preserves structured evidence: applicable reason
codes, attribute-by-attribute comparison, normalization evidence, and a
confidence breakdown. An opaque aggregate score alone is insufficient.

Initial reason-code groups include technical conflicts, data-quality
issues, normalization issues, and matching insufficiency/ambiguity. A
recommendation retains all applicable reasons, not only a primary reason.

The original AI recommendation must never be modified or deleted by
human governance actions.

---

# 18. Pair Canonicalization

The system must distinguish:

```text
Logical relationship
```

from:

```text
Database duplicate prevention
```

Therefore:

```text
source_material_id
candidate_material_id
```

preserve the logical direction used by the matching operation, UI,
explanations, and API responses.

The backend also generates:

```text
canonical_material_low_id
canonical_material_high_id
canonical_pair_key
```

using stable ordering of the two material UUIDs.

Rules:

* source and candidate must be different materials
* duplicate prevention uses canonical_pair_key
* source/candidate context is preserved for product behavior

The same pair must not generate duplicate recommendations for identical
comparison inputs.

---

# 19. MatchingRun

## Purpose

MatchingRun is ONLY a synchronous execution/idempotency record.

It is NOT:

* a background job
* a queue
* a workflow
* a polling resource
* a worker
* a distributed execution mechanism

The MVP matching operation executes synchronously inside the HTTP
request.

## Fields

```text
id
operation_key
input_fingerprint
generator_version
normalization_version
automation_policy_version
created_at
```

`operation_key` must be unique.

`input_fingerprint` represents the canonicalized matching inputs.

The backend generates both values.

The frontend must never supply them.

## Input fingerprint

The canonical input should account for:

* sorted requested source material IDs
* relevant normalized material fingerprints
* canonically ordered candidate material IDs
* relevant candidate input fingerprints
* server-owned candidate selection scope/parameters
* relevant category identity-schema versions as part of the normalized
  material input fingerprint

## Operation key

Generated from:

```text
input_fingerprint
+
generator_version
+
normalization_version
+
automation_policy_version
```

## Execution

```text
POST /api/v1/matches/run
        ↓
Canonicalize inputs
        ↓
Generate input_fingerprint
        ↓
Generate operation_key
        ↓
Existing MatchingRun?
   ├── YES → return existing results
   └── NO
          ↓
     Create MatchingRun
          ↓
     Generate recommendations synchronously
          ↓
     Create applicable decisions/mappings/audit records
          ↓
     Commit transaction
          ↓
     Return results
```

No:

* status field
* RUNNING
* QUEUED
* FAILED
* progress tracking
* polling
* background workers
* Redis
* Celery
* distributed locking

## Failure behavior

Matching execution should be transactional.

If synchronous generation fails:

```text
transaction
    ↓
failure
    ↓
ROLLBACK
```

No incomplete MatchingRun or partial result set should remain.

## Concurrent identical requests

If two identical requests arrive concurrently:

```text
Request A ─┐
           ├── same operation_key
Request B ─┘
```

database uniqueness on operation_key ensures only one MatchingRun is
created.

The losing request retrieves the existing committed run/results.

---

# 20. National Material Family and Specification

National Material hierarchy is:

```text
Material Category
        ↓
National Material Family
        ↓
National Material Specification
        ↓
CPSE Material Mapping
```

A National Material Family is a broader conceptual or functional
material grouping. It contains a category, family identity, family name,
canonical family description, and identity-schema version. Its canonical
description is a display/grouping field, not specification identity.

Family assignment is based primarily on material category, functional
type, and broad technical purpose. For `VALVE`, BALL VALVE, GATE VALVE,
BUTTERFLY VALVE, and CHECK VALVE are separate Families. Size, pressure
class, body material, trim, and similar category-defined technical values
normally belong to Specification identity rather than Family identity.

A National Material Specification is a technically distinct standardized
configuration within a Family. It contains the category-aware canonical
identity attributes, identity key, canonical description, and the
National Material Code.

Example:

```text
VALVE
└── BALL VALVE FAMILY
    ├── NMMC-VAL-000041: DN50 / CARBON STEEL / CLASS 150 / RF
    └── NMMC-VAL-000042: DN50 / CARBON STEEL / CLASS 300 / RF
```

The National Material Code belongs to the specific National Material
Specification, never merely to the broader Family. CPSE Materials map to
Specifications, not Families. The code is backend generated, unique, and
never supplied by a client.

Family creation may be AI-assisted when backend validation confirms a
valid category, valid Family definition/name, required Family attributes,
and uniqueness within the category. Authorized reviewers/admins may also
create a Family under the same validation rules. Family creation is
audited.

Uncertain AI Family assignment must not be silently accepted. Review must
show candidate Families, confidence, supporting evidence, and conflicts;
the human chooses the final Family. A later authorized Family movement
preserves the old assignment in governance/audit history and makes the
new assignment active through the applicable Specification relationship.

Families may be retired without deleting historical records. A retired
Family cannot receive new active assignments unless explicitly
reactivated by authorized administration.

---

# 21. National Material Specification Identity

National Material Specification identity is category-aware.

The backend generates an `identity_key` from:

* material category
* identity-schema version
* category-specific required core normalized attributes
* normalized UOM where relevant

For example, a valve identity schema may require:

```text
category
valve type
size
material
pressure class
connection type
normalized UOM
```

The exact identity attributes can vary by category.

The identity key is a deterministic hash of canonicalized values.

`canonical_description` is a display field only.

Description alone must NEVER determine National Material Specification
identity.

Different Families cannot be the same Specification. A technical identity
change such as `CLASS 300` to `CLASS 150` is a different Specification,
not merely a changed display description.

---

# 22. National Material Specification Creation

Before creating a National Material Specification:

```text
Calculate category-aware identity_key
        ↓
Look for existing active National Material Specification
        ↓
Existing?
   ├── YES → reuse
   └── NO → evaluate completeness
```

A new National Material Specification may be created automatically only when all
category-required identity attributes are present and unambiguous.

Missing or ambiguous required attributes prevent automatic creation
and require human review.

## Human completion of canonical identity

When a reviewer confirms that materials should be harmonized but no
existing National Material Specification is suitable, the reviewer may provide or
complete the missing canonical identity attributes required by the
relevant category schema.

This authority applies only to DERIVED/CANONICAL DATA. Original CPSE
source material remains immutable.

The backend must:

1. validate all required category-specific identity attributes before
   creating a National Material Specification;
2. generate the National Material Specification identity_key server-side;
3. generate the National Material Code server-side;
4. never accept a National Material Code directly from the reviewer or
   frontend;
5. check for an existing active National Material Specification with the calculated
   identity_key before creating a new one;
6. reuse an existing National Material Specification when the identity_key matches;
7. create a new National Material Specification only when the required identity
   attributes are complete and unambiguous;
8. record reviewer-provided canonical attributes and the resulting
   action in governance and audit history; and
9. never allow reviewer actions to modify original CPSE source fields.

A reviewer may complete or correct derived canonical values such as
normalized size, material, pressure class, connection type, valve type,
and other category-defined identity attributes. This does not permit a
reviewer to invent an unsupported technical specification. Canonical
values must be supported by available source evidence; unresolved
attributes remain unresolved and cannot be used for National Material
Specification creation.

Canonical attributes must eventually preserve sufficient provenance to
answer where each standardized value came from. At minimum, the later
domain implementation must distinguish AI-derived attributes from
human-confirmed/completed attributes. This is an implementation
requirement, not a new dedicated domain model at this stage.

Example:

```text
Valve:
size = 50 MM
material = CARBON STEEL
pressure = CLASS 300
connection = MISSING
```

must NOT automatically become identical to:

```text
Valve:
size = 50 MM
material = CARBON STEEL
pressure = CLASS 300
connection = RF
```

National Material Specification identity must never rely solely on description
similarity.

National Material Specification identity_key must be unique among active
Specifications. Transaction-safe identity-key lookup/creation prevents
duplicate Specifications when matching runs occur concurrently.

## Correction, versioning, and lifecycle

A correction to canonical data may retain the same Specification/NMMC
when category identity attributes are unchanged, for example a corrected
typo or representation. A change to an identity-defining attribute creates
or selects the correct distinct Specification; versioning must never make
technically incompatible configurations share one identity.

Specification history/versioning preserves corrections and standardized
definition history. National Material Specifications may be retired, but
retirement never deletes source mappings, governance decisions, audit
events, historical versions, or prior recommendations. Retired
Specifications cannot receive new active mappings unless explicitly
reactivated/authorized.

If a Specification was incorrectly too broad, later governance may split
its standardized representation into distinct Specifications. Affected
mappings are reviewed or migrated under governance; historical records
remain intact. Conversely, if two NMMCs are later found technically
identical, they must not be automatically merged. An authorized human
merge decision selects the surviving canonical Specification, preserves
all mappings/governance/audit references, and retires, supersedes, or
merges the other record according to the final audited representation.
AI may recommend a merge but cannot perform the authoritative merge.

---

# 23. MaterialNationalMapping

Represents the relationship between a CPSE Material and a National
Material Specification.

Core rule:

> One CPSE Material can have at most ONE ACTIVE National Material
> Specification mapping at any point in time.

Historical mappings remain preserved.

Example:

```text
CPCL-001
    ↓
NMMC-001   SUPERSEDED
    ↓
NMMC-047   ACTIVE
```

Never edit the target of an existing historical mapping.

Never delete mapping history.

A database constraint must enforce at most one ACTIVE mapping per
material.

There must never be two ACTIVE National Material mappings for the same
current CPSE Material. The previous mapping is never deleted; when it is no
longer valid, it becomes historical/inactive/superseded. A new source
version must not automatically inherit the old mapping merely because the
CPSE material code is unchanged. Any replacement mapping must be
independently validated or expressly governed. The backend determines
whether the old mapping remains valid, and the frontend cannot silently
bypass review or automation rules by reusing an older mapping state.

When a new immutable source version is created for an existing CPSE
material code, old mapping validity is re-evaluated against the current
source version. If the mapping remains technically valid, the active
mapping may continue unchanged. If it is no longer valid, the old mapping
is marked inactive/superseded, the current mapping is cleared or remains
unmapped until a new authorized result is produced, and matching is re-run
against the new source version. `AUTO_SAME` remains the only automatic path
for creating a new active mapping, and `POTENTIALLY_EQUIVALENT` can never
create one automatically. Any source-data change that fails the normal
server-owned automation policy must go through human review instead of an
implicit remap. Existing historical `GovernanceDecision` and `AuditEvent`
records remain untouched.

---

# 24. Mapping Basis

The mapping basis is exactly one of:

```text
AUTO_SAME
HUMAN_CONFIRMED_SAME
HUMAN_OVERRIDE
```

## AUTO_SAME

Created only when:

```text
AI classification = SAME
+
automation policy permits AUTO_ACCEPT
```

POTENTIALLY_EQUIVALENT can never create AUTO_SAME.

When a source-data version changes, the old mapping is not blindly
transferred. The backend reevaluates whether the old mapping remains
technically valid for the current source version. If still valid, the
existing mapping remains active. If no longer valid, the old mapping is
marked inactive/superseded, matching is rerun on the new source version,
and a new mapping is created only if the result independently satisfies the
normal server-owned `AUTO_SAME` policy or after an authorized human
decision. A source-data change must never silently bypass human review
when automation policy is not satisfied.

## HUMAN_CONFIRMED_SAME

Created when a reviewer confirms a SAME recommendation.

Also used when a reviewer determines that a POTENTIALLY_EQUIVALENT
pair is technically equivalent enough to harmonize.

The original AI classification remains:

```text
POTENTIALLY_EQUIVALENT
```

The mapping records the human-confirmed harmonization.

## HUMAN_OVERRIDE

Created when a reviewer:

* chooses a different existing National Material Specification
* performs a direct REMAP

---

# 25. Human Governance

Humans can intervene at any time.

Human actions:

```text
ACCEPT
REJECT
MARK_DIFFERENT
OVERRIDE
UNMAP
REMAP
```

Authorized governance also covers Family movement, approval of a new
Family, permitted completion/correction of derived canonical attributes,
and consequential Specification split/merge operations according to role.

AI classification, human governance decision, and final canonical
database state are separate concepts. A human action may change the
current canonical state but never modifies or erases the original AI
recommendation or earlier governance decisions.

## ACCEPT

Confirms the AI proposal.

If the recommendation was already automatically accepted, this records
human confirmation without replacing the original AI decision.

## REJECT

Rejects the proposed equivalence.

A rejection reason is required where the reviewer is correcting or
contradicting AI evidence. The reason is retained in governance and audit
history.

If a mapping was created solely because of the rejected recommendation,
the mapping becomes inactive while history remains preserved.

## MARK_DIFFERENT

Marks the specific pair as different.

This does NOT globally blacklist either material from future matching.

Example:

```text
CPCL-001 ↔ IOCL-002
    ↓
MARK_DIFFERENT
```

does not prevent:

```text
CPCL-001 ↔ BPCL-872
```

from being evaluated later.

## OVERRIDE

Changes the target to a different EXISTING National Material Specification.

Example:

```text
AI:
CPCL-001 → NMMC-042

Human:
CPCL-001 → NMMC-087
```

The previous mapping becomes historical/superseded.

## UNMAP

Removes the current active mapping while preserving history.

## REMAP

Moves the material from its current National Material Specification to
another existing National Material Specification while preserving the old
mapping.

## Reviewer authority over canonical data

Reviewer authority applies to derived canonical data only. A reviewer
may provide or complete category-defined canonical identity attributes
when confirming harmonization under Section 22, provided those values
are supported by available source evidence.

Reviewer authority does not permit modification of:

* original CPSE material code;
* original CPSE description;
* original CPSE UOM;
* original CPSE specifications;
* any other immutable source field; or
* a National Material Code.

Reviewers also cannot bypass backend identity validation or mapping
constraints, erase AI history, or erase audit history. Authorization is
enforced server-side for every consequential governance/master-data action.

The backend validates completed canonical attributes, calculates the
identity_key, reuses an existing matching active National Material
Specification when
available, and generates a new National Material Code only when a new,
complete, unambiguous canonical identity is valid. Reviewer-provided
canonical attributes and their provenance must be recorded in governance
and audit history.

---

# 26. GovernanceDecision

Human governance decisions must be stored separately from AI
recommendations.

Important principle:

```text
AI decision != Human decision
```

The original AI recommendation is immutable.

A GovernanceDecision should preserve:

* recommendation reference where applicable
* decision type
* decision source
* actor
* reason/note where applicable
* timestamp
* affected mapping
* previous state
* resulting state

It must also preserve a reviewer reason where required, including reject,
override, remap, and a confirmation that contradicts AI evidence. The
latest authorized decision controls current canonical state while all
previous decisions remain auditable.

Governance decisions are append-only.

---

# 27. AuditEvent

Important state changes must generate audit events.

Audit events are append-only.

At minimum audit:

* AI decisions
* automatic mappings
* human accept/reject
* overrides
* remaps
* unmaps
* material import operations
* important National Material Family/Specification changes
* reviewer-provided canonical attribute provenance
* Family creation, movement, retirement, and reactivation
* Specification correction, retirement, split, and human-authorized merge
* source-data version creation and mapping re-evaluation

Audit information should include:

```text
event source
decision/action
state transition
actor where applicable
timestamp
```

Do not store authentication secrets in audit records.

---

# 28. Idempotency

The system must prevent duplicate processing.

Repeated identical matching operations must not unnecessarily create:

* duplicate MatchingRun records
* duplicate MatchRecommendations
* duplicate AI GovernanceDecisions
* duplicate mappings
* duplicate National Material Specifications
* duplicate audit events

Relevant database uniqueness constraints must protect these invariants.

---

# 29. Ingestion

MVP supports:

```text
CSV
XLSX
```

Required:

```text
Material Code
Description
UOM
```

Optional:

```text
Specifications
```

Other fields should be preserved as raw source data where appropriate.

Ingestion must:

1. validate input
2. identify the CPSE
3. preserve source data
4. reject/flag invalid records
5. create immutable Material source records

Manual editing of source material records is out of scope.

Later imports with changed values for an existing CPSE material code use
the immutable source-versioning rules in Section 10; they never mutate the
historical source record.

## Dataset strategy

The prototype prioritizes real, legitimately accessible CPSE
material/procurement data, initially focusing on CPCL and IOCL and the
VALVE category. BPCL and HPCL may be added later. Public official
procurement/e-procurement records may be used where appropriate; the
prototype must not claim access to confidential or internal SAP material
master data unless such access is actually obtained. Every dataset must
have clear provenance.

---

# 30. API Architecture

All APIs use:

```text
/api/v1/
```

The canonical API contract is:

```text
docs/api/openapi.yaml
```

OpenAPI is the source of truth for communication between backend and
frontend.

The frontend must not invent API contracts independently.

The backend implementation must follow the agreed OpenAPI contract.

Initial/future MVP API areas include:

```text
CPSEs
Materials
Imports
Matching
Governance decisions
National Material Families and Specifications
Mappings
Audit
```

The matching endpoint uses:

```text
POST /api/v1/matches/run
```

The governance endpoint uses:

```text
POST /api/v1/matches/{id}/decisions
```

Material mapping decisions may use:

```text
POST /api/v1/materials/{id}/mapping-decisions
```

Mapping history:

```text
GET /api/v1/materials/{id}/mapping-history
```

Exact request/response schemas must be maintained in the canonical
OpenAPI contract.

---

# 31. Authentication and Authorization

Production SSO is out of scope for the MVP.

However, authorization must still be enforced server-side.

Use:

```text
get_current_user()
        ↓
User
        ↓
role
```

The authentication mechanism must be replaceable.

Development users may be seeded for demonstration.

Reviewer/admin permissions must be enforced by the backend.

Never trust client-provided:

* role
* user ID
* reviewer ID
* decision source
* approval status
* confidence
* classification
* National Material Code

---

# 32. Ground-Truth Evaluation and Test Data

The matching engine will eventually be evaluated against controlled
ground-truth cases. Synthetic data is useful for controlled demonstrations,
edge cases, regression testing, and evaluation, but must not be presented
as real CPSE data.

Target:

```text
~100 canonical materials
        ↓
5–10 variations per material
        ↓
~500–1,000 material records
```

The dataset should contain known relationships for:

* SAME
* POTENTIALLY_EQUIVALENT
* DIFFERENT

Evaluation metrics:

* precision
* recall
* F1
* false positives
* false negatives

The benchmark dataset is evaluation/test data.

It is not part of the production domain schema.

---

# 33. MVP Scope

## MUST HAVE

```text
CPSE registration
        ↓
CSV/XLSX ingestion
        ↓
Material storage
        ↓
Source-data preservation
        ↓
Source-data version history
        ↓
Normalization
        ↓
Structured attributes
        ↓
Candidate generation
        ↓
Pairwise matching
        ↓
AI recommendations
        ↓
Automation policy
        ↓
Auto decisions / review queue
        ↓
Human intervention
        ↓
National Material Family/Specification creation and reuse
        ↓
CPSE-to-National mapping
        ↓
Mapping history
        ↓
Family/Specification lifecycle history
        ↓
Audit trail
        ↓
REST APIs
```

## SHOULD HAVE

* semantic embeddings
* richer material-category schemas
* improved explainability
* analytics/dashboard APIs
* benchmark evaluation
* Docker deployment
* improved review UI

The SIH demonstration should visibly show ingestion, normalization,
technical attribute extraction, explainable cross-CPSE comparison,
Family grouping with multiple Specifications, safe automatic
harmonization, human review/override, audit history, and before-versus-
after duplicate-reduction analytics derived from actual run results.

## OUT OF SCOPE FOR MVP

* live SAP integration
* live ERP integration
* production SSO
* microservices
* Redis
* Celery
* Kafka
* Kubernetes
* distributed AI infrastructure
* OCR
* mobile application
* model training
* advanced procurement optimization
* national-scale production infrastructure

---

# 34. Implementation Phases

## Phase 1 — Foundation

Build:

* Python project
* FastAPI
* configuration
* PostgreSQL connection
* SQLAlchemy
* Alembic
* authentication boundary
* health endpoint
* testing foundation
* OpenAPI foundation

Do NOT create domain models yet.

---

## Phase 2 — Core Domain

Implement:

* CPSE
* User
* MaterialImport
* Material
* NationalMaterialFamily
* NationalMaterialSpecification
* MaterialNationalMapping
* MatchRecommendation
* GovernanceDecision
* AuditEvent
* MatchingRun

Review database constraints before creating the first domain migration.

Include immutable source-version relationships and Family/Specification
lifecycle-history requirements in the domain review without introducing
unnecessary infrastructure.

---

## Phase 3 — Ingestion

Implement:

```text
CSV/XLSX
    ↓
validation
    ↓
CPSE identification
    ↓
immutable source records
```

---

## Phase 4 — Normalization

Implement:

```text
raw description
    ↓
normalized description
    ↓
structured attributes
```

Version normalization behavior.

Implement category-specific attribute rules, starting with VALVE_V1.

---

## Phase 5 — Matching Baseline

Implement:

* candidate generation
* cross-CPSE filtering
* fuzzy/lexical matching
* attribute comparison
* classification
* confidence scoring

No LLM dependency required initially.

---

## Phase 6 — Automation

Implement:

```text
SAME + high confidence → AUTO_ACCEPT
SAME + uncertain → REVIEW
POTENTIALLY_EQUIVALENT → REVIEW
DIFFERENT + strong evidence → AUTO_DIFFERENT
```

Hard technical conflicts prevent AUTO_SAME and must remain explainable;
human governance can review or override any AI decision later.

Implement MatchingRun idempotency.

---

## Phase 7 — Governance

Implement:

* accept
* reject
* mark different
* override
* unmap
* remap
* Family movement and lifecycle governance
* Specification correction/split/merge governance
* mapping history
* audit events

---

## Phase 8 — Evaluation

Build synthetic ground-truth dataset.

Measure:

* precision
* recall
* F1
* false positives
* false negatives

Tune automation thresholds based on evaluation results.

---

## Phase 9 — Dashboard APIs

Provide APIs for:

* material statistics
* duplicate counts
* match counts
* review queue
* National Material Family/Specification statistics
* mapping history
* audit history

---

## Phase 10 — Frontend/Demo

Build the SIH demonstration UI around the stable API contract.

Core screens:

1. National dashboard
2. CPSE/material ingestion
3. Material explorer
4. AI matching results
5. Review queue
6. National Material view
7. Mapping/history
8. Audit trail

---

# 35. Target Product Flow

The complete product should demonstrate:

```text
CPSE uploads material master
            ↓
System validates/imports data
            ↓
Source records preserved
            ↓
System normalizes material descriptions
            ↓
System extracts technical attributes
            ↓
System finds cross-CPSE candidates
            ↓
AI compares candidate pairs
            ↓
AI classifies:
SAME / POTENTIALLY_EQUIVALENT / DIFFERENT
            ↓
Automation policy acts
            ↓
High-confidence SAME → automatic harmonization
Potential equivalence → human review
Uncertain SAME → human review
Strong DIFFERENT → automatic different decision
            ↓
National Material Specification reused or created within a Family
            ↓
CPSE material mapped
            ↓
Human can intervene at any time
            ↓
All decisions and changes audited
```

---

# 36. Final Architecture Summary

The system is fundamentally:

> An AI-powered material entity-resolution and master-data governance
> platform.

It is NOT simply:

> An LLM that compares material descriptions.

The core architecture is:

```text
                CPSE MATERIAL DATA
                       ↓
                  INGESTION
                       ↓
                 NORMALIZATION
                       ↓
              STRUCTURED ATTRIBUTES
                       ↓
              CANDIDATE RETRIEVAL
                       ↓
               PAIRWISE MATCHING
                       ↓
              MATCH RECOMMENDATION
                       ↓
               AUTOMATION POLICY
                       ↓
             GOVERNANCE DECISION
                       ↓
          NATIONAL MATERIAL FAMILY
                       ↓
       NATIONAL MATERIAL SPECIFICATION
                       ↓
               CPSE MAPPING
                       ↓
                  AUDIT TRAIL
```

With:

```text
AI = automated intelligence
Human = governance and override
Database = source of truth
Audit = permanent history
```

And:

```text
MatchingRun = synchronous idempotency record only
```

---

# 37. Non-Negotiable Invariants

The following rules must always hold:

1. Original CPSE source material is immutable.
2. AI recommendations are immutable.
3. Human decisions never overwrite AI decisions.
4. POTENTIALLY_EQUIVALENT never automatically creates a mapping.
5. Only high-confidence SAME may be automatically harmonized.
6. National Material identity is category-aware.
7. Description alone cannot establish National Material identity.
8. National Material codes are backend-generated.
9. A material has at most one active National Material Specification mapping.
10. Historical mappings are preserved.
11. MARK_DIFFERENT applies to a specific pair, not globally to a material.
12. Matching recommendations are pair-based.
13. MatchingRun is synchronous and is not a job system.
14. Identical matching operations are idempotent.
15. Important state changes generate audit events.
16. Client input is never trusted for authorization or AI decisions.
17. The OpenAPI specification is the canonical API contract.
18. Architecture changes require explicit approval.
19. Reviewer-provided canonical attributes may complete derived National
    Material identity, but can never modify immutable CPSE source data
    or directly assign a National Material Code.
20. A National Material Family is a conceptual grouping; a National
    Material Specification is the technically distinct standardized
    configuration that receives the National Material Code.
21. A CPSE Material maps to one active National Material Specification,
    not merely to a Family.
22. Family-level similarity never implies specification-level identity.
23. Hard category identity conflicts prevent AUTO_SAME and semantic
    similarity cannot override them.
24. Category-specific attribute rules determine which attributes are hard
    identity attributes and which require review.
25. AI classification, human governance decision, and final canonical
    database state remain distinct.
26. Reviewer-supplied derived canonical data must be supported by source
    or approved technical evidence and preserve provenance.
27. National Material Specification creation first reuses a matching
    active identity_key and cannot create duplicate Specifications during
    concurrent matching runs.
28. Family assignment is distinct from Specification identity; an
    uncertain Family assignment requires review and Family history is
    preserved.
29. Families and Specifications may be retired without deleting history;
    retired records receive no new active assignments/mappings unless
    explicitly reactivated by authorized action.
30. For VALVE_V1, valve type, size, body material, pressure class,
    connection type, trim, and normalized UOM are identity-defining.
31. Missing values remain unknown and are never inferred merely to
    increase similarity; UOM equivalence requires an approved rule.
32. Corrections that preserve identity may retain an NMMC, but changes to
    identity-defining attributes require the correct distinct
    Specification rather than versioning incompatible identities together.
33. Source-data changes create immutable source versions and can never
    silently cause an unsafe remap.
34. Specification split and merge operations require preserved history;
    authoritative merges require authorized human approval.
35. Source-data version changes never silently transfer an old mapping to
    the new source version; the old mapping is retained historically and
    any new mapping must be independently validated or governed.

---

# END OF ARCHITECTURE
