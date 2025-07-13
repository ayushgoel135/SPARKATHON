from datetime import datetime, timedelta
from django.db.models import Q
from logistics.models import DeliveryRoute, TrafficPattern

class DeliveryScheduler:
    @staticmethod
    def calculate_optimal_delivery_times():
        """
        Calculate optimal delivery times based on traffic patterns
        Returns a dictionary of optimal time windows
        """
        optimal_times = {}
        
        # Get traffic patterns for today's day of week
        today = datetime.now().weekday()
        patterns = TrafficPattern.objects.filter(day_of_week=today)
        
        for pattern in patterns:
            # Simple logic - avoid times with congestion > 0.7
            if pattern.congestion_level < 0.7:
                optimal_times[pattern.location] = {
                    'best_time': pattern.time_slot,
                    'average_speed': pattern.average_speed
                }
        
        return optimal_times

    @staticmethod
    def schedule_deliveries():
        """
        Schedule deliveries for the current day
        Assigns routes based on optimal times
        """
        optimal_times = DeliveryScheduler.calculate_optimal_delivery_times()
        
        # Get unscheduled routes for today
        today = datetime.now().date()
        routes = DeliveryRoute.objects.filter(
            planned_date=today,
            status='planned'
        )
        
        for route in routes:
            if route.warehouse.address in optimal_times:
                best_time = optimal_times[route.warehouse.address]['best_time']
                # Update route with optimal time (simplified)
                route.notes = f"Scheduled for {best_time} based on traffic patterns"
                route.save()