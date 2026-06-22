from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import GoogleLogin, BookTravellerView, SearchTravellersView, StopListView, UserBookingsView, CustomerSignupView
from .views import CabBookingView
from .views import manage_cars, add_car, vendor_cab_bookings, confirm_cab_booking
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # Auth
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('auth/google/', GoogleLogin.as_view(), name='google_login'),
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh_token'),
    path('customer-signup/', CustomerSignupView.as_view(), name='customer_signup'),
    path('book-traveller/', BookTravellerView.as_view(), name='book_traveller'),
    path('vendor-bookings/', views.vendor_bookings_view, name='vendor_bookings'),
    path('search-travellers/', SearchTravellersView.as_view(), name='search_travellers'),
    path('stops/', StopListView.as_view(), name='stop_list'),
    path('cab-bookings/', CabBookingView.as_view(), name='cab_bookings'),
    path('cars/', manage_cars, name='manage_cars'),
    path('cars/add/', add_car, name='add_car'),
    path('', vendor_cab_bookings, name='vendor_cab_bookings'),
    path('cab-bookings/<int:booking_id>/confirm/', confirm_cab_booking, name='confirm_cab_booking'),
    path('my-bookings/', UserBookingsView.as_view(), name='my_bookings'),

    # Traveller (Trip) Management
    path('travellors/add/', views.add_travellor, name='add_travellor'),
    path('travellors/bulk-add/', views.bulk_add_travellor, name='bulk_add_travellor'),
    path('travellors/', views.list_travellors, name='list_travellors'),
    path('travellors/<int:travellor_id>/edit/', views.edit_travellor, name='edit_travellor'),

    # Route Management
    path('routes/add/', views.manage_route, name='manage_route'),
    path('routes/', views.list_routes, name='list_routes'),
    path('routes/<int:route_id>/edit/', views.edit_route, name='edit_route'),

    # Stop Management
    path('stops/add/', views.create_stop, name='create_stop'),
]

