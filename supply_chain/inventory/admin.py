from django.contrib import admin
from .models import Product, Warehouse, Inventory, SalesHistory, DemandForecast

class InventoryInline(admin.TabularInline):
    model = Inventory
    extra = 1

class ProductAdmin(admin.ModelAdmin):
    list_display = ('SKU', 'name', 'category', 'unit_cost', 'selling_price')
    search_fields = ('SKU', 'name', 'category')
    list_filter = ('category', 'is_active')
    inlines = [InventoryInline]

class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'type', 'address', 'is_active')
    search_fields = ('code', 'name', 'address')
    list_filter = ('type', 'is_active')


class InventoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'warehouse', 'quantity_on_hand', 'quantity_allocated', 'reorder_point')
    search_fields = ('product__SKU', 'product__name', 'warehouse__code')
    list_filter = ('warehouse',)

class SalesHistoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'warehouse', 'date', 'quantity_sold', 'revenue')
    search_fields = ('product__SKU', 'product__name', 'warehouse__code')
    list_filter = ('warehouse', 'date', 'promotion_flag')
    date_hierarchy = 'date'

class DemandForecastAdmin(admin.ModelAdmin):
    list_display = ('product', 'warehouse', 'forecast_date', 'period', 'forecast_start', 'forecast_end')
    search_fields = ('product__SKU', 'product__name', 'warehouse__code')
    list_filter = ('warehouse', 'period', 'algorithm_used')
    date_hierarchy = 'forecast_date'

admin.site.register(Product, ProductAdmin)
admin.site.register(Warehouse, WarehouseAdmin)
admin.site.register(Inventory, InventoryAdmin)
admin.site.register(SalesHistory, SalesHistoryAdmin)
admin.site.register(DemandForecast, DemandForecastAdmin)