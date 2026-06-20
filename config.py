"""
Centralized configuration for the Starlink Constellation Monitor.

NIST SP 800-53 CM-2: Baseline Configuration
NIST SP 800-53 CM-3: Configuration Change Control
NIST SP 800-53 CM-6: Configuration Settings

All tunable parameters live here so the system's baseline configuration
is explicit, versioned, and auditable in a single location.
"""

CONFIG_VERSION = "1.0.0"

# === Satellite Tracking ===
DEFAULT_NUM_SATELLITES = 500
TLE_CACHE_MAX_AGE_HOURS = 2  # Respects Celestrak rate limit

# === Coverage / Orbital ===
MIN_ELEVATION_DEG = 25.0     # Minimum elevation angle for usable signal
EARTH_RADIUS_KM = 6371.0

# === Network Simulation ===
MAX_ISL_DISTANCE_KM = 1500.0  # Max inter-satellite laser link range
SPEED_OF_LIGHT_KM_MS = 299.792
UPLINK_DOWNLINK_LATENCY_MS = 10.0  # per hop, ground-to-satellite
ISL_HOP_LATENCY_MS = 5.0

# === Telemetry Simulation ===
BASELINE_SIGNAL_STRENGTH_DBM = -70.0
BASELINE_LATENCY_MS = 30.0
BASELINE_PACKET_LOSS_PCT = 0.1
SIGNAL_NOISE_STD = 2.0
DEFAULT_NUM_TELEMETRY_FRAMES = 200
DEFAULT_JAM_PROBABILITY = 0.1
DEFAULT_JAM_SEVERITY = 0.8

# === Anomaly Detection ===
SIGNAL_DEVIATION_MULTIPLIER = 2.0
LATENCY_DEVIATION_MULTIPLIER = 2.0
PACKET_LOSS_THRESHOLD = 0.3
FREQUENCY_DEVIATION_MHZ = 1.5

# === AWS / Alerting ===
SNS_TOPIC_NAME = "starlink-jamming-alerts"
DEFAULT_AWS_REGION = "us-east-1"

# === Audit Logging ===
AUDIT_LOG_DIR = "audit_logs"
AUDIT_LOG_FILE = "audit_logs/scan_audit.json"
NIST_CONTROLS_APPLIED = [
    "AU-2", "AU-3", "AU-6", "AU-9", "AU-12",  # Audit and Accountability
    "SI-3", "SI-4",                            # System and Information Integrity
    "IR-4", "IR-5", "IR-6",                     # Incident Response
    "SC-7", "SC-8",                             # System and Communications Protection
    "RA-3", "RA-5",                             # Risk Assessment
    "CM-2", "CM-3", "CM-6",                     # Configuration Management
]

# === Ground Stations ===
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


def print_config_summary():
    """
    Prints the active configuration baseline.
    NIST SP 800-53 CM-2: Baseline Configuration
    """
    print(f"\n=== Configuration Baseline (v{CONFIG_VERSION}) ===")
    print(f"Satellites tracked:     {DEFAULT_NUM_SATELLITES}")
    print(f"Min elevation angle:    {MIN_ELEVATION_DEG}°")
    print(f"Max ISL distance:       {MAX_ISL_DISTANCE_KM} km")
    print(f"Jam probability:        {DEFAULT_JAM_PROBABILITY * 100}%")
    print(f"Anomaly threshold:      {SIGNAL_DEVIATION_MULTIPLIER}σ")
    print(f"AWS region:             {DEFAULT_AWS_REGION}")
    print(f"Ground stations:        {len(DEFAULT_GROUND_STATIONS)}")
    print(f"NIST controls applied:  {len(NIST_CONTROLS_APPLIED)}")