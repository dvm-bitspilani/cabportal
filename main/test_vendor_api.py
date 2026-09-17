from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import Booking, CabBooking, Car, Customer, Route, RouteStop, Stop, Travellor, Vendor


class VendorApiTestCase(TestCase):
    def setUp(self):
        self.vendor_user = User.objects.create_user("vendor", password="secret")
        Vendor.objects.create(user=self.vendor_user, company_name="Ride Co")
        self.other_user = User.objects.create_user("other", password="secret")
        Vendor.objects.create(user=self.other_user, company_name="Other Co")
        self.customer_user = User.objects.create_user("customer", password="secret")
        self.customer = Customer.objects.create(user=self.customer_user, name="Rider", contact_number="999")
        self.client = APIClient()

    def login(self):
        response = self.client.post(reverse("vendor_api:login"), {"username": "vendor", "password": "secret"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return response

    def make_route(self):
        one = Stop.objects.create(name="One")
        two = Stop.objects.create(name="Two")
        route = Route.objects.create(name="One to Two")
        RouteStop.objects.create(route=route, stop=one, order=1, minutes_from_previous_stop=0, distance_from_previous_stop=0)
        RouteStop.objects.create(route=route, stop=two, order=2, minutes_from_previous_stop=10, distance_from_previous_stop=5)
        return route

    def test_login_is_vendor_only_and_refresh_works(self):
        response = self.login()
        self.assertEqual(response.data["vendor"]["company_name"], "Ride Co")
        refresh = self.client.post(reverse("vendor_api:refresh"), {"refresh": response.data["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, status.HTTP_200_OK)
        rejected = APIClient().post(reverse("vendor_api:login"), {"username": "customer", "password": "secret"}, format="json")
        self.assertEqual(rejected.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_vendor_permission_and_global_resources(self):
        self.assertEqual(self.client.get(reverse("vendor_api:stops")).status_code, status.HTTP_401_UNAUTHORIZED)
        self.login()
        created = self.client.post(reverse("vendor_api:stops"), {"name": "Global", "description": "Shared"}, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        other = APIClient(); other.force_authenticate(self.other_user)
        self.assertEqual(other.get(reverse("vendor_api:stops")).data["count"], 1)

    def test_route_validation_and_atomic_write(self):
        self.login()
        first = Stop.objects.create(name="First"); second = Stop.objects.create(name="Second")
        invalid = self.client.post(reverse("vendor_api:routes"), {"name": "Bad", "description": "", "stops": [
            {"stop_id": first.id, "order": 1, "minutes_from_previous_stop": 1, "distance_from_previous_stop": 0},
            {"stop_id": second.id, "order": 1, "minutes_from_previous_stop": 2, "distance_from_previous_stop": 2},
        ]}, format="json")
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Route.objects.filter(name="Bad").exists())
        valid = self.client.post(reverse("vendor_api:routes"), {"name": "Good", "description": "", "stops": [
            {"stop_id": first.id, "order": 1, "minutes_from_previous_stop": 0, "distance_from_previous_stop": 0},
            {"stop_id": second.id, "order": 2, "minutes_from_previous_stop": 2, "distance_from_previous_stop": 2},
        ]}, format="json")
        self.assertEqual(valid.status_code, status.HTTP_201_CREATED)

    def test_trip_and_booking_isolation_and_bulk_count(self):
        route = self.make_route()
        own = Travellor.objects.create(driver=self.vendor_user, route=route, departure_time=timezone.now(), vehicle_capacity=4, cost_per_km=10)
        other = Travellor.objects.create(driver=self.other_user, route=route, departure_time=timezone.now(), vehicle_capacity=4, cost_per_km=10)
        Booking.objects.create(trip=own, customer=self.customer, start_stop=route.routestop_set.get(order=1), end_stop=route.routestop_set.get(order=2), seats=1)
        self.login()
        trips = self.client.get(reverse("vendor_api:trips"))
        self.assertEqual([x["id"] for x in trips.data["results"]], [own.id])
        self.assertEqual(self.client.get(reverse("vendor_api:trip-detail", args=[other.id])).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(reverse("vendor_api:bookings")).data["count"], 1)
        bulk = self.client.post(reverse("vendor_api:trips-bulk"), {"route": route.id, "departure_time": "09:30", "month": 2, "year": 2028, "vehicle_capacity": 5, "cost_per_km": "12.50"}, format="json")
        self.assertEqual(bulk.status_code, status.HTTP_201_CREATED)
        self.assertEqual(bulk.data["created_count"], 29)

    def test_cab_confirmation_cannot_be_overwritten(self):
        car = Car.objects.create(name="Sedan", license_plate="RJ01AA1")
        booking = CabBooking.objects.create(customer=self.customer, pickup_location="A", dropoff_location="B", pickup_time=timezone.now(), people_count=2)
        self.login()
        url = reverse("vendor_api:cab-booking-confirm", args=[booking.id])
        payload = {"car": car.id, "driver_name": "Driver One", "driver_no": "12345"}
        self.assertEqual(self.client.post(url, payload, format="json").status_code, status.HTTP_200_OK)
        payload["driver_name"] = "Driver Two"
        self.assertEqual(self.client.post(url, payload, format="json").status_code, status.HTTP_409_CONFLICT)
        booking.refresh_from_db()
        self.assertEqual(booking.driver_name, "Driver One")
