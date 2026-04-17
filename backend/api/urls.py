from django.urls import path

from .views import FloorplanJobDemoView, FloorplanJobDetailView, FloorplanJobListCreateView, FloorplanJobStartView, HealthView

urlpatterns = [
    path('health/', HealthView.as_view(), name='health'),
    path('jobs/', FloorplanJobListCreateView.as_view(), name='job-list'),
    path('jobs/demo/', FloorplanJobDemoView.as_view(), name='job-demo'),
    path('jobs/<int:pk>/', FloorplanJobDetailView.as_view(), name='job-detail'),
    path('jobs/<int:pk>/start/', FloorplanJobStartView.as_view(), name='job-start'),
]
