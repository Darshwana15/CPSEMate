# SIH MVP Scope

## Relationship to the production architecture

```text
docs/ARCHITECTURE.md
    ↓
Long-term / production architecture and domain source of truth

docs/MVP_SCOPE.md
    ↓
SIH MVP implementation boundary
```

The MVP is a deliberately simplified implementation of the larger architecture.

The MVP must NOT contradict the domain principles in `docs/ARCHITECTURE.md`.

When the MVP omits a production feature, it must be explicitly labeled:

```text
DEFERRED — FUTURE / PRODUCTION
```

Do not reinterpret a deferred feature as a changed business rule.

---

# 1. SUPPORTED MATERIAL CATEGORIES

The MVP supports the following material categories:

```text
VALVE
PUMP
GASKET
FLANGE
BEARING
FASTENER
```

Do NOT build a generic category-schema engine.

Do NOT build:

- configurable category schemas
- dynamic attribute registries
- category-specific schema versioning
- plugin-style category definitions
- generic attribute metadata frameworks

For the MVP, use explicit typed fields for valve technical attributes.

The Material and NationalMaterial models should conceptually support:

- category
- valve_type
- size
- body_material
- pressure_class
- connection_type
- trim
- normalized_uom

The exact database representation will be decided later during schema design.

If additional categories are discussed, they belong to the future production architecture.

This is an intentional MVP simplification.

---

# 2. VALVE IDENTITY RULE

For the MVP, these are the primary identity-defining valve attributes:

- valve_type
- size
- body_material
- pressure_class
- connection_type
- trim

Normalized UOM may also participate where required by the agreed identity logic.

Examples:

```text
CLASS150 != CLASS300
SS304 != SS316 when trim is identity-relevant
BALL VALVE != GATE VALVE
```

The matching system must not allow a high textual/semantic similarity score to override a hard technical conflict.

---

# 3. NATIONAL MATERIAL IDENTITY — KEEP IT SIMPLE

The MVP must NOT implement the production identity-schema/version framework.

The MVP needs a deterministic way to reuse an existing National Material instead of creating duplicates.

Use a simple deterministic identity representation.

Preferred conceptual approach:

```text
identity_key =
    canonicalized category +
    canonicalized identity-defining valve attributes
```

Example:

```text
VALVE|BALL|DN50|CARBON_STEEL|CLASS300|RF|SS304
```

The identity key must be deterministic and unique for the relevant technical specification.

The backend should:

1. calculate the canonical identity
2. check whether an existing NationalMaterial already has that identity
3. reuse the existing NationalMaterial when appropriate
4. create a new NationalMaterial only when no matching identity exists

If any identity-defining attribute is missing or unknown, the
`identity_key` must not be used to automatically reuse or create a
`NationalMaterial`. Route the material to human review instead.

`UNKNOWN` is not a valid wildcard identity value.

For example, this must NOT cause automatic reuse:

```text
VALVE|BALL|DN50|CARBON_STEEL|CLASS300|RF|UNKNOWN
```

Two materials with unknown identity-defining attributes must not be
automatically assumed to represent the same NationalMaterial.

This is only a business rule; it does not introduce identity-schema
versioning, probabilistic identity keys, or new tables.

National codes remain backend-generated.

Frontend and AI/ML must never generate authoritative National Material codes.

Do NOT implement:

- identity-schema version tables
- complex identity hash infrastructure
- distributed deduplication
- identity service
- category plugin architecture

A normal database uniqueness constraint is sufficient for MVP.

---

# 4. AI/ML BOUNDARY — LOGICAL, NOT PHYSICAL

Clarify the AI/ML architecture.

The MVP is a modular monolith.

AI/ML does NOT need to be a separate microservice.

The intended MVP pattern is conceptually:

```text
FastAPI endpoint
    ↓
matching Python module
    ↓
classify(material_a, material_b)
    ↓
MatchResult
    ↓
backend persistence/governance
```

For example, conceptually:

```python
def classify(material_a, material_b) -> MatchResult:
    ...
```

This is a logical architectural boundary, not a requirement for a separate process, HTTP service, container, queue, or deployment.

Do NOT introduce:

- AI microservices
- internal HTTP calls
- Redis
- Celery
- Kafka
- message queues
- distributed workers

The AI/ML module may return:

- classification
- confidence
- scores
- evidence
- reason codes where implemented
- explanation

The backend remains responsible for:

- persistence
- governance
- mapping
- National Material creation
- authorization
- audit
- final state

AI/ML must never write directly to PostgreSQL.

---

# 5. NORMALIZATION / ATTRIBUTE EXTRACTION IS A PROTECTED MILESTONE

Normalization and technical attribute extraction are foundational to the entire matching system.

Do NOT rush past P1 to build flashy AI features.

The dependency chain is:

```text
BAD SOURCE NORMALIZATION
        ↓
BAD TECHNICAL ATTRIBUTES
        ↓
BAD MATCHING
        ↓
BAD AI RECOMMENDATIONS
        ↓
BAD HARMONIZATION
```

Therefore:

P1 must be considered complete enough before significant effort is spent on advanced matching/embeddings/LLM features.

The team should validate normalization and extraction against the evaluation/demo dataset.

At minimum validate:

- size
- valve type
- body material
- pressure class
- connection type
- trim
- UOM

Normalization must preserve the original source values.

---

# 6. NORMALIZATION FIRST, AI SECOND

The MVP matching strategy should remain:

```text
V1:

deterministic normalization
+
structured attribute extraction
+
candidate generation
+
hard conflict checks
+
fuzzy matching
```

Then, only if time permits:

```text
embeddings
```

Then, only if still useful:

```text
LLM-assisted extraction/explanation
```

Do NOT make the MVP dependent on an LLM.

A strong deterministic baseline is required before advanced AI.

---

# 7. SIX CORE MVP ENTITIES

Retain the approximately six core entities:

1. CPSE
2. Material
3. MatchRecommendation
4. Mapping
5. NationalMaterial
6. AuditLog

Do not add production entities simply because they exist in the long-term architecture.

Specifically defer:

- MatchingRun
- source-version entity
- full Family entity
- Family lifecycle
- complex provenance entities
- merge/split workflow entities
- production workflow/job entities

If implementation later reveals that a tiny supporting table is genuinely necessary, that must be justified before introducing it.

---

# 8. MVP Implementation Priority

The implementation sequence should be:

```text
P0 — Project Foundation
- FastAPI project structure
- PostgreSQL connection
- SQLAlchemy setup
- basic configuration
- basic security hygiene

P1 — Normalization + Attribute Extraction
- CPSE
- Material
- CSV/XLSX ingestion
- source validation
- deterministic normalization
- valve technical attribute extraction
- validation against evaluation/demo dataset

P1 IS A PROTECTED MILESTONE.

Do not move substantial effort to advanced AI or UI until the core
technical attributes can be reliably extracted.

Core attributes:
- valve_type
- size
- body_material
- pressure_class
- connection_type
- trim
- normalized_uom

P2 — Candidate Generation + Matching
- candidate filtering
- technical comparison
- hard conflict detection
- fuzzy matching
- SAME / POTENTIALLY_EQUIVALENT / DIFFERENT

P3 — National Material + Mapping + Automation
- NationalMaterial
- deterministic identity
- reuse-before-create
- Mapping
- AUTO_SAME
- automated DIFFERENT where implemented

P4 — Human Review + Audit
- review queue
- accept
- reject
- mark different
- override
- remap
- unmap where supported
- AuditLog

P5 — Dashboard + Demo Polish
- matching statistics
- harmonization impact
- before/after counts
- review metrics
- explainability
- polished demo flow
```

AI enhancements such as embeddings or LLM assistance come AFTER the
deterministic baseline works.

---

# 9. FAMILY SIMPLIFICATION

Keep the production hierarchy documented in `docs/ARCHITECTURE.md`:

```text
Category
    ↓
Family
    ↓
Specification
```

But do NOT implement a complete Family system for MVP.

For MVP, represent the relevant valve function/category directly using simple fields.

Do not implement:

- Family lifecycle
- Family merge
- Family split
- Family retirement workflow
- Family reassignment workflow
- Family versioning

These remain future/production features.

---

# 10. NATIONAL MATERIAL

NationalMaterial should be simple.

Conceptually:

- national_code
- category
- canonical_description
- valve_type
- size
- body_material
- pressure_class
- connection_type
- trim
- normalized_uom where required
- active status where needed
- deterministic identity key

Do not build a generic canonical-attribute engine.

Do not build a generic schema registry.

---

# 11. MATCH RECOMMENDATION

Keep:

- source_material_id
- candidate_material_id
- classification
- confidence/scoring
- explanation
- evidence/reason information
- created_at

Classifications remain exactly:

```text
SAME
POTENTIALLY_EQUIVALENT
DIFFERENT
```

Do not implement the production canonical UUID pair machinery for MVP.

---

# 12. AUTOMATION

Keep:

```text
SAME + very high confidence + no hard conflict
    → AUTO_ACCEPT

SAME + uncertain
    → REVIEW

POTENTIALLY_EQUIVALENT
    → REVIEW

DIFFERENT + strong evidence
    → AUTO_MARK_DIFFERENT where implemented
```

The backend owns the actual governance threshold.

Frontend must not decide thresholds.

AI/ML must not decide authoritative governance.

---

# 13. HUMAN REVIEW

Human review remains a core MVP feature.

Reviewer can, where authorized:

- ACCEPT
- REJECT
- MARK_DIFFERENT
- OVERRIDE
- REMAP
- UNMAP

Human decisions must preserve the original AI recommendation.

Explicit rule:

> REJECT, MARK_DIFFERENT, and OVERRIDE must capture a short reason string.
> The reason is persisted in AuditLog. For MVP, the reason may be stored either in AuditLog.before_state/after_state or in a dedicated AuditLog.reason field if a directly queryable reason field is preferred.
>
> No separate review-reason or governance-decision table is required.

Do NOT create a separate ReviewReason table.

Do NOT build a complex reason-code taxonomy.

Example:

```text
AI recommendation:
SAME
Confidence: 98%

Human:
REJECT

Reason:
Pressure class mismatch: CLASS150 vs CLASS300
```

The final system should preserve both:

- AI recommendation (immutable in MatchRecommendation)
- human decision + reason (persisted in AuditLog)

A reviewer may correct permitted derived canonical information.

A reviewer may not modify immutable source data.

---

# 14. MAPPING

Mapping connects:

```text
Material
    ↓
NationalMaterial
```

Mapping basis remains:

```text
AUTO_SAME
HUMAN_CONFIRMED_SAME
HUMAN_OVERRIDE
```

A Material can have at most one active mapping.

Historical/superseded mappings may remain with a simple status.

Do not implement the full production mapping lifecycle.

---

# 15. AUDIT

Keep one simple AuditLog.

The MVP uses ONE generic AuditLog table.

Minimum conceptual fields:

```text
AuditLog:
- actor
- action
- entity_type
- entity_id
- before_state
- after_state
- timestamp
```

Purpose of each field:

- actor: who performed the action. For automated actions, represent the backend/system actor appropriately.
- action: the operation that occurred, for example IMPORT, AUTO_MAPPING, ACCEPT, REJECT, MARK_DIFFERENT, OVERRIDE, REMAP, UNMAP, or CANONICAL_DATA_CORRECTION.
- entity_type: the type of entity affected.
- entity_id: the identifier of the affected entity.
- before_state: relevant state before the action, where applicable.
- after_state: relevant state after the action, where applicable.
- timestamp: when the action occurred.

Keep before_state and after_state simple. For MVP they may use a JSON/JSONB representation if appropriate.

Important actions include:

- import
- automatic mapping
- human acceptance
- rejection
- override
- remap
- unmap
- canonical-data correction

Do NOT create a complex event-sourcing system.

Do NOT create multiple audit tables.

Keep it simple.

Do not build the full production AuditEvent taxonomy.

---

# 16. DATA VERSIONING

Explicitly defer source-version chains for MVP.

The MVP may simply ingest the current source records.

Do not build:

- supersedes_material_id
- source version chains
- automatic historical rematching
- source-version lifecycle workflows

The source/original values should still be preserved on the Material record.

---

# 17. MATCHINGRUN

Explicitly defer:

- MatchingRun
- operation_key
- input_fingerprint
- concurrent request idempotency
- polling
- background jobs

Matching remains synchronous.

Conceptually:

```text
POST /api/v1/matches/run
    ↓
normalize/canonicalize inputs
    ↓
candidate generation
    ↓
matching
    ↓
governance
    ↓
persist results
    ↓
return response
```

Do not build a job system.

---

# 18. DATABASE COMPLEXITY

The MVP database should remain simple.

Do not add:

- distributed locks
- event sourcing
- workflow engines
- generic metadata systems
- vector databases
- complex inheritance structures
- unnecessary repository abstractions

Prefer straightforward relational tables, foreign keys, indexes, and unique constraints.

---

# 19. SECURITY

The MVP still requires basic security hygiene.

At minimum:

- backend validation
- parameterized/database-safe queries through SQLAlchemy
- controlled file ingestion
- file type/size validation
- no secrets in source code
- no direct database access from frontend
- authorization checks on human-review actions
- no trusting frontend-provided governance decisions
- no client-generated National Material codes

Do not build production SSO for MVP.

---

# 20. P1 TIME PROTECTION

Add a prominent implementation note:

```text
P1 NORMALIZATION + ATTRIBUTE EXTRACTION IS A PROTECTED MILESTONE.
```

Before moving substantial engineering effort to:

- embeddings
- LLMs
- advanced UI
- advanced analytics

the team should demonstrate reliable extraction of the core valve attributes on the evaluation/demo dataset.

This is a dependency, not an optional polish phase.

Matching quality is dependent on normalization and attribute-extraction quality. P2 matching should not be treated as reliable until P1 has been validated against the evaluation/demo dataset.

The team should inspect extraction examples manually before proceeding to advanced matching.

This does NOT mean P1 must be perfect. It means the team must have confidence that the extracted technical attributes are sufficiently reliable for the MVP dataset.

---

# 21. DEMO DATA

The demo/evaluation dataset should deliberately contain:

1. Exact duplicate materials
2. Same technical material with different descriptions
3. Abbreviations
4. Formatting differences
5. UOM variations
6. CLASS150 vs CLASS300
7. SS304 vs SS316 trim differences
8. Different valve types
9. Different connection types
10. Missing identity-defining attributes
11. Ambiguous attributes
12. Genuinely different materials
13. Multiple plausible candidates
14. Records where normalization is necessary before matching

Important:

Synthetic/demo data must be clearly labelled as synthetic if it is not real authorized CPSE material-master data.

Do not claim synthetic data is real CPSE data.

The dataset should be intentionally designed to demonstrate both:

```text
SUCCESSFUL HARMONIZATION
```

and

```text
SAFE NON-HARMONIZATION.
```

Especially demonstrate:

```text
CLASS150 ≠ CLASS300
```

and:

```text
UNKNOWN trim ≠ permission to merge.
```

---

# 22. MVP SUCCESS CRITERIA

A judge should be able to follow this complete sequence:

1. Upload CPSE CSV/XLSX files.
2. Validate imported records.
3. See imported source materials.
4. See normalized technical attributes.
5. Start matching.
6. See candidate materials.
7. See attribute-by-attribute technical comparison.
8. See SAME / POTENTIALLY_EQUIVALENT / DIFFERENT.
9. See why the recommendation was made.
10. See high-confidence SAME cases automatically harmonized.
11. See uncertain cases enter human review.
12. Human accepts/rejects/overrides/remaps as appropriate.
13. See resulting National Material mapping.
14. See audit/history.
15. See before/after harmonization impact.

Short demo example for explainability:

```text
AI:
SAME

Human:
REJECT

Reason:
Pressure class mismatch — CLASS150 vs CLASS300
```

The UI should make this visible during the demonstration.

The purpose is to demonstrate that human governance is explainable and auditable rather than simply changing a status value.

The exact metric values shown in the demo must come from the actual dataset and system output.

Never fabricate impact numbers.

---

# 23. MVP WOW FACTOR

The wow factor should come from the workflow, not infrastructure.

The judge should see:

```text
CPSE files
    ↓
normalized technical attributes
    ↓
candidate matches
    ↓
clear technical comparison
    ↓
AI classification
    ↓
automatic harmonization
    ↓
human review for uncertain cases
    ↓
National Material
    ↓
audit/history
    ↓
before/after impact
```

Make hard conflicts visually obvious.

Example:

```text
CLASS150
vs
CLASS300
```

must visibly show why they are different.

---

# 24. DEFERRED FEATURES REMAIN DEFERRED

Preserve the existing deferred feature list.

Do not convert deferred production capabilities into MVP requirements.

The following remain explicitly deferred:

- MatchingRun
- source version chains
- production category schema engine
- Family lifecycle
- National Material merge/split workflows
- complex provenance
- production governance event model
- production SSO
- SAP/ERP integration
- Redis
- Celery
- Kafka
- microservices
- Kubernetes
- vector database
- distributed processing
- production ML infrastructure

---

# 25. DO NOT OVER-GENERALIZE

Add an explicit design rule:

> The MVP should solve the VALVE use case well rather than building abstractions for hypothetical future categories.

When a judge asks how the system can expand to other categories, the team can explain that the production architecture supports category-specific identity schemas and attributes.

The MVP does not need to implement that generalization.

---

# 26. MVP Definition of Done

The MVP is NOT done merely because individual APIs work.

It is done when the team can demonstrate the complete workflow:

```text
CPSE data
→ ingestion
→ normalization
→ technical attribute extraction
→ candidate generation
→ matching
→ classification
→ governance
→ automatic mapping where permitted
→ human review where required
→ National Material
→ audit
→ measurable harmonization impact
```

The system must also demonstrate safe handling of:

- hard technical conflicts
- missing identity attributes
- ambiguous attributes
- UOM differences
- human override

---

# 27. FINAL MVP IMPLEMENTATION PRINCIPLE

The MVP should be:

```text
SMALL
RELIABLE
EXPLAINABLE
DEMONSTRABLE
EXTENSIBLE
```

but NOT:

```text
ENTERPRISE-GRADE INFRASTRUCTURE
```

The goal is to prove the core harmonization workflow.

---

# 28. DO NOT REINTRODUCE PRODUCTION COMPLEXITY

The purpose of this patch is to restore execution guidance, not expand the MVP.

Do not reintroduce:

- MatchingRun
- operation_key
- input_fingerprint
- source version chains
- generic category schema engine
- Family lifecycle
- complex provenance
- AI microservice
- Redis
- Celery
- Kafka
- microservices
- vector database
- production SSO
- complex identity infrastructure

---

# 29. FINAL CONSISTENCY CHECK

After editing this document, inspect the entire document.

Verify there is no implication that we are building:

- a generic category engine
- a Family lifecycle system
- a separate AI service
- a MatchingRun job system
- production source versioning
- complex identity infrastructure

Verify that these remain mandatory:

- VALVE technical attributes
- hard conflict detection
- SAME / POTENTIALLY_EQUIVALENT / DIFFERENT
- human review
- human override
- backend-controlled National Material creation
- deterministic National Material identity
- approved UOM normalization
- explainability
- audit
- one active mapping
- protected normalization/attribute-extraction milestone

If a contradiction with `docs/ARCHITECTURE.md` is found:

DO NOT silently resolve it.

Report the contradiction and wait for approval.

---

# END OF MVP SCOPE
