from datetime import datetime

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import Booking, CabBooking, Car, Route, Stop, Travellor
from .vendor_permissions import IsVendor
from .vendor_serializers import (
    BulkTripSerializer,
    CabBookingConfirmSerializer,
    CarSerializer,
    RouteSerializer,
    StopSerializer,
    TripSerializer,
    VendorBookingSerializer,
    VendorCabBookingSerializer,
    VendorSummarySerializer,
    VendorTokenObtainPairSerializer,
    VendorTokenRefreshSerializer,
)


class VendorPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class VendorLoginView(TokenObtainPairView):
    serializer_class = VendorTokenObtainPairSerializer


class VendorRefreshView(TokenRefreshView):
    serializer_class = VendorTokenRefreshSerializer


class MeView(APIView):
    permission_classes = (IsVendor,)

    def get(self, request):
        return Response(VendorSummarySerializer(request.user.vendor_profile).data)


class StopListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsVendor,)
    serializer_class = StopSerializer
    pagination_class = VendorPagination

    def get_queryset(self):
        queryset = Stop.objects.all().order_by("name", "id")
        query = self.request.query_params.get("search")
        return queryset.filter(Q(name__icontains=query) | Q(description__icontains=query)) if query else queryset


class RouteListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsVendor,)
    serializer_class = RouteSerializer
    pagination_class = VendorPagination

    def get_queryset(self):
        queryset = Route.objects.prefetch_related("routestop_set__stop").annotate(stop_count=Count("routestop")).order_by("name", "id")
        query = self.request.query_params.get("search")
        return queryset.filter(Q(name__icontains=query) | Q(description__icontains=query)) if query else queryset


class RouteDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsVendor,)
    serializer_class = RouteSerializer
    http_method_names = ("get", "patch", "head", "options")
    queryset = Route.objects.prefetch_related("routestop_set__stop").annotate(stop_count=Count("routestop"))


class TripListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsVendor,)
    serializer_class = TripSerializer
    pagination_class = VendorPagination

    def get_queryset(self):
        queryset = (
            Travellor.objects.filter(driver=self.request.user)
            .select_related("route")
            .prefetch_related("route__routestop_set__stop", "bookings")
            .annotate(booked_seats=Sum("bookings__seats", filter=Q(bookings__status="CONFIRMED")))
            .order_by("-departure_time", "-id")
        )
        status_value = self.request.query_params.get("status")
        date_from = parse_date(self.request.query_params.get("date_from", ""))
        date_to = parse_date(self.request.query_params.get("date_to", ""))
        search = self.request.query_params.get("search")
        if status_value:
            queryset = queryset.filter(status=status_value)
        if date_from:
            queryset = queryset.filter(departure_time__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(departure_time__date__lte=date_to)
        if search:
            queryset = queryset.filter(route__name__icontains=search)
        return queryset

    def perform_create(self, serializer):
        serializer.save(driver=self.request.user)


class TripDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsVendor,)
    serializer_class = TripSerializer
    http_method_names = ("get", "patch", "head", "options")

    def get_queryset(self):
        return Travellor.objects.filter(driver=self.request.user).select_related("route").prefetch_related("route__routestop_set__stop", "bookings")


class BulkTripView(APIView):
    permission_classes = (IsVendor,)

    def post(self, request):
        serializer = BulkTripSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        trips = serializer.save()
        return Response(
            {"created_count": len(trips), "results": TripSerializer(trips, many=True).data},
            status=status.HTTP_201_CREATED,
        )


class BookingListView(generics.ListAPIView):
    permission_classes = (IsVendor,)
    serializer_class = VendorBookingSerializer
    pagination_class = VendorPagination

    def get_queryset(self):
        queryset = Booking.objects.filter(trip__driver=self.request.user).select_related(
            "customer", "trip__route", "start_stop__stop", "end_stop__stop"
        ).order_by("-booking_time", "-id")
        status_value = self.request.query_params.get("status")
        date_from = parse_date(self.request.query_params.get("date_from", ""))
        date_to = parse_date(self.request.query_params.get("date_to", ""))
        search = self.request.query_params.get("search")
        if status_value:
            queryset = queryset.filter(status=status_value)
        if date_from:
            queryset = queryset.filter(booking_time__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(booking_time__date__lte=date_to)
        if search:
            queryset = queryset.filter(Q(customer__name__icontains=search) | Q(trip__route__name__icontains=search))
        return queryset


class CarListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsVendor,)
    serializer_class = CarSerializer
    pagination_class = VendorPagination
    queryset = Car.objects.all().order_by("name", "id")


class CabBookingListView(generics.ListAPIView):
    permission_classes = (IsVendor,)
    serializer_class = VendorCabBookingSerializer
    pagination_class = VendorPagination

    def get_queryset(self):
        queryset = CabBooking.objects.select_related("customer", "car").order_by("pickup_time", "id")
        status_value = self.request.query_params.get("status")
        date_from = parse_date(self.request.query_params.get("date_from", ""))
        date_to = parse_date(self.request.query_params.get("date_to", ""))
        search = self.request.query_params.get("search")
        if status_value:
            queryset = queryset.filter(status=status_value)
        if date_from:
            queryset = queryset.filter(pickup_time__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(pickup_time__date__lte=date_to)
        if search:
            queryset = queryset.filter(
                Q(customer__name__icontains=search)
                | Q(pickup_location__icontains=search)
                | Q(dropoff_location__icontains=search)
            )
        return queryset


class CabBookingConfirmView(APIView):
    permission_classes = (IsVendor,)

    @transaction.atomic
    def post(self, request, pk):
        serializer = CabBookingConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = get_object_or_404(
            CabBooking.objects.select_for_update().select_related("customer", "car"), pk=pk
        )
        if booking.status != "BOOKED":
            return Response(
                {"detail": "Only booked cab requests can be confirmed."},
                status=status.HTTP_409_CONFLICT,
            )
        booking.car = serializer.validated_data["car"]
        booking.driver_name = serializer.validated_data["driver_name"]
        booking.driver_no = serializer.validated_data["driver_no"]
        booking.status = "CONFIRMED"
        booking.save(update_fields=("car", "driver_name", "driver_no", "status"))
        return Response(VendorCabBookingSerializer(booking).data)
