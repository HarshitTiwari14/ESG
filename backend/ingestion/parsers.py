"""
Parsers for the three data sources.

SAP: We handle the flat-file (BAPI/RFC table export) format — tab/semicolon-delimited,
     often with German headers (Menge=quantity, Meins=unit, Werks=plant, Bukrs=company code).
     Justification: IDoc is XML-wrapped EDI used for system-to-system; most clients
     who hand us data are exporting from SE16/MB51 as a spreadsheet. OData requires
     live API access which enterprises rarely grant. Flat file is the realistic hand-off.

Utility: Portal CSV export. Justification: PDF bills require OCR and are error-prone;
     utility APIs (e.g. Green Button) exist but rarely provisioned for B2B clients.
     The facilities team usually exports from the utility web portal as CSV — this is
     the most common real-world hand-off we'd see.

Travel: Concur/Navan standard expense export CSV. Both platforms allow bulk exports.
     Navan calls it "Trip Report Export"; Concur calls it "Standard Detail" report.
     We handle the common subset: trip date, origin, destination, class, amount.
     When distance is absent we compute it from IATA airport coordinates.
"""
import csv
import io
import re
from decimal import Decimal, InvalidOperation
from datetime import date
import pandas as pd
from dateutil import parser as dateparser

from django.conf import settings


# ---------------------------------------------------------------------------
# Unit normalization helpers
# ---------------------------------------------------------------------------

FUEL_UNIT_MAP = {
    'l': 1.0, 'liter': 1.0, 'litre': 1.0, 'litres': 1.0, 'liters': 1.0,
    'l.': 1.0,
    'gal': 3.78541, 'gallon': 3.78541, 'gallons': 3.78541,
    'm3': 1000.0, 'm³': 1000.0, 'cbm': 1000.0,
    'kg': 1.0,  # for natural gas by weight — simplified
}

ENERGY_UNIT_MAP = {
    'kwh': 1.0, 'kw/h': 1.0,
    'mwh': 1000.0,
    'gwh': 1_000_000.0,
    'gj': 277.778,
    'mj': 0.277778,
    'kj': 0.000278,
    'btu': 0.000293,
    'therm': 29.3,
}

DISTANCE_UNIT_MAP = {
    'km': 1.0,
    'mi': 1.60934, 'mile': 1.60934, 'miles': 1.60934,
    'nm': 1.852,  # nautical miles
}

# Rough IATA→lat/lon for distance estimation (subset, extend as needed)
AIRPORT_COORDS = {
    'DEL': (28.5665, 77.1031), 'BOM': (19.0896, 72.8656), 'BLR': (13.1986, 77.7066),
    'MAA': (12.9941, 80.1709), 'HYD': (17.2403, 78.4294), 'CCU': (22.6520, 88.4463),
    'LHR': (51.4775, -0.4614), 'CDG': (49.0097, 2.5479), 'AMS': (52.3086, 4.7639),
    'FRA': (50.0379, 8.5622), 'JFK': (40.6413, -73.7781), 'LAX': (33.9425, -118.4081),
    'ORD': (41.9742, -87.9073), 'DXB': (25.2532, 55.3657), 'SIN': (1.3644, 103.9915),
    'HKG': (22.3080, 113.9185), 'NRT': (35.7653, 140.3856), 'SYD': (-33.9461, 151.1772),
    'GRU': (-23.4356, -46.4731), 'JNB': (-26.1392, 28.2460),
}


def haversine_km(lat1, lon1, lat2, lon2):
    import math
    R = 6371
    dl = math.radians(lat2 - lat1)
    dg = math.radians(lon2 - lon1)
    a = math.sin(dl/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dg/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_distance_km(origin, destination):
    """Return great-circle distance between two IATA codes, or None."""
    o = AIRPORT_COORDS.get(origin.upper())
    d = AIRPORT_COORDS.get(destination.upper())
    if o and d:
        return round(haversine_km(*o, *d), 1)
    return None


def normalize_unit(value_str, unit_str, unit_map):
    """Convert value+unit to canonical unit. Returns (norm_value, factor) or raises ValueError."""
    unit_clean = unit_str.strip().lower()
    factor = unit_map.get(unit_clean)
    if factor is None:
        raise ValueError(f"Unknown unit: '{unit_str}'")
    try:
        val = Decimal(str(value_str).replace(',', '.').strip())
    except InvalidOperation:
        raise ValueError(f"Cannot parse numeric value: '{value_str}'")
    return val * Decimal(str(factor)), factor


def parse_date(val):
    """Parse a date string that might be DD.MM.YYYY (SAP German), YYYY-MM-DD, MM/DD/YYYY, etc."""
    if isinstance(val, date):
        return val
    s = str(val).strip()
    # SAP German format DD.MM.YYYY
    m = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', s)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    try:
        return dateparser.parse(s, dayfirst=False).date()
    except Exception:
        raise ValueError(f"Cannot parse date: '{val}'")


# ---------------------------------------------------------------------------
# SAP Flat-File Parser
# ---------------------------------------------------------------------------

# SAP German→English header aliases from SE16/MB51 exports
SAP_HEADER_ALIASES = {
    # German          English canonical
    'Menge': 'quantity',
    'Meins': 'unit',
    'Werks': 'plant_code',
    'Bukrs': 'company_code',
    'Kostl': 'cost_center',
    'Belnr': 'document_number',
    'Bldat': 'document_date',
    'Budat': 'posting_date',
    'Matnr': 'material_number',
    'Maktx': 'material_description',
    'Lifnr': 'vendor_number',
    'Name1': 'vendor_name',
    'Netwr': 'net_value',
    'Waers': 'currency',
    # English equivalents (already normalized exports)
    'Quantity': 'quantity',
    'Unit': 'unit',
    'Plant': 'plant_code',
    'Company Code': 'company_code',
    'Cost Center': 'cost_center',
    'Document Number': 'document_number',
    'Document Date': 'document_date',
    'Posting Date': 'posting_date',
    'Material': 'material_number',
    'Material Description': 'material_description',
    'Vendor': 'vendor_number',
    'Vendor Name': 'vendor_name',
    'Net Value': 'net_value',
    'Currency': 'currency',
    'Fuel Type': 'fuel_type',
}

# Map material description keywords → emission category
MATERIAL_CATEGORY_MAP = [
    (['diesel', 'hsd', 'gas oil'], 'fuel_diesel'),
    (['petrol', 'gasoline', 'mogas', 'ms '], 'fuel_petrol'),
    (['natural gas', 'cng', 'lng', 'lpg'], 'fuel_natural_gas'),
]


def _infer_fuel_category(description):
    desc_lower = str(description).lower()
    for keywords, cat in MATERIAL_CATEGORY_MAP:
        if any(k in desc_lower for k in keywords):
            return cat
    return 'fuel_diesel'  # fallback


def parse_sap_file(file_obj):
    """
    Parse SAP flat-file export (semicolon or tab delimited, UTF-8 or Latin-1).
    Returns list of dicts with normalized keys.
    """
    content = file_obj.read()
    # Try UTF-8, fall back to Latin-1 (SAP German Windows exports)
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        text = content.decode('latin-1')

    # Detect delimiter
    sample = text[:2000]
    delimiter = ';' if sample.count(';') > sample.count('\t') else '\t'

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = []
    for i, raw_row in enumerate(reader):
        # Normalize headers
        norm = {}
        for k, v in raw_row.items():
            if k is None:
                continue
            canonical = SAP_HEADER_ALIASES.get(k.strip(), k.strip().lower().replace(' ', '_'))
            norm[canonical] = (v or '').strip()
        norm['_row_index'] = i
        rows.append(norm)
    return rows


def sap_row_to_emission(norm_row):
    """
    Convert a normalized SAP row dict to an emission record dict.
    Returns dict suitable for EmissionRecord creation, or raises ValueError.
    """
    # Date: prefer posting_date, fall back to document_date
    date_str = norm_row.get('posting_date') or norm_row.get('document_date', '')
    activity_date = parse_date(date_str)

    qty_str = norm_row.get('quantity', '')
    unit_str = norm_row.get('unit', 'L')
    desc = norm_row.get('material_description', '') or norm_row.get('fuel_type', '')
    category = _infer_fuel_category(desc)

    # Natural gas billed in kWh or m³
    if category == 'fuel_natural_gas' and unit_str.lower() in ('kwh', 'kw/h', 'mwh'):
        norm_val, _ = normalize_unit(qty_str, unit_str, ENERGY_UNIT_MAP)
        norm_unit = 'kWh'
        ef = settings.EMISSION_FACTORS['natural_gas_kwh']
    else:
        norm_val, _ = normalize_unit(qty_str, unit_str, FUEL_UNIT_MAP)
        norm_unit = 'litres'
        ef_key = 'diesel' if category == 'fuel_diesel' else 'petrol'
        ef = settings.EMISSION_FACTORS[ef_key]

    co2e = norm_val * Decimal(str(ef))

    return {
        'scope': 1,
        'category': category,
        'activity_value_raw': Decimal(str(qty_str).replace(',', '.') or '0'),
        'activity_unit_raw': unit_str,
        'activity_value_norm': norm_val,
        'activity_unit_norm': norm_unit,
        'co2e_kg': co2e,
        'emission_factor': Decimal(str(ef)),
        'activity_date': activity_date,
        'description': desc,
        'sap_document_number': norm_row.get('document_number', ''),
        'sap_plant_code': norm_row.get('plant_code', ''),
        'sap_cost_center': norm_row.get('cost_center', ''),
        'vendor': norm_row.get('vendor_name', ''),
        'location': norm_row.get('plant_code', ''),
    }


# ---------------------------------------------------------------------------
# Utility (Electricity) Parser
# ---------------------------------------------------------------------------

UTILITY_HEADER_ALIASES = {
    'Meter ID': 'meter_id', 'MeterID': 'meter_id', 'meter_id': 'meter_id',
    'Account Number': 'meter_id',
    'Billing Period Start': 'period_start', 'Period Start': 'period_start',
    'Billing Period End': 'period_end', 'Period End': 'period_end',
    'Consumption (kWh)': 'consumption_kwh', 'kWh': 'consumption_kwh',
    'Usage': 'consumption_kwh', 'Consumption': 'consumption_kwh',
    'Unit': 'unit', 'Units': 'unit',
    'Tariff': 'tariff', 'Rate Plan': 'tariff',
    'Site': 'site', 'Location': 'site', 'Facility': 'site',
    'Amount': 'amount', 'Total Amount': 'amount',
    'Currency': 'currency',
    'Grid Region': 'grid_region', 'Region': 'grid_region',
}


def parse_utility_file(file_obj):
    content = file_obj.read()
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        text = content.decode('latin-1')

    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for i, raw_row in enumerate(reader):
        norm = {}
        for k, v in raw_row.items():
            if k is None:
                continue
            canonical = UTILITY_HEADER_ALIASES.get(k.strip(), k.strip().lower().replace(' ', '_'))
            norm[canonical] = (v or '').strip()
        norm['_row_index'] = i
        rows.append(norm)
    return rows


def utility_row_to_emission(norm_row):
    # Determine kWh value — may be labeled in different units
    consumption_str = norm_row.get('consumption_kwh', '') or norm_row.get('usage', '')
    unit_str = norm_row.get('unit', 'kWh')

    norm_val, _ = normalize_unit(consumption_str, unit_str, ENERGY_UNIT_MAP)

    period_start_str = norm_row.get('period_start', '')
    period_end_str = norm_row.get('period_end', '')
    activity_date = parse_date(period_start_str) if period_start_str else None
    period_end = parse_date(period_end_str) if period_end_str else None

    # Grid emission factor — use India default, override if region given
    region = norm_row.get('grid_region', '').lower()
    if 'uk' in region or 'gb' in region:
        ef = settings.EMISSION_FACTORS['electricity_uk']
    elif 'us' in region or 'usa' in region:
        ef = settings.EMISSION_FACTORS['electricity_us']
    else:
        ef = settings.EMISSION_FACTORS['electricity_india']

    co2e = norm_val * Decimal(str(ef))

    return {
        'scope': 2,
        'category': 'electricity',
        'activity_value_raw': Decimal(str(consumption_str).replace(',', '') or '0'),
        'activity_unit_raw': unit_str,
        'activity_value_norm': norm_val,
        'activity_unit_norm': 'kWh',
        'co2e_kg': co2e,
        'emission_factor': Decimal(str(ef)),
        'activity_date': activity_date or date.today(),
        'activity_period_end': period_end,
        'utility_meter_id': norm_row.get('meter_id', ''),
        'utility_tariff': norm_row.get('tariff', ''),
        'location': norm_row.get('site', ''),
    }


# ---------------------------------------------------------------------------
# Travel Parser (Concur/Navan-style export)
# ---------------------------------------------------------------------------

TRAVEL_HEADER_ALIASES = {
    'Trip Date': 'trip_date', 'Travel Date': 'trip_date', 'Date': 'trip_date',
    'Departure Date': 'trip_date',
    'Origin': 'origin', 'From': 'origin', 'Departure': 'origin',
    'Destination': 'destination', 'To': 'destination', 'Arrival': 'destination',
    'Travel Type': 'travel_type', 'Type': 'travel_type', 'Category': 'travel_type',
    'Mode': 'travel_type',
    'Class': 'cabin_class', 'Cabin': 'cabin_class', 'Fare Class': 'cabin_class',
    'Distance (km)': 'distance_km', 'Distance': 'distance_km',
    'Traveler': 'traveler_id', 'Employee ID': 'traveler_id', 'Employee': 'traveler_id',
    'Cost Center': 'cost_center',
    'Amount': 'amount', 'Cost': 'amount',
    'Hotel Name': 'hotel_name', 'Property': 'hotel_name',
    'Nights': 'nights', 'Room Nights': 'nights',
    'Check-in': 'checkin', 'Check In': 'checkin',
    'Check-out': 'checkout', 'Check Out': 'checkout',
}

TRAVEL_TYPE_MAP = {
    'flight': 'flight', 'air': 'flight', 'airplane': 'flight', 'plane': 'flight',
    'hotel': 'hotel', 'lodging': 'hotel', 'accommodation': 'hotel',
    'car': 'car_rental', 'car rental': 'car_rental', 'rental car': 'car_rental',
    'taxi': 'taxi', 'cab': 'taxi', 'rideshare': 'taxi', 'uber': 'taxi', 'lyft': 'taxi',
    'train': 'train', 'rail': 'train', 'metro': 'train',
    'ground': 'taxi',
}

FLIGHT_CLASS_FACTORS = {
    'economy': 1.0, 'coach': 1.0,
    'premium economy': 1.6,
    'business': 2.9,
    'first': 4.0,
}


def parse_travel_file(file_obj):
    content = file_obj.read()
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        text = content.decode('latin-1')

    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for i, raw_row in enumerate(reader):
        norm = {}
        for k, v in raw_row.items():
            if k is None:
                continue
            canonical = TRAVEL_HEADER_ALIASES.get(k.strip(), k.strip().lower().replace(' ', '_'))
            norm[canonical] = (v or '').strip()
        norm['_row_index'] = i
        rows.append(norm)
    return rows


def travel_row_to_emission(norm_row):
    travel_type_raw = norm_row.get('travel_type', 'flight').strip().lower()
    travel_type = TRAVEL_TYPE_MAP.get(travel_type_raw, 'flight')
    activity_date = parse_date(norm_row.get('trip_date') or norm_row.get('checkin') or date.today())

    if travel_type == 'flight':
        origin = norm_row.get('origin', '').upper().strip()[:3]
        dest = norm_row.get('destination', '').upper().strip()[:3]
        dist_str = norm_row.get('distance_km', '')
        if dist_str:
            try:
                dist_km = Decimal(str(dist_str).replace(',', ''))
            except InvalidOperation:
                dist_km = None
        else:
            dist_km = None

        if dist_km is None:
            dist_km_float = estimate_distance_km(origin, dest)
            dist_km = Decimal(str(dist_km_float)) if dist_km_float else Decimal('0')

        cabin = norm_row.get('cabin_class', 'economy').strip().lower()
        class_multiplier = FLIGHT_CLASS_FACTORS.get(cabin, 1.0)

        base_ef = settings.EMISSION_FACTORS[
            'flight_short_haul' if dist_km < 1500 else 'flight_long_haul'
        ]
        ef = base_ef * class_multiplier
        co2e = dist_km * Decimal(str(ef))

        return {
            'scope': 3,
            'category': 'flight',
            'activity_value_raw': dist_km,
            'activity_unit_raw': 'km',
            'activity_value_norm': dist_km,
            'activity_unit_norm': 'km',
            'co2e_kg': co2e,
            'emission_factor': Decimal(str(ef)),
            'activity_date': activity_date,
            'travel_origin': origin,
            'travel_destination': dest,
            'travel_traveler_id': norm_row.get('traveler_id', ''),
            'travel_class': cabin,
            'travel_distance_km': dist_km,
            'description': f"Flight {origin}→{dest}",
            'location': f"{origin}-{dest}",
        }

    elif travel_type == 'hotel':
        nights_str = norm_row.get('nights', '1')
        try:
            nights = Decimal(str(nights_str).replace(',', '') or '1')
        except InvalidOperation:
            nights = Decimal('1')
        ef = settings.EMISSION_FACTORS['hotel_night']
        co2e = nights * Decimal(str(ef))
        hotel_name = norm_row.get('hotel_name', '')
        checkin = norm_row.get('checkin', '')
        checkout = norm_row.get('checkout', '')
        period_end = parse_date(checkout) if checkout else None

        return {
            'scope': 3,
            'category': 'hotel',
            'activity_value_raw': nights,
            'activity_unit_raw': 'nights',
            'activity_value_norm': nights,
            'activity_unit_norm': 'room-nights',
            'co2e_kg': co2e,
            'emission_factor': Decimal(str(ef)),
            'activity_date': activity_date,
            'activity_period_end': period_end,
            'travel_traveler_id': norm_row.get('traveler_id', ''),
            'description': hotel_name or 'Hotel stay',
            'location': norm_row.get('destination', ''),
        }

    else:
        # Ground transport: car, taxi, train
        dist_str = norm_row.get('distance_km', '0')
        try:
            dist_km = Decimal(str(dist_str).replace(',', '') or '0')
        except InvalidOperation:
            dist_km = Decimal('0')

        ef_key = {'car_rental': 'car_rental_km', 'taxi': 'taxi_km', 'train': 'train_km'}.get(travel_type, 'taxi_km')
        ef = settings.EMISSION_FACTORS[ef_key]
        co2e = dist_km * Decimal(str(ef))

        return {
            'scope': 3,
            'category': travel_type,
            'activity_value_raw': dist_km,
            'activity_unit_raw': 'km',
            'activity_value_norm': dist_km,
            'activity_unit_norm': 'km',
            'co2e_kg': co2e,
            'emission_factor': Decimal(str(ef)),
            'activity_date': activity_date,
            'travel_traveler_id': norm_row.get('traveler_id', ''),
            'description': f"{travel_type.replace('_', ' ').title()} trip",
            'location': norm_row.get('destination', ''),
        }
