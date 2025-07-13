from django.contrib import admin
from .models import Vehicle, Driver, Customer, Order, OrderItem, DeliveryRoute, RouteOrder, TrafficPattern

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1

class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer', 'warehouse', 'order_date', 'status', 'total_amount')
    search_fields = ('order_number', 'customer__name', 'customer__email')
    list_filter = ('status', 'warehouse', 'is_express', 'is_gift')
    date_hierarchy = 'order_date'
    inlines = [OrderItemInline]

class RouteOrderInline(admin.TabularInline):
    model = RouteOrder
    extra = 1

class DeliveryRouteAdmin(admin.ModelAdmin):
    list_display = ('route_id', 'warehouse', 'planned_date', 'status', 'total_distance', 'estimated_duration')
    search_fields = ('route_id', 'warehouse__code', 'warehouse__name')
    list_filter = ('status', 'warehouse', 'planned_date')
    date_hierarchy = 'planned_date'
    inlines = [RouteOrderInline]

class VehicleAdmin(admin.ModelAdmin):
    list_display = ('registration', 'type', 'capacity_volume', 'capacity_weight', 'status')
    search_fields = ('registration',)
    list_filter = ('type', 'status')

class DriverAdmin(admin.ModelAdmin):
    list_display = ('name', 'license_number', 'home_base', 'status', 'rating')
    search_fields = ('name', 'license_number')
    list_filter = ('status', 'home_base')

class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'loyalty_points')
    search_fields = ('name', 'email', 'phone')

class TrafficPatternAdmin(admin.ModelAdmin):
    list_display = ('location', 'day_of_week', 'time_slot', 'average_speed', 'congestion_level')
    search_fields = ('location',)
    list_filter = ('day_of_week', 'time_slot')

admin.site.register(Vehicle, VehicleAdmin)
admin.site.register(Driver, DriverAdmin)
admin.site.register(Customer, CustomerAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(DeliveryRoute, DeliveryRouteAdmin)
admin.site.register(TrafficPattern, TrafficPatternAdmin)