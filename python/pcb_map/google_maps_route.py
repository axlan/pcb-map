import requests
import polyline  # pip install polyline

def get_route_segments(
    origin: str,
    destination: str,
    mode: str = "driving",
    api_key: str | None = None,
) -> list[dict]:
    """
    Get lat/lon line segments describing the route between two addresses.

    Args:
        origin:      Starting address (e.g. "1600 Amphitheatre Parkway, Mountain View, CA")
        destination: Ending address   (e.g. "1 Infinite Loop, Cupertino, CA")
        mode:        Travel mode — "driving", "walking", or "bicycling"
        api_key:     Google Maps API key

    Returns:
        List of dicts, each with:
          - start_lat, start_lng  : start of segment
          - end_lat,   end_lng    : end of segment
          - distance_m            : segment distance in metres
          - duration_s            : segment duration in seconds
          - instruction           : human-readable step instruction
    """
    valid_modes = {"driving", "walking", "bicycling"}
    if mode not in valid_modes:
        raise ValueError(f"mode must be one of {valid_modes}, got {mode!r}")

    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "key": api_key,
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    if data["status"] != "OK":
        raise RuntimeError(
            f"Directions API error: {data['status']} — "
            f"{data.get('error_message', 'no details')}"
        )

    segments = []

    # A route can have multiple legs (if waypoints are used); we iterate all.
    for leg in data["routes"][0]["legs"]:
        for step in leg["steps"]:
            # Each step carries a polyline we decode into (lat, lng) pairs.
            points = polyline.decode(step["polyline"]["points"])

            # Build one segment per consecutive pair of decoded points.
            for i in range(len(points) - 1):
                segments.append(
                    {
                        "start_lat": points[i][0],
                        "start_lng": points[i][1],
                        "end_lat":   points[i + 1][0],
                        "end_lng":   points[i + 1][1],
                        # Step-level distance/duration applies to the whole step;
                        # subdivide proportionally if you need per-micro-segment values.
                        "distance_m":  step["distance"]["value"],
                        "duration_s":  step["duration"]["value"],
                        "instruction": step["html_instructions"],
                    }
                )

    return segments


def get_route_coords(segments: list[dict]) -> list[tuple[float, float]]:
    if len(segments) == 0:
        return []
    
    start = [(segments[0]['start_lat'], segments[0]['start_lng'])]
    return start + [(s['end_lat'], s['end_lng']) for s in segments]


# ── Example usage ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

    origin      = "Ferry Building, San Francisco, CA"
    destination = "Golden Gate Park, San Francisco, CA"

    for travel_mode in ("driving", "walking", "bicycling"):
        print(f"\n{'='*60}")
        print(f"Mode: {travel_mode.upper()}")
        print(f"{'='*60}")

        segs = get_route_segments(
            origin=origin,
            destination=destination,
            mode=travel_mode,
            api_key=API_KEY,
        )

        print(f"Total segments: {len(segs)}")
        for i, seg in enumerate(segs[:5]):   # print first 5 to keep output short
            print(
                f"  [{i:>3}] ({seg['start_lat']:.5f}, {seg['start_lng']:.5f})"
                f" → ({seg['end_lat']:.5f}, {seg['end_lng']:.5f})"
                f"  {seg['distance_m']} m / {seg['duration_s']} s"
            )
        if len(segs) > 5:
            print(f"  ... and {len(segs) - 5} more segments")
