"""
Populate Pilani <-> Loharu stops, routes, shared trips (Travellor) and cab
bookings for testuser.

Usage (inside the web container):
    python manage.py seed_pilani_loharu
    python manage.py seed_pilani_loharu --bookings 25 --trips 12 --seed 42 --clear

Stops, routes and drivers are created idempotently (get_or_create), so
re-running only adds new trips and bookings unless --clear is passed.
"""
import random
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from main.models import (
    Customer, Stop, Route, RouteStop, Travellor, Booking, Car, CabBooking,
)

# ---------------------------------------------------------------------------
# The Pilani -> Loharu corridor (~40 km, roughly an hour by road).
# (name, description, minutes_from_previous, km_from_previous)
# ---------------------------------------------------------------------------
PILANI_LOHARU_STOPS = [
    ("BITS Pilani Main Gate", "BITS Pilani campus main gate, Vidya Vihar", 0, 0),
    ("Pilani Bus Stand", "Pilani town bus stand, near Shiv Ganga Chowk", 10, 3),
    ("Pilani Toll Plaza", "Toll plaza on the Pilani-Loharu road", 12, 8),
    ("Rajasthan-Haryana Border", "State border crossing on the Pilani-Loharu road", 15, 12),
    ("Loharu Bus Stand", "Loharu town bus stand, Bhiwani district", 15, 13),
    ("Loharu Railway Station", "Loharu Junction railway station", 8, 4),
]

FORWARD_ROUTE_NAME = "Pilani to Loharu"
REVERSE_ROUTE_NAME = "Loharu to Pilani"

CAR_MODELS = [
    "Maruti Suzuki Ertiga", "Toyota Innova", "Maruti Suzuki Dzire",
    "Mahindra Bolero", "Hyundai Aura", "Tata Indigo",
]
DRIVER_NAMES = [
    "Ramesh Saini", "Vijay Yadav", "Sunil Jangid", "Mahesh Kumawat",
    "Dinesh Sharma", "Naresh Bhargava", "Kailash Meena", "Om Prakash",
]


def phone():
    return f"{random.randint(6, 9)}{random.randint(0, 999999999):09d}"


def plate():
    return (
        f"RJ-{random.randint(1, 37):02d}-"
        f"{random.choice('ABCDEFGH')}{random.choice('ABCDEFGH')}-"
        f"{random.randint(1000, 9999)}"
    )


class Command(BaseCommand):
    help = "Seed Pilani<->Loharu stops/routes and cab bookings owned by testuser."

    def add_arguments(self, parser):
        parser.add_argument("--bookings", type=int, default=20,
                            help="Number of cab bookings to create (default 20).")
        parser.add_argument("--trips", type=int, default=10,
                            help="Number of Travellor trips on the two routes (default 10).")
        parser.add_argument("--seat-bookings", type=int, default=8,
                            help="Number of seat bookings on those trips for the user (default 8).")
        parser.add_argument("--drivers", type=int, default=4,
                            help="Number of drivers to run the trips (default 4).")
        parser.add_argument("--username", default="testuser",
                            help="Customer username to attach the bookings to.")
        parser.add_argument("--seed", type=int, default=None,
                            help="Seed the RNG for reproducible output.")
        parser.add_argument("--clear", action="store_true",
                            help="Delete this user's existing Pilani/Loharu cab bookings first.")

    def handle(self, *args, **opts):
        if opts["seed"] is not None:
            random.seed(opts["seed"])

        with transaction.atomic():
            customer = self._get_customer(opts["username"])
            stops = self._create_stops()
            routes = self._create_routes(stops)
            cars = self._create_cars()
            drivers = self._create_drivers(opts["drivers"])

            if opts["clear"]:
                self._clear(customer, stops, routes)

            trips = self._create_trips(opts["trips"], routes, drivers)
            n_seats = self._create_seat_bookings(
                opts["seat_bookings"], trips, customer)
            n_cab = self._create_cab_bookings(opts["bookings"], customer, stops, cars)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone:\n"
            f"  stops={len(stops)} routes=2 ({routes[0].name} / {routes[1].name})\n"
            f"  cars={len(cars)} drivers={len(drivers)} trips={len(trips)}\n"
            f"  seat_bookings={n_seats} cab_bookings={n_cab}\n"
            f"  -> customer '{customer.name}' ({customer.user.username})"
        ))

    def _clear(self, customer, stops, routes):
        n_seat, _ = Booking.objects.filter(
            customer=customer, trip__route__in=routes).delete()
        n_trip, _ = Travellor.objects.filter(route__in=routes).delete()
        n_cab, _ = CabBooking.objects.filter(
            customer=customer, pickup_location__in=[s.name for s in stops],
        ).delete()
        self.stdout.write(
            f"Cleared {n_cab} cab booking(s), {n_trip} trip(s), {n_seat} seat booking(s).")

    # ------------------------------------------------------------------ setup
    def _get_customer(self, username):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@example.com",
                      "first_name": "Test", "last_name": "User"},
        )
        if created:
            user.set_password("test1234")
            user.save()
            self.stdout.write(f"Created user '{username}' (password: test1234).")

        customer, created = Customer.objects.get_or_create(
            user=user,
            defaults={"name": (user.get_full_name() or username), "contact_number": phone()},
        )
        if created:
            self.stdout.write(f"Created customer profile for '{username}'.")
        return customer

    def _create_stops(self):
        self.stdout.write("Creating Pilani-Loharu stops...")
        stops = []
        for name, desc, _mins, _dist in PILANI_LOHARU_STOPS:
            stop, _ = Stop.objects.get_or_create(name=name, defaults={"description": desc})
            stops.append(stop)
        return stops

    def _create_routes(self, stops):
        self.stdout.write("Creating Pilani-Loharu routes...")
        legs = [(mins, dist) for _n, _d, mins, dist in PILANI_LOHARU_STOPS]

        forward = self._build_route(
            FORWARD_ROUTE_NAME,
            "Road route from BITS Pilani to Loharu Junction, via the Pilani-Loharu road.",
            stops, legs,
        )

        # Reversed: the leg cost of arriving at stop i going backwards is the
        # forward cost of the hop that originally led *into* stop i+1.
        rev_stops = list(reversed(stops))
        rev_legs = [(0, 0)] + list(reversed(legs[1:]))
        reverse = self._build_route(
            REVERSE_ROUTE_NAME,
            "Return road route from Loharu Junction to BITS Pilani.",
            rev_stops, rev_legs,
        )
        return [forward, reverse]

    def _build_route(self, name, description, stops, legs):
        route, created = Route.objects.get_or_create(
            name=name, defaults={"description": description})
        if not created:
            return route
        for order, (stop, (mins, dist)) in enumerate(zip(stops, legs), start=1):
            RouteStop.objects.create(
                route=route, stop=stop, order=order,
                minutes_from_previous_stop=mins,
                distance_from_previous_stop=dist,
            )
        return route

    def _create_cars(self):
        cars = []
        for model in CAR_MODELS:
            car = Car.objects.filter(name=model).first()
            if car is None:
                car = Car.objects.create(name=model, license_plate=plate())
            cars.append(car)
        return cars

    def _create_drivers(self, n):
        drivers = []
        for i in range(n):
            name = DRIVER_NAMES[i % len(DRIVER_NAMES)]
            first, last = name.split(" ", 1)
            user, created = User.objects.get_or_create(
                username=f"pilani_driver{i + 1}",
                defaults={"email": f"pilani_driver{i + 1}@example.com",
                          "first_name": first, "last_name": last},
            )
            if created:
                user.set_password("driver123")
                user.save()
            drivers.append(user)
        return drivers

    # ------------------------------------------------------------------ trips
    def _create_trips(self, n, routes, drivers):
        self.stdout.write(f"Creating {n} trips on the Pilani-Loharu routes...")
        now = timezone.now()
        trips = []
        for i in range(n):
            departure = now + timezone.timedelta(
                days=random.randint(-7, 14),
                hours=random.choice([6, 7, 8, 9, 14, 16, 17, 18, 19]),
                minutes=random.choice([0, 15, 30, 45]),
            )
            if departure < now:
                status = random.choice(["COMPLETED", "COMPLETED", "CANCELLED"])
            else:
                status = "SCHEDULED"
            cost = Decimal(str(round(random.uniform(2.0, 4.5), 2))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP)
            trips.append(Travellor.objects.create(
                driver=random.choice(drivers),
                # Alternate direction so both routes get trips.
                route=routes[i % len(routes)],
                departure_time=departure,
                vehicle_capacity=random.choice([6, 7, 12, 20, 30]),
                cost_per_km=cost,
                status=status,
            ))
        return trips

    def _create_seat_bookings(self, n, trips, customer):
        self.stdout.write(f"Creating {n} seat bookings for {customer.user.username}...")
        # Booking.save() runs full_clean(): stops must be on the trip's route,
        # start.order < end.order, and seats must fit segment availability.
        # Retry on ValidationError rather than pre-computing every constraint.
        bookable = [t for t in trips if t.status != "CANCELLED"]
        if not bookable:
            return 0
        created = 0
        attempts = 0
        while created < n and attempts < n * 10:
            attempts += 1
            trip = random.choice(bookable)
            route_stops = list(
                RouteStop.objects.filter(route=trip.route).order_by("order"))
            if len(route_stops) < 2:
                continue
            i = random.randint(0, len(route_stops) - 2)
            j = random.randint(i + 1, len(route_stops) - 1)
            try:
                Booking.objects.create(
                    trip=trip,
                    customer=customer,
                    start_stop=route_stops[i],
                    end_stop=route_stops[j],
                    seats=random.randint(1, 3),
                    status="COMPLETED" if trip.status == "COMPLETED" else "CONFIRMED",
                )
                created += 1
            except ValidationError:
                continue  # segment full or invalid combo; try another
        if created < n:
            self.stdout.write(self.style.WARNING(
                f"  only created {created}/{n} seat bookings (trips filled up)"))
        return created

    # -------------------------------------------------------------------- cab
    def _create_cab_bookings(self, n, customer, stops, cars):
        self.stdout.write(f"Creating {n} cab bookings for {customer.user.username}...")
        now = timezone.now()
        pilani_end = [s.name for s in stops[:3]]   # Pilani-side pickup points
        loharu_end = [s.name for s in stops[-2:]]  # Loharu-side pickup points

        for i in range(n):
            # Alternate direction so the user has both outbound and return rides.
            if i % 2 == 0:
                pickup, dropoff = random.choice(pilani_end), random.choice(loharu_end)
            else:
                pickup, dropoff = random.choice(loharu_end), random.choice(pilani_end)

            pickup_time = now + timezone.timedelta(
                days=random.randint(-14, 14),
                hours=random.randint(0, 23),
                minutes=random.choice([0, 15, 30, 45]),
            )

            if pickup_time < now:
                status = random.choice(["CONFIRMED", "CONFIRMED", "CANCELLED"])
            else:
                status = random.choice(["BOOKED", "BOOKED", "CONFIRMED"])

            assigned = status == "CONFIRMED"
            CabBooking.objects.create(
                customer=customer,
                pickup_location=pickup,
                dropoff_location=dropoff,
                pickup_time=pickup_time,
                people_count=random.randint(1, 4),
                status=status,
                driver_name=random.choice(DRIVER_NAMES) if assigned else None,
                driver_no=phone() if assigned else None,
                car=random.choice(cars) if assigned else None,
            )
        return n
