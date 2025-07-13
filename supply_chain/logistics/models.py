from django.db import models
# from django.contrib.postgres.fields import JSONField
from inventory.models import Warehouse, Product
from django.core.validators import MinValueValidator
from django.db.models import Q, Sum, F
from django.db import transaction
from inventory.models import Inventory, Warehouse  
from geopy.distance import geodesic 
import datetime
from django.utils import timezone

class Vehicle(models.Model):
    VEHICLE_TYPES = (
        ('truck', 'Delivery Truck'),
        ('van', 'Delivery Van'),
        ('bike', 'Motorcycle'),
        ('drone', 'Drone'),
        ('autonomous', 'Autonomous Vehicle'),
    )
    
    registration = models.CharField(max_length=20, unique=True)
    type = models.CharField(max_length=20, choices=VEHICLE_TYPES)
    capacity_volume = models.FloatField(help_text="Cubic meters")
    capacity_weight = models.FloatField(help_text="Kilograms")
    current_location = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=(
        ('available', 'Available'),
        ('in_transit', 'In Transit'),
        ('maintenance', 'Maintenance'),
        ('out_of_service', 'Out of Service'),
    ))
    last_maintenance = models.DateField(null=True, blank=True)
    next_maintenance = models.DateField(null=True, blank=True)
    fuel_efficiency = models.FloatField(null=True, blank=True, help_text="km per liter")
    operational_cost_per_km = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.registration} ({self.get_type_display()})"

class Driver(models.Model):
    name = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50, unique=True)
    contact_number = models.CharField(max_length=20)
    vehicle_types = models.CharField(max_length=100, help_text="Comma-separated list of vehicle types driver is certified for")
    home_base = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=(
        ('available', 'Available'),
        ('on_delivery', 'On Delivery'),
        ('on_leave', 'On Leave'),
    ))
    rating = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0)])

    def __str__(self):
        return self.name

class Customer(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    preferred_delivery_window = models.CharField(max_length=50, blank=True, null=True)
    delivery_instructions = models.TextField(blank=True, null=True)
    loyalty_points = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Order(models.Model):
    ORDER_STATUS = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('packed', 'Packed'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    )
    
    order_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2)
    expected_delivery_date = models.DateField(null=True, blank=True)
    actual_delivery_date = models.DateField(null=True, blank=True)
    delivery_notes = models.TextField(blank=True, null=True)
    is_express = models.BooleanField(default=False)
    is_gift = models.BooleanField(default=False)

    def __str__(self):
        return self.order_number
    
    def fulfill_order(self):
        """Attempt to fulfill the order from available inventory"""
        if self.status != 'pending':
            return False
            
        with transaction.atomic():
            # Check all items are available
            for item in self.items.all():
                inventory = Inventory.objects.filter(
                    product=item.product,
                    warehouse=self.warehouse,
                    quantity_on_hand__gte=item.quantity
                ).first()
                
                if not inventory:
                    return False
            
            # Allocate inventory
            for item in self.items.all():
                inventory = Inventory.objects.select_for_update().get(
                    product=item.product,
                    warehouse=self.warehouse
                )
                inventory.quantity_on_hand -= item.quantity
                inventory.quantity_allocated += item.quantity
                inventory.save()
                item.allocated_inventory = inventory
                item.save()
            
            self.status = 'processing'
            self.save()
            return True
    
    def calculate_shipping_cost(self):
        """Calculate shipping cost based on weight and distance"""
        total_weight = self.items.aggregate(
            total_weight=Sum(F('product__weight') * F('quantity'))
        )['total_weight'] or 0
        
        # Base cost + weight-based cost
        base_cost = 5.00  # USD
        weight_cost = max(0, (total_weight - 5)) * 0.5  # $0.5 per kg over 5kg
        
        # Express delivery premium
        express_cost = 10.00 if self.is_express else 0
        
        return round(base_cost + weight_cost + express_cost, 2)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    allocated_inventory = models.ForeignKey('inventory.Inventory', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.SKU} for {self.order.order_number}"

class DeliveryRoute(models.Model):
    ROUTE_STATUS = (
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    route_id = models.CharField(max_length=50, unique=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True)
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True)
    planned_date = models.DateField()
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ROUTE_STATUS, default='planned')
    total_distance = models.FloatField(null=True, blank=True, help_text="In kilometers")
    estimated_duration = models.FloatField(null=True, blank=True, help_text="In minutes")
    actual_duration = models.FloatField(null=True, blank=True, help_text="In minutes")
    route_path = models.JSONField(null=True, blank=True)  # GeoJSON or polyline
    orders = models.ManyToManyField(Order, through='RouteOrder')
    fuel_consumed = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Route {self.route_id} on {self.planned_date}"
    
    def calculate_efficiency(self):
        """Calculate route efficiency score (0-100)"""
        if not self.actual_duration or not self.estimated_duration:
            return 0
        
        # Time efficiency (50% weight)
        time_efficiency = min(100, (self.estimated_duration / self.actual_duration) * 100) * 0.5
        
        # Distance efficiency (30% weight)
        optimal_distance = self.calculate_optimal_distance()
        distance_efficiency = min(100, (optimal_distance / self.total_distance) * 100) * 0.3 if optimal_distance else 0
        
        # Order completion (20% weight)
        completed_orders = self.routeorder_set.filter(delivery_status='delivered').count()
        total_orders = self.routeorder_set.count()
        completion_efficiency = (completed_orders / total_orders * 100) * 0.2 if total_orders else 0
        
        return round(time_efficiency + distance_efficiency + completion_efficiency, 2)
    
    def calculate_optimal_distance(self):
        """Calculate optimal distance using straight-line distances"""
        locations = [self.warehouse] + [ro.order.customer for ro in self.routeorder_set.order_by('sequence')]
        total_distance = 0
        
        for i in range(len(locations) - 1):
            loc1 = (locations[i].latitude, locations[i].longitude)
            loc2 = (locations[i+1].latitude, locations[i+1].longitude)
            total_distance += geodesic(loc1, loc2).kilometers
        
        # Add return to warehouse
        loc1 = (locations[-1].latitude, locations[-1].longitude)
        loc2 = (self.warehouse.latitude, self.warehouse.longitude)
        total_distance += geodesic(loc1, loc2).kilometers
        
        return total_distance

class RouteOrder(models.Model):
    route = models.ForeignKey(DeliveryRoute, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField()
    estimated_arrival = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True)
    delivery_status = models.CharField(max_length=20, choices=Order.ORDER_STATUS)
    customer_signature = models.TextField(blank=True, null=True)
    proof_of_delivery = models.ImageField(upload_to='pod/', null=True, blank=True)

    class Meta:
        unique_together = ('route', 'order')
        ordering = ['sequence']

    def __str__(self):
        return f"Order {self.order.order_number} in route {self.route.route_id} (stop {self.sequence})"

class TrafficPattern(models.Model):
    location = models.CharField(max_length=100)
    day_of_week = models.PositiveSmallIntegerField(choices=(
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ))
    time_slot = models.CharField(max_length=20)  # e.g., "morning", "afternoon"
    average_speed = models.FloatField(help_text="km/h")
    congestion_level = models.FloatField(help_text="0-1 scale")
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('location', 'day_of_week', 'time_slot')

    def __str__(self):
        return f"Traffic at {self.location} on {self.get_day_of_week_display()} {self.time_slot}"