# Generated by Django 5.2.4 on 2025-07-13 07:21

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('phone', models.CharField(max_length=20)),
                ('address', models.TextField()),
                ('latitude', models.FloatField()),
                ('longitude', models.FloatField()),
                ('preferred_delivery_window', models.CharField(blank=True, max_length=50, null=True)),
                ('delivery_instructions', models.TextField(blank=True, null=True)),
                ('loyalty_points', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Driver',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('license_number', models.CharField(max_length=50, unique=True)),
                ('contact_number', models.CharField(max_length=20)),
                ('vehicle_types', models.CharField(help_text='Comma-separated list of vehicle types driver is certified for', max_length=100)),
                ('status', models.CharField(choices=[('available', 'Available'), ('on_delivery', 'On Delivery'), ('on_leave', 'On Leave')], max_length=20)),
                ('rating', models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('home_base', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='inventory.warehouse')),
            ],
        ),
        migrations.CreateModel(
            name='DeliveryRoute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('route_id', models.CharField(max_length=50, unique=True)),
                ('planned_date', models.DateField()),
                ('start_time', models.DateTimeField(blank=True, null=True)),
                ('end_time', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('planned', 'Planned'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='planned', max_length=20)),
                ('total_distance', models.FloatField(blank=True, help_text='In kilometers', null=True)),
                ('estimated_duration', models.FloatField(blank=True, help_text='In minutes', null=True)),
                ('actual_duration', models.FloatField(blank=True, help_text='In minutes', null=True)),
                ('route_path', models.JSONField(blank=True, null=True)),
                ('fuel_consumed', models.FloatField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.warehouse')),
                ('driver', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='logistics.driver')),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_number', models.CharField(max_length=50, unique=True)),
                ('order_date', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('packed', 'Packed'), ('shipped', 'Shipped'), ('out_for_delivery', 'Out for Delivery'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled'), ('returned', 'Returned')], default='pending', max_length=20)),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('shipping_cost', models.DecimalField(decimal_places=2, max_digits=10)),
                ('expected_delivery_date', models.DateField(blank=True, null=True)),
                ('actual_delivery_date', models.DateField(blank=True, null=True)),
                ('delivery_notes', models.TextField(blank=True, null=True)),
                ('is_express', models.BooleanField(default=False)),
                ('is_gift', models.BooleanField(default=False)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='logistics.customer')),
                ('warehouse', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='inventory.warehouse')),
            ],
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('discount', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('allocated_inventory', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='inventory.inventory')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='logistics.order')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.product')),
            ],
        ),
        migrations.CreateModel(
            name='RouteOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence', models.PositiveIntegerField()),
                ('estimated_arrival', models.DateTimeField(blank=True, null=True)),
                ('actual_arrival', models.DateTimeField(blank=True, null=True)),
                ('delivery_status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('packed', 'Packed'), ('shipped', 'Shipped'), ('out_for_delivery', 'Out for Delivery'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled'), ('returned', 'Returned')], max_length=20)),
                ('customer_signature', models.TextField(blank=True, null=True)),
                ('proof_of_delivery', models.ImageField(blank=True, null=True, upload_to='pod/')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='logistics.order')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='logistics.deliveryroute')),
            ],
            options={
                'ordering': ['sequence'],
                'unique_together': {('route', 'order')},
            },
        ),
        migrations.AddField(
            model_name='deliveryroute',
            name='orders',
            field=models.ManyToManyField(through='logistics.RouteOrder', to='logistics.order'),
        ),
        migrations.CreateModel(
            name='TrafficPattern',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('location', models.CharField(max_length=100)),
                ('day_of_week', models.PositiveSmallIntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])),
                ('time_slot', models.CharField(max_length=20)),
                ('average_speed', models.FloatField(help_text='km/h')),
                ('congestion_level', models.FloatField(help_text='0-1 scale')),
                ('timestamp', models.DateTimeField(auto_now=True)),
            ],
            options={
                'unique_together': {('location', 'day_of_week', 'time_slot')},
            },
        ),
        migrations.CreateModel(
            name='Vehicle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('registration', models.CharField(max_length=20, unique=True)),
                ('type', models.CharField(choices=[('truck', 'Delivery Truck'), ('van', 'Delivery Van'), ('bike', 'Motorcycle'), ('drone', 'Drone'), ('autonomous', 'Autonomous Vehicle')], max_length=20)),
                ('capacity_volume', models.FloatField(help_text='Cubic meters')),
                ('capacity_weight', models.FloatField(help_text='Kilograms')),
                ('status', models.CharField(choices=[('available', 'Available'), ('in_transit', 'In Transit'), ('maintenance', 'Maintenance'), ('out_of_service', 'Out of Service')], max_length=20)),
                ('last_maintenance', models.DateField(blank=True, null=True)),
                ('next_maintenance', models.DateField(blank=True, null=True)),
                ('fuel_efficiency', models.FloatField(blank=True, help_text='km per liter', null=True)),
                ('operational_cost_per_km', models.FloatField(blank=True, null=True)),
                ('current_location', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='inventory.warehouse')),
            ],
        ),
        migrations.AddField(
            model_name='deliveryroute',
            name='vehicle',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='logistics.vehicle'),
        ),
    ]
