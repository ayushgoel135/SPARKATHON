from celery import shared_task
from django.db.models import F, Sum, ExpressionWrapper
from inventory.models import Inventory, DemandForecast, SalesHistory,  Product, Warehouse
from inventory.utils.forecasting import DemandForecaster
from datetime import date, timedelta
from django.db.models.fields import DecimalField
import logging

logger = logging.getLogger(__name__)

@shared_task
def generate_daily_forecasts():
    """Generate daily demand forecasts for all products"""
    products = Inventory.objects.values_list(
        'product_id', 'warehouse_id'
    ).distinct()
    
    for product_id, warehouse_id in products:
        try:
            forecaster = DemandForecaster(product_id, warehouse_id)
            forecast = forecaster.generate_forecast(
                method='random_forest',
                periods=30
            )
            logger.info(
                f"Generated forecast for product {product_id} at warehouse {warehouse_id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to generate forecast for product {product_id} at warehouse {warehouse_id}: {str(e)}"
            )
    
    return f"Generated forecasts for {products.count()} product-warehouse combinations"

@shared_task
def update_reorder_points():
    """Update reorder points based on recent demand"""
    # Get products that need reorder point updates
    inventories = Inventory.objects.filter(
        last_count_date__lte=date.today() - timedelta(days=7)
    ).select_related('product')
    
    updated_count = 0
    
    for inventory in inventories:
        try:
            # Get recent sales data (last 3 months)
            sales_data = SalesHistory.objects.filter(
                product=inventory.product,
                warehouse=inventory.warehouse,
                date__gte=date.today() - timedelta(days=90)
            ).aggregate(
                avg_daily_sales=ExpressionWrapper(
                    Sum('quantity_sold') / 90,
                    output_field=DecimalField()
                )
            )
            
            avg_daily_sales = sales_data['avg_daily_sales'] or 0
            
            # Calculate new reorder point (lead time demand + safety stock)
            lead_time_demand = avg_daily_sales * inventory.lead_time_days
            safety_stock = avg_daily_sales * 7  # 1 week safety stock
            new_reorder_point = round(lead_time_demand + safety_stock)
            
            if new_reorder_point != inventory.reorder_point:
                inventory.reorder_point = new_reorder_point
                inventory.safety_stock = round(safety_stock)
                inventory.last_count_date = date.today()
                inventory.save()
                updated_count += 1
                
        except Exception as e:
            logger.error(
                f"Failed to update reorder point for inventory {inventory.id}: {str(e)}"
            )
    
    return f"Updated reorder points for {updated_count} inventory items"