import numpy as np
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from geopy.distance import geodesic
import polyline
import folium
from datetime import datetime, timedelta
import os
from django.conf import settings
import json
from inventory.models import Warehouse
from logistics.models import Order, Vehicle, Driver, DeliveryRoute, RouteOrder

class RouteOptimizer:
    def __init__(self, warehouse_id, date, vehicle_type='van', time_windows=True):
        self.warehouse = Warehouse.objects.get(pk=warehouse_id)
        self.date = date
        self.vehicle_type = vehicle_type
        self.time_windows = time_windows
        self.orders = self._get_orders()
        self.customers = self._get_customers()
        self.vehicle = self._get_vehicle()
        self.driver = self._get_driver()
        
    def _get_orders(self):
        return Order.objects.filter(
            warehouse_id=self.warehouse.id,
            status__in=['processing', 'packed'],
            expected_delivery_date=self.date
        ).prefetch_related('items', 'customer')
    
    def _get_customers(self):
        return {order.customer for order in self.orders}
    
    def _get_vehicle(self):
        return Vehicle.objects.filter(
            current_location=self.warehouse,
            type=self.vehicle_type,
            status='available'
        ).first()
    
    def _get_driver(self):
        return Driver.objects.filter(
            home_base=self.warehouse,
            status='available',
            vehicle_types__contains=self.vehicle_type
        ).first()
    
    def create_distance_matrix(self):
        """Create distance matrix with realistic road distances (simplified)"""
        locations = [self.warehouse] + list(self.customers)
        num_locations = len(locations)
        distance_matrix = np.zeros((num_locations, num_locations))
        
        # Straight-line distances multiplied by a factor to simulate road distances
        for i in range(num_locations):
            for j in range(num_locations):
                if i == j:
                    distance_matrix[i][j] = 0
                else:
                    loc1 = (locations[i].latitude, locations[i].longitude)
                    loc2 = (locations[j].latitude, locations[j].longitude)
                    straight_distance = geodesic(loc1, loc2).kilometers
                    # Multiply by road distance factor (typically 1.2-1.5)
                    distance_matrix[i][j] = straight_distance * 1.3
                    
        return distance_matrix, locations
    
    def create_time_matrix(self, distance_matrix):
        """Convert distance matrix to time matrix considering traffic patterns"""
        time_matrix = np.zeros_like(distance_matrix)
        day_of_week = self.date.weekday()
        hour_of_day = 9  # Assuming morning departure
        
        # Traffic speed factors by time of day
        if 7 <= hour_of_day < 10:  # Morning rush hour
            speed_factor = 0.7
        elif 16 <= hour_of_day < 19:  # Evening rush hour
            speed_factor = 0.6
        else:
            speed_factor = 1.0
        
        # Weekend traffic is different
        if day_of_week >= 5:  # Saturday or Sunday
            speed_factor = 0.9 if 11 <= hour_of_day < 15 else 1.1
        
        # Base speed in km/h
        base_speed = 40 * speed_factor
        
        # Convert distance to time in minutes
        time_matrix = (distance_matrix / base_speed) * 60
        
        return time_matrix
    
    def create_time_windows(self, locations):
        """Create time windows for each location"""
        time_windows = []
        
        # Warehouse time window (open hours)
        time_windows.append((0, 8*60))  # 8 hours (e.g., 8am-4pm)
        
        # Customer time windows
        for customer in locations[1:]:
            if customer.preferred_delivery_window:
                # Parse preferred window (format like "9:00-12:00")
                start, end = customer.preferred_delivery_window.split('-')
                start_h, start_m = map(int, start.split(':'))
                end_h, end_m = map(int, end.split(':'))
                time_windows.append((
                    start_h * 60 + start_m,
                    end_h * 60 + end_m
                ))
            else:
                # Default window (9am-5pm)
                time_windows.append((9*60, 17*60))
        
        return time_windows
    
    def optimize_route(self):
        """Optimize delivery route using OR-Tools"""
        if not self.orders or not self.customers:
            return None
            
        distance_matrix, locations = self.create_distance_matrix()
        time_matrix = self.create_time_matrix(distance_matrix)
        time_windows = self.create_time_windows(locations) if self.time_windows else None
        
        # Create routing index manager
        num_locations = len(locations)
        num_vehicles = 1  # Single vehicle for simplicity
        depot = 0  # Warehouse is the starting point
        
        manager = pywrapcp.RoutingIndexManager(
            num_locations, num_vehicles, depot)
        
        # Create routing model
        routing = pywrapcp.RoutingModel(manager)
        
        # Define cost of each arc (time in this case)
        def time_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(time_matrix[from_node][to_node])
            
        transit_callback_index = routing.RegisterTransitCallback(time_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        
        # Add time dimension
        time = 'Time'
        routing.AddDimension(
            transit_callback_index,
            30,  # allow waiting time
            8*60,  # maximum time per vehicle (8 hours)
            False,  # Don't force start cumul to zero
            time)
        time_dimension = routing.GetDimensionOrDie(time)
        
        # Add time window constraints
        if time_windows:
            for location_idx, time_window in enumerate(time_windows):
                if location_idx == depot:
                    continue
                    
                index = manager.NodeToIndex(location_idx)
                time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])
        
        # Add capacity constraints (weight and volume)
        def weight_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            if from_node == depot:
                return 0
            customer = locations[from_node]
            order = next(o for o in self.orders if o.customer == customer)
            return sum(item.product.weight * item.quantity for item in order.items.all())
            
        weight_callback_index = routing.RegisterUnaryTransitCallback(weight_callback)
        routing.AddDimensionWithVehicleCapacity(
            weight_callback_index,
            0,  # null capacity slack
            [self.vehicle.capacity_weight],  # vehicle maximum capacities
            True,  # start cumul to zero
            'Weight')
            
        # Similar for volume capacity
        def volume_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            if from_node == depot:
                return 0
            customer = locations[from_node]
            order = next(o for o in self.orders if o.customer == customer)
            return sum(item.product.dimensions_volume() * item.quantity for item in order.items.all())
            
        volume_callback_index = routing.RegisterUnaryTransitCallback(volume_callback)
        routing.AddDimensionWithVehicleCapacity(
            volume_callback_index,
            0,  # null capacity slack
            [self.vehicle.capacity_volume],  # vehicle maximum capacities
            True,  # start cumul to zero
            'Volume')
        
        # Setting first solution heuristic
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
        search_parameters.time_limit.seconds = 30
        
        # Solve the problem
        solution = routing.SolveWithParameters(search_parameters)
        
        if not solution:
            return None
            
        # Extract the route
        index = routing.Start(0)
        route_locations = []
        route_distance = 0
        route_time = 0
        
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_locations.append(locations[node_index])
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += distance_matrix[manager.IndexToNode(previous_index)][manager.IndexToNode(index)]
            route_time += time_matrix[manager.IndexToNode(previous_index)][manager.IndexToNode(index)]
        
        # Add the depot at the end
        node_index = manager.IndexToNode(index)
        route_locations.append(locations[node_index])
        
        # Create a map visualization
        route_map = self._create_route_map(route_locations)
        
        # Create polyline for storage
        coordinates = [(loc.latitude, loc.longitude) for loc in route_locations]
        route_path = polyline.encode(coordinates)
        
        return {
            'route_locations': route_locations,
            'route_distance': round(route_distance, 2),
            'route_time': round(route_time, 2),
            'route_map': route_map,
            'route_path': route_path,
            'vehicle': self.vehicle,
            'driver': self.driver,
            'orders': self.orders
        }
    
    def _create_route_map(self, route_locations):
        """Create interactive Folium map of the route"""
        if not route_locations:
            return None
            
        # Create map centered on warehouse
        m = folium.Map(
            location=[self.warehouse.latitude, self.warehouse.longitude],
            zoom_start=12,
            tiles='cartodbpositron'
        )
        
        # Add warehouse marker
        folium.Marker(
            [self.warehouse.latitude, self.warehouse.longitude],
            popup=f"<b>Warehouse:</b> {self.warehouse.name}<br>"
                  f"<b>Address:</b> {self.warehouse.address}",
            icon=folium.Icon(color='green', icon='warehouse', prefix='fa')
        ).add_to(m)
        
        # Add route polyline
        locations = [(loc.latitude, loc.longitude) for loc in route_locations]
        folium.PolyLine(
            locations,
            color='blue',
            weight=3,
            opacity=0.8,
            tooltip="Delivery Route"
        ).add_to(m)
        
        # Add customer markers with order info
        for i, location in enumerate(route_locations[1:-1], start=1):
            customer = location
            order = next(o for o in self.orders if o.customer == customer)
            
            popup_html = f"""
            <b>Customer:</b> {customer.name}<br>
            <b>Order #:</b> {order.order_number}<br>
            <b>Items:</b> {order.items.count()}<br>
            <b>Total:</b> ${order.total_amount}<br>
            <b>Status:</b> {order.get_status_display()}
            """
            
            folium.Marker(
                [customer.latitude, customer.longitude],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color='red', icon='user', prefix='fa'),
                tooltip=f"Stop {i}: {customer.name}"
            ).add_to(m)
        
        # Save map to HTML file
        map_dir = os.path.join(settings.MEDIA_ROOT, 'routes')
        os.makedirs(map_dir, exist_ok=True)
        map_filename = f"route_{self.date}_{self.warehouse.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.html"
        map_path = os.path.join(map_dir, map_filename)
        m.save(map_path)
        
        return f"/media/routes/{map_filename}"
    
    def save_optimized_route(self, optimization_result):
        """Save optimized route to database"""
        if not optimization_result:
            return None
            
        route = DeliveryRoute(
            route_id=f"ROUTE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            warehouse=self.warehouse,
            vehicle=self.vehicle,
            driver=self.driver,
            planned_date=self.date,
            status='planned',
            total_distance=optimization_result['route_distance'],
            estimated_duration=optimization_result['route_time'],
            route_path=optimization_result['route_path'],
            map_url=optimization_result['route_map']
        )
        route.save()
        
        # Add orders to route
        customer_order_map = {order.customer_id: order for order in self.orders}
        
        for i, location in enumerate(optimization_result['route_locations']):
            if hasattr(location, 'id') and location.id in customer_order_map:
                order = customer_order_map[location.id]
                RouteOrder.objects.create(
                    route=route,
                    order=order,
                    sequence=i,
                    delivery_status='processing',
                    estimated_arrival=self._calculate_estimated_arrival(
                        optimization_result['route_time'],
                        i,
                        len(optimization_result['route_locations'])
                    )
                )
                # Update order status
                order.status = 'shipped'
                order.save()
        
        return route
    
    def _calculate_estimated_arrival(self, total_route_time, stop_number, total_stops):
        """Calculate estimated arrival time for each stop"""
        # Simplified proportional distribution
        proportion = (stop_number + 1) / total_stops
        estimated_minutes = proportion * total_route_time
        
        # Create datetime for today at 9am (default start time)
        arrival_time = datetime.combine(self.date, datetime.min.time()) + timedelta(hours=9)
        arrival_time += timedelta(minutes=estimated_minutes)
        
        return arrival_time