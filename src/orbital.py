import numpy as np
from skyfield.api import load, wgs84
from datetime import datetime, timezone


# Minimum elevation angle for a satellite to be considered "visible" (degrees)
MIN_ELEVATION_DEG = 25.0

# Earth radius in km
EARTH_RADIUS_KM = 6371.0


def get_coverage_radius_km(alt_km: float, min_elevation_deg: float = MIN_ELEVATION_DEG) -> float:
    """
    Computes the ground coverage radius of a satellite at a given altitude.
    Based on the minimum elevation angle for usable signal.

    Returns the coverage radius in km.
    """
    min_elev_rad = np.radians(min_elevation_deg)
    earth_central_angle = np.arccos(
        np.cos(min_elev_rad) / (1 + alt_km / EARTH_RADIUS_KM)
    ) - min_elev_rad

    return EARTH_RADIUS_KM * earth_central_angle


def compute_footprints(positions: list[dict], min_elevation_deg: float = MIN_ELEVATION_DEG) -> list[dict]:
    """
    Computes coverage footprint radius for each satellite position.
    Adds 'coverage_radius_km' to each position dict.
    """
    for pos in positions:
        pos["coverage_radius_km"] = round(
            get_coverage_radius_km(pos["alt_km"], min_elevation_deg), 2
        )
    return positions


def is_visible(sat_lat: float, sat_lon: float, sat_alt_km: float,
               ground_lat: float, ground_lon: float,
               min_elevation_deg: float = MIN_ELEVATION_DEG) -> bool:
    """
    Returns True if a satellite is visible from a ground point
    above the minimum elevation angle.
    """
    ts = load.timescale()
    now = ts.now()

    ground = wgs84.latlon(ground_lat, ground_lon)

    # Use the coverage radius as a proxy for visibility
    coverage_radius_km = get_coverage_radius_km(sat_alt_km, min_elevation_deg)
    distance_km = haversine_km(sat_lat, sat_lon, ground_lat, ground_lon)

    return distance_km <= coverage_radius_km


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes the great-circle distance between two points on Earth in km.
    """
    R = EARTH_RADIUS_KM
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))

    return R * c


def find_best_satellite(ground_lat: float, ground_lon: float,
                        positions: list[dict]) -> dict | None:
    """
    Finds the best satellite to serve a ground point — the one with
    the smallest angular distance (closest to directly overhead).

    Returns the best satellite position dict, or None if none are visible.
    """
    best = None
    best_distance = float("inf")

    for pos in positions:
        if not is_visible(pos["lat"], pos["lon"], pos["alt_km"], ground_lat, ground_lon):
            continue

        distance = haversine_km(pos["lat"], pos["lon"], ground_lat, ground_lon)
        if distance < best_distance:
            best_distance = distance
            best = pos

    return best


def compute_handoffs(ground_stations: list[dict], positions: list[dict]) -> list[dict]:
    """
    For each ground station, finds the best serving satellite.
    Simulates handoff by tracking which satellite serves each station.

    ground_stations: [{"name": str, "lat": float, "lon": float}, ...]
    Returns: [{"station": str, "serving_satellite": str | None, "distance_km": float}, ...]
    """
    handoffs = []

    for station in ground_stations:
        best = find_best_satellite(station["lat"], station["lon"], positions)

        if best:
            distance = haversine_km(station["lat"], station["lon"], best["lat"], best["lon"])
            handoffs.append({
                "station": station["name"],
                "serving_satellite": best["name"],
                "satellite_lat": best["lat"],
                "satellite_lon": best["lon"],
                "satellite_alt_km": best["alt_km"],
                "coverage_radius_km": best.get("coverage_radius_km", 0),
                "distance_km": round(distance, 2),
                "status": "connected",
            })
        else:
            handoffs.append({
                "station": station["name"],
                "serving_satellite": None,
                "distance_km": None,
                "status": "no_coverage",
            })

    return handoffs


# Default ground stations for simulation
DEFAULT_GROUND_STATIONS = [
    {"name": "New York", "lat": 40.7128, "lon": -74.0060},
    {"name": "London", "lat": 51.5074, "lon": -0.1278},
    {"name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    {"name": "Sydney", "lat": -33.8688, "lon": 151.2093},
    {"name": "Kyiv", "lat": 50.4501, "lon": 30.5234},
    {"name": "São Paulo", "lat": -23.5505, "lon": -46.6333},
    {"name": "Dubai", "lat": 25.2048, "lon": 55.2708},
    {"name": "Singapore", "lat": 1.3521, "lon": 103.8198},
]