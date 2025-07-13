from celery import shared_task
from django.db.models import Q
from logistics.models import DeliveryRoute, Order
from logistics.utils.route_optimization import RouteOptimizer
from datetime import date, timedelta, datetime
from inventory.models import Warehouse 
import logging

logger = logging.getLogger(__name__)

@shared_task
def optimize_daily_routes():
    """Optimize delivery routes for today's orders"""
    today = date.today()
    warehouses = Warehouse.objects.filter(
        deliveryroute__planned_date=today
    ).distinct()
    
    optimized_routes = 0
    
    for warehouse in warehouses:
        try:
            optimizer = RouteOptimizer(
                warehouse.id,
                today,
                vehicle_type='van',
                time_windows=True
            )
            result = optimizer.optimize_route()
            
            if result:
                optimizer.save_optimized_route(result)
                optimized_routes += 1
                logger.info(
                    f"Optimized route for warehouse {warehouse.code}"
                )
        except Exception as e:
            logger.error(
                f"Failed to optimize route for warehouse {warehouse.code}: {str(e)}"
            )
    
    return f"Optimized routes for {optimized_routes} warehouses"

@shared_task
def update_delivery_statuses():
    """Update delivery statuses based on estimated times"""
    today = date.today()
    in_progress_routes = DeliveryRoute.objects.filter(
        planned_date=today,
        status='in_progress'
    ).prefetch_related('routeorder_set')
    
    updated_count = 0
    
    for route in in_progress_routes:
        try:
            for route_order in route.routeorder_set.filter(
                delivery_status='out_for_delivery'
            ):
                if route_order.estimated_arrival and route_order.estimated_arrival <= datetime.now():
                    route_order.delivery_status = 'delivered'
                    route_order.actual_arrival = datetime.now()
                    route_order.save()
                    
                    # Update order status
                    route_order.order.status = 'delivered'
                    route_order.order.actual_delivery_date = today
                    route_order.order.save()
                    
                    updated_count += 1
        except Exception as e:
            logger.error(
                f"Failed to update statuses for route {route.route_id}: {str(e)}"
            )
    
    # Check if all orders are delivered
    for route in in_progress_routes:
        if not route.routeorder_set.filter(~Q(delivery_status='delivered')).exists():
            route.status = 'completed'
            route.end_time = datetime.now()
            route.save()
    
    return f"Updated statuses for {updated_count} deliveries"