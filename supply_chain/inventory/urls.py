from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.InventoryDashboardView.as_view(), name='inventory_dashboard'),
    path('product/<int:product_id>/warehouse/<int:warehouse_id>/forecast/', 
         views.ProductForecastView.as_view(), name='product_forecast'),
    path('api/sales/', views.SalesDataAPIView.as_view(), name='sales_data_api'),
    path('optimize/', views.InventoryOptimizationView.as_view(), name='inventory_optimization'),
]