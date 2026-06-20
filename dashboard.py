from flask import Flask, render_template_string, jsonify
from skyfield.api import load
from src.tle_fetcher import get_satellite_positions
from src.orbital import compute_footprints, compute_handoffs, DEFAULT_GROUND_STATIONS
from src.telemetry import generate_telemetry_stream, frames_to_dicts
from src.anomaly import compute_baseline, detect_anomalies, summarize_detections
from src.network_sim import compute_isl_links, simulate_station_routing, summarize_network
import json

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Starlink Constellation Monitor</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #060b18; color: #e0e6f0; font-family: 'Courier New', monospace; }

        header {
            padding: 1.2rem 2rem;
            border-bottom: 1px solid #1a2540;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        header h1 { font-size: 1.2rem; color: #00d4ff; letter-spacing: 0.05em; }
        header .subtitle { font-size: 0.75rem; color: #3a5070; margin-top: 0.2rem; }

        .stats {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 1px;
            background: #1a2540;
            border-bottom: 1px solid #1a2540;
        }

        .stat {
            background: #060b18;
            padding: 1rem 1.5rem;
        }

        .stat .label { font-size: 0.65rem; color: #3a5070; text-transform: uppercase; letter-spacing: 0.1em; }
        .stat .value { font-size: 1.5rem; font-weight: bold; margin-top: 0.3rem; }
        .stat.satellites .value { color: #00d4ff; }
        .stat.links .value { color: #7b61ff; }
        .stat.stations .value { color: #2ed573; }
        .stat.jammed .value { color: #ff4757; }
        .stat.detection .value { color: #ffa502; }

        .main {
            display: grid;
            grid-template-columns: 1fr 340px;
            height: calc(100vh - 130px);
        }

        #globe { width: 100%; height: 100%; }

        .sidebar {
            background: #080d1c;
            border-left: 1px solid #1a2540;
            overflow-y: auto;
            padding: 1rem;
        }

        .section-title {
            font-size: 0.65rem;
            color: #3a5070;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin: 1rem 0 0.5rem;
            padding-bottom: 0.3rem;
            border-bottom: 1px solid #1a2540;
        }

        .station-card {
            background: #0f1628;
            border: 1px solid #1a2540;
            border-radius: 6px;
            padding: 0.7rem;
            margin-bottom: 0.5rem;
            font-size: 0.8rem;
        }

        .station-card .name { color: #00d4ff; font-weight: bold; margin-bottom: 0.3rem; }
        .station-card .sat { color: #7b61ff; font-size: 0.75rem; }
        .station-card .dist { color: #3a5070; font-size: 0.7rem; margin-top: 0.2rem; }

        .badge {
            display: inline-block;
            padding: 0.1rem 0.4rem;
            border-radius: 3px;
            font-size: 0.65rem;
            font-weight: bold;
            float: right;
        }
        .badge.connected { background: #2ed57320; color: #2ed573; border: 1px solid #2ed57340; }
        .badge.no_coverage { background: #ff475720; color: #ff4757; border: 1px solid #ff475740; }

        .alert-card {
            background: #1a0a0a;
            border: 1px solid #ff475740;
            border-radius: 6px;
            padding: 0.7rem;
            margin-bottom: 0.5rem;
            font-size: 0.75rem;
        }

        .alert-card .sat { color: #ff4757; font-weight: bold; }
        .alert-card .station { color: #ffa502; }
        .alert-card .score { color: #ff4757; float: right; font-size: 0.7rem; }

        .route-card {
            background: #0f1628;
            border: 1px solid #1a2540;
            border-radius: 6px;
            padding: 0.7rem;
            margin-bottom: 0.5rem;
            font-size: 0.75rem;
        }

        .route-card .pair { color: #00d4ff; font-weight: bold; margin-bottom: 0.2rem; }
        .route-card .hops { color: #7b61ff; }
        .route-card .latency { color: #2ed573; float: right; }

        .refresh-btn {
            background: none;
            border: 1px solid #1a2540;
            color: #3a5070;
            padding: 0.3rem 0.8rem;
            border-radius: 4px;
            cursor: pointer;
            font-family: inherit;
            font-size: 0.75rem;
        }
        .refresh-btn:hover { border-color: #00d4ff; color: #00d4ff; }
    </style>
</head>
<body>
    <header>
        <div>
            <h1>⚡ Starlink Constellation Monitor</h1>
            <div class="subtitle">Real-time orbital tracking · ISL mesh routing · Jamming detection</div>
        </div>
        <button class="refresh-btn" onclick="location.reload()">↻ Refresh</button>
    </header>

    <div class="stats">
        <div class="stat satellites">
            <div class="label">Satellites Tracked</div>
            <div class="value">{{ stats.satellites }}</div>
        </div>
        <div class="stat links">
            <div class="label">ISL Links</div>
            <div class="value">{{ stats.isl_links }}</div>
        </div>
        <div class="stat stations">
            <div class="label">Ground Stations</div>
            <div class="value">{{ stats.connected_stations }}</div>
        </div>
        <div class="stat jammed">
            <div class="label">Jamming Alerts</div>
            <div class="value">{{ stats.jamming_alerts }}</div>
        </div>
        <div class="stat detection">
            <div class="label">Detection Rate</div>
            <div class="value">{{ stats.detection_rate }}%</div>
        </div>
    </div>

    <div class="main">
        <div id="globe"></div>
        <div class="sidebar">
            <div class="section-title">Ground Stations</div>
            {% for h in handoffs %}
            <div class="station-card">
                <span class="badge {{ h.status }}">{{ h.status.replace('_', ' ').upper() }}</span>
                <div class="name">{{ h.station }}</div>
                {% if h.serving_satellite %}
                <div class="sat">↑ {{ h.serving_satellite }}</div>
                <div class="dist">{{ h.distance_km }} km away</div>
                {% endif %}
            </div>
            {% endfor %}

            <div class="section-title">Jamming Alerts</div>
            {% if alerts %}
                {% for a in alerts[:8] %}
                <div class="alert-card">
                    <span class="score">score: {{ a.anomaly_score }}</span>
                    <div class="sat">🚨 {{ a.satellite_name }}</div>
                    <div class="station">Station: {{ a.station_name }}</div>
                    <div style="color:#3a5070;font-size:0.7rem;margin-top:0.2rem">
                        Signal: {{ a.signal_strength_dbm }} dBm | Latency: {{ a.latency_ms }}ms
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div style="color:#3a5070;font-size:0.8rem;padding:0.5rem">No jamming detected</div>
            {% endif %}

            <div class="section-title">Routing Table</div>
            {% for r in routes[:6] %}
            <div class="route-card">
                <span class="latency">{{ r.estimated_latency_ms }}ms</span>
                <div class="pair">{{ r.from_station }} → {{ r.to_station }}</div>
                <div class="hops">{{ r.hops }} hops · {{ r.status }}</div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        const data = {{ globe_data | safe }};

        const layout = {
            paper_bgcolor: '#060b18',
            plot_bgcolor: '#060b18',
            margin: { l: 0, r: 0, t: 0, b: 0 },
            geo: {
                showland: true,
                landcolor: '#0d1829',
                showocean: true,
                oceancolor: '#060d1a',
                showlakes: false,
                showcountries: true,
                countrycolor: '#1a2540',
                showcoastlines: true,
                coastlinecolor: '#1e3050',
                bgcolor: '#060b18',
                projection: { type: 'orthographic', rotation: { lon: 0, lat: 20, roll: 0 } },
                lonaxis: { showgrid: true, gridcolor: '#0d1829', gridwidth: 0.5 },
                lataxis: { showgrid: true, gridcolor: '#0d1829', gridwidth: 0.5 },
            },
            legend: {
                bgcolor: '#080d1c',
                bordercolor: '#1a2540',
                borderwidth: 1,
                font: { color: '#3a5070', size: 10 },
                x: 0.01, y: 0.99,
            }
        };

        Plotly.newPlot('globe', data, layout, { responsive: true, displayModeBar: false });
    </script>
</body>
</html>
"""


def build_globe_data(positions, handoffs, alerts_dict, links):
    traces = []

    # Satellites
    sat_lats = [p["lat"] for p in positions]
    sat_lons = [p["lon"] for p in positions]
    sat_names = [p["name"] for p in positions]
    sat_alts = [round(p["alt_km"], 1) for p in positions]

    traces.append({
        "type": "scattergeo",
        "lat": sat_lats,
        "lon": sat_lons,
        "mode": "markers",
        "name": "Starlink Satellites",
        "marker": {"size": 3, "color": "#00d4ff", "opacity": 0.7},
        "text": [f"{n}<br>{a} km" for n, a in zip(sat_names, sat_alts)],
        "hoverinfo": "text",
    })

    # Ground stations
    gs_lats = [gs["lat"] for gs in DEFAULT_GROUND_STATIONS]
    gs_lons = [gs["lon"] for gs in DEFAULT_GROUND_STATIONS]
    gs_names = [gs["name"] for gs in DEFAULT_GROUND_STATIONS]

    traces.append({
        "type": "scattergeo",
        "lat": gs_lats,
        "lon": gs_lons,
        "mode": "markers+text",
        "name": "Ground Stations",
        "marker": {"size": 8, "color": "#2ed573", "symbol": "triangle-up"},
        "text": gs_names,
        "textposition": "top center",
        "textfont": {"size": 9, "color": "#2ed573"},
        "hoverinfo": "text",
    })

    # ISL links (sample 50 for performance)
    for link in links[:50]:
        sat_a = next((p for p in positions if p["name"] == link["sat_a"]), None)
        sat_b = next((p for p in positions if p["name"] == link["sat_b"]), None)
        if sat_a and sat_b:
            traces.append({
                "type": "scattergeo",
                "lat": [sat_a["lat"], sat_b["lat"], None],
                "lon": [sat_a["lon"], sat_b["lon"], None],
                "mode": "lines",
                "line": {"width": 0.4, "color": "#7b61ff"},
                "opacity": 0.3,
                "showlegend": False,
                "hoverinfo": "skip",
            })

    # Jamming alerts
    if alerts_dict:
        alert_lats = [a["lat"] for a in alerts_dict if a.get("lat")]
        alert_lons = [a["lon"] for a in alerts_dict if a.get("lon")]
        alert_names = [a["satellite_name"] for a in alerts_dict if a.get("lat")]

        if alert_lats:
            traces.append({
                "type": "scattergeo",
                "lat": alert_lats,
                "lon": alert_lons,
                "mode": "markers",
                "name": "Jamming Detected",
                "marker": {"size": 8, "color": "#ff4757", "symbol": "x"},
                "text": alert_names,
                "hoverinfo": "text",
            })

    return traces


@app.route("/")
def index():
    sats = load.tle_file("gp.php")
    positions = get_satellite_positions(sats, 500)
    positions = compute_footprints(positions)
    handoffs = compute_handoffs(DEFAULT_GROUND_STATIONS, positions)
    links = compute_isl_links(positions)
    routes = simulate_station_routing(handoffs, positions, links)

    frames = generate_telemetry_stream(handoffs, num_frames=200, jam_probability=0.1)
    baseline = compute_baseline(frames)
    flagged = detect_anomalies(frames, baseline)
    detection_summary = summarize_detections(frames, flagged)

    # Build position lookup for flagged satellites
    pos_lookup = {p["name"]: p for p in positions}
    alerts_with_pos = []
    for f in flagged:
        entry = frames_to_dicts([f])[0]
        pos = pos_lookup.get(f.satellite_name, {})
        entry["lat"] = pos.get("lat")
        entry["lon"] = pos.get("lon")
        alerts_with_pos.append(entry)

    connected_stations = sum(1 for h in handoffs if h["status"] == "connected")

    stats = {
        "satellites": len(positions),
        "isl_links": len(links),
        "connected_stations": connected_stations,
        "jamming_alerts": len(flagged),
        "detection_rate": detection_summary["detection_rate_pct"],
    }

    globe_data = build_globe_data(positions, handoffs, alerts_with_pos, links)

    return render_template_string(
        HTML,
        stats=stats,
        handoffs=handoffs,
        alerts=alerts_with_pos,
        routes=routes[:10],
        globe_data=json.dumps(globe_data),
    )


if __name__ == "__main__":
    print("[*] Loading Starlink TLE data...")
    app.run(host="127.0.0.1", port=8050, debug=False)