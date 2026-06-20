import argparse
from skyfield.api import load
from src.tle_fetcher import fetch_tle_data, get_satellite_positions
from src.orbital import compute_footprints, compute_handoffs, DEFAULT_GROUND_STATIONS
from src.telemetry import generate_telemetry_stream
from src.anomaly import compute_baseline, detect_anomalies, summarize_detections
from src.network_sim import compute_isl_links, simulate_station_routing, summarize_network
from src.audit_logger import log_scan, print_audit_summary
from src.alert import create_topic, send_jamming_alert, setup_alerts


def run_scan(
    num_satellites: int = 500,
    jam_probability: float = 0.1,
    verbose: bool = False,
    topic_arn: str = None,
):
    """
    Full pipeline scan — 8 steps with NIST SP 800-53 compliance.
    """

    print("\n=== Starlink Constellation Monitor ===")
    print(f"Satellites: {num_satellites} | Jam probability: {jam_probability * 100}%\n")

    # Step 1: Load TLE data
    print("[1/8] Loading TLE data...")
    try:
        satellites = fetch_tle_data()
    except Exception:
        print("    [!] Fetch failed — falling back to cached file")
        satellites = load.tle_file("gp.php")
    print(f"    Loaded {len(satellites)} satellites")

    # Step 2: Compute positions
    print(f"[2/8] Computing positions for {num_satellites} satellites...")
    positions = get_satellite_positions(satellites, num_satellites)
    print(f"    {len(positions)} positions computed")

    # Step 3: Coverage footprints
    print("[3/8] Computing coverage footprints...")
    positions = compute_footprints(positions)
    avg_coverage = sum(p["coverage_radius_km"] for p in positions) / len(positions)
    print(f"    Average coverage radius: {round(avg_coverage, 1)} km")

    # Step 4: Ground station handoffs
    print("[4/8] Simulating ground station handoffs...")
    handoffs = compute_handoffs(DEFAULT_GROUND_STATIONS, positions)
    connected = [h for h in handoffs if h["status"] == "connected"]
    print(f"    {len(connected)}/{len(handoffs)} stations connected")
    for h in handoffs:
        status = "✅" if h["status"] == "connected" else "❌"
        sat = h["serving_satellite"] or "none"
        print(f"    {status} {h['station']} → {sat}")

    # Step 5: ISL mesh + routing
    print("[5/8] Building ISL mesh and computing routes...")
    links = compute_isl_links(positions)
    routes = simulate_station_routing(handoffs, positions, links)
    summarize_network(positions, links, routes)

    if verbose:
        print("\n    Route details:")
        for r in routes:
            if r["status"] == "routed":
                print(f"    {r['from_station']} → {r['to_station']}: {r['hops']} hops, {r['estimated_latency_ms']}ms")

    # Step 6: Telemetry stream
    print("\n[6/8] Generating telemetry stream...")
    frames = generate_telemetry_stream(handoffs, num_frames=200, jam_probability=jam_probability)

    # Step 7: Anomaly/jamming detection
    print("[7/8] Running jamming detection...")
    baseline = compute_baseline(frames)
    flagged = detect_anomalies(frames, baseline)
    detection_summary = summarize_detections(frames, flagged)

    if flagged:
        print(f"\n🚨 Jamming alerts:")
        for f in flagged[:5]:
            print(f"    {f.satellite_name} @ {f.station_name} | signal={round(f.signal_strength_dbm, 1)} dBm | score={f.anomaly_score}")

    # Step 8: Audit logging (NIST SP 800-53 AU)
    print("\n[8/8] Writing audit log...")
    scan_id = log_scan(
        positions=positions,
        handoffs=handoffs,
        links=links,
        routes=routes,
        frames=frames,
        flagged=flagged,
        detection_summary=detection_summary,
    )
    print_audit_summary(scan_id)

    # SNS alert if jamming detected and topic configured (NIST SP 800-53 IR)
    if flagged and topic_arn:
        send_jamming_alert(topic_arn, flagged, scan_id)

    print("\n=== Scan Complete ===")
    return {
        "positions": positions,
        "handoffs": handoffs,
        "links": links,
        "routes": routes,
        "frames": frames,
        "flagged": flagged,
        "summary": detection_summary,
        "scan_id": scan_id,
    }


def main():
    parser = argparse.ArgumentParser(description="Starlink Constellation Monitor")
    parser.add_argument(
        "--satellites",
        type=int,
        default=500,
        help="Number of satellites to track (default: 500)",
    )
    parser.add_argument(
        "--jam-probability",
        type=float,
        default=0.1,
        help="Simulated jamming probability 0.0-1.0 (default: 0.1)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed route information",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Launch the web dashboard after scan",
    )
    parser.add_argument(
        "--email",
        type=str,
        help="Email address for SNS jamming alerts",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Create SNS topic and subscribe email (run once)",
    )
    args = parser.parse_args()

    topic_arn = None

    if args.setup and args.email:
        topic_arn = setup_alerts(args.email)
    elif args.email:
        topic_arn = create_topic()

    results = run_scan(
        num_satellites=args.satellites,
        jam_probability=args.jam_probability,
        verbose=args.verbose,
        topic_arn=topic_arn,
    )

    if args.dashboard:
        print("\n[*] Launching dashboard at http://127.0.0.1:8050")
        import subprocess
        import webbrowser
        import time
        subprocess.Popen(["python", "dashboard.py"])
        time.sleep(2)
        webbrowser.open("http://127.0.0.1:8050")


if __name__ == "__main__":
    main