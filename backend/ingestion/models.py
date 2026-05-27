"""
Core ingestion models for Breathe ESG.

Design principles:
- Every emission record traces back to a single IngestionBatch (who uploaded it, when, from where)
- EmissionRecord is the canonical normalized row; RawRow stores the verbatim source data
- Scope 1/2/3 is an attribute of EmissionRecord, not a separate table
- Units are ALWAYS stored normalized (kWh for energy, litres for fuel, km for distance,
  room-nights for hotel) alongside raw values so we can re-run emission factors without
  re-parsing
- Review state machine: PENDING → FLAGGED | APPROVED → LOCKED
  Locked rows are immutable; audit log captures every transition
"""
from django.db import models
from django.conf import settings
from accounts.models import Organisation


class IngestionBatch(models.Model):
    """
    One upload / pull event. Ties all rows from a single ingest together.
    We keep the original file so an analyst can always go back to source.
    """
    SOURCE_SAP = 'sap'
    SOURCE_UTILITY = 'utility'
    SOURCE_TRAVEL = 'travel'
    SOURCE_CHOICES = [
        (SOURCE_SAP, 'SAP (Fuel & Procurement)'),
        (SOURCE_UTILITY, 'Utility (Electricity)'),
        (SOURCE_TRAVEL, 'Corporate Travel'),
    ]

    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='batches')
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='batches'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    original_filename = models.CharField(max_length=512, blank=True)
    original_file = models.FileField(upload_to='raw_uploads/%Y/%m/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROCESSING)
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.source_type} batch {self.id} — {self.organisation} @ {self.uploaded_at:%Y-%m-%d}"


class RawRow(models.Model):
    """
    Verbatim capture of each row as parsed from the source file.
    Stored as JSON so we never throw away original data.
    This is the audit-proof record of exactly what came in.
    """
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='raw_rows')
    row_index = models.IntegerField(help_text="0-based row index within the file")
    raw_data = models.JSONField(help_text="Column→value dict from the source file verbatim")
    parse_error = models.TextField(blank=True, help_text="Non-empty if this row failed to parse")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['row_index']
        unique_together = [('batch', 'row_index')]


class EmissionRecord(models.Model):
    """
    The normalized emission record. One row = one emission-generating activity.

    Scope assignment:
      Scope 1 — direct combustion (SAP fuel data)
      Scope 2 — purchased electricity (utility data)
      Scope 3 — value chain incl. business travel

    Unit normalization strategy:
      Fuel → stored in litres (convert L, gal, m³ at ingest)
      Electricity → stored in kWh (convert MWh, GJ at ingest)
      Distance → stored in km (convert miles at ingest)
      Hotel → stored in room-nights (no conversion needed)

    CO2e is computed at ingest using EMISSION_FACTORS from settings,
    but stored explicitly so historical records survive factor updates.
    The factor_version field lets us know which factors were used.
    """
    SCOPE_1 = 1
    SCOPE_2 = 2
    SCOPE_3 = 3
    SCOPE_CHOICES = [(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')]

    CATEGORY_FUEL_DIESEL = 'fuel_diesel'
    CATEGORY_FUEL_PETROL = 'fuel_petrol'
    CATEGORY_FUEL_NATURAL_GAS = 'fuel_natural_gas'
    CATEGORY_ELECTRICITY = 'electricity'
    CATEGORY_FLIGHT = 'flight'
    CATEGORY_HOTEL = 'hotel'
    CATEGORY_CAR = 'car_rental'
    CATEGORY_TAXI = 'taxi'
    CATEGORY_TRAIN = 'train'
    CATEGORY_CHOICES = [
        (CATEGORY_FUEL_DIESEL, 'Diesel'),
        (CATEGORY_FUEL_PETROL, 'Petrol / Gasoline'),
        (CATEGORY_FUEL_NATURAL_GAS, 'Natural Gas'),
        (CATEGORY_ELECTRICITY, 'Electricity'),
        (CATEGORY_FLIGHT, 'Flight'),
        (CATEGORY_HOTEL, 'Hotel'),
        (CATEGORY_CAR, 'Car Rental'),
        (CATEGORY_TAXI, 'Taxi / Rideshare'),
        (CATEGORY_TRAIN, 'Train'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_FLAGGED = 'flagged'
    STATUS_APPROVED = 'approved'
    STATUS_LOCKED = 'locked'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_FLAGGED, 'Flagged'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_LOCKED, 'Locked for Audit'),
    ]

    # Provenance
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='records')
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='records')
    raw_row = models.OneToOneField(RawRow, on_delete=models.SET_NULL, null=True, blank=True)

    # Classification
    scope = models.IntegerField(choices=SCOPE_CHOICES)
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)

    # Activity data — raw as received
    activity_value_raw = models.DecimalField(max_digits=18, decimal_places=4)
    activity_unit_raw = models.CharField(max_length=30, help_text="Original unit string from source")

    # Activity data — normalized
    activity_value_norm = models.DecimalField(
        max_digits=18, decimal_places=4,
        help_text="Value in canonical unit (litres / kWh / km / room-nights)"
    )
    activity_unit_norm = models.CharField(max_length=20)

    # Emission calculation
    co2e_kg = models.DecimalField(max_digits=18, decimal_places=4, help_text="kg CO2e")
    emission_factor = models.DecimalField(
        max_digits=12, decimal_places=6,
        help_text="Factor applied (kgCO2e per unit)"
    )
    factor_version = models.CharField(max_length=20, default='DEFRA-2023')

    # Temporal
    activity_date = models.DateField(help_text="Date of the activity (not upload date)")
    activity_period_end = models.DateField(null=True, blank=True, help_text="For billing-period data")

    # Source metadata (varies by source type)
    location = models.CharField(max_length=255, blank=True, help_text="Plant code, meter ID, airport pair, etc.")
    vendor = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=500, blank=True)

    # SAP-specific
    sap_document_number = models.CharField(max_length=50, blank=True)
    sap_plant_code = models.CharField(max_length=20, blank=True)
    sap_cost_center = models.CharField(max_length=20, blank=True)

    # Utility-specific
    utility_meter_id = models.CharField(max_length=50, blank=True)
    utility_tariff = models.CharField(max_length=100, blank=True)

    # Travel-specific
    travel_origin = models.CharField(max_length=10, blank=True, help_text="IATA code or city")
    travel_destination = models.CharField(max_length=10, blank=True)
    travel_traveler_id = models.CharField(max_length=50, blank=True)
    travel_class = models.CharField(max_length=20, blank=True, help_text="economy/business/first")
    travel_distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Review workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    flag_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='approved_records'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False, help_text="True if any field was manually corrected")

    class Meta:
        ordering = ['-activity_date', '-created_at']
        indexes = [
            models.Index(fields=['organisation', 'status']),
            models.Index(fields=['organisation', 'scope', 'activity_date']),
            models.Index(fields=['batch']),
        ]

    def __str__(self):
        return f"{self.get_category_display()} | {self.activity_date} | {self.co2e_kg} kgCO2e"


class AuditLog(models.Model):
    """
    Immutable log of every state change on an EmissionRecord.
    Written by signals/services, never by user code directly.
    """
    ACTION_CREATED = 'created'
    ACTION_FLAGGED = 'flagged'
    ACTION_APPROVED = 'approved'
    ACTION_LOCKED = 'locked'
    ACTION_EDITED = 'edited'
    ACTION_UNFLAGGED = 'unflagged'
    ACTION_CHOICES = [
        (ACTION_CREATED, 'Created'),
        (ACTION_FLAGGED, 'Flagged'),
        (ACTION_APPROVED, 'Approved'),
        (ACTION_LOCKED, 'Locked'),
        (ACTION_EDITED, 'Edited'),
        (ACTION_UNFLAGGED, 'Unflagged'),
    ]

    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
