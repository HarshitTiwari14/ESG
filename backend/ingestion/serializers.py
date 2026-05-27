from rest_framework import serializers
from .models import IngestionBatch, RawRow, EmissionRecord, AuditLog


class IngestionBatchSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)

    class Meta:
        model = IngestionBatch
        fields = [
            'id', 'source_type', 'uploaded_by_name', 'uploaded_at',
            'original_filename', 'status', 'row_count', 'error_count', 'notes'
        ]


class RawRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRow
        fields = ['id', 'row_index', 'raw_data', 'parse_error', 'created_at']


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'action', 'actor_name', 'timestamp', 'note', 'before_state', 'after_state']


class EmissionRecordSerializer(serializers.ModelSerializer):
    batch_source = serializers.CharField(source='batch.source_type', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.username', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)
    audit_logs = AuditLogSerializer(many=True, read_only=True)
    raw_data = serializers.JSONField(source='raw_row.raw_data', read_only=True)

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'scope', 'category', 'batch', 'batch_source',
            'activity_value_raw', 'activity_unit_raw',
            'activity_value_norm', 'activity_unit_norm',
            'co2e_kg', 'emission_factor', 'factor_version',
            'activity_date', 'activity_period_end',
            'location', 'vendor', 'description',
            'sap_document_number', 'sap_plant_code', 'sap_cost_center',
            'utility_meter_id', 'utility_tariff',
            'travel_origin', 'travel_destination', 'travel_traveler_id',
            'travel_class', 'travel_distance_km',
            'status', 'flag_reason',
            'reviewed_by_name', 'reviewed_at',
            'approved_by_name', 'approved_at',
            'created_at', 'updated_at', 'is_edited',
            'audit_logs', 'raw_data',
        ]
        read_only_fields = [
            'scope', 'category', 'batch', 'co2e_kg', 'emission_factor',
            'factor_version', 'created_at', 'updated_at',
        ]
