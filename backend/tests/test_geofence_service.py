import pytest

from app.services.geofence import calculate_distance_meters, is_inside_geofence


def test_same_coordinates_have_zero_distance() -> None:
    distance = calculate_distance_meters(
        -6.7924,
        39.2083,
        -6.7924,
        39.2083,
    )

    assert distance == pytest.approx(0)


def test_nearby_location_is_inside_geofence() -> None:
    inside, distance = is_inside_geofence(
        church_latitude=-6.7924,
        church_longitude=39.2083,
        device_latitude=-6.7925,
        device_longitude=39.2084,
        radius_meters=100,
    )

    assert inside is True
    assert distance < 100


def test_distant_location_is_outside_geofence() -> None:
    inside, distance = is_inside_geofence(
        church_latitude=-6.7924,
        church_longitude=39.2083,
        device_latitude=-6.8000,
        device_longitude=39.2200,
        radius_meters=100,
    )

    assert inside is False
    assert distance > 100