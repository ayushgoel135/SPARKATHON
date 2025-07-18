# Generated by Django 5.2.4 on 2025-07-13 07:21

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('SKU', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('category', models.CharField(max_length=100)),
                ('unit_cost', models.DecimalField(decimal_places=2, max_digits=10)),
                ('selling_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('weight', models.DecimalField(decimal_places=2, help_text='Weight in kg', max_digits=10)),
                ('dimensions', models.CharField(help_text='LxWxH in cm', max_length=50)),
                ('image', models.ImageField(blank=True, null=True, upload_to='products/')),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Warehouse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('type', models.CharField(choices=[('regional', 'Regional Distribution Center'), ('local', 'Local Fulfillment Center'), ('store', 'Store Backroom')], max_length=20)),
                ('address', models.TextField()),
                ('latitude', models.FloatField()),
                ('longitude', models.FloatField()),
                ('capacity', models.PositiveIntegerField(help_text='Total storage capacity in cubic meters')),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='SalesHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('quantity_sold', models.PositiveIntegerField()),
                ('revenue', models.DecimalField(decimal_places=2, max_digits=12)),
                ('promotion_flag', models.BooleanField(default=False)),
                ('weather_condition', models.CharField(blank=True, max_length=50, null=True)),
                ('special_event', models.CharField(blank=True, max_length=100, null=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.product')),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.warehouse')),
            ],
            options={
                'verbose_name_plural': 'Sales History',
                'unique_together': {('product', 'warehouse', 'date')},
            },
        ),
        migrations.CreateModel(
            name='Inventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity_on_hand', models.PositiveIntegerField(default=0)),
                ('quantity_allocated', models.PositiveIntegerField(default=0)),
                ('quantity_on_order', models.PositiveIntegerField(default=0)),
                ('last_count_date', models.DateField(blank=True, null=True)),
                ('next_count_date', models.DateField(blank=True, null=True)),
                ('lead_time_days', models.PositiveIntegerField(default=7)),
                ('safety_stock', models.PositiveIntegerField(default=0)),
                ('reorder_point', models.PositiveIntegerField(default=0)),
                ('economic_order_quantity', models.PositiveIntegerField(blank=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.product')),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.warehouse')),
            ],
            options={
                'verbose_name_plural': 'Inventory',
                'unique_together': {('product', 'warehouse')},
            },
        ),
        migrations.CreateModel(
            name='DemandForecast',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('forecast_date', models.DateField()),
                ('forecast_created', models.DateTimeField(auto_now_add=True)),
                ('period', models.CharField(choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], max_length=20)),
                ('forecast_start', models.DateField()),
                ('forecast_end', models.DateField()),
                ('forecast_values', models.JSONField()),
                ('confidence_interval', models.JSONField(blank=True, null=True)),
                ('algorithm_used', models.CharField(max_length=100)),
                ('accuracy_metrics', models.JSONField(blank=True, null=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.product')),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.warehouse')),
            ],
            options={
                'verbose_name_plural': 'Demand Forecasts',
                'unique_together': {('product', 'warehouse', 'forecast_date', 'period')},
            },
        ),
    ]
