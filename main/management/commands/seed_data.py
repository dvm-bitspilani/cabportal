"""
Populate the database with randomized sample data for development/testing.

Usage (inside the web container):
    python manage.py seed_data --clear
    python manage.py seed_data --customers 30 --trips 50 --bookings 80 --seed 42

Uses only the standard library `random` (no Faker dependency) so it runs in the
Docker image as-is.
"""
import random
from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from main.models import (
    Vendor, Customer, Stop, Route, RouteStop, Travellor, Booking, Car, CabBooking,
)

# ---------------------------------------------------------------------------
# Curated pools for realistic-looking random data
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "Amit", "Priya", "Rahul", "Sneha", "Vikram", "Anjali", "Rajesh", "Pooja",
    "Suresh", "Kavya", "Arjun", "Divya", "Karan", "Meera", "Rohan", "Nisha",
    "Sanjay", "Isha", "Manoj", "Aarti", "Deepak", "Ritu", "Sachin", "Neha",
]
LAST_NAMES = [
    "Sharma", "Patel", "Kumar", "Singh", "Reddy", "Gupta", "Mehta", "Nair",
    "Iyer", "Joshi", "Desai", "Rao", "Verma", "Shah", "Chopra", "Bose",
]
COMPANY_NAMES = [
    "Ridezy Travels", "SwiftCab Co", "MetroMove Logistics", "CityLink Cabs",
    "Prime Rides", "GoFleet Services", "Urban Transit", "Skyline Travels",
]
STOP_POOL = [
    ("Mumbai Central", "Main railway station, Mumbai Central"),
    ("Bandra", "Bandra West, near the bus stand"),
    ("Andheri", "Andheri East, near the airport"),
    ("Borivali", "Borivali National Park area"),
    ("Dadar", "Dadar station area"),
    ("Thane", "Thane station west"),
    ("Navi Mumbai", "Vashi sector 15 bus stop"),
    ("Panvel", "Panvel junction"),
    ("Pune Station", "Pune railway station"),
    ("Shivajinagar", "Shivajinagar bus stand, Pune"),
    ("Hinjewadi", "Hinjewadi phase 3 IT park"),
    ("Swargate", "Swargate bus terminus, Pune"),
    ("Kharadi", "Kharadi EON IT park"),
    ("Wakad", "Wakad chowk"),
    ("Lonavala", "Lonavala market"),
    ("Kalyan", "Kalyan junction"),
]
CAR_MODELS = [
    "Toyota Innova", "Maruti Suzuki Ertiga", "Honda City", "Toyota Fortuner",
    "Tata Indica", "Hyundai Aura", "Mahindra Marazzo", "Kia Carens",
]
LOCATION_POOL = [
    "Mumbai Airport, T2 Terminal", "Grand Hyatt, Bandra Kurla Complex",
    "Andheri Station, East Side", "Phoenix Marketcity, Kurla",
    "Powai, Hiranandani Gardens", "Colaba Causeway",
    "Pune Airport, Lohegaon", "Koregaon Park, Lane 5",
    "Hinjewadi Phase 1", "Viman Nagar, Phoenix Mall",
    "Thane Station, West", "Vashi, Inorbit Mall",
]
ROUTE_ADJECTIVES = ["Express", "Local", "Direct", "Shuttle", "Highway", "Loop"]


def phone():
    return f"{random.randint(6, 9)}{random.randint(0, 9999999999):09d}"[:10]


def plate():
    return (
        f"MH-{random.randint(1, 20):02d}-"
        f"{random.choice('ABCDEFGH')}{random.choice('ABCDEFGH')}-"
        f"{random.randint(1000, 9999)}"
    )


class Command(BaseCommand):
    help = "Populate the database with randomized sample data for development/testing."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true",
                            help="Delete existing non-superuser data before seeding.")
        parser.add_argument("--seed", type=int, default=None,
                            help="Seed the RNG for reproducible output.")
        parser.add_argument("--vendors", type=int, default=3)
        parser.add_argument("--drivers", type=int, default=6)
        parser.add_argument("--customers", type=int, default=15)
        parser.add_argument("--stops", type=int, default=12)
        parser.add_argument("--routes", type=int, default=4)
        parser.add_argument("--cars", type=int, default=6)
        parser.add_argument("--trips", type=int, default=25)
        parser.add_argument("--bookings", type=int, default=40)
        parser.add_argument("--cab-bookings", type=int, default=30)

    def handle(self, *args, **opts):
        if opts["seed"] is not None:
            random.seed(opts["seed"])

        if opts["clear"]:
            self._clear_data()

        with transaction.atomic():
            drivers = self._create_vendors_and_drivers(opts["vendors"], opts["drivers"])
            customers = self._create_customers(opts["customers"])
            stops = self._create_stops(opts["stops"])
            routes = self._create_routes(opts["routes"], stops)
            cars = self._create_cars(opts["cars"])
            trips = self._create_trips(opts["trips"], routes, drivers)
            n_bookings = self._create_bookings(opts["bookings"], trips, customers)
            n_cab = self._create_cab_bookings(opts["cab_bookings"], customers, cars)

        self.stdout.write(self.style.SUCCESS(
            "\nSeed complete:\n"
            f"  vendors={opts['vendors']} drivers={len(drivers)} customers={len(customers)}\n"
            f"  stops={len(stops)} routes={len(routes)} cars={len(cars)} trips={len(trips)}\n"
            f"  bookings={n_bookings} cab_bookings={n_cab}\n"
            "\nApp test login -> username: testuser  password: test1234"
        ))

    # ------------------------------------------------------------------ utils
    def _unique_username(self, base):
        username = base
        while User.objects.filter(username=username).exists():
            username = f"{base}{random.randint(1000, 9999)}"
        return username

    def _clear_data(self):
        self.stdout.write("Clearing existing data...")
        CabBooking.objects.all().delete()
        Booking.objects.all().delete()
        Travellor.objects.all().delete()
        Car.objects.all().delete()
        RouteStop.objects.all().delete()
        Route.objects.all().delete()
        Stop.objects.all().delete()
        Customer.objects.all().delete()
        Vendor.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

    # --------------------------------------------------------------- creators
    def _create_vendors_and_drivers(self, n_vendors, n_drivers):
        self.stdout.write("Creating vendors and drivers...")
        for i in range(n_vendors):
            user = User.objects.create_user(
                username=self._unique_username(f"vendor{i + 1}"),
                password="vendor123",
                email=f"vendor{i + 1}@example.com",
                first_name=random.choice(FIRST_NAMES),
                last_name=random.choice(LAST_NAMES),
            )
            Vendor.objects.create(
                user=user,
                company_name=random.choice(COMPANY_NAMES),
                contact_number=phone(),
                address=f"{random.randint(1, 300)}, {random.choice(STOP_POOL)[0]} Road",
            )

        drivers = []
        for i in range(n_drivers):
            fn, ln = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
            driver = User.objects.create_user(
                username=self._unique_username(f"driver{i + 1}"),
                password="driver123",
                email=f"driver{i + 1}@example.com",
                first_name=fn,
                last_name=ln,
            )
            drivers.append(driver)
        return drivers

    def _create_customers(self, n):
        self.stdout.write("Creating customers...")
        customers = []

        # One deterministic account for logging into the mobile app.
        if not User.objects.filter(username="testuser").exists():
            test_user = User.objects.create_user(
                username="testuser", password="test1234",
                email="testuser@example.com", first_name="Test", last_name="User",
            )
            customers.append(Customer.objects.create(
                user=test_user, name="Test User", contact_number=phone(),
            ))

        for i in range(n):
            fn, ln = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
            user = User.objects.create_user(
                username=self._unique_username(f"customer{i + 1}"),
                password="customer123",
                email=f"customer{i + 1}@example.com",
                first_name=fn, last_name=ln,
            )
            customers.append(Customer.objects.create(
                user=user, name=f"{fn} {ln}", contact_number=phone(),
            ))
        return customers

    def _create_stops(self, n):
        self.stdout.write("Creating stops...")
        chosen = random.sample(STOP_POOL, min(n, len(STOP_POOL)))
        return [Stop.objects.create(name=name, description=desc) for name, desc in chosen]

    def _create_routes(self, n, stops):
        self.stdout.write("Creating routes...")
        routes = []
        for _ in range(n):
            count = random.randint(3, min(7, len(stops)))
            route_stops = random.sample(stops, count)
            origin, dest = route_stops[0].name, route_stops[-1].name
            route = Route.objects.create(
                name=f"{origin} to {dest} ({random.choice(ROUTE_ADJECTIVES)})",
                description=f"Route from {origin} to {dest}",
            )
            for order, stop in enumerate(route_stops, start=1):
                # order==1 must be 0/0; every later stop must be > 0 (model.clean()).
                mins = 0 if order == 1 else random.randint(5, 90)
                dist = 0 if order == 1 else random.randint(2, 80)
                RouteStop.objects.create(
                    route=route, stop=stop, order=order,
                    minutes_from_previous_stop=mins, distance_from_previous_stop=dist,
                )
            routes.append(route)
        return routes

    def _create_cars(self, n):
        self.stdout.write("Creating cars...")
        return [Car.objects.create(name=random.choice(CAR_MODELS), license_plate=plate())
                for _ in range(n)]

    def _create_trips(self, n, routes, drivers):
        self.stdout.write("Creating trips...")
        now = timezone.now()
        trips = []
        for _ in range(n):
            # departure spread from 5 days ago to 10 days ahead
            departure = now + timezone.timedelta(
                days=random.randint(-5, 10),
                hours=random.randint(0, 23),
                minutes=random.choice([0, 15, 30, 45]),
            )
            if departure < now:
                status = random.choice(["COMPLETED", "COMPLETED", "CANCELLED"])
            else:
                status = "SCHEDULED"
            cost = Decimal(str(round(random.uniform(1.5, 4.0), 2))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP)
            trips.append(Travellor.objects.create(
                driver=random.choice(drivers),
                route=random.choice(routes),
                departure_time=departure,
                vehicle_capacity=random.choice([20, 30, 35, 40, 45, 50]),
                cost_per_km=cost,
                status=status,
            ))
        return trips

    def _create_bookings(self, n, trips, customers):
        self.stdout.write("Creating bookings...")
        created = 0
        attempts = 0
        # Booking.save() runs full_clean(): stops must be on the trip's route,
        # start.order < end.order, and seats must fit the segment availability.
        # We retry on ValidationError rather than pre-computing every constraint.
        while created < n and attempts < n * 5:
            attempts += 1
            trip = random.choice(trips)
            route_stops = list(
                RouteStop.objects.filter(route=trip.route).order_by("order")
            )
            if len(route_stops) < 2:
                continue
            i = random.randint(0, len(route_stops) - 2)
            j = random.randint(i + 1, len(route_stops) - 1)
            try:
                Booking.objects.create(
                    trip=trip,
                    customer=random.choice(customers),
                    start_stop=route_stops[i],
                    end_stop=route_stops[j],
                    seats=random.randint(1, 4),
                    status=random.choice(["CONFIRMED", "CONFIRMED", "COMPLETED"]),
                )
                created += 1
            except ValidationError:
                continue  # segment full or invalid combo; try another
        return created

    def _create_cab_bookings(self, n, customers, cars):
        self.stdout.write("Creating cab bookings...")
        now = timezone.now()
        for _ in range(n):
            pickup, dropoff = random.sample(LOCATION_POOL, 2)
            pickup_time = now + timezone.timedelta(
                days=random.randint(-3, 7), hours=random.randint(0, 23),
            )
            assigned = random.random() < 0.6
            CabBooking.objects.create(
                customer=random.choice(customers),
                pickup_location=pickup,
                dropoff_location=dropoff,
                pickup_time=pickup_time,
                people_count=random.randint(1, 6),
                status="CONFIRMED" if assigned else random.choice(["BOOKED", "CANCELLED"]),
                driver_name=(f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
                             if assigned else None),
                driver_no=phone() if assigned else None,
                car=random.choice(cars) if assigned else None,
            )
        return n
