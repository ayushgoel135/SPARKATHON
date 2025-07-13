from django.db import models
# from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.db import transaction

class Product(models.Model):
    SKU = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    weight = models.DecimalField(max_digits=10, decimal_places=2, help_text="Weight in kg")
    dimensions = models.CharField(max_length=50, help_text="LxWxH in cm")
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # created_at = models.DateTimeField(auto_now_add=True)
    # updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.SKU} - {self.name}"
    
    def get_current_stock(self, warehouse=None):
        """Get current stock level for this product"""
        if warehouse:
            inventory = Inventory.objects.filter(product=self, warehouse=warehouse).first()
            return inventory.quantity_on_hand if inventory else 0
        return Inventory.objects.filter(product=self).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
    
    def calculate_lead_time(self):
        """Calculate average lead time across all warehouses"""
        avg_lead_time = Inventory.objects.filter(product=self).aggregate(
            avg_lead_time=ExpressionWrapper(
                Sum(F('lead_time_days') * F('quantity_on_hand')) / Sum('quantity_on_hand'),
                output_field=DecimalField()
            )
        )['avg_lead_time']
        return avg_lead_time or 7  # default to 7 days
    
    def allocate_inventory(self, warehouse, quantity):
        """Allocate inventory for an order"""
        with transaction.atomic():
            inventory = Inventory.objects.select_for_update().get(
                product=self, warehouse=warehouse
            )
            if inventory.quantity_on_hand >= quantity:
                inventory.quantity_on_hand -= quantity
                inventory.quantity_allocated += quantity
                inventory.save()
                return True
            return False

class Warehouse(models.Model):
    WAREHOUSE_TYPES = (
        ('regional', 'Regional Distribution Center'),
        ('local', 'Local Fulfillment Center'),
        ('store', 'Store Backroom'),
    )
    
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=WAREHOUSE_TYPES)
    address = models.TextField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    capacity = models.PositiveIntegerField(help_text="Total storage capacity in cubic meters")
    # operational_hours = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

class Inventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    quantity_on_hand = models.PositiveIntegerField(default=0)
    quantity_allocated = models.PositiveIntegerField(default=0)
    quantity_on_order = models.PositiveIntegerField(default=0)
    last_count_date = models.DateField(null=True, blank=True)
    next_count_date = models.DateField(null=True, blank=True)
    lead_time_days = models.PositiveIntegerField(default=7)
    safety_stock = models.PositiveIntegerField(default=0)
    reorder_point = models.PositiveIntegerField(default=0)
    economic_order_quantity = models.PositiveIntegerField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'warehouse')
        verbose_name_plural = "Inventory"

    def __str__(self):
        return f"{self.product.SKU} at {self.warehouse.code}"

class SalesHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    date = models.DateField()
    quantity_sold = models.PositiveIntegerField()
    revenue = models.DecimalField(max_digits=12, decimal_places=2)
    promotion_flag = models.BooleanField(default=False)
    weather_condition = models.CharField(max_length=50, blank=True, null=True)
    special_event = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        unique_together = ('product', 'warehouse', 'date')
        verbose_name_plural = "Sales History"

    def __str__(self):
        return f"{self.product.SKU} sales on {self.date}"

class DemandForecast(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    forecast_date = models.DateField()
    forecast_created = models.DateTimeField(auto_now_add=True)
    period = models.CharField(max_length=20, choices=(
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ))
    forecast_start = models.DateField()
    forecast_end = models.DateField()
    forecast_values = models.JSONField()  # {date: quantity, ...}
    confidence_interval = models.JSONField(null=True, blank=True)
    algorithm_used = models.CharField(max_length=100)
    accuracy_metrics = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ('product', 'warehouse', 'forecast_date', 'period')
        verbose_name_plural = "Demand Forecasts"

    def __str__(self):
        return f"{self.product.SKU} forecast for {self.forecast_start} to {self.forecast_end}"