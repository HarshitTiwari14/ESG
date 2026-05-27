# Tradeoffs — Breathe ESG

## 1. No emission factor calculation engine

We compute CO2e at ingest using hardcoded factors from `settings.EMISSION_FACTORS` (simplified DEFRA/EPA/IEA values). We did not build a factor management system.

**What that means:** factors can't be updated per-client, per-year, or per-grid-region without a code change. There's no audit trail for factor changes. If DEFRA releases 2024 factors, all historical records remain at 2023 values.

**Why we skipped it:** A proper factor engine is a significant domain problem: factors are published annually, vary by country, fuel grade, grid intensity, and reporting standard (DEFRA vs EPA vs GHG Protocol). Implementing it half-heartedly would produce wrong numbers that look right. The `factor_version` field on every EmissionRecord is the hook for a future factor table.

**What production needs:** A `EmissionFactor` table keyed by (category, region, year, standard), with a versioned snapshot at the time of each batch ingest.

---

## 2. No real-time API integrations

All three sources use file upload, not live API pulls. There is no scheduler, no OAuth token management, no webhook handler.

**Why we skipped it:** Concur OAuth requires client IT provisioning (2–4 weeks). SAP OData requires BASIS configuration. Green Button requires utility account provisioning. None of these can be demonstrated in a prototype without real client credentials that take weeks to obtain. File upload is the honest mechanism for a first-integration.

**What production needs:** A Celery task queue for scheduled pulls, OAuth token refresh per-client, retry logic with exponential backoff, and a connection status UI. Each source would have a `DataSource` model storing credentials (encrypted), last-pull timestamp, and pull schedule.

---

## 3. No Scope 3 categories beyond travel

We handle Scope 3 Category 6 (business travel) only. We do not handle:
- Category 1: Purchased goods and services (the SAP procurement data could feed this, but requires spend-based or supplier-specific emission factors)
- Category 11: Use of sold products
- Category 15: Investments
- Any other Scope 3 category

**Why we skipped it:** Each Scope 3 category requires a different calculation methodology. Category 1 (purchased goods) requires either a spend-based approach (spend × economic emission factor from Exiobase/EEIO) or a supplier-specific approach (supplier discloses their emissions). Neither is trivial. The SAP procurement data in this prototype is parsed but only the fuel subset is categorized; the rest would need a material-group → Scope 3 category mapping built with the client.

**What production needs:** A configurable Scope 3 category mapping, integration with economic emission factor databases (Exiobase, EPA USEEIO), and a supplier engagement portal.
