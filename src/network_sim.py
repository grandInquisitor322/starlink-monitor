import numpy as np
from src.orbital import haversine_km


# Maximum inter-satellite link distance in km (laser ISL range)
MAX_ISL_DISTANCE_KM = 1500.0

# Speed of light in km/ms for latency calculations
SPEED_OF_LIGHT_KM_MS = 299.792


def compute_isl_links(positions: list[dict], max_distance_km: float = MAX_ISL_DISTANCE_KM) -> list[dict]:
    """
    Computes inter-satellite links (ISLs) between satellites within range.
    Simulates Starlink's laser-based ISL mesh network.

    Returns a list of links:
    [{"sat_a": str, "sat_b": str, "distance_km": float, "latency_ms": float}, ...]
    """
    links = []
    n = len(positions)

    for i in range(n):
        for j in range(i + 1, n):
            sat_a = positions[i]
            sat_b = positions[j]

            distance = haversine_km(
                sat_a["lat"], sat_a["lon"],
                sat_b["lat"], sat_b["lon"]
            )

            if distance <= max_distance_km:
                latency_ms = (distance / SPEED_OF_LIGHT_KM_MS) * 2  # round trip
                links.append({
                    "sat_a": sat_a["name"],
                    "sat_b": sat_b["name"],
                    "distance_km": round(distance, 2),
                    "latency_ms": round(latency_ms, 3),
                })

    return links


def build_adjacency(positions: list[dict], links: list[dict]) -> dict:
    """
    Builds an adjacency map for the satellite mesh network.
    {satellite_name: [neighbor_name, ...]}
    """
    adjacency = {pos["name"]: [] for pos in positions}

    for link in links:
        adjacency[link["sat_a"]].append(link["sat_b"])
        adjacency[link["sat_b"]].append(link["sat_a"])

    return adjacency


def find_route(source: str, destination: str, adjacency: dict) -> list[str] | None:
    """
    Finds the shortest hop route between two satellites using BFS.
    Returns the route as a list of satellite names, or None if unreachable.
    """
    if source == destination:
        return [source]

    if source not in adjacency or destination not in adjacency:
        return None

    visited = {source}
    queue = [[source]]

    while queue:
        path = queue.pop(0)
        current = path[-1]

        for neighbor in adjacency.get(current, []):
            if neighbor == destination:
                return path + [neighbor]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(path + [neighbor])

    return None


def simulate_station_routing(handoffs: list[dict], positions: list[dict], links: list[dict]) -> list[dict]:
    """
    Simulates routing between pairs of ground stations through the satellite mesh.
    For each pair of connected stations, finds the satellite-to-satellite route.

    Returns routing results:
    [{"from_station": str, "to_station": str, "route": list, "hops": int,
      "estimated_latency_ms": float, "status": str}, ...]
    """
    adjacency = build_adjacency(positions, links)

    connected = {h["station"]: h["serving_satellite"] for h in handoffs if h["status"] == "connected"}
    station_names = list(connected.keys())

    routes = []

    for i in range(len(station_names)):
        for j in range(i + 1, len(station_names)):
            src_station = station_names[i]
            dst_station = station_names[j]

            src_sat = connected[src_station]
            dst_sat = connected[dst_station]

            if src_sat == dst_sat:
                routes.append({
                    "from_station": src_station,
                    "to_station": dst_station,
                    "route": [src_sat],
                    "hops": 0,
                    "estimated_latency_ms": 20.0,
                    "status": "same_satellite",
                })
                continue

            route = find_route(src_sat, dst_sat, adjacency)

            if route:
                # Estimate latency: uplink (10ms) + ISL hops + downlink (10ms)
                hop_latency = (len(route) - 1) * 5.0
                estimated_latency = 20.0 + hop_latency
                routes.append({
                    "from_station": src_station,
                    "to_station": dst_station,
                    "route": route,
                    "hops": len(route) - 1,
                    "estimated_latency_ms": round(estimated_latency, 2),
                    "status": "routed",
                })
            else:
                routes.append({
                    "from_station": src_station,
                    "to_station": dst_station,
                    "route": [],
                    "hops": None,
                    "estimated_latency_ms": None,
                    "status": "unreachable",
                })

    return routes


def summarize_network(positions: list[dict], links: list[dict], routes: list[dict]):
    """
    Prints a summary of the simulated network topology.
    """
    reachable = sum(1 for r in routes if r["status"] in ["routed", "same_satellite"])
    unreachable = sum(1 for r in routes if r["status"] == "unreachable")
    avg_hops = np.mean([r["hops"] for r in routes if r["hops"] is not None]) if routes else 0

    print(f"\n=== Network Simulation Summary ===")
    print(f"Satellites in mesh:   {len(positions)}")
    print(f"ISL links:            {len(links)}")
    print(f"Avg links/satellite:  {round(len(links) * 2 / max(len(positions), 1), 1)}")
    print(f"Station pairs routed: {reachable}")
    print(f"Unreachable pairs:    {unreachable}")
    print(f"Avg hops per route:   {round(avg_hops, 1)}")