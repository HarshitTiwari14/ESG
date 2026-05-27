from django.contrib import admin
from .models import IngestionBatch, RawRow, EmissionRecord, AuditLog

@admin.register(IngestionBatch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'source_type', 'uploaded_by', 'uploaded_at', 'status', 'row_count', 'error_count']
    list_filter = ['source_type', 'status']

@admin.register(EmissionRecord)
class RecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'scope', 'category', 'activity_date', 'co2e_kg', 'status', 'organisation']
    list_filter = ['scope', 'category', 'status']
    search_fields = ['description', 'location', 'sap_document_number']

@admin.register(RawRow)
class RawRowAdmin(admin.ModelAdmin):
    list_display = ['id', 'batch', 'row_index', 'parse_error']

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'record', 'action', 'actor', 'timestamp']
    list_filter = ['action']