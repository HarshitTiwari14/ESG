# Sources Research — Breathe ESG

## SAP

**Real-world format researched:** MB51 (Material Document List) flat-file export from SAP ECC/S4HANA.

**What we learned:**
- MB51 is the standard report a sustainability team requests from their SAP team for fuel and goods movement data
- The export is semicolon or tab-delimited depending on the SAP system locale
- German column headers are common: Belnr (document number), Bldat (document date), Budat (posting date), Werks (plant), Kostl (cost center), Matnr (material number), Maktx (material description), Menge (quantity), Meins (unit of measure), Lifnr (vendor), Name1 (vendor name)
- Date format in German SAP: DD.MM.YYYY — completely different from ISO 8601
- Units include L (litres), GAL (gallons), KG (kilograms), M3 (cubic metres), KWH for gaseous fuels
- Material descriptions are client-specific but contain keywords (Diesel, Petrol, CNG, LNG)
- SAP sometimes inserts subtotal rows with `*` or `**` in the document type column — these must be skipped

**Sample data looks like:** Realistic Indian manufacturing plant with three facilities (IN01 Mumbai, IN02 Delhi, IN03 Pune). Materials cover HSD (High Speed Diesel), petrol (Mogas), and CNG. Vendor names are real Indian oil companies. Quantities are realistic for mid-size industrial operations (8,000–25,000 litres per month).

**What would break in production:**
- Plant code → location name lookup requires the client's SAP material master (`MARC` table)
- Material number → fuel category mapping must be built per-client (our keyword approach is heuristic)
- Movement type filtering (201, 261, etc.) is needed to exclude internal transfers
- Some SAP versions export Excel (.xlsx) not CSV — the parser handles CSV only

---

## Utility (Electricity)

**Real-world format researched:** DISCOM portal CSV exports from Indian utilities: BSES Rajdhani, TATA Power Delhi, BESCOM (Bangalore), MSEDCL (Maharashtra), Adani Electricity Mumbai.

**What we learned:**
- Most Indian DISCOM portals offer a "Download billing history" as CSV
- Columns typically include: Account/Meter ID, Billing Period (start and end dates), Units Consumed (in kWh), Sanctioned Load, Tariff Category, Amount, Currency
- Billing periods are the utility's billing cycle, not calendar months (e.g., 18 Jan – 17 Feb)
- Large commercial accounts (HT = High Tension) are billed monthly; small LT accounts may be billed bi-monthly
- Some exports use "Units" instead of "kWh" (Indian English for kWh units)
- Grid emission factor for India: 0.82 kgCO2e/kWh (CEA national average 2023). State-wise factors vary significantly (e.g., Goa: ~0.4, UP: ~0.96)

**Sample data looks like:** Four sites (Bangalore Office, Bangalore Warehouse, Delhi HQ, Mumbai Branch) across 4 months. HT (high voltage commercial) accounts show higher consumption (48,000–72,000 kWh/month). Tariff labels match real BESCOM/TPDDL tariff names.

**What would break in production:**
- Multi-meter buildings need aggregation — a floor on a shared meter appears as a separate row
- Some DISCOMs export MWh, not kWh (unit normalization handles this, but edge cases exist)
- Bill date ≠ consumption period end date — we use period start/end fields, not bill date
- Green energy certificates (RECs) would change the Scope 2 factor — not handled

---

## Corporate Travel

**Real-world format researched:** Navan (formerly TripActions) "Trip Report" CSV export and Concur Expense Reports v3.0 "Standard Detail" report.

**What we learned:**
- Navan exports segment-level data: each flight leg, hotel night, and ground trip is a separate row
- Concur exports expense-level data: a round-trip flight might appear as one row or two depending on how it was booked
- Common columns across both platforms: Trip/Travel Date, Traveler Name/ID, Type (Air/Hotel/Car/Taxi/Train), Origin/From, Destination/To, Cabin Class, Amount, Currency, Cost Center
- Flight distance is not always in the export — we estimate from IATA airport coordinates (haversine formula)
- Cabin class names vary: "economy", "coach", "Y" (Concur IATA code), "business", "J", "first", "F"
- Hotel rows often have no origin/destination — only a city and property name

**Emission factors used:**
- Short-haul flight (<1500 km): 0.255 kgCO2e/km/passenger (DEFRA 2023)
- Long-haul flight (>1500 km): 0.195 kgCO2e/km/passenger (DEFRA 2023, includes radiative forcing)
- Cabin multipliers: economy 1×, premium economy 1.6×, business 2.9×, first 4×
- Hotel: 31 kgCO2e/room-night (DEFRA 2023 UK average — real factor would be region-specific)
- Car rental: 0.171 kgCO2e/km (average petrol car, DEFRA)
- Taxi/rideshare: 0.149 kgCO2e/km (DEFRA)
- Train: 0.041 kgCO2e/km (national rail average, DEFRA)

**Sample data looks like:** 20 trips from 9 employees across Jan–Apr 2024. Routes include DEL-BLR (domestic), BOM-DEL (business class for exec), DEL-JFK and DEL-LHR (long-haul). Hotel stays in Bangalore, Dubai, London, Singapore, Paris. Taxis and train within India. Amounts in INR (typical for Indian corporate travel exports).

**What would break in production:**
- Unknown IATA routes (we only cover ~25 airports) — needs aviation distance API
- Multi-leg trips with layovers: DEL-DXB-LHR should count both legs but may appear as one row in Concur
- Concur vs Navan schema differences: Concur uses "Expense Type" + "Expense Code"; Navan uses "Travel Type"
- Hotel emission factor should be region-specific (a hotel in Delhi has different grid intensity than London)
- Mileage-based car rental without fuel type information
