from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import IngestionBatchViewSet, FileUploadView, EmissionRecordViewSet, DashboardStatsView

router = DefaultRouter()
router.register('batches', IngestionBatchViewSet, basename='batch')
router.register('records', EmissionRecordViewSet, basename='record')

urlpatterns = [
    path('', include(router.urls)),
    path('upload/', FileUploadView.as_view(), name='upload'),
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
]
