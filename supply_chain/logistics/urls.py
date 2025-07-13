from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.DeliveryDashboardView.as_view(), name='delivery_dashboard'),
    path('optimize/', views.RouteOptimizationView.as_view(), name='route_optimization'),
    path('route/<str:route_id>/map/', views.DeliveryMapView.as_view(), name='delivery_map'),
    path('api/status/', views.DeliveryStatusAPIView.as_view(), name='delivery_status_api'),
    path('traffic-analysis/', views.TrafficPatternAnalysisView.as_view(), name='traffic_analysis'),
]