"""
Ingestion service layer.
Keeps views thin: views validate HTTP, services do domain logic.
"""
from decimal import Decimal
from django.utils import timezone
from .models import IngestionBatch, RawRow, EmissionRecord, AuditLog
from .parsers import (
    parse_sap_file, sap_row_to_emission,
    parse_utility_file, utility_row_to_emission,
    parse_travel_file, travel_row_to_emission,
)

# Suspicion thresholds for auto-flagging
THRESHOLDS = {
    'fuel_diesel': Decimal('50000'),    # litres per row — flag if > 50k
    'fuel_petrol': Decimal('20000'),
    'fuel_natural_gas': Decimal('100000'),  # kWh
    'electricity': Decimal('500000'),       # kWh
    'flight': Decimal('20000'),             # km (>20k km is suspicious for one trip)
    'hotel': Decimal('60'),                 # room-nights (2 months)
}


def _should_flag(category, norm_value):
    """Return (flagged: bool, reason: str)"""
    threshold = THRESHOLDS.get(category)
    if threshold and norm_value > threshold:
        return True, f"Value {norm_value} exceeds threshold {threshold} for {category}"
    if norm_value <= 0:
        return True, "Zero or negative activity value"
    return False, ""


def _write_audit(record, action, actor=None, note=''):
    AuditLog.objects.create(
        record=record,
        action=action,
        actor=actor,
        note=note,
    )


PARSER_MAP = {
    IngestionBatch.SOURCE_SAP: (parse_sap_file, sap_row_to_emission),
    IngestionBatch.SOURCE_UTILITY: (parse_utility_file, utility_row_to_emission),
    IngestionBatch.SOURCE_TRAVEL: (parse_travel_file, travel_row_to_emission),
}


def ingest_file(file_obj, source_type, organisation, user, filename=''):
    """
    Main entry point. Parses the file, creates a batch + raw rows + emission records.
    Returns the IngestionBatch.
    """
    batch = IngestionBatch.objects.create(
        organisation=organisation,
        source_type=source_type,
        uploaded_by=user,
        original_filename=filename,
        status=IngestionBatch.STATUS_PROCESSING,
    )

    parse_fn, convert_fn = PARSER_MAP[source_type]

    try:
        rows = parse_fn(file_obj)
    except Exception as e:
        batch.status = IngestionBatch.STATUS_FAILED
        batch.notes = f"File parsing failed: {e}"
        batch.save()
        return batch

    error_count = 0
    record_count = 0

    for row in rows:
        idx = row.get('_row_index', 0)
        raw_row = RawRow.objects.create(
            batch=batch,
            row_index=idx,
            raw_data={k: v for k, v in row.items() if not k.startswith('_')},
        )

        try:
            emission_data = convert_fn(row)
        except (ValueError, Exception) as e:
            raw_row.parse_error = str(e)
            raw_row.save()
            error_count += 1
            continue

        flagged, flag_reason = _should_flag(
            emission_data['category'],
            emission_data['activity_value_norm']
        )

        record = EmissionRecord.objects.create(
            organisation=organisation,
            batch=batch,
            raw_row=raw_row,
            status=EmissionRecord.STATUS_FLAGGED if flagged else EmissionRecord.STATUS_PENDING,
            flag_reason=flag_reason,
            **emission_data,
        )
        _write_audit(record, AuditLog.ACTION_CREATED, actor=user,
                     note=f"Ingested from batch {batch.id}")
        record_count += 1

    batch.row_count = record_count
    batch.error_count = error_count
    batch.status = IngestionBatch.STATUS_DONE
    batch.save()
    return batch


def approve_record(record, user):
    if record.status == EmissionRecord.STATUS_LOCKED:
        raise ValueError("Record is locked and cannot be modified")
    old_status = record.status
    record.status = EmissionRecord.STATUS_APPROVED
    record.approved_by = user
    record.approved_at = timezone.now()
    record.save()
    _write_audit(record, AuditLog.ACTION_APPROVED, actor=user,
                 note=f"Status changed from {old_status} to approved")


def flag_record(record, user, reason=''):
    if record.status == EmissionRecord.STATUS_LOCKED:
        raise ValueError("Record is locked and cannot be modified")
    record.status = EmissionRecord.STATUS_FLAGGED
    record.flag_reason = reason
    record.save()
    _write_audit(record, AuditLog.ACTION_FLAGGED, actor=user, note=reason)


def lock_batch(batch, user):
    """Lock all approved records in a batch for audit."""
    records = EmissionRecord.objects.filter(
        batch=batch, status=EmissionRecord.STATUS_APPROVED
    )
    for r in records:
        r.status = EmissionRecord.STATUS_LOCKED
        r.save()
        _write_audit(r, AuditLog.ACTION_LOCKED, actor=user, note="Locked for audit")
    return records.count()
