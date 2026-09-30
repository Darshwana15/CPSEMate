## Purpose

This document defines the MVP-only AI/ML boundary for the SIH26099 backend. The purpose is to keep AI/ML work tightly focused on the existing deterministic matching baseline and to prevent scope expansion beyond what is required for a validated MVP.

The working backend baseline is the deterministic matcher in `app/services/matching.py`. The AI/ML team's job is not to rebuild the matching system from scratch. The job is to evaluate the existing matcher, measure whether a simple ML improvement is justified, and if it is, improve the matching/scoring/classification logic while preserving the safety rules already enforced by the backend.

## Existing Backend Baseline

The current backend already contains working deterministic logic for the MVP:

- Normalization is handled in the backend using deterministic parsing and attribute extraction.
- Candidate generation occurs in the existing matching flow and is designed to compare materials across CPSEs while rejecting same-CPSE comparisons.
- Similarity and scoring are computed using deterministic rules and structured attribute comparison.
- Classification remains `SAME`, `POTENTIALLY_EQUIVALENT`, or `DIFFERENT`.
- Evidence and explanation are produced from explicit attribute-level comparisons.

This deterministic matcher is the baseline. It is the reference implementation for the AI/ML team.

## AI/ML MVP Scope

AI/ML work is in scope only when it demonstrates a measurable improvement over the existing deterministic matcher.

In scope:

- evaluate the existing matching logic
- improve material-pair similarity/scoring if justified
- use normalized technical attributes
- use text similarity and feature engineering
- train a simple supervised model if labelled data exists
- calibrate `SAME`, `POTENTIALLY_EQUIVALENT`, and `DIFFERENT` thresholds
- produce `confidence`
- produce `evidence`
- produce `explanation`
- add tests
- compare baseline vs improved approach

Possible MVP models:

- Logistic Regression
- Random Forest
- XGBoost / LightGBM

Use the simplest model that demonstrates measurable improvement over the baseline.

## OUT OF MVP

The following are explicitly out of scope for the SIH26099 MVP:

- LLM-based normalization
- LLM agents
- specialized model training beyond the MVP evaluation path
- external vector storage systems
- pgvector
- Milvus
- Redis
- Kafka
- Celery
- separate ML microservices
- operational model-serving infrastructure
- online learning
- production training loops
- new database tables
- new feedback pipelines

Normalization remains the existing deterministic backend implementation for the MVP.

Human review data may be used to create an offline labelled dataset, but ongoing model retraining is out of scope.

## Non-Negotiable Safety Rules

The ML model is never the final authority over technical conflicts.

Hard conflicts must override ML predictions.

Examples:

- `CLASS150` vs `CLASS300` -> `DIFFERENT` -> confidence `0.0`
- `DN50` vs `DN100` -> `DIFFERENT` -> confidence `0.0`
- `BALL` vs `GATE` -> `DIFFERENT` -> confidence `0.0`
- `RF` vs `SOCKET_WELD` -> `DIFFERENT` -> confidence `0.0`

`NULL` means `UNKNOWN`.

`NULL` is never a wildcard.

Never infer a missing identity attribute simply to increase similarity.

If required identity information is missing, the system must not turn the pair into an automatic `SAME` mapping.

## Required Output

The matching component must continue to produce:

- `classification`
- `confidence`
- `evidence`
- `explanation`

Classification values remain exactly:

- `SAME`
- `POTENTIALLY_EQUIVALENT`
- `DIFFERENT`

Do not introduce additional classifications for the MVP.

## Backend Boundary

AI/ML must not directly:

- `INSERT`
- `UPDATE`
- `DELETE`

PostgreSQL data.

AI/ML only returns a matching result. The backend remains responsible for:

- database writes
- transactions
- `NationalMaterial`
- mappings
- `AuditLog`
- human review
- authentication
- API behavior

A normal Python module/function is sufficient. Do not create a separate service.

## Evaluation

Before replacing any existing logic, the team must report:

1. Existing matcher accuracy, precision, and recall where labelled data allows.
2. False `SAME` cases.
3. False `DIFFERENT` cases.
4. `POTENTIALLY_EQUIVALENT` cases.
5. Proposed ML approach.
6. ML metrics.
7. Baseline vs ML comparison.
8. Recommended thresholds.

The objective is not to maximize `SAME` matches. The objective is:

- high-precision `SAME`
- safe `DIFFERENT`
- useful review queue

## Deliverable

The AI/ML team must return:

- baseline evaluation
- labelled dataset
- proposed ML approach
- ML implementation only if justified by measurable improvement
- baseline-vs-ML comparison
- calibrated thresholds
- evidence/explanation format
- tests
- integration instructions

If the deterministic baseline performs sufficiently well for the MVP,
the correct outcome is to keep the deterministic implementation rather
than introduce ML unnecessarily.

Keep the implementation compatible with the existing
`app/services/matching.py` architecture.

## Scope Lock

If an AI/ML feature is not required to demonstrate a better MVP matching result, do not build it.

No scope expansion without explicit approval.

The AI/ML team must remain within the deterministic backend baseline unless there is clear, measured evidence that a simple ML improvement yields a better MVP result.
