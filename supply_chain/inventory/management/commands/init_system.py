from django.core.management.base import BaseCommand
from inventory.models import Warehouse, Product, Inventory
from logistics.models import Vehicle, Driver
import random

class Command(BaseCommand):
    help = 'Initialize the system with sample data'
    
    def handle(self, *args, **options):
        # Create sample warehouses
        warehouses = [
            Warehouse.objects.get_or_create(
                code=f"WH-{i}",
                defaults={
                    'name': f"Warehouse {i}",
                    'type': random.choice(['regional', 'local']),
                    'address': f"{i} Main St, City {i}",
                    'latitude': random.uniform(35.0, 45.0),
                    'longitude': random.uniform(-120.0, -80.0),
                    'capacity': random.randint(1000, 5000)
                }
            )[0] for i in range(1, 4)
        ]
        
        # Create sample products
        products = [
            Product.objects.get_or_create(
                SKU=f"SKU-{i:03d}",
                defaults={
                    'name': f"Product {i}",
                    'category': random.choice(['Electronics', 'Clothing', 'Home', 'Grocery']),
                    'unit_cost': round(random.uniform(5, 100), 2),
                    'selling_price': round(random.uniform(10, 150), 2),
                    'weight': round(random.uniform(0.1, 10), 2),
                    'dimensions': f"{random.randint(5,30)}x{random.randint(5,30)}x{random.randint(5,30)}"
                }
            )[0] for i in range(1, 21)
        ]
        
        # Create inventory for each product at each warehouse
        for product in products:
            for warehouse in warehouses:
                Inventory.objects.get_or_create(
                    product=product,
                    warehouse=warehouse,
                    defaults={
                        'quantity_on_hand': random.randint(10, 100),
                        'lead_time_days': random.randint(1, 14),
                        'safety_stock': random.randint(5, 20)
                    }
                )
        
        # Create sample vehicles
        vehicles = [
            Vehicle.objects.get_or_create(
                registration=f"VH-{i:03d}",
                defaults={
                    'type': random.choice(['truck', 'van', 'bike']),
                    'capacity_volume': random.randint(10, 50),
                    'capacity_weight': random.randint(100, 1000),
                    'current_location': random.choice(warehouses),
                    'status': 'available'
                }
            )[0] for i in range(1, 6)
        ]
        
        # Create sample drivers
        drivers = [
            Driver.objects.get_or_create(
                name=f"Driver {i}",
                license_number=f"DL-{i:05d}",
                defaults={
                    'contact_number': f"555-{i:04d}",
                    'vehicle_types': ','.join(random.sample(['truck', 'van', 'bike'], 2)),
                    'home_base': random.choice(warehouses),
                    'status': 'available'
                }
            )[0] for i in range(1, 6)
        ]
        
        self.stdout.write(self.style.SUCCESS('Successfully initialized system with sample data'))