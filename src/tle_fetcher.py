import requests
import os
from datetime import datetime, timezone
from skyfield.api import load, EarthSatellite


CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle"
TLE_CACHE_FILE = "starlink.tle"
CACHE_MAX_AGE_HOURS = 2  # Celestrak updates every 2 hours


def is_cache_valid() -> bool:
    """
    Returns True if the cached TLE file exists and is less than 2 hours old.
    Respects Celestrak's one-download-per-update policy.
    """
    if not os.path.exists(TLE_CACHE_FILE):
        return False

    age_seconds = (datetime.now(timezone.utc).timestamp() - os.path.getmtime(TLE_CACHE_FILE))
    age_hours = age_seconds / 3600

    return age_hours < CACHE_MAX_AGE_HOURS


def fetch_tle_data(force_refresh: bool = False) -> list:
    """
    Fetches Starlink TLE data from Celestrak or returns cached data.
    Respects Celestrak's rate limit — max one download per 2 hours.

    Returns a list of EarthSatellite objects.
    """
    ts = load.timescale()

    if not force_refresh and is_cache_valid():
        print(f"[TLE] Using cached data: {TLE_CACHE_FILE}")
        satellites = load.tle_file(TLE_CACHE_FILE)
        print(f"[TLE] Loaded {len(satellites)} Starlink satellites from cache")
        return satellites

    print(f"[TLE] Fetching fresh TLE data from Celestrak...")
    satellites = load.tle_file(CELESTRAK_URL, filename=TLE_CACHE_FILE)
    print(f"[TLE] Loaded {len(satellites)} Starlink satellites")

    return satellites


def get_satellite_positions(satellites: list, num_satellites: int = 200) -> list[dict]:
    """
    Computes current lat/lon/altitude for a subset of satellites.
    Limits to num_satellites for performance.

    Returns a list of dicts:
    {
        "name": str,
        "lat": float,
        "lon": float,
        "alt_km": float,
        "epoch": str,
    }
    """
    ts = load.timescale()
    now = ts.now()

    positions = []
    for sat in satellites[:num_satellites]:
        try:
            geocentric = sat.at(now)
            subpoint = geocentric.subpoint()

            positions.append({
                "name": sat.name,
                "lat": subpoint.latitude.degrees,
                "lon": subpoint.longitude.degrees,
                "alt_km": subpoint.elevation.km,
                "epoch": str(sat.epoch.utc_datetime()),
            })
        except Exception:
            continue

    return positions


def filter_active(satellites: list, min_alt_km: float = 300) -> list:
    """
    Filters satellites to only those currently above a minimum altitude.
    Removes decayed or recently launched satellites still raising orbit.
    """
    ts = load.timescale()
    now = ts.now()

    active = []
    for sat in satellites:
        try:
            geocentric = sat.at(now)
            subpoint = geocentric.subpoint()
            if subpoint.elevation.km >= min_alt_km:
                active.append(sat)
        except Exception:
            continue

    return active