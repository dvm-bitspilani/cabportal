# API Documentation

This document provides documentation for all the API endpoints in the Cab Portal application.

## Authentication

The API uses **JWT (SimpleJWT)**. Obtain an `access`/`refresh` token pair via one of
the login endpoints below, then send `Authorization: Bearer <access>` on every
endpoint marked `IsAuthenticated`. When the access token expires, exchange the
refresh token at `/auth/refresh/` for a new access token.

> **User provisioning:** There is no self-serve registration API. Users are created
> by an administrator through the Django admin or `python manage.py createsuperuser`
> (Google Login also auto-creates a user on first sign-in). Passwords are stored
> hashed using Django's default PBKDF2 hasher.

### Username / Password Login

*   **URL**: `/auth/login/`
*   **Method**: `POST`
*   **Description**: Authenticates an existing user with their username and password and returns a JWT access and refresh token pair.
*   **Permissions**: None
*   **Request Body**:
    *   `username` (string, required)
    *   `password` (string, required)
    ```json
    {
        "username": "ashutosh",
        "password": "your_password"
    }
    ```
*   **Success Response (200 OK)**:
    ```json
    {
        "refresh": "...",
        "access": "..."
    }
    ```
*   **Error Response (401 Unauthorized)**:
    ```json
    {
        "detail": "No active account found with the given credentials"
    }
    ```

### Refresh Token

*   **URL**: `/auth/refresh/`
*   **Method**: `POST`
*   **Description**: Exchanges a valid refresh token for a new access token.
*   **Permissions**: None
*   **Request Body**:
    *   `refresh` (string, required)
    ```json
    {
        "refresh": "..."
    }
    ```
*   **Success Response (200 OK)**:
    ```json
    {
        "access": "..."
    }
    ```
*   **Error Response (401 Unauthorized)**:
    ```json
    {
        "detail": "Token is invalid or expired",
        "code": "token_not_valid"
    }
    ```

### Google Login

*   **URL**: `/auth/google/`
*   **Method**: `POST`
*   **Description**: Authenticates a user using a Google ID token. If the user does not exist, a new user is created. It returns a JWT access and refresh token.
*   **Permissions**: None
*   **Request Body**:
    *   `token` (string, required): The ID token obtained from Google after a successful sign-in.
    ```json
    {
        "token": "your_google_id_token"
    }
    ```
*   **Success Response (200 OK)**:
    *   `refresh` (string): A refresh token for obtaining new access tokens.
    *   `access` (string): An access token for authenticating subsequent requests.
    *   `customer` (object | null): The customer profile if it exists, otherwise `null`.
    ```json
    {
        "refresh": "...",
        "access": "...",
        "customer": {
            "name": "Ashutosh",
            "contact_number": "1234567890"
        }
    }
    ```
*   **Error Response (400 Bad Request)**:
    ```json
    {
        "error": "Google token is required"
    }
    ```
*   **Error Response (401 Unauthorized)**:
    ```json
    {
        "error": "Invalid Google token"
    }
    ```

#### Setting up Google Sign-In

The backend endpoint above already works — it only needs a valid `GOOGLE_CLIENT_ID`.
The frontend is responsible for the OAuth flow and posting the resulting ID token.

**1. Create an OAuth client in the Google Cloud Console**

1. Go to <https://console.cloud.google.com/> and create or select a project.
2. **APIs & Services → OAuth consent screen** → choose **External**, set the app
   name and support email. While the app is in "Testing", add your Google
   account(s) under **Test users**.
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
4. **Application type: Web application.**
    *   Under **Authorized JavaScript origins**, add the frontend origin(s), e.g.
        `http://localhost:3000` and your production domain.
    *   **Authorized redirect URIs** are only needed if the frontend uses the
        redirect/code flow. The Google Identity Services popup / ID-token flow
        needs only the JavaScript origin.
5. Copy the generated **Client ID** and set it as `GOOGLE_CLIENT_ID` in `.env`
   (see `.env.example`). Use the **same** Client ID in the frontend Google button
   config so the token's `aud` claim matches what the backend verifies.

**2. Sign-in flow (frontend → backend)**

1. The frontend loads Google Identity Services and renders the sign-in button
   configured with `client_id = GOOGLE_CLIENT_ID`.
2. On success Google returns a **credential (ID token, a JWT)**.
3. The frontend calls `POST /auth/google/` with `{ "token": "<id_token>" }`.
4. The backend verifies the token against `GOOGLE_CLIENT_ID`, gets-or-creates the
   `User`, and returns `{ access, refresh, customer }`.
5. If the user is new (`customer` is `null`), the frontend calls
   `POST /customer-signup/` with the `Bearer <access>` token to create the
   customer profile.

> A missing or mismatched `GOOGLE_CLIENT_ID` causes the endpoint to return
> `401 { "error": "Invalid Google token" }`.

---

## Customer

### Customer Signup

*   **URL**: `/customer-signup/`
*   **Method**: `POST`
*   **Description**: Creates a customer profile for an authenticated user. This endpoint should be used after a user has logged in with Google but before they have created a customer profile.
*   **Permissions**: `IsAuthenticated`
*   **Request Body**:
    *   `name` (string, required): The full name of the customer.
    *   `contact_number` (string, required): The contact number of the customer.
    ```json
    {
        "name": "Ashutosh",
        "contact_number": "1234567890"
    }
    ```
*   **Success Response (201 Created)**:
    *   Returns the created customer profile.
    ```json
    {
        "name": "Ashutosh",
        "contact_number": "1234567890"
    }
    ```
*   **Error Response (400 Bad Request)**:
    ```json
    {
        "error": "Customer profile already exists."
    }
    ```

---

## Bookings

### Book a Trip

*   **URL**: `/book-traveller/`
*   **Method**: `POST`
*   **Description**: Books a trip for the authenticated user. The user must have a customer profile.
*   **Permissions**: `IsAuthenticated`
*   **Request Body**:
    *   `trip` (integer, required): The ID of the `Travellor` (trip) to book.
    *   `start_stop` (integer, required): The ID of the `RouteStop` where the user will start the trip.
    *   `end_stop` (integer, required): The ID of the `RouteStop` where the user will end the trip.
    *   `seats` (integer, required): The number of seats to book.
    ```json
    {
        "trip": 1,
        "start_stop": 1,
        "end_stop": 2,
        "seats": 1
    }
    ```
*   **Success Response (201 Created)**:
    *   Returns a `Booking` object with the details of the new booking.
    ```json
    {
        "id": 1,
        "trip": 1,
        "customer": 1,
        "start_stop": 1,
        "end_stop": 2,
        "seats": 1,
        "status": "CONFIRMED",
        "booking_time": "2025-09-25T10:00:00Z"
    }
    ```
*   **Error Response (400 Bad Request)**:
    ```json
    {
        "error": "Not enough seats available. Only 2 seat(s) left for this segment."
    }
    ```

### View User Bookings

*   **URL**: `/my-bookings/`
*   **Method**: `GET`
*   **Description**: Retrieves a list of all bookings for the currently authenticated user.
*   **Permissions**: `IsAuthenticated`
*   **Success Response (200 OK)**:
    *   Returns a list of `BookingDetail` objects.
    ```json
    [
        {
            "id": 1,
            "trip": {
                "id": 1,
                "driver_name": "vendor_user",
                "route_name": "City Center to Airport",
                "departure_time": "2025-10-01T09:00:00Z",
                "vehicle_capacity": 10,
                "status": "SCHEDULED",
                "cost_per_km": "2.50",
                "price": "75.00",
                "route_stops": [
                    {
                        "id": 1,
                        "stop": {
                            "id": 1,
                            "name": "City Center",
                            "description": ""
                        },
                        "order": 1,
                        "minutes_from_previous_stop": 0,
                        "distance_from_previous_stop": 0,
                        "estimated_arrival_time": "2025-10-01T09:00:00Z"
                    }
                ]
            },
            "customer_name": "Ashutosh",
            "start_stop": {
                "id": 1,
                "name": "City Center",
                "description": ""
            },
            "end_stop": {
                "id": 2,
                "name": "Airport",
                "description": ""
            },
            "seats": 1,
            "status": "CONFIRMED",
            "booking_time": "2025-09-25T10:00:00Z",
            "estimated_departure": "2025-10-01T09:00:00Z",
            "estimated_arrival": "2025-10-01T09:30:00Z",
            "price": "75.00"
        }
    ]
    ```

---

## Travellers and Routes

### Search for Travellers

*   **URL**: `/search-travellers/`
*   **Method**: `GET`
*   **Description**: Searches for available travellers between two stops, optionally filtered by travel date.
*   **Permissions**: `IsAuthenticated`
*   **Query Parameters**:
    *   `start_stop_id` (integer, required): The ID of the start `Stop`.
    *   `end_stop_id` (integer, required): The ID of the end `Stop`.
    *   `date` (string, optional): Filter travellers departing on this date. Format: `YYYY-MM-DD` (e.g., `2025-10-01`).
*   **Success Response (200 OK)**:
    *   Returns a list of `Travellor` objects that match the search criteria.
    ```json
    [
        {
            "id": 1,
            "driver_name": "vendor_user",
            "route_name": "City Center to Airport",
            "departure_time": "2025-10-01T09:00:00Z",
            "vehicle_capacity": 10,
            "status": "SCHEDULED",
            "cost_per_km": "2.50",
            "price": "75.00",
            "route_stops": [
                {
                    "id": 1,
                    "stop": {
                        "id": 1,
                        "name": "City Center",
                        "description": ""
                    },
                    "order": 1,
                    "minutes_from_previous_stop": 0,
                    "distance_from_previous_stop": 0,
                    "estimated_arrival_time": "2025-10-01T09:00:00Z"
                }
            ],
            "departure_from_start": "2025-10-01T09:00:00Z",
            "arrival_at_end": "2025-10-01T09:30:00Z",
            "start_stop_id": 1,
            "end_stop_id": 2
        }
    ]
    ```

### List All Stops

*   **URL**: `/stops/`
*   **Method**: `GET`
*   **Description**: Retrieves a list of all stops.
*   **Permissions**: `IsAuthenticated`
*   **Success Response (200 OK)**:
    *   Returns a list of `Stop` objects.
    ```json
    [
        {
            "id": 1,
            "name": "City Center",
            "description": "Near the main post office"
        },
        {
            "id": 2,
            "name": "Airport",
            "description": ""
        }
    ]
    ```
---

## Vendor

### Vendor Bookings

*   **URL**: `/vendor-bookings/`
*   **Method**: `GET`
*   **Description**: This is a server-side rendered page that displays all bookings for the trips created by the logged-in vendor. It is not a REST API endpoint.
*   **Permissions**: `login_required`, `vendor_profile`

---

## Cab Bookings

These endpoints allow authenticated customers to create cab bookings and retrieve their cab booking history. Vendor-side confirmation is done via the server-rendered admin/vendor pages in the application (`/vendor-cab-bookings/`), not via these REST endpoints.

### Create a Cab Booking

*   **URL**: `/cab-bookings/`
*   **Method**: `POST`
*   **Description**: Create a new cab booking for the authenticated user. The user must have a `Customer` profile. The operation is performed inside a database transaction to reduce race conditions.
*   **Permissions**: `IsAuthenticated`
*   **Request Body** (JSON):
    *   `pickup_location` (string, required): Address or description of the pickup point.
    *   `dropoff_location` (string, required): Address or description of the dropoff point.
    *   `pickup_time` (string, required): ISO8601 datetime for when the user wants to be picked up (e.g. `"2025-10-01T09:30:00Z"`).
    *   `people_count` (integer, required): Number of passengers for this booking (must be >= 1).
    ```json
    {
        "pickup_location": "123 Main St, City Center",
        "dropoff_location": "Airport Terminal 1",
        "pickup_time": "2025-10-01T09:30:00Z",
        "people_count": 2
    }
    ```
*   **Success Response (201 Created)**:
    *   Returns the created `CabBooking` object. Fields explained below.
    ```json
    {
        "id": 1,
        "customer": 1,
        "people_count": 2,
        "pickup_location": "123 Main St, City Center",
        "dropoff_location": "Airport Terminal 1",
        "pickup_time": "2025-10-01T09:30:00Z",
        "status": "BOOKED",
        "booking_time": "2025-09-25T10:00:00Z",
        "driver_name": null,
        "driver_no": null
    }
    ```
    Fields:
    - `id` (integer): Booking id assigned by the server.
    - `customer` (integer): The `Customer` id who created the booking.
    - `car` (integer | null): The preferred `Car` id provided (or null if not provided).
    - `pickup_location` / `dropoff_location` (string): Addresses.
    - `pickup_time` (string): ISO8601 datetime of requested pickup.
    - `status` (string): One of `BOOKED`, `CONFIRMED`, `CANCELLED`.
    - `booking_time` (string): Server timestamp when booking was created.
    - `driver_name`, `driver_no` (string | null): Filled when vendor assigns driver details.

*   **Error Responses**:
    *   `400 Bad Request` - validation errors e.g., missing required fields or invalid datetime format:
    ```json
    {
        "pickup_time": ["This field is required."]
    }
    ```
    *   `401 Unauthorized` - when the user is not authenticated.

### List Current User's Cab Bookings

*   **URL**: `/cab-bookings/`
*   **Method**: `GET`
*   **Description**: Returns a list of cab bookings created by the currently authenticated user, ordered by newest first.
*   **Permissions**: `IsAuthenticated`
*   **Success Response (200 OK)**:
    *   Returns a list of detailed `CabBooking` objects. Example response shows `car` nested when available.
    ```json
    [
        {
            "id": 1,
            "customer": 1,
            "car": {
                "id": 2,
                "name": "Toyota Prius",
                "license_plate": "XYZ-1234"
            },
            "pickup_location": "123 Main St, City Center",
            "dropoff_location": "Airport Terminal 1",
            "pickup_time": "2025-10-01T09:30:00Z",
            "status": "CONFIRMED",
            "booking_time": "2025-09-25T10:00:00Z",
            "driver_name": "John Driver",
            "driver_no": "+911234567890"
        }
    ]
    ```

*   Notes:
    - Vendor confirmation (assignment of `car`, `driver_name`, `driver_no` and changing `status` to `CONFIRMED`) is performed in the server-rendered vendor tools (see `/vendor-cab-bookings/` and the confirm page at `/cab-bookings/<id>/confirm/`).

