from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Sum, F, Q
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.http import require_POST
from .models import Product, Warehouse, Inventory, SalesHistory, DemandForecast
from .utils.forecasting import DemandForecaster
from .utils.optimizers import InventoryOptimizer
from django.views.generic import ListView, DetailView
import json
from datetime import datetime, timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
import plotly.express as px
import pandas as pd

class InventoryDashboardView(LoginRequiredMixin, View):
    template_name = 'inventory/dashboard.html'
    
    def get(self, request):
        # Get low stock items (below reorder point)
        low_stock = Inventory.objects.filter(
            quantity_on_hand__lt=F('reorder_point')
        ).select_related('product', 'warehouse')
        
        # Get excess stock items (more than 3 months supply)
        excess_stock = Inventory.objects.filter(
            quantity_on_hand__gt=F('safety_stock')*3
        ).select_related('product', 'warehouse')
        
        # Get recent sales
        recent_sales = SalesHistory.objects.order_by('-date')[:10]
        
        context = {
            'low_stock': low_stock,
            'excess_stock': excess_stock,
            'recent_sales': recent_sales,
        }
        
        return render(request, self.template_name, context)

class ProductForecastView(LoginRequiredMixin, View):
    template_name = 'inventory/forecast.html'
    
    def get(self, request, product_id, warehouse_id):
        product = get_object_or_404(Product, pk=product_id)
        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)
        
        # Get latest forecast
        forecast = DemandForecast.objects.filter(
            product=product,
            warehouse=warehouse
        ).order_by('-forecast_created').first()
        
        # Get sales history for chart
        sales_history = SalesHistory.objects.filter(
            product=product,
            warehouse=warehouse
        ).order_by('date')[:365]  # Last year
        
        # Prepare data for chart
        dates = [sh.date for sh in sales_history]
        quantities = [sh.quantity_sold for sh in sales_history]
        
        if forecast:
            forecast_dates = [datetime.strptime(date, '%Y-%m-%d').date() for date in forecast.forecast_values.keys()]
            forecast_values = list(forecast.forecast_values.values())
        else:
            forecast_dates, forecast_values = [], []
        
        # Create Plotly figure
        fig = px.line(
            x=dates + forecast_dates,
            y=quantities + forecast_values,
            labels={'x': 'Date', 'y': 'Quantity Sold'},
            title=f"Sales History and Forecast for {product.name} at {warehouse.name}"
        )
        
        # Add vertical line to separate history and forecast
        if dates and forecast_dates:
            fig.add_vline(x=dates[-1], line_dash="dash", line_color="red")
        
        chart = fig.to_html(full_html=False)
        
        context = {
            'product': product,
            'warehouse': warehouse,
            'forecast': forecast,
            'chart': chart,
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request, product_id, warehouse_id):
        method = request.POST.get('method', 'random_forest')
        periods = int(request.POST.get('periods', 30))
        
        forecaster = DemandForecaster(product_id, warehouse_id)
        forecast = forecaster.generate_forecast(method=method, periods=periods)
        
        # Redirect back to the forecast page
        return JsonResponse({
            'status': 'success',
            'forecast_id': forecast.id
        })

class InventoryOptimizationView(LoginRequiredMixin, View):
    def post(self, request):
        optimizer = InventoryOptimizer()
        optimizer.optimize_inventory_levels()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Inventory optimization completed'
        })

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'inventory/product_list.html'
    context_object_name = 'products'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related()
        search_query = self.request.GET.get('search')
        
        if search_query:
            queryset = queryset.filter(
                Q(SKU__icontains=search_query) |
                Q(name__icontains=search_query) |
                Q(category__icontains=search_query)
            )
        
        return queryset.annotate(
            total_inventory=Sum('inventory__quantity_on_hand')
        ).order_by('name')

class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = 'inventory/product_detail.html'
    context_object_name = 'product'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        
        # Inventory across warehouses
        context['inventory'] = product.inventory_set.select_related('warehouse').all()
        
        # Sales history data for charts
        sales_history = SalesHistory.objects.filter(
            product=product
        ).order_by('date')[:365]  # Last year
        
        if sales_history:
            df = pd.DataFrame(list(sales_history.values('date', 'quantity_sold')))
            fig = px.line(
                df, x='date', y='quantity_sold',
                title=f"Sales History for {product.name}",
                labels={'quantity_sold': 'Quantity Sold', 'date': 'Date'}
            )
            context['sales_chart'] = fig.to_html(full_html=False)
        
        # Forecast data if available
        latest_forecast = DemandForecast.objects.filter(
            product=product
        ).order_by('-forecast_created').first()
        
        if latest_forecast:
            forecast_data = [
                {'date': date, 'quantity': quantity}
                for date, quantity in latest_forecast.forecast_values.items()
            ]
            forecast_df = pd.DataFrame(forecast_data)
            forecast_df['date'] = pd.to_datetime(forecast_df['date'])
            
            fig = px.line(
                forecast_df, x='date', y='quantity',
                title=f"Demand Forecast for {product.name}",
                labels={'quantity': 'Forecasted Quantity', 'date': 'Date'}
            )
            context['forecast_chart'] = fig.to_html(full_html=False)
        
        return context

@method_decorator(require_POST, name='dispatch')
class GenerateForecastView(LoginRequiredMixin, View):
    def post(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        warehouse_id = request.POST.get('warehouse_id')
        method = request.POST.get('method', 'random_forest')
        periods = int(request.POST.get('periods', 30))
        
        forecaster = DemandForecaster(product_id, warehouse_id)
        forecast = forecaster.generate_forecast(method=method, periods=periods)
        
        return JsonResponse({
            'status': 'success',
            'forecast_id': forecast.id,
            'forecast_start': forecast.forecast_start,
            'forecast_end': forecast.forecast_end
        })

class InventoryLevelsView(LoginRequiredMixin, View):
    def get(self, request):
        # Get inventory levels across all products and warehouses
        inventory = Inventory.objects.select_related(
            'product', 'warehouse'
        ).values(
            'product__name', 'warehouse__name'
        ).annotate(
            on_hand=Sum('quantity_on_hand'),
            allocated=Sum('quantity_allocated'),
            reorder_point=Sum('reorder_point')
        ).order_by('product__name')
        
        # Convert to DataFrame for visualization
        df = pd.DataFrame(list(inventory))
        
        if not df.empty:
            fig = px.bar(
                df, x='product__name', y=['on_hand', 'allocated'],
                color='warehouse__name', barmode='group',
                title='Current Inventory Levels',
                labels={'product__name': 'Product', 'value': 'Quantity'}
            )
            chart_html = fig.to_html(full_html=False)
        else:
            chart_html = "<p>No inventory data available</p>"
        
        return render(request, 'inventory/inventory_levels.html', {
            'chart_html': chart_html
        })

@method_decorator(csrf_exempt, name='dispatch')
class SalesDataAPIView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['product_id', 'warehouse_id', 'date', 'quantity_sold']
            if not all(field in data for field in required_fields):
                return JsonResponse({'error': 'Missing required fields'}, status=400)
            
            # Create or update sales record
            sales, created = SalesHistory.objects.update_or_create(
                product_id=data['product_id'],
                warehouse_id=data['warehouse_id'],
                date=data['date'],
                defaults={
                    'quantity_sold': data['quantity_sold'],
                    'revenue': data.get('revenue', 0),
                    'promotion_flag': data.get('promotion_flag', False),
                    'weather_condition': data.get('weather_condition'),
                    'special_event': data.get('special_event')
                }
            )
            
            return JsonResponse({
                'status': 'created' if created else 'updated',
                'sales_id': sales.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)