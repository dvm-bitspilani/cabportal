from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponseForbidden
from django.db import transaction
from .forms import TravellorForm, RouteForm, RouteStopFormSet, StopForm
from .forms import CarForm, CabBookingConfirmForm, BulkTravellorForm
from .models import Route, Travellor, Stop, Booking, Customer, CabBooking
from .models import Car
from .serializers import (
    BookingSerializer,
    TravellorSerializer,
    StopSerializer,
    BookingDetailSerializer,
    CustomerSerializer,
    CabBookingSerializer,
    CabBookingDetailSerializer,
    CustomTokenObtainPairSerializer,
)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from google.oauth2 import id_token
from google.auth.transport import requests
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError  
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
import calendar

# --- Stop Management ---

@login_required
def create_stop(request):
    """View for a vendor to create a new Stop."""
    # Ensure the user has a vendor profile before proceeding
    if not hasattr(request.user, 'vendor_profile'):
        return HttpResponseForbidden("You do not have permission to add stops.")
        
    if request.method == 'POST':
        form = StopForm(request.POST)
        if form.is_valid():
            form.save()
            # Redirect to the list of routes where stops are most relevant
            return redirect('list_routes') 
    else:
        form = StopForm()
    return render(request, 'main/create_stop.html', {'form': form})


# --- Traveller (Trip) Management ---

@login_required
def add_travellor(request):
    """View for a vendor to add a new Travellor (trip)."""
    if not hasattr(request.user, 'vendor_profile'):
        return HttpResponseForbidden("You do not have permission to add a trip.")

    if request.method == 'POST':
        form = TravellorForm(request.POST)
        if form.is_valid():
            travellor = form.save(commit=False)
            travellor.driver = request.user # Assign the logged-in user as the driver
            travellor.save()
            return redirect('list_travellors')
    else:
        form = TravellorForm()
    return render(request, 'main/add_travellor.html', {'form': form})


@login_required
def list_travellors(request):
    """View for a vendor to see all their created trips."""
    if not hasattr(request.user, 'vendor_profile'):
        return HttpResponseForbidden("You do not have permission to view this page.")
    
    # Filter trips to show only those created by the currently logged-in user
    travellors = Travellor.objects.filter(driver=request.user).order_by('-departure_time')
    return render(request, 'main/list_travellors.html', {'travellors': travellors})


@login_required
def edit_travellor(request, travellor_id):
    """View for a vendor to edit one of their existing trips."""
    travellor = get_object_or_404(Travellor, id=travellor_id)

    # Security check: ensure the logged-in user is the driver for this trip
    if travellor.driver != request.user:
        return HttpResponseForbidden("You do not have permission to edit this trip.")

    if request.method == 'POST':
        form = TravellorForm(request.POST, instance=travellor)
        if form.is_valid():
            form.save()
            return redirect('list_travellors')
    else:
        form = TravellorForm(instance=travellor)

    return render(request, 'main/edit_travellor.html', {'form': form, 'travellor': travellor})


@login_required
def bulk_add_travellor(request):
    """View for a vendor to create daily trips for an entire month."""
    if not hasattr(request.user, 'vendor_profile'):
        return HttpResponseForbidden("You do not have permission to add trips.")

    if request.method == 'POST':
        form = BulkTravellorForm(request.POST)
        if form.is_valid():
            route = form.cleaned_data['route']
            departure_time = form.cleaned_data['departure_time']
            month = int(form.cleaned_data['month'])
            year = int(form.cleaned_data['year'])
            vehicle_capacity = form.cleaned_data['vehicle_capacity']
            cost_per_km = form.cleaned_data['cost_per_km']

            days_in_month = calendar.monthrange(year, month)[1]
            trips_created = 0

            with transaction.atomic():
                for day in range(1, days_in_month + 1):
                    departure_datetime = datetime(
                        year=year,
                        month=month,
                        day=day,
                        hour=departure_time.hour,
                        minute=departure_time.minute
                    )
                    Travellor.objects.create(
                        driver=request.user,
                        route=route,
                        departure_time=departure_datetime,
                        vehicle_capacity=vehicle_capacity,
                        cost_per_km=cost_per_km,
                        status='SCHEDULED'
                    )
                    trips_created += 1

            return render(request, 'main/bulk_add_travellor.html', {
                'form': BulkTravellorForm(),
                'success_message': f'Successfully created {trips_created} trips for {calendar.month_name[month]} {year}.'
            })
    else:
        form = BulkTravellorForm()

    return render(request, 'main/bulk_add_travellor.html', {'form': form})


# --- Route Management ---

@login_required
def manage_route(request):
    """View for a vendor to add a new Route with its associated stops."""
    if not hasattr(request.user, 'vendor_profile'):
        return HttpResponseForbidden("You do not have permission to manage routes.")

    if request.method == 'POST':
        form = RouteForm(request.POST)
        formset = RouteStopFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                route = form.save()
                formset.instance = route
                formset.save()
                return redirect('list_routes')
    else:
        form = RouteForm()
        formset = RouteStopFormSet()

    return render(request, 'main/manage_route.html', {'form': form, 'formset': formset})


@login_required
def list_routes(request):
    """View for a vendor to see all available routes in the system."""
    if not hasattr(request.user, 'vendor_profile'):
        return HttpResponseForbidden("You do not have permission to view routes.")
    routes = Route.objects.all().order_by('name')
    return render(request, 'main/list_routes.html', {'routes': routes})


@login_required
def edit_route(request, route_id):
    """View for a vendor to edit an existing Route and its stops."""
    route = get_object_or_404(Route, id=route_id)
    if not hasattr(request.user, 'vendor_profile'):
        return HttpResponseForbidden("You do not have permission to edit routes.")

    if request.method == 'POST':
        form = RouteForm(request.POST, instance=route)
        formset = RouteStopFormSet(request.POST, instance=route)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
                return redirect('list_routes')
    else:
        form = RouteForm(instance=route)
        formset = RouteStopFormSet(instance=route)

    return render(request, 'main/edit_route.html', {'form': form, 'formset': formset, 'route': route})


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class GoogleLogin(APIView):
    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response({"error": "Google token is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), settings.GOOGLE_CLIENT_ID)
            email = idinfo['email']
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'username': email.split('@')[0]}
            )
            refresh = RefreshToken.for_user(user)
            customer = Customer.objects.filter(user=user).first()
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'customer': CustomerSerializer(customer).data if customer else None
            },status=200)
        except ValueError:
            return Response({"error": "Invalid Google token"}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({"error": "Customer does not exist"}, status=status.HTTP_401_UNAUTHORIZED)


class CustomerSignupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if hasattr(request.user, 'customer_profile'):
            return Response({"error": "Customer profile already exists."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CustomerSerializer(data=request.data)
        if serializer.is_valid():
            customer = serializer.save(user=request.user)
            return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BookTravellerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        customer = get_object_or_404(Customer, user=request.user)
        serializer = BookingSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    booking = serializer.save(customer=customer)
                    return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StopListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        stops = Stop.objects.all()
        serializer = StopSerializer(stops, many=True)
        return Response(serializer.data)


class CabBookingView(APIView):
    """Create a new cab booking (POST) and list user's cab bookings (GET)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Create a cab booking; operation must be atomic to avoid double-booking issues
        customer = get_object_or_404(Customer, user=request.user)
        serializer = CabBookingSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    # serializer.create expects customer passed via kwargs
                    cab_booking = serializer.create(serializer.validated_data, customer=customer)
                    return Response(CabBookingDetailSerializer(cab_booking).data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        # List current user's cab bookings
        customer = get_object_or_404(Customer, user=request.user)
        bookings = CabBooking.objects.filter(customer=customer).order_by('-booking_time')
        serializer = CabBookingDetailSerializer(bookings, many=True)
        return Response(serializer.data)


@login_required
def manage_cars(request):
    """View for a vendor to add or list cars belonging to their company/vendor."""
    if not hasattr(request.user, 'vendor_profile'):
        return HttpResponseForbidden("You do not have permission to manage cars.")

    cars = Car.objects.all().order_by('name')
    return render(request, 'main/manage_cars.html', {'cars': cars})


@login_required
def add_car(request):
    """Form view for vendors to add a new Car."""
    if not hasattr(request.user, 'vendor_profile'):
        return HttpResponseForbidden("You do not have permission to add cars.")

    if request.method == 'POST':
        form = CarForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('manage_cars')
    else:
        form = CarForm()
    return render(request, 'main/add_car.html', {'form': form})


@login_required
def vendor_cab_bookings(request):
    """Server-rendered page showing cab bookings for vendors to review and confirm."""
    if not hasattr(request.user, 'vendor_profile'):
        return HttpResponseForbidden("You do not have permission to view this page.")

    # For now, show all unconfirmed/booked cab bookings so vendor can assign cars/drivers
    bookings = CabBooking.objects.filter().order_by('pickup_time')
    return render(request, 'main/vendor_cab_bookings.html', {'bookings': bookings})


@login_required
def confirm_cab_booking(request, booking_id):
    """Allow vendor to assign a car and driver info to a CabBooking and confirm it."""
    if not hasattr(request.user, 'vendor_profile'):
        return HttpResponseForbidden("You do not have permission to confirm bookings.")

    booking = get_object_or_404(CabBooking, id=booking_id)

    if request.method == 'POST':
        form = CabBookingConfirmForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            booking.status = 'CONFIRMED'
            booking.save()
            return redirect('vendor_cab_bookings')
    else:
        form = CabBookingConfirmForm(instance=booking)

    return render(request, 'main/confirm_cab_booking.html', {'form': form, 'booking': booking})


@login_required
def vendor_bookings_view(request):
    if not hasattr(request.user, 'vendor_profile'):
        return HttpResponseForbidden("You do not have permission to view this page.")
    
    bookings = Booking.objects.filter(trip__driver=request.user).order_by('-booking_time')
    return render(request, 'main/vendor_bookings.html', {'bookings': bookings})


class SearchTravellersView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        cust=get_object_or_404(Customer, user=request.user)
        start_stop_id = request.query_params.get('start_stop_id')
        end_stop_id = request.query_params.get('end_stop_id')
        travel_date = request.query_params.get('date')  # Expected format: YYYY-MM-DD

        if not start_stop_id or not end_stop_id:
            return Response({"error": "Both start_stop_id and end_stop_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            start_stop = Stop.objects.get(id=start_stop_id)
            end_stop = Stop.objects.get(id=end_stop_id)
        except Stop.DoesNotExist:
            return Response({"error": "Invalid stop ID provided."}, status=status.HTTP_404_NOT_FOUND)

        # Find routes that contain both stops
        routes = Route.objects.filter(stops=start_stop).filter(stops=end_stop)

        # Filter travellers on these routes
        travellers = Travellor.objects.filter(route__in=routes, status='SCHEDULED', departure_time__gte=datetime.now()).order_by('departure_time')

        # Filter by date if provided
        if travel_date:
            try:
                date_obj = datetime.strptime(travel_date, '%Y-%m-%d').date()
                if date_obj < datetime.now().date():
                    return Response({"error": "Travel date cannot be in the past."}, status=status.HTTP_400_BAD_REQUEST)
                day_start = datetime.combine(date_obj, datetime.min.time())
                day_end = datetime.combine(date_obj, datetime.max.time())
                travellers = travellers.filter(departure_time__gte=day_start, departure_time__lte=day_end)
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        # Further filter to ensure the stop order is correct and calculate arrival times
        valid_travellers_data = []
        for traveller in travellers:
            try:
                schedule = traveller.get_schedule()
                start_route_stop = next((item for item in schedule if item['stop_id'] == start_stop.id), None)
                end_route_stop = next((item for item in schedule if item['stop_id'] == end_stop.id), None)
                available_seats = traveller.vehicle_capacity-traveller.get_booked_seats_for_segment(start_route_stop['order'], end_route_stop['order'])  # To ensure validation
                if start_route_stop and end_route_stop and start_route_stop['order'] < end_route_stop['order']:
                    serializer_context = {
                        'start_stop_id': start_stop.id,
                        'end_stop_id': end_stop.id
                    }
                    traveller_data = TravellorSerializer(traveller, context=serializer_context).data
                    traveller_data['departure_from_start'] = start_route_stop['estimated_arrival_time']
                    traveller_data['arrival_at_end'] = end_route_stop['estimated_arrival_time']
                    traveller_data['start_stop_id'] = start_route_stop['route_stop_id']
                    traveller_data['end_stop_id'] = end_route_stop['route_stop_id']
                    traveller_data['available_seats'] = available_seats
                    valid_travellers_data.append(traveller_data)
            except Stop.DoesNotExist:
                continue

        return Response(valid_travellers_data)


class UserBookingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        customer = get_object_or_404(Customer, user=request.user)
        bookings = Booking.objects.filter(customer=customer).order_by('-booking_time')
        serializer = BookingDetailSerializer(bookings, many=True)
        return Response(serializer.data)


