from django.db import transaction
from inventory.models import Inventory, Product, Warehouse

class InventoryOptimizer:
    @staticmethod
    def optimize_inventory_levels():
        """
        Optimize inventory levels across all warehouses
        Sets reorder points and safety stock levels
        """
        with transaction.atomic():
            for product in Product.objects.all():
                for warehouse in Warehouse.objects.all():
                    inventory, created = Inventory.objects.get_or_create(
                        product=product,
                        warehouse=warehouse,
                        defaults={
                            'quantity_on_hand': 0,
                            'reorder_point': 10,  # Default value
                            'safety_stock': 5     # Default value
                        }
                    )
                    
                    if not created:
                        # Calculate optimal levels based on sales history
                        # This is a simplified version - you should implement your own logic
                        inventory.reorder_point = max(10, inventory.quantity_on_hand // 2)
                        inventory.safety_stock = max(5, inventory.reorder_point // 2)
                        inventory.save()