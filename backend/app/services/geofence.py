from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_METERS = 6_371_000


def calculate_distance_meters(
    latitude_one: float,
    longitude_one: float,
    latitude_two: float,
    longitude_two: float,
) -> float:
    """Calculate the distance between two GPS coordinates."""

    latitude_one_radians = radians(latitude_one)
    latitude_two_radians = radians(latitude_two)

    latitude_difference = radians(latitude_two - latitude_one)
    longitude_difference = radians(longitude_two - longitude_one)

    haversine_value = (
        sin(latitude_difference / 2) ** 2
        + cos(latitude_one_radians)
        * cos(latitude_two_radians)
        * sin(longitude_difference / 2) ** 2
    )

    central_angle = 2 * asin(sqrt(haversine_value))

    return EARTH_RADIUS_METERS * central_angle


def is_inside_geofence(
    church_latitude: float,
    church_longitude: float,
    device_latitude: float,
    device_longitude: float,
    radius_meters: int,
) -> tuple[bool, float]:
    """Return whether the device is inside the boundary and its distance."""

    distance_meters = calculate_distance_meters(
        church_latitude,
        church_longitude,
        device_latitude,
        device_longitude,
    )

    return distance_meters <= radius_meters, distance_meters