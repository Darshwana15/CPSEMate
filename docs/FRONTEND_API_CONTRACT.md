# SIH26099 Frontend API Contract

This document provides the API contract for the frontend team to integrate with the SIH26099 Material Harmonization backend.

## Base URL
All endpoints are relative to: `/api/v1`

*Note for local development: The default local backend typically runs on `http://localhost:8000`. Ensure your frontend environment variables point to the correct base URL.*

## Authentication
MVP endpoints requiring human governance (e.g., Review Queue and Review Actions) are protected by a static MVP token.
**Header Required:** `X-Reviewer-Token`
**Value:** `<configured reviewer token>` (Configured via backend environment)

*Do not implement complex JWT/SSO for the MVP. Pass this token explicitly in your API client headers when calling protected endpoints.*

## CORS
CORS is configured via the backend's environment variables (`CORS_ALLOWED_ORIGINS`). By default, it supports standard local development ports (e.g., `http://localhost:3000`). If your frontend runs on a different port, update the `.env` file on the backend. Do not bypass CORS using insecure extensions.

## Error Format
The API uses standardized HTTP status codes:
- **400 Bad Request**: Validation errors or business rule violations (e.g., trying to map an incomplete material, missing a required reason).
- **401 Unauthorized**: Missing or invalid `X-Reviewer-Token`.
- **404 Not Found**: The requested resource (Material or Recommendation) does not exist.
- **413 Content Too Large**: Uploaded file exceeds the 5MB limit.
- **500 Internal Server Error**: Unexpected backend failure.

Error responses always take the shape:
```json
{
  "detail": "Human readable error message explaining the rule violation."
}
```

---

## Endpoint Inventory


### 0. Create CPSE
**POST** `/cpses`
**Auth Required**: No

**Request Payload:**
```json
{
  "code": "CPCL-DEMO",
  "name": "Chennai Petroleum Corporation Limited"
}
```

**Response (201 Created):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "code": "CPCL-DEMO",
  "name": "Chennai Petroleum Corporation Limited",
  "created_at": "2026-08-31T12:00:00Z",
  "updated_at": "2026-08-31T12:00:00Z"
}
```


### 0.1. List CPSEs
**GET** `/cpses`
**Auth Required**: No

**Request Payload:** None

**Response (200 OK):**
```json
[
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "code": "CPCL-DEMO",
    "name": "Chennai Petroleum Corporation Limited",
    "created_at": "2026-08-31T12:00:00Z",
    "updated_at": "2026-08-31T12:00:00Z"
  }
]
```

### 0.1.1. Delete CPSE
**DELETE** `/cpses/{cpse_id}`
**Auth Required**: Yes (`X-Reviewer-Token`)

**Request Payload:** None

**Behavior & Safety Rules:**
- Requires reviewer authentication via `X-Reviewer-Token`.
- Removes the CPSE and its source-material operational data in an atomic transaction.
- Dependent records removed:
  - Dependent `MaterialNationalMapping` rows for all materials belonging to the CPSE
  - Dependent `MatchRecommendation` rows (as source or candidate) for all materials belonging to the CPSE
  - All source `Material` rows belonging to the CPSE
  - The `CPSE` record
- **National Material Preservation**: `NationalMaterial` records are shared assets and are **never** deleted.
- **Audit Preservation**: Historical `AuditLog` entries are immutable and **never** deleted.
- Returns `404 Not Found` if `cpse_id` does not exist.

**Response (200 OK):**
```json
{
  "status": "success",
  "deleted_id": "123e4567-e89b-12d3-a456-426614174000",
  "deleted_type": "CPSE"
}
```

### 0.2. List Materials for CPSE
**GET** `/cpses/{cpse_id}/materials`
**Auth Required**: No

**Request Payload:** None

**Response (200 OK):**
```json
[
  {
    "id": "222e4567-e89b-12d3-a456-426614174000",
    "cpse_id": "123e4567-e89b-12d3-a456-426614174000",
    "source_material_code": "VLV-001",
    "source_description": "BALL VALVE 2IN 300LB",
    "category": "VALVE",
    "normalized_description": "Ball Valve, 2\", Class 300"
  }
]
```
*Note: Returns `[]` if the CPSE exists but has no materials. Returns `404 Not Found` if the `cpse_id` does not exist.*

### 0.3. Get Material Detail
**GET** `/materials/{material_id}`
**Auth Required**: No

**Request Payload:** None

**Response (200 OK):**
```json
{
  "id": "222e4567-e89b-12d3-a456-426614174000",
  "cpse_id": "123e4567-e89b-12d3-a456-426614174000",
  "source_material_code": "VLV-001",
  "source_description": "BALL VALVE 2IN 300LB",
  "source_uom": "EA",
  "source_specifications": "API 6D",
  "raw_source_data": {"Code": "VLV-001", "Desc": "BALL VALVE 2IN 300LB"},
  "category": "VALVE",
  "valve_type": "BALL",
  "size": "DN50",
  "body_material": "CARBON_STEEL",
  "pressure_class": "CLASS300",
  "connection_type": "RF",
  "trim": "SS316",
  "normalized_uom": "EACH",
  "normalized_description": "Ball Valve, 2\", Class 300",
  "normalized_attributes": {"extracted_trim": "SS316"},
  "created_at": "2026-08-31T12:00:00Z",
  "updated_at": "2026-08-31T12:00:00Z"
}
```
*Note: Returns `404 Not Found` if the material ID does not exist. A malformed UUID will return standard HTTP 422.*

### 0.4. Delete Material
**DELETE** `/materials/{material_id}`
**Auth Required**: Yes (`X-Reviewer-Token`)

**Request Payload:** None

**Behavior & Safety Rules:**
- Requires reviewer authentication via `X-Reviewer-Token`.
- Removes a single Material and its dependent operational data in an atomic transaction.
- Dependent records removed:
  - Dependent `MaterialNationalMapping` rows for this material
  - Dependent `MatchRecommendation` rows where this material is source or candidate
  - The source `Material` record
- **National Material Preservation**: `NationalMaterial` records are shared assets and are **never** deleted.
- **Audit Preservation**: Historical `AuditLog` entries are immutable and **never** deleted.
- Returns `404 Not Found` if `material_id` does not exist.

**Response (200 OK):**
```json
{
  "status": "success",
  "deleted_id": "222e4567-e89b-12d3-a456-426614174000",
  "deleted_type": "MATERIAL"
}
```

### 1. Upload Materials
**POST** `/materials/import`
**Auth Required**: No
**Content-Type**: `multipart/form-data`

**Request:**
- `cpse_id` (string/UUID, form data)
- `file` (binary, form data - `.csv` or `.xlsx` under 5MB)

**Response (200 OK):**
```json
{
  "total_rows": 100,
  "imported_rows": 98,
  "rejected_rows": 2,
  "duplicate_rows": 1,
  "errors": [
    {
      "row": 15,
      "error": "Missing mandatory fields (code, desc, or uom)"
    }
  ]
}
```

### 2. Normalize Material
**POST** `/materials/{material_id}/normalize`
**Auth Required**: No

**Request:** Empty body

**Response (200 OK):**
```json
{
  "status": "success",
  "material_id": "123e4567-e89b-12d3-a456-426614174000",
  "normalized": true
}
```

### 3. Generate Match Recommendations
**POST** `/materials/{material_id}/match`
**Auth Required**: No

**Request:** Empty body

**Response (200 OK):**
```json
{
  "status": "success",
  "material_id": "123e4567-e89b-12d3-a456-426614174000",
  "candidate_count": 5,
  "recommendations_created": 5,
  "recommendations": [
    {
      "candidate_id": "987e6543-e21b-34d5-c678-426614174999",
      "classification": "SAME",
      "confidence": 0.92,
      "explanation": "Same valve type, size, body material, pressure class, connection type, and trim."
    }
  ]
}
```

### 4. Auto-Harmonize Safe Matches
**POST** `/materials/{material_id}/harmonize`
**Auth Required**: No

**Request:** Empty body

**Response (200 OK):**
```json
{
  "status": "success",
  "national_material_id": "555e4567-e89b-12d3-a456-426614174111",
  "national_material_action": "CREATED",
  "mapping_id": "777e4567-e89b-12d3-a456-426614174222",
  "national_code": "NM-12345678"
}
```
*Note: If the material lacks safe recommendations or is already mapped, this returns an appropriate message indicating skipped processing.*

### 5. Fetch Review Queue
**GET** `/reviews/queue`
**Auth Required**: Yes (`X-Reviewer-Token`)

**Request:** None

**Response (200 OK):**
```json
{
  "queue": [
    {
      "recommendation_id": "444e4567-e89b-12d3-a456-426614174000",
      "source_material_id": "123e4567-e89b-12d3-a456-426614174000",
      "candidate_material_id": "987e6543-e21b-34d5-c678-426614174999",
      "classification": "POTENTIALLY_EQUIVALENT",
      "confidence": 0.86,
      "evidence": {
        "attributes": {
           "valve_type": {"match": true, "source": "BALL", "candidate": "BALL", "weight": 0.12},
           "trim": {"match": null, "source": "SS304", "candidate": null, "weight": 0.0}
        },
        "description_similarity": 0.86
      },
      "explanation": "Missing information for trim.",
      "source_valve_type": "BALL",
      "source_size": "DN50",
      "source_body_material": "CARBON_STEEL",
      "source_pressure_class": "CLASS300",
      "source_connection_type": "RF",
      "source_trim": "SS304"
    }
  ]
}
```

### 6. Perform Human Review Action
**POST** `/reviews/{recommendation_id}/action`
**Auth Required**: Yes (`X-Reviewer-Token`)
**Content-Type**: `application/json`

**Request Payload:**
```json
{
  "action": "ACCEPT",
  "reason": "Verified drawing specs matching the target.",
  "national_material_id": null
}
```

#### Supported Actions & Business Rules:
- **`ACCEPT`**: Approves a `SAME` or `POTENTIALLY_EQUIVALENT` match.
  - *Rule*: Frontend MUST NOT assume that `ACCEPT` is valid for every `POTENTIALLY_EQUIVALENT` or `SAME` recommendation. The backend is authoritative and may reject `ACCEPT` with `HTTP 400` when business rules or incomplete identity data prevent safe acceptance.
  - *Rule*: If the backend rejects `ACCEPT`, the frontend should display the backend error and allow the reviewer to use the appropriate action, such as `OVERRIDE`, when applicable.
  - *Rule*: Will return `400 Bad Request` if the source material has an incomplete identity (e.g., missing trim). Incomplete identities CANNOT be accepted natively; they must use `OVERRIDE`.
- **`REJECT`**: Declines the match.
  - *Rule*: `reason` is **strictly required**.
- **`MARK_DIFFERENT`**: Declares the candidates technically distinct despite text similarities.
  - *Rule*: `reason` is **strictly required**.
- **`OVERRIDE`**: Forces a mapping to a specific National Material, bypassing automated logic.
  - *Rule*: `reason` and `national_material_id` are **strictly required**.

**Response (200 OK):**
```json
{
  "status": "success",
  "action": "ACCEPT",
  "mapping_created": true,
  "mapping_id": "777e4567-e89b-12d3-a456-426614174222"
}
```


### 7. List National Materials
**GET** `/national-materials`
**Auth Required**: No

**Request Payload:** None

**Response (200 OK):**
```json
[
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "national_code": "NM-12345678",
    "canonical_description": "Ball Valve, 2\", Class 300",
    "status": "ACTIVE"
  }
]
```

### 8. Get National Material Detail
**GET** `/national-materials/{national_material_id}`
**Auth Required**: No

**Request Payload:** None

**Response (200 OK):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "national_code": "NM-12345678",
  "category": "VALVE",
  "canonical_description": "Ball Valve, 2\", Class 300",
  "valve_type": "BALL",
  "size": "DN50",
  "body_material": "CARBON_STEEL",
  "pressure_class": "CLASS300",
  "connection_type": "RF",
  "trim": "SS316",
  "normalized_uom": "EACH",
  "identity_key": "VALVE|BALL|DN50|CARBON_STEEL|CLASS300|RF|SS316",
  "status": "ACTIVE"
}
```

### 9. Get Material Mapping History
**GET** `/materials/{material_id}/mapping-history`
**Auth Required**: No

**Request Payload:** None

**Response (200 OK):**
```json
[
  {
    "id": "777e4567-e89b-12d3-a456-426614174222",
    "material_id": "123e4567-e89b-12d3-a456-426614174000",
    "national_material_id": "555e4567-e89b-12d3-a456-426614174111",
    "basis": "AUTO_SAME",
    "status": "ACTIVE",
    "recommendation_id": "444e4567-e89b-12d3-a456-426614174000",
    "created_at": "2026-08-31T12:00:00Z",
    "updated_at": "2026-08-31T12:00:00Z"
  }
]
```

### 10. List Audit Logs
**GET** `/audit`
**Auth Required**: No
**Query Parameters:**
- `entity_type` (optional string): Filter by entity type (e.g., "MATERIAL")
- `entity_id` (optional string): Filter by entity ID

**Response (200 OK):**
```json
[
  {
    "id": "888e4567-e89b-12d3-a456-426614174333",
    "actor": "SYSTEM",
    "action": "NORMALIZE",
    "entity_type": "MATERIAL",
    "entity_id": "123e4567-e89b-12d3-a456-426614174000",
    "before_state": {},
    "after_state": {"valve_type": "BALL"},
    "reason": "Normalized from raw data",
    "created_at": "2026-08-31T12:00:00Z"
  }
]
```


### 11. Dashboard Overview
**GET** `/dashboard`
**Auth Required**: No

**Request Payload:** None

**Response (200 OK):**
```json
{
  "inventory": {
    "total_materials": 1500,
    "total_cpses": 3
  },
  "harmonization": {
    "total_national_materials": 450,
    "total_mapped_materials": 1200,
    "automation_rate_percentage": 85.5
  },
  "review": {
    "pending_reviews": 45,
    "completed_reviews": 120
  },
  "cpse_breakdown": [
    {
      "cpse_id": "123e4567-e89b-12d3-a456-426614174000",
      "cpse_name": "CPSE A",
      "total_materials": 500,
      "mapped_materials": 400
    }
  ]
}
```

---

## Frontend Scope Lock

The frontend is responsible for:
- displaying backend data
- displaying classification, confidence, evidence, and explanations
- uploading files
- triggering normalization, matching, and harmonization endpoints
- displaying the review queue
- submitting human review actions
- displaying backend success/error responses

The frontend MUST NOT:
- calculate matching scores
- calculate confidence
- classify materials
- implement hard-conflict rules
- infer missing attributes
- decide whether a material is safe to harmonize
- create NationalMaterials
- create mappings directly
- write to PostgreSQL
- duplicate backend business rules

The backend is the single authority for business logic and state.

## Workflows and Integration Rules

**The backend is the absolute authority on business rules, mappings, and state.**

### 1. Materials Workflow
- **Source vs Derived:** The frontend must clearly distinguish between source data (e.g. `raw_source_data`, `source_description`) and normalized data (`valve_type`, `size`, etc.).
- **Immutability:** Source data is immutable. The frontend must never offer inputs or forms attempting to mutate `source_` fields.

### 2. Matching Workflow
- **No Client-Side Scoring:** The frontend must NOT calculate text similarities or determine whether two values represent a "conflict". Simply display the JSON structure provided by the backend's `evidence` field.
- **Classification Display:** Utilize standard UI badges for the backend's strict enum outputs: `SAME`, `POTENTIALLY_EQUIVALENT`, and `DIFFERENT`.
- **Backend Contract Values:** The frontend must treat `SAME`, `POTENTIALLY_EQUIVALENT`, and `DIFFERENT` as backend contracts. Do not introduce frontend-only classifications.

### 3. Harmonization Workflow
- **Automated Mapping:** The backend decides which `SAME` materials are safe for auto-harmonization based on complete identities. The frontend merely triggers `/harmonize`. Do NOT attempt to build client-side logic to determine if a material "should" be auto-harmonized.

### 4. Review & Audit Workflow
- **Human Actions:** Present buttons exclusively for the available actions: `ACCEPT`, `REJECT`, `MARK_DIFFERENT`, and `OVERRIDE`.
- **Reasoning:** Enforce text boxes for `reason` where the backend requires it (e.g. `REJECT`). The backend will throw a `400 Bad Request` if a reason is missing.
- **Overrides:** The `OVERRIDE` action bypasses logic to map to a specific target; the UI must prompt the user for the `national_material_id` explicitly for this action.
