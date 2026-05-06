
import hashlib
import json
import requests

from pcb_map.constants import (
    CACHE_DIR,
)

OPEN_ROUTE_SERVICE_BASE = "https://api.openrouteservice.org"

# ── ORS helpers ───────────────────────────────────────────────────────────────


def geocode(address, api_key):
    r = requests.get(
        f"{OPEN_ROUTE_SERVICE_BASE}/geocode/search",
        params={"api_key": api_key, "text": address, "size": 1},
    )
    r.raise_for_status()
    coords = r.json()["features"][0]["geometry"]["coordinates"]
    return coords  # [longitude, latitude]


def get_route(origin_address, dest_address, api_key):
    CACHE_DIR.mkdir(exist_ok=True)
    cache_key = hashlib.md5(f"{origin_address}:{dest_address}".encode()).hexdigest()
    cache_file = CACHE_DIR / f"route_{cache_key}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text())

    origin = geocode(origin_address, api_key)
    dest = geocode(dest_address, api_key)

    r = requests.post(
        f"{OPEN_ROUTE_SERVICE_BASE}/v2/directions/driving-car/geojson",
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        json={"coordinates": [origin, dest]},
    )
    r.raise_for_status()
    data = r.json()
    cache_file.write_text(json.dumps(data))
    return data


def get_route_coords(origin_address, dest_address, api_key):
    route_json = get_route(origin_address, dest_address, api_key)
    return [
        (lon, lat) for lon, lat in route_json["features"][0]["geometry"]["coordinates"]
    ]
