from datetime import timezone,datetime
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Booking, Travellor, Stop, RouteStop, Customer, Car, CabBooking, Route, Vendor
from django.contrib.auth.models import User
from django.db.models import Sum


class BookingSerializer(serializers.ModelSerializer):
    start_stop = serializers.PrimaryKeyRelatedField(queryset=RouteStop.objects.all())
    end_stop = serializers.PrimaryKeyRelatedField(queryset=RouteStop.objects.all())

    class Meta:
        model = Booking
        fields = ['id', 'trip', 'customer', 'start_stop', 'end_stop', 'seats', 'status', 'booking_time']
        read_only_fields = ('id', 'customer', 'status', 'booking_time')

    def validate(self, data):
        """
        Check that the start stop is before the end stop.
        """
        if data['start_stop'].order >= data['end_stop'].order:
            raise serializers.ValidationError("End stop must be after start stop.")
        if data['trip'].departure_time < timezone.now():
            raise serializers.ValidationError("Cannot book a trip that has already departed.")
        if data['start_stop'].route != data['trip'].route or data['end_stop'].route != data['trip'].route:
            raise serializers.ValidationError("Stops must be on the trip's route.")

        return data


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['name', 'contact_number']


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)  # {refresh, access}; sets self.user
        customer = Customer.objects.filter(user=self.user).first()
        data['customer'] = CustomerSerializer(customer).data if customer else None
        return data


class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stop
        fields = ['id', 'name', 'description']


class RouteStopSerializer(serializers.ModelSerializer):
    stop = StopSerializer(read_only=True)
    estimated_arrival_time = serializers.DateTimeField(read_only=True)

    class Meta:
        model = RouteStop
        fields = ['id', 'stop', 'order', 'minutes_from_previous_stop', 'distance_from_previous_stop', 'estimated_arrival_time']


class TravellorSerializer(serializers.ModelSerializer):
    route_stops = serializers.SerializerMethodField()
    driver_name = serializers.CharField(source='driver.username', read_only=True)
    route_name = serializers.CharField(source='route.name', read_only=True)
    price = serializers.SerializerMethodField()

    class Meta:
        model = Travellor
        fields = ['id', 'driver_name', 'route_name', 'departure_time', 'vehicle_capacity', 'status', 'route_stops', 'cost_per_km', 'price']

    def get_route_stops(self, obj):
        schedule = obj.get_schedule()
        route_stop_ids = [item['route_stop_id'] for item in schedule]
        route_stops = RouteStop.objects.filter(id__in=route_stop_ids).order_by('order')
        
        for rs in route_stops:
            for item in schedule:
                if rs.id == item['route_stop_id']:
                    rs.estimated_arrival_time = item['estimated_arrival_time']
                    break
        
        return RouteStopSerializer(route_stops, many=True).data

    def get_price(self, obj):
        # start_stop_id = self.context.get('start_stop_id')
        # end_stop_id = self.context.get('end_stop_id')

        # if not start_stop_id or not end_stop_id:
        #     return None

        # try:
        #     start_stop = RouteStop.objects.get(route=obj.route, stop_id=start_stop_id)
        #     end_stop = RouteStop.objects.get(route=obj.route, stop_id=end_stop_id)
        # except RouteStop.DoesNotExist:
        #     return None

        # if start_stop.order >= end_stop.order:
        #     return None

        # total_distance = RouteStop.objects.filter(
        #     route=obj.route,
        #     order__gt=start_stop.order,
        #     order__lte=end_stop.order
        # ).aggregate(total=Sum('distance_from_previous_stop'))['total'] or 0

        return int(obj.cost_per_km)



class BookingDetailSerializer(serializers.ModelSerializer):
    trip = TravellorSerializer(read_only=True)
    start_stop = StopSerializer(source='start_stop.stop', read_only=True)
    end_stop = StopSerializer(source='end_stop.stop', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    estimated_departure = serializers.SerializerMethodField()
    estimated_arrival = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id', 
            'trip', 
            'customer_name', 
            'start_stop', 
            'end_stop', 
            'seats', 
            'status', 
            'booking_time',
            'estimated_departure',
            'estimated_arrival',
            'price'
        ]

    def get_estimated_departure(self, obj):
        schedule = obj.trip.get_schedule()
        start_stop_schedule = next((item for item in schedule if item['route_stop_id'] == obj.start_stop.id), None)
        return start_stop_schedule['estimated_arrival_time'] if start_stop_schedule else None

    def get_estimated_arrival(self, obj):
        schedule = obj.trip.get_schedule()
        end_stop_schedule = next((item for item in schedule if item['route_stop_id'] == obj.end_stop.id), None)
        return end_stop_schedule['estimated_arrival_time'] if end_stop_schedule else None

    def get_price(self, obj):
        start_stop = obj.start_stop
        end_stop = obj.end_stop
        trip = obj.trip

        if not all([start_stop, end_stop, trip]):
            return None


        return trip.cost_per_km *obj.seats


class CarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Car
        fields = ['id', 'name', 'license_plate']


class CabBookingSerializer(serializers.ModelSerializer):
    # Expose car id for selection and allow driver fields to be returned
    # For customer booking, they provide people_count (number of passengers).
    # `car` remains optional but is not required when creating a booking.
    car = serializers.PrimaryKeyRelatedField(queryset=Car.objects.all(), required=False, allow_null=True)
    people_count = serializers.IntegerField(required=True, min_value=1)

    class Meta:
        model = CabBooking
        fields = ['id', 'customer', 'pickup_location', 'dropoff_location', 'pickup_time', 'people_count', 'status', 'driver_no', 'driver_name', 'car', 'booking_time']
        read_only_fields = ('id', 'customer', 'status', 'booking_time','driver_no', 'driver_name', 'car',)

    def validate(self, data):
        # pickup_time should be provided
        pickup_time = data.get('pickup_time')
        if pickup_time is None:
            raise serializers.ValidationError({'pickup_time': 'Pickup time is required.'})
        # if pickup_time < int(datetime.now()):
        #     raise serializers.ValidationError({'pickup_time': 'Pickup time must be in the future.'})
        # people_count must be a positive integer
        people_count = data.get('people_count')
        if people_count is None:
            raise serializers.ValidationError({'people_count': 'people_count is required.'})
        if not isinstance(people_count, int) or people_count < 1:
            raise serializers.ValidationError({'people_count': 'people_count must be an integer >= 1.'})

        # Additional validations can be added here (e.g., location checks)
        return data

    def create(self, validated_data, **kwargs):
        # allow view to pass customer via save(customer=...)
        customer = kwargs.pop('customer', None)
        if customer is None:
            raise serializers.ValidationError('Customer must be provided')
        validated_data['customer'] = customer
        return super().create(validated_data)


class CabBookingDetailSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    car = CarSerializer(read_only=True)
    people_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CabBooking
        fields = ['id', 'customer', 'pickup_location', 'dropoff_location', 'pickup_time', 'people_count', 'booking_time', 'status', 'driver_no', 'driver_name', 'car']


# ===== VENDOR API SERIALIZERS =====

class RouteStopCreateSerializer(serializers.Serializer):
    """Serializer for creating route stops within a route."""
    stop_id = serializers.IntegerField()
    order = serializers.IntegerField(min_value=1)
    minutes_from_previous_stop = serializers.IntegerField(min_value=0)
    distance_from_previous_stop = serializers.IntegerField(min_value=0)


class RouteListSerializer(serializers.ModelSerializer):
    """Compact serializer for route listing."""
    stop_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Route
        fields = ['id', 'name', 'description', 'stop_count']
    
    def get_stop_count(self, obj):
        return obj.routestop_set.count()


class RouteDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with all stops."""
    stops = serializers.SerializerMethodField()
    
    class Meta:
        model = Route
        fields = ['id', 'name', 'description', 'stops']
    
    def get_stops(self, obj):
        route_stops = obj.routestop_set.select_related('stop').order_by('order')
        return RouteStopSerializer(route_stops, many=True).data


class RouteCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating routes with stops."""
    stops = RouteStopCreateSerializer(many=True, write_only=True)
    
    class Meta:
        model = Route
        fields = ['id', 'name', 'description', 'stops']
        read_only_fields = ['id']
    
    def create(self, validated_data):
        stops_data = validated_data.pop('stops', [])
        route = Route.objects.create(**validated_data)
        
        for stop_data in stops_data:
            stop = Stop.objects.get(id=stop_data['stop_id'])
            RouteStop.objects.create(
                route=route,
                stop=stop,
                order=stop_data['order'],
                minutes_from_previous_stop=stop_data['minutes_from_previous_stop'],
                distance_from_previous_stop=stop_data['distance_from_previous_stop']
            )
        
        return route
    
    def update(self, instance, validated_data):
        stops_data = validated_data.pop('stops', None)
        
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.save()
        
        if stops_data is not None:
            # Delete existing stops and recreate
            instance.routestop_set.all().delete()
            for stop_data in stops_data:
                stop = Stop.objects.get(id=stop_data['stop_id'])
                RouteStop.objects.create(
                    route=instance,
                    stop=stop,
                    order=stop_data['order'],
                    minutes_from_previous_stop=stop_data['minutes_from_previous_stop'],
                    distance_from_previous_stop=stop_data['distance_from_previous_stop']
                )
        
        return instance


class TravellorCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating trips."""
    class Meta:
        model = Travellor
        fields = ['id', 'route', 'departure_time', 'vehicle_capacity', 'cost_per_km', 'status']
        read_only_fields = ['id']


class TravellorListSerializer(serializers.ModelSerializer):
    """Serializer for listing vendor's trips."""
    route_name = serializers.CharField(source='route.name', read_only=True)
    booked_seats = serializers.SerializerMethodField()
    
    class Meta:
        model = Travellor
        fields = ['id', 'route', 'route_name', 'departure_time', 'vehicle_capacity', 'cost_per_km', 'status', 'booked_seats']
    
    def get_booked_seats(self, obj):
        return obj.bookings.filter(status='CONFIRMED').aggregate(total=Sum('seats'))['total'] or 0


class BulkTravellorSerializer(serializers.Serializer):
    """Serializer for bulk trip creation."""
    route = serializers.PrimaryKeyRelatedField(queryset=Route.objects.all())
    departure_time = serializers.TimeField()
    month = serializers.IntegerField(min_value=1, max_value=12)
    year = serializers.IntegerField(min_value=2024)
    vehicle_capacity = serializers.IntegerField(min_value=1)
    cost_per_km = serializers.DecimalField(max_digits=6, decimal_places=2)


class VendorBookingSerializer(serializers.ModelSerializer):
    """Serializer for vendor to view trip bookings."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_phone = serializers.CharField(source='customer.contact_number', read_only=True)
    route_name = serializers.CharField(source='trip.route.name', read_only=True)
    start_stop_name = serializers.CharField(source='start_stop.stop.name', read_only=True)
    end_stop_name = serializers.CharField(source='end_stop.stop.name', read_only=True)
    departure_time = serializers.DateTimeField(source='trip.departure_time', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'customer_name', 'customer_phone', 'route_name', 
            'start_stop_name', 'end_stop_name', 'seats', 'status', 
            'booking_time', 'departure_time'
        ]


class VendorCabBookingSerializer(serializers.ModelSerializer):
    """Serializer for vendor to view and manage cab bookings."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_phone = serializers.CharField(source='customer.contact_number', read_only=True)
    car_name = serializers.CharField(source='car.name', read_only=True, allow_null=True)
    car_plate = serializers.CharField(source='car.license_plate', read_only=True, allow_null=True)
    
    class Meta:
        model = CabBooking
        fields = [
            'id', 'customer_name', 'customer_phone', 'pickup_location', 
            'dropoff_location', 'pickup_time', 'people_count', 'status',
            'booking_time', 'driver_name', 'driver_no', 'car', 'car_name', 'car_plate'
        ]


class CabBookingConfirmSerializer(serializers.Serializer):
    """Serializer for confirming a cab booking."""
    car = serializers.PrimaryKeyRelatedField(queryset=Car.objects.all())
    driver_name = serializers.CharField(max_length=100)
    driver_no = serializers.CharField(max_length=15)


class StopCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating stops."""
    class Meta:
        model = Stop
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']
