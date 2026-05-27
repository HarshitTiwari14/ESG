from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count
from django.utils import timezone

from .models import IngestionBatch, EmissionRecord, AuditLog
from .serializers import IngestionBatchSerializer, EmissionRecordSerializer, AuditLogSerializer
from .services import ingest_file, approve_record, flag_record, lock_batch


class IngestionBatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngestionBatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = self.request.user.organisation
        return IngestionBatch.objects.filter(organisation=org).order_by('-uploaded_at')

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        batch = self.get_object()
        locked = lock_batch(batch, request.user)
        return Response({'locked_count': locked})


class FileUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        source_type = request.data.get('source_type')
        if source_type not in [IngestionBatch.SOURCE_SAP, IngestionBatch.SOURCE_UTILITY, IngestionBatch.SOURCE_TRAVEL]:
            return Response({'error': 'Invalid source_type'}, status=status.HTTP_400_BAD_REQUEST)

        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        org = request.user.organisation
        if not org:
            return Response({'error': 'User has no organisation'}, status=status.HTTP_403_FORBIDDEN)

        batch = ingest_file(
            file_obj=file_obj,
            source_type=source_type,
            organisation=org,
            user=request.user,
            filename=file_obj.name,
        )
        return Response(IngestionBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class EmissionRecordViewSet(viewsets.ModelViewSet):
    serializer_class = EmissionRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'vendor', 'location', 'sap_document_number']
    ordering_fields = ['activity_date', 'co2e_kg', 'created_at']
    ordering = ['-activity_date']

    def get_queryset(self):
        org = self.request.user.organisation
        qs = EmissionRecord.objects.filter(organisation=org).select_related(
            'batch', 'raw_row', 'reviewed_by', 'approved_by'
        ).prefetch_related('audit_logs__actor')

        # Manual filtering (no django-filters needed)
        scope = self.request.query_params.get('scope')
        cat = self.request.query_params.get('category')
        stat = self.request.query_params.get('status')
        batch_id = self.request.query_params.get('batch')

        if scope:
            qs = qs.filter(scope=scope)
        if cat:
            qs = qs.filter(category=cat)
        if stat:
            qs = qs.filter(status=stat)
        if batch_id:
            qs = qs.filter(batch_id=batch_id)

        return qs

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        record = self.get_object()
        try:
            approve_record(record, request.user)
            return Response(EmissionRecordSerializer(record).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def flag(self, request, pk=None):
        record = self.get_object()
        reason = request.data.get('reason', '')
        try:
            flag_record(record, request.user, reason)
            return Response(EmissionRecordSerializer(record).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def unflag(self, request, pk=None):
        record = self.get_object()
        if record.status == EmissionRecord.STATUS_LOCKED:
            return Response({'error': 'Locked'}, status=status.HTTP_400_BAD_REQUEST)
        record.status = EmissionRecord.STATUS_PENDING
        record.flag_reason = ''
        record.save()
        AuditLog.objects.create(record=record, action=AuditLog.ACTION_UNFLAGGED, actor=request.user)
        return Response(EmissionRecordSerializer(record).data)


class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = request.user.organisation
        qs = EmissionRecord.objects.filter(organisation=org)

        scope_totals = {}
        for scope in [1, 2, 3]:
            agg = qs.filter(scope=scope).aggregate(
                total_co2e=Sum('co2e_kg'), count=Count('id')
            )
            scope_totals[f'scope_{scope}'] = {
                'total_co2e_kg': float(agg['total_co2e'] or 0),
                'count': agg['count'],
            }

        review_counts = {
            'pending': qs.filter(status='pending').count(),
            'flagged': qs.filter(status='flagged').count(),
            'approved': qs.filter(status='approved').count(),
            'locked': qs.filter(status='locked').count(),
        }

        recent_batches = IngestionBatch.objects.filter(organisation=org).order_by('-uploaded_at')[:5]

        cat_breakdown = list(
            qs.values('category').annotate(
                total_co2e=Sum('co2e_kg'), count=Count('id')
            ).order_by('-total_co2e')
        )
        for row in cat_breakdown:
            row['total_co2e'] = float(row['total_co2e'] or 0)

        return Response({
            'scope_totals': scope_totals,
            'review_counts': review_counts,
            'recent_batches': IngestionBatchSerializer(recent_batches, many=True).data,
            'category_breakdown': cat_breakdown,
            'total_co2e_kg': float(qs.aggregate(t=Sum('co2e_kg'))['t'] or 0),
        })
