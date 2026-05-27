# Decisions — Breathe ESG

## SAP — Flat file (MB51/SE16 export), not OData or IDoc

**What we chose:** Semicolon/tab-delimited flat-file export from SAP transaction MB51 (material document list) or SE16 (table browser on MSEG). German column headers supported (Menge, Meins, Werks, Budat, etc.) alongside English equivalents.

**Why not OData:** SAP OData services require a BASIS team to activate and configure the service in transaction SICF. Most enterprise SAP clients have not done this for sustainability data, and it requires SAP BASIS involvement that can't happen in the client onboarding window.

**Why not IDoc:** IDocs are XML-wrapped EDI documents used for system-to-system integration (SAP ↔ SAP or SAP ↔ ERP). A sustainability team exporting fuel data does not use IDocs — they use SE16/MB51 and export to CSV/Excel. IDoc would be the right choice for a real-time integration where the client's SAP pushes data to us automatically; the prototype handles the realistic hand-off.

**Why not BAPI/RFC:** Requires network access to the SAP system and a service user with appropriate authorizations. Not achievable without client IT involvement.

**Subset handled:** MSEG (goods movement) records for fuel materials (diesel, petrol, CNG/LNG). Material description keywords determine category. Plant codes are preserved as-is (production would need a lookup table from the client's SAP material master).

**What I'd ask the PM:** Do you have the plant-to-location name mapping? SAP plant codes (IN01, IN02) are meaningless without a master data table. Also: what movement types should we filter for? (201 = goods issue to cost center, 261 = goods issue to production order — both could be relevant.)

**Ignored:** FI (financial) documents, cost centre allocations, CO module data, plant-level CO2 factors from SAP EHS.

---

## Utility — Portal CSV export, not PDF bills or Green Button API

**What we chose:** CSV export from the utility portal (DISCOM in India: BSES, TPDDL, Adani, MSEDCL, BESCOM). Columns: Meter ID, Billing Period Start/End, Consumption (kWh), Unit, Tariff, Site, Amount.

**Why not PDF bills:** PDF parsing requires OCR (Tesseract or a paid API) and is brittle — every utility has a different bill layout, and layout changes break parsers. The facilities team already exports from the portal to CSV; asking them to upload PDFs adds complexity with no benefit.

**Why not Green Button API:** Green Button (NAESB standard) is used by US utilities. Indian DISCOMs do not expose Green Button APIs. Even in the US, only some utilities support it and it requires an API key per account.

**Billing period alignment:** Utility bills don't align with calendar months (a billing period might be 15 Jan to 14 Feb). We store both `period_start` and `period_end` on EmissionRecord so this is preserved exactly. Analysts can group by calendar month using period_start.

**What I'd ask the PM:** Do any sites have multiple meters per building that need to be aggregated? If so we need a meter-to-building grouping table. Also: are there any sites on green/renewable tariffs that should be excluded from Scope 2?

**Ignored:** Demand charges, reactive energy (kVARh), power factor penalties, time-of-use breakdowns. These don't affect carbon calculation.

---

## Travel — CSV file upload (Navan/Concur export format), not live API

**What we chose:** CSV upload matching the Navan "Trip Report Export" and Concur "Standard Detail" report format. Columns: Trip Date, Traveler, Travel Type (Flight/Hotel/Car/Taxi/Train), Origin, Destination, Class, Distance (km), Nights, Amount.

**Why not Concur API:** Concur OAuth requires a client_id + client_secret from Concur's App Center — the client's IT team must provision this, and it typically takes 2–4 weeks. The travel manager can export a CSV today.

**Why not Navan API:** Same reason. Navan's API requires an API key provisioned by the Navan account team. File export is the immediate option.

**Distance calculation:** When the CSV provides distance, we use it. When it doesn't (common for Concur exports), we compute great-circle distance from IATA airport coordinates for a hardcoded set of common routes. In production this would call an aviation distance API (e.g. AviationStack, OpenFlights, or the ICAO distance calculator).

**Emission factors:** We use simplified DEFRA/EPA factors: 0.255 kgCO2e/km for short-haul (<1500 km), 0.195 for long-haul. Cabin class multipliers applied (economy: 1×, business: 2.9×, first: 4×). In production: DEFRA's detailed aviation factors by route type, or ICAO's Carbon Offset calculator.

**What I'd ask the PM:** Does the client use Concur or Navan? The column names differ (Concur calls it "Expense Type", Navan calls it "Travel Type"). Also: should we count return legs separately, or only one-way? GHG Protocol says round-trips should count both legs.

**Ignored:** Multi-leg itineraries with layovers (we count each segment separately, which is correct but requires the export to be segment-level, not trip-level). Taxi/rideshare without distance (Uber receipts often omit distance). Car rental without daily mileage.

---

## Review workflow — linear state machine, not approval chains

Lock-for-audit is one-way (locked → cannot be unlocked via the UI). Intentional — auditors need immutable data. A Django admin action can unlock if needed for corrections.

We don't implement two-person approval (maker-checker). This is a common requirement for GHG reporting under ISO 14064 but adds significant scope. The `role` field on User is ready for it.

## Authentication — JWT, not session auth

JWT chosen so the React frontend and a future mobile app can authenticate without cookies. Tokens are stored in localStorage — acceptable for a prototype, but in production we'd use httpOnly cookies to prevent XSS token theft.
