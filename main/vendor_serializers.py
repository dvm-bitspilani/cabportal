import calendar
from datetime import datetime

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Booking, CabBooking, Car, Route, RouteStop, Stop, Travellor


class VendorSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    company_name = serializers.CharField(read_only=True)
    contact_number = serializers.CharField(read_only=True)
    address = serializers.CharField(read_only=True)


class VendorTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if not hasattr(self.user, "vendor_profile"):
            raise AuthenticationFailed("A vendor account is required.")
        data["vendor"] = VendorSummarySerializer(self.user.vendor_profile).data
        return data


class VendorTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = RefreshToken(attrs["refresh"])
        user = User.objects.filter(pk=refresh.get("user_id"), is_active=True).first()
        if not user or not hasattr(user, "vendor_profile"):
            raise AuthenticationFailed("A vendor account is required.")
        return super().validate(attrs)


class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stop
        fields = ("id", "name", "description")
        read_only_fields = ("id",)


class RouteStopReadSerializer(serializers.ModelSerializer):
    stop = StopSerializer(read_only=True)
    stop_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = RouteStop
        fields = (
            "id",
            "stop_id",
            "stop",
            "order",
            "minutes_from_previous_stop",
            "distance_from_previous_stop",
        )


class RouteStopWriteSerializer(serializers.Serializer):
    stop_id = serializers.PrimaryKeyRelatedField(
        source="stop", queryset=Stop.objects.all()
    )
    order = serializers.IntegerField(min_value=1)
    minutes_from_previous_stop = serializers.IntegerField(min_value=0)
    distance_from_previous_stop = serializers.IntegerField(min_value=0)


class RouteSerializer(serializers.ModelSerializer):
    stops = RouteStopWriteSerializer(many=True, write_only=True, required=False)
    route_stops = RouteStopReadSerializer(
        source="routestop_set", many=True, read_only=True
    )
    stop_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Route
        fields = ("id", "name", "description", "stop_count", "stops", "route_stops")
        read_only_fields = ("id",)

    def validate_stops(self, stops):
        if len(stops) < 2:
            raise serializers.ValidationError("A route must contain at least two stops.")
        orders = [item["order"] for item in stops]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError("Route stop orders must be unique.")
        if sorted(orders) != list(range(1, len(orders) + 1)):
            raise serializers.ValidationError("Route stop orders must be consecutive from 1.")
        stop_ids = [item["stop"].pk for item in stops]
        if len(stop_ids) != len(set(stop_ids)):
            raise serializers.ValidationError("A stop may only appear once in a route.")
        for item in stops:
            first = item["order"] == 1
            minutes = item["minutes_from_previous_stop"]
            distance = item["distance_from_previous_stop"]
            if first and (minutes != 0 or distance != 0):
                raise serializers.ValidationError(
                    "The first stop must have zero distance and travel time."
                )
            if not first and (minutes <= 0 or distance <= 0):
                raise serializers.ValidationError(
                    "Stops after the first require positive distance and travel time."
                )
        return stops

    def validate(self, attrs):
        if not self.instance and "stops" not in attrs:
            raise serializers.ValidationError({"stops": "This field is required."})
        return attrs

    def _replace_stops(self, route, stops):
        route.routestop_set.all().delete()
        RouteStop.objects.bulk_create(
            [RouteStop(route=route, **item) for item in sorted(stops, key=lambda x: x["order"])]
        )

    @transaction.atomic
    def create(self, validated_data):
        stops = validated_data.pop("stops")
        route = Route.objects.create(**validated_data)
        self._replace_stops(route, stops)
        return route

    @transaction.atomic
    def update(self, instance, validated_data):
        stops = validated_data.pop("stops", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if stops is not None:
            self._replace_stops(instance, stops)
        return instance


class TripSerializer(serializers.ModelSerializer):
    route_name = serializers.CharField(source="route.name", read_only=True)
    booked_seats = serializers.SerializerMethodField()
    schedule = serializers.SerializerMethodField()

    class Meta:
        model = Travellor
        fields = (
            "id",
            "route",
            "route_name",
            "departure_time",
            "vehicle_capacity",
            "cost_per_km",
            "status",
            "booked_seats",
            "schedule",
        )
        read_only_fields = ("id",)

    def get_booked_seats(self, obj):
        return getattr(obj, "booked_seats", None) or sum(
            booking.seats for booking in obj.bookings.all() if booking.status == "CONFIRMED"
        )

    def get_schedule(self, obj):
        return obj.get_schedule()

    def validate_vehicle_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Must be greater than zero.")
        return value

    def validate_cost_per_km(self, value):
        if value <= 0:
            raise serializers.ValidationError("Must be greater than zero.")
        return value

    def validate_status(self, value):
        if not self.instance:
            if value != "SCHEDULED":
                raise serializers.ValidationError("New trips must be scheduled.")
            return value
        transitions = {
            "SCHEDULED": {"SCHEDULED", "IN_PROGRESS", "CANCELLED"},
            "IN_PROGRESS": {"IN_PROGRESS", "COMPLETED", "CANCELLED"},
            "COMPLETED": {"COMPLETED"},
            "CANCELLED": {"CANCELLED"},
        }
        if value not in transitions[self.instance.status]:
            raise serializers.ValidationError(
                f"Cannot change status from {self.instance.status} to {value}."
            )
        return value


class BulkTripSerializer(serializers.Serializer):
    route = serializers.PrimaryKeyRelatedField(queryset=Route.objects.all())
    departure_time = serializers.TimeField()
    month = serializers.IntegerField(min_value=1, max_value=12)
    year = serializers.IntegerField(min_value=2024, max_value=2100)
    vehicle_capacity = serializers.IntegerField(min_value=1)
    cost_per_km = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=0.01)

    def validate(self, attrs):
        try:
            calendar.monthrange(attrs["year"], attrs["month"])
        except (ValueError, OverflowError):
            raise serializers.ValidationError({"month": "Invalid month and year."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        days = calendar.monthrange(validated_data["year"], validated_data["month"])[1]
        tz = timezone.get_current_timezone()
        trips = []
        for day in range(1, days + 1):
            local_departure = datetime.combine(
                datetime(validated_data["year"], validated_data["month"], day).date(),
                validated_data["departure_time"],
            )
            departure = timezone.make_aware(local_departure, tz)
            trips.append(
                Travellor(
                    driver=user,
                    route=validated_data["route"],
                    departure_time=departure,
                    vehicle_capacity=validated_data["vehicle_capacity"],
                    cost_per_km=validated_data["cost_per_km"],
                    status="SCHEDULED",
                )
            )
        return Travellor.objects.bulk_create(trips)


class VendorBookingSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_phone = serializers.CharField(source="customer.contact_number", read_only=True)
    trip_id = serializers.IntegerField(source="trip.id", read_only=True)
    route_name = serializers.CharField(source="trip.route.name", read_only=True)
    departure_time = serializers.DateTimeField(source="trip.departure_time", read_only=True)
    start_stop = StopSerializer(source="start_stop.stop", read_only=True)
    end_stop = StopSerializer(source="end_stop.stop", read_only=True)

    class Meta:
        model = Booking
        fields = (
            "id", "trip_id", "customer_name", "customer_phone", "route_name",
            "departure_time", "start_stop", "end_stop", "seats", "status", "booking_time",
        )


class CarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Car
        fields = ("id", "name", "license_plate")
        read_only_fields = ("id",)

    def validate_license_plate(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value


class VendorCabBookingSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_phone = serializers.CharField(source="customer.contact_number", read_only=True)
    car = CarSerializer(read_only=True)

    class Meta:
        model = CabBooking
        fields = (
            "id", "customer_name", "customer_phone", "pickup_location", "dropoff_location",
            "pickup_time", "people_count", "booking_time", "status", "driver_name", "driver_no", "car",
        )


class CabBookingConfirmSerializer(serializers.Serializer):
    car = serializers.PrimaryKeyRelatedField(queryset=Car.objects.all())
    driver_name = serializers.CharField(max_length=100, allow_blank=False, trim_whitespace=True)
    driver_no = serializers.CharField(max_length=15, allow_blank=False, trim_whitespace=True)

    def validate_driver_no(self, value):
        if not value.strip():
            raise serializers.ValidationError("Driver phone number is required.")
        return value
