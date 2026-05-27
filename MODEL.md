# Data Model — Breathe ESG

## Overview
Three Django apps: `accounts` (auth + multi-tenancy), `ingestion` (parsing, normalization, review workflow).

---

## Multi-tenancy
Every piece of data is scoped to an `Organisation`. The `User` model carries an `organisation` FK directly — simpler than a membership join table for a prototype, and sufficient for the use case where one user belongs to one client.

**Query pattern:** every view does `EmissionRecord.objects.filter(organisation=request.user.organisation)`. No cross-tenant leaks possible because the organisation FK is on the User, not resolved at query time.

**What we'd add for production:** row-level security at the Postgres layer, a proper `TenantMembership` table for multi-org access, and middleware that sets the org on the request rather than in every view.

---

## Models

### `Organisation`
Top-level tenant. Every key model has an `organisation` FK.
- `reporting_year_start`: MM-DD string. Lets us group by fiscal year without duplicating date logic.

### `User` (extends AbstractUser)
- `organisation`: FK to Organisation
- `role`: analyst / admin / auditor. Analyst can review; admin can lock; auditor is read-only.

### `IngestionBatch`
One batch = one file upload or API pull.
- Tracks: source_type (sap/utility/travel), uploaded_by, uploaded_at, original_filename, status (processing/done/failed), row_count, error_count.
- **Why we store the batch:** so analysts can see "32 SAP rows came in on 15 Jan from Priya" and can correlate records back to a single ingest event.

### `RawRow`
Verbatim capture of each parsed row as a JSON object. This is the audit-proof record of exactly what came in — even if we change parsing logic later, the original data is preserved.

### `EmissionRecord`
The canonical normalized emission record. One row = one emission-generating activity.

**Scope assignment (GHG Protocol):**
- Scope 1: Direct combustion — SAP fuel records (diesel, petrol, LNG/CNG)
- Scope 2: Purchased electricity — utility data
- Scope 3: Value chain — business travel (flights, hotel, car, taxi, train)

**Unit normalization strategy:**
| Source | Raw units | Normalized to |
|--------|-----------|---------------|
| SAP fuel | L, gal, m³, kg | litres |
| SAP gas | kWh, MWh, m³ | kWh |
| Utility | kWh, MWh, GJ, MJ | kWh |
| Travel flight | km, miles | km |
| Travel hotel | nights | room-nights |

Raw value and raw unit are always stored alongside the normalized values so we can re-run emission factors without re-parsing.

**CO2e calculation:**
Computed at ingest using `settings.EMISSION_FACTORS`. Factor version is stored on each record so historical records survive factor updates. Factors are simplified DEFRA/EPA/IEA values.

**Review state machine:**
```
PENDING → FLAGGED (analyst flags suspicious row)
PENDING → APPROVED (analyst signs off)
FLAGGED → PENDING (unflag)
FLAGGED → APPROVED
APPROVED → LOCKED (admin locks for audit — one-way)
```
Locked records are immutable via the API. An admin Django action can unlock if needed.

### `AuditLog`
Immutable. Written by service functions, never directly. Captures: action, actor, timestamp, before/after state as JSON, optional note. Never delete rows from this table.

---

## Source-of-truth tracking
Every `EmissionRecord` has:
- `batch` FK → which upload produced it
- `raw_row` OneToOne → verbatim source data
- `activity_value_raw` + `activity_unit_raw` → original before normalization
- `sap_document_number` / `utility_meter_id` / `travel_traveler_id` → source-system identifiers
- `is_edited` flag — set if any field was manually corrected after ingest
- Full `AuditLog` chain

---

## Indexes
Composite indexes on `(organisation, status)`, `(organisation, scope, activity_date)`, and `(batch)` cover the three main query patterns: review queue, scope breakdown, and batch detail.
