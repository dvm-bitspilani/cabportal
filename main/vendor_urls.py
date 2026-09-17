from django.urls import path

from . import vendor_views


app_name = "vendor_api"

urlpatterns = [
    path("auth/login", vendor_views.VendorLoginView.as_view(), name="login"),
    path("auth/refresh", vendor_views.VendorRefreshView.as_view(), name="refresh"),
    path("me", vendor_views.MeView.as_view(), name="me"),
    path("stops", vendor_views.StopListCreateView.as_view(), name="stops"),
    path("routes", vendor_views.RouteListCreateView.as_view(), name="routes"),
    path("routes/<int:pk>", vendor_views.RouteDetailView.as_view(), name="route-detail"),
    path("trips", vendor_views.TripListCreateView.as_view(), name="trips"),
    path("trips/bulk", vendor_views.BulkTripView.as_view(), name="trips-bulk"),
    path("trips/<int:pk>", vendor_views.TripDetailView.as_view(), name="trip-detail"),
    path("bookings", vendor_views.BookingListView.as_view(), name="bookings"),
    path("cars", vendor_views.CarListCreateView.as_view(), name="cars"),
    path("cab-bookings", vendor_views.CabBookingListView.as_view(), name="cab-bookings"),
    path("cab-bookings/<int:pk>/confirm", vendor_views.CabBookingConfirmView.as_view(), name="cab-booking-confirm"),
]
