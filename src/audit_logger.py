import json
import os
from datetime import datetime, timezone
from src.telemetry import frames_to_dicts


AUDIT_LOG_DIR = "audit_logs"
AUDIT_LOG_FILE = os.path.join(AUDIT_LOG_DIR, "scan_audit.json")


def ensure_log_dir():
    """
    Creates the audit log directory if it doesn't exist.
    NIST SP 800-53 AU-9: Protection of Audit Information
    """
    os.makedirs(AUDIT_LOG_DIR, exist_ok=True)


def load_existing_logs() -> list:
    """
    Loads existing audit log entries from disk.
    """
    if not os.path.exists(AUDIT_LOG_FILE):
        return []

    with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def log_scan(
    positions: list[dict],
    handoffs: list[dict],
    links: list[dict],
    routes: list[dict],
    frames: list,
    flagged: list,
    detection_summary: dict,
) -> str:
    """
    Persists a full scan result to the audit log.
    NIST SP 800-53 AU-2: Event Logging
    NIST SP 800-53 AU-3: Content of Audit Records
    NIST SP 800-53 AU-12: Audit Record Generation

    Returns the scan ID.
    """
    ensure_log_dir()

    scan_id = f"scan_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    timestamp = datetime.now(timezone.utc).isoformat()

    audit_entry = {
        "scan_id": scan_id,
        "timestamp": timestamp,
        "nist_controls": ["AU-2", "AU-3", "AU-12", "SI-3", "IR-5"],
        "summary": {
            "satellites_tracked": len(positions),
            "isl_links": len(links),
            "ground_stations_total": len(handoffs),
            "ground_stations_connected": sum(1 for h in handoffs if h["status"] == "connected"),
            "routes_computed": len(routes),
            "telemetry_frames": len(frames),
            "jamming_alerts": len(flagged),
            "detection_rate_pct": detection_summary.get("detection_rate_pct", 0),
            "false_positive_rate_pct": detection_summary.get("false_positive_rate_pct", 0),
        },
        "ground_station_status": [
            {
                "station": h["station"],
                "status": h["status"],
                "serving_satellite": h.get("serving_satellite"),
                "distance_km": h.get("distance_km"),
            }
            for h in handoffs
        ],
        "routing_table": [
            {
                "from": r["from_station"],
                "to": r["to_station"],
                "hops": r.get("hops"),
                "latency_ms": r.get("estimated_latency_ms"),
                "status": r["status"],
            }
            for r in routes
        ],
        "jamming_events": [
            {
                "satellite": f.satellite_name,
                "station": f.station_name,
                "signal_strength_dbm": round(f.signal_strength_dbm, 2),
                "latency_ms": round(f.latency_ms, 2),
                "packet_loss_pct": round(f.packet_loss_pct, 4),
                "anomaly_score": f.anomaly_score,
                "timestamp": f.timestamp,
            }
            for f in flagged
        ],
    }

    # Append to existing logs
    logs = load_existing_logs()
    logs.append(audit_entry)

    with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, default=str)

    print(f"[Audit] Scan logged: {scan_id} → {AUDIT_LOG_FILE}")
    return scan_id


def get_recent_scans(limit: int = 10) -> list[dict]:
    """
    Returns the most recent N scan audit entries.
    NIST SP 800-53 AU-6: Audit Record Review
    """
    logs = load_existing_logs()
    return logs[-limit:]


def print_audit_summary(scan_id: str):
    """
    Prints a human-readable summary of a specific scan.
    """
    logs = load_existing_logs()
    entry = next((l for l in logs if l["scan_id"] == scan_id), None)

    if not entry:
        print(f"[Audit] Scan {scan_id} not found")
        return

    s = entry["summary"]
    print(f"\n=== Audit Record: {scan_id} ===")
    print(f"Timestamp:           {entry['timestamp']}")
    print(f"NIST Controls:       {', '.join(entry['nist_controls'])}")
    print(f"Satellites tracked:  {s['satellites_tracked']}")
    print(f"ISL links:           {s['isl_links']}")
    print(f"Stations connected:  {s['ground_stations_connected']}/{s['ground_stations_total']}")
    print(f"Telemetry frames:    {s['telemetry_frames']}")
    print(f"Jamming alerts:      {s['jamming_alerts']}")
    print(f"Detection rate:      {s['detection_rate_pct']}%")
    print(f"False positive rate: {s['false_positive_rate_pct']}%")