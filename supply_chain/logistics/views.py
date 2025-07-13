from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.db.models import Q, Count, Sum, F
from django.views.generic import ListView, DetailView
from .models import Vehicle, Driver, Customer, Order, DeliveryRoute, RouteOrder, TrafficPattern
from .utils.route_optimization import RouteOptimizer
from .utils.delivery_scheduling import DeliveryScheduler
from logistics.models import Vehicle, Driver, DeliveryRoute, Order
from inventory.models import Warehouse
import json
from datetime import datetime, timedelta
from django.db import transaction
import plotly.express as px
import pandas as pd
import folium
import polyline

class DeliveryDashboardView(LoginRequiredMixin, View):
    template_name = 'logistics/dashboard.html'
    
    def get(self, request):
        # Get today's routes
        today = datetime.now().date()
        routes = DeliveryRoute.objects.filter(planned_date=today).prefetch_related(
            Prefetch('routeorder_set', queryset=RouteOrder.objects.select_related('order'))
        )
        
        # Get available vehicles
        vehicles = Vehicle.objects.filter(status='available')
        
        # Get available drivers
        drivers = Driver.objects.filter(status='available')
        
        # Get pending orders
        pending_orders = Order.objects.filter(
            status__in=['processing', 'packed'],
            expected_delivery_date=today
        ).count()
        
        context = {
            'routes': routes,
            'vehicles': vehicles,
            'drivers': drivers,
            'pending_orders': pending_orders,
            'today': today,
        }
        
        return render(request, self.template_name, context)

class DeliveryRouteListView(LoginRequiredMixin, ListView):
    model = DeliveryRoute
    template_name = 'logistics/route_list.html'
    context_object_name = 'routes'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'warehouse', 'vehicle', 'driver'
        )
        
        date_filter = self.request.GET.get('date')
        status_filter = self.request.GET.get('status')
        
        if date_filter:
            try:
                date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                queryset = queryset.filter(planned_date=date)
            except ValueError:
                pass
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.annotate(
            order_count=Count('routeorder'),
            delivered_count=Count('routeorder', filter=Q(routeorder__delivery_status='delivered'))
        ).order_by('-planned_date')

class DeliveryRouteDetailView(LoginRequiredMixin, DetailView):
    model = DeliveryRoute
    template_name = 'logistics/route_detail.html'
    context_object_name = 'route'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        route = self.object
        
        # Get route orders with customer and order details
        context['route_orders'] = route.routeorder_set.select_related(
            'order', 'order__customer'
        ).order_by('sequence')
        
        # Calculate route statistics
        context['efficiency_score'] = route.calculate_efficiency()
        context['completion_percentage'] = round(
            route.routeorder_set.filter(delivery_status='delivered').count() /
            route.routeorder_set.count() * 100, 2
        ) if route.routeorder_set.count() > 0 else 0
        
        # Create timeline visualization
        stops = []
        for ro in context['route_orders']:
            stops.append({
                'sequence': ro.sequence,
                'customer': ro.order.customer.name,
                'order': ro.order.order_number,
                'estimated_arrival': ro.estimated_arrival.strftime('%H:%M'),
                'actual_arrival': ro.actual_arrival.strftime('%H:%M') if ro.actual_arrival else None,
                'status': ro.get_delivery_status_display()
            })
        
        context['stops'] = stops
        
        return context

class VehicleListView(LoginRequiredMixin, ListView):
    model = Vehicle
    template_name = 'logistics/vehicle_list.html'
    context_object_name = 'vehicles'
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('current_location')
        
        status_filter = self.request.GET.get('status')
        type_filter = self.request.GET.get('type')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if type_filter:
            queryset = queryset.filter(type=type_filter)
        
        return queryset.annotate(
            route_count=Count('deliveryroute'),
            completed_routes=Count('deliveryroute', filter=Q(deliveryroute__status='completed'))
        ).order_by('registration')

@method_decorator(require_POST, name='dispatch')
class UpdateRouteStatusView(LoginRequiredMixin, View):
    def post(self, request, route_id):
        route = get_object_or_404(DeliveryRoute, pk=route_id)
        status = request.POST.get('status')
        
        if status not in dict(DeliveryRoute.ROUTE_STATUS):
            return JsonResponse({'error': 'Invalid status'}, status=400)
        
        route.status = status
        
        if status == 'in_progress':
            route.start_time = datetime.now()
        elif status == 'completed':
            route.end_time = datetime.now()
        
        route.save()
        
        return JsonResponse({
            'status': 'success',
            'new_status': route.get_status_display()
        })

class DeliveryAnalyticsView(LoginRequiredMixin, View):
    def get(self, request):
        # Delivery performance metrics
        routes = DeliveryRoute.objects.filter(
            status='completed',
            planned_date__gte=datetime.now() - timedelta(days=30)
        ).annotate(
            duration_diff=F('actual_duration') - F('estimated_duration')
        )
        
        # On-time delivery percentage
        on_time = routes.filter(duration_diff__lte=15).count()
        total = routes.count()
        on_time_percentage = round(on_time / total * 100, 2) if total > 0 else 0
        
        # Create efficiency chart
        df = pd.DataFrame(list(routes.values(
            'planned_date', 'total_distance', 'estimated_duration', 'actual_duration'
        )))
        
        if not df.empty:
            df['efficiency'] = df['estimated_duration'] / df['actual_duration']
            fig = px.line(
                df, x='planned_date', y='efficiency',
                title='Delivery Efficiency Over Time',
                labels={'planned_date': 'Date', 'efficiency': 'Efficiency Score'}
            )
            chart_html = fig.to_html(full_html=False)
        else:
            chart_html = "<p>No delivery data available</p>"
        
        return render(request, 'logistics/delivery_analytics.html', {
            'on_time_percentage': on_time_percentage,
            'total_deliveries': total,
            'chart_html': chart_html
        })

class RouteOptimizationView(LoginRequiredMixin, View):
    def post(self, request):
        warehouse_id = request.POST.get('warehouse_id')
        date_str = request.POST.get('date')
        vehicle_type = request.POST.get('vehicle_type', 'van')
        
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return JsonResponse({'error': 'Invalid date format'}, status=400)
        
        optimizer = RouteOptimizer(warehouse_id, date, vehicle_type)
        optimization_result = optimizer.optimize_route()
        
        if not optimization_result:
            return JsonResponse({'error': 'No orders to optimize or no available vehicle'}, status=400)
            
        route = optimizer.save_optimized_route(optimization_result)
        
        return JsonResponse({
            'status': 'success',
            'route_id': route.route_id,
            'distance': optimization_result['route_distance'],
            'estimated_time': optimization_result['route_time'],
            'map_url': f"/media/routes/route_{date}_{warehouse_id}.html"
        })

class DeliveryMapView(LoginRequiredMixin, View):
    template_name = 'logistics/delivery_map.html'
    
    def get(self, request, route_id):
        route = get_object_or_404(DeliveryRoute, route_id=route_id)
        
        # Decode the route path
        if route.route_path:
            coordinates = polyline.decode(route.route_path)
            center = coordinates[0] if coordinates else [0, 0]
            
            # Create map
            m = folium.Map(location=center, zoom_start=12)
            
            # Add warehouse marker
            folium.Marker(
                [route.warehouse.latitude, route.warehouse.longitude],
                popup=f"Warehouse: {route.warehouse.name}",
                icon=folium.Icon(color='green', icon='warehouse')
            ).add_to(m)
            
            # Add route
            folium.PolyLine(coordinates, color="red", weight=2.5, opacity=1).add_to(m)
            
            # Add customer markers
            for route_order in route.routeorder_set.select_related('order__customer'):
                customer = route_order.order.customer
                folium.Marker(
                    [customer.latitude, customer.longitude],
                    popup=f"Customer: {customer.name}\nOrder: {route_order.order.order_number}",
                    icon=folium.Icon(color='blue', icon='user')
                ).add_to(m)
            
            # Save to HTML
            map_html = m._repr_html_()
        else:
            map_html = "<p>No route path available</p>"
        
        context = {
            'route': route,
            'map_html': map_html,
        }
        
        return render(request, self.template_name, context)

@method_decorator(csrf_exempt, name='dispatch')
class DeliveryStatusAPIView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            order_id = data.get('order_id')
            status = data.get('status')
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            if not order_id or not status:
                return JsonResponse({'error': 'Missing order_id or status'}, status=400)
            
            # Update order status
            order = Order.objects.get(pk=order_id)
            order.status = status
            
            if status == 'delivered':
                order.actual_delivery_date = datetime.now().date()
            
            order.save()
            
            # Update route order status if exists
            route_order = RouteOrder.objects.filter(order=order).first()
            if route_order:
                route_order.delivery_status = status
                route_order.actual_arrival = timestamp
                route_order.save()
            
            return JsonResponse({'status': 'success'})
            
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Order not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class TrafficPatternAnalysisView(LoginRequiredMixin, View):
    def get(self, request):
        # Analyze traffic patterns for route optimization
        scheduler = DeliveryScheduler()
        optimal_times = scheduler.calculate_optimal_delivery_times()
        
        return JsonResponse({
            'status': 'success',
            'optimal_times': optimal_times
        })