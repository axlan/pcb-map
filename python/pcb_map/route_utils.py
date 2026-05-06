"""
route_grid.py

Quantize a GeoJSON route (LineString) into a sequence of (grid_col, grid_row) cells
with the distance spent in each, in order of traversal.

Requires:
    pip install requests haversine

"""

from haversine import haversine, Unit
from collections import namedtuple

from pcb_map.constants import (
    MATRIX_HEIGHT,
    MATRIX_WIDTH,
    START_LATITUDE,
    START_LONGITUDE,
    END_LATITUDE,
    END_LONGITUDE,
)

from pcb_map.open_route_service import get_route_coords


# ── Grid helpers ──────────────────────────────────────────────────────────────


def point_to_cell(lon, lat, min_lon, min_lat, cell_w, cell_h, n_cols, n_rows):
    """Return the (col, row) grid index for a point (clamped to valid range)."""
    col = int((lon - min_lon) / cell_w)
    row = int((lat - min_lat) / cell_h)
    col = max(0, min(n_cols - 1, col))
    row = max(0, min(n_rows - 1, row))
    return col, row


# ── Core algorithm ────────────────────────────────────────────────────────────


def _crossing_t(v0, v1, boundary):
    """
    Parameter t in [0,1] where the linear interpolation from v0 to v1
    crosses the given boundary value. Returns None if no crossing.
    """
    dv = v1 - v0
    if dv == 0:
        return None
    t = (boundary - v0) / dv
    return t if 0.0 < t < 1.0 else None


def segment_crossings(
    lon0, lat0, lon1, lat1, min_lon, min_lat, cell_w, cell_h, n_cols, n_rows
) -> list[float]:
    """
    Return a sorted list of t-values (0 < t < 1) where the segment
    (lon0,lat0) -> (lon1,lat1) crosses a grid line.
    """
    ts = []

    # Vertical grid lines  (lon = min_lon + i*cell_w)
    lo_col = min(int((lon0 - min_lon) / cell_w), int((lon1 - min_lon) / cell_w))
    hi_col = max(int((lon0 - min_lon) / cell_w), int((lon1 - min_lon) / cell_w))
    for i in range(lo_col + 1, hi_col + 1):
        boundary = min_lon + i * cell_w
        t = _crossing_t(lon0, lon1, boundary)
        if t is not None:
            ts.append(t)

    # Horizontal grid lines (lat = min_lat + j*cell_h)
    lo_row = min(int((lat0 - min_lat) / cell_h), int((lat1 - min_lat) / cell_h))
    hi_row = max(int((lat0 - min_lat) / cell_h), int((lat1 - min_lat) / cell_h))
    for j in range(lo_row + 1, hi_row + 1):
        boundary = min_lat + j * cell_h
        t = _crossing_t(lat0, lat1, boundary)
        if t is not None:
            ts.append(t)

    return sorted(ts)


CellDistance = namedtuple("CellDistance", ["col", "row", "distance_miles"])


def quantize_route(coords: list[tuple[float, float]]) -> list[CellDistance]:
    """
    Split the route at every grid-line crossing and accumulate distance per cell.

    Returns a list of CellDistance(col, row, distance_miles) in traversal order,
    with consecutive runs in the same cell merged.
    """

    # Accumulate as ordered list of (cell, distance) so we preserve traversal order
    # but merge adjacent identical cells.
    result: list[CellDistance] = []
    n_cols = MATRIX_HEIGHT
    n_rows = MATRIX_WIDTH
    min_lat = min(START_LATITUDE, END_LATITUDE)
    min_lon = min(START_LONGITUDE, END_LONGITUDE)
    max_lat = max(START_LATITUDE, END_LATITUDE)
    max_lon = max(START_LONGITUDE, END_LONGITUDE)
    cell_w = (max_lon - min_lon) / n_cols
    cell_h = (max_lat - min_lat) / n_rows

    def add(col, row, dist_miles):
        if dist_miles < 1e-9:
            return
        if result and result[-1].col == col and result[-1].row == row:
            result[-1] = CellDistance(col, row, result[-1].distance_miles + dist_miles)
        else:
            result.append(CellDistance(col, row, dist_miles))

    for i in range(len(coords) - 1):
        lon0, lat0 = coords[i]
        lon1, lat1 = coords[i + 1]

        ts = segment_crossings(
            lon0, lat0, lon1, lat1, min_lon, min_lat, cell_w, cell_h, n_cols, n_rows
        )

        # Walk sub-segments defined by [0, t1, t2, ..., 1]
        breakpoints = [0.0] + ts + [1.0]
        for j in range(len(breakpoints) - 1):
            ta, tb = breakpoints[j], breakpoints[j + 1]
            mid_t = (ta + tb) / 2.0

            # Midpoint of sub-segment → determines which cell this piece is in
            mid_lon = lon0 + mid_t * (lon1 - lon0)
            mid_lat = lat0 + mid_t * (lat1 - lat0)
            col, row = point_to_cell(
                mid_lon, mid_lat, min_lon, min_lat, cell_w, cell_h, n_cols, n_rows
            )

            # Start and end points of sub-segment (for haversine distance)
            pa_lon = lon0 + ta * (lon1 - lon0)
            pa_lat = lat0 + ta * (lat1 - lat0)
            pb_lon = lon0 + tb * (lon1 - lon0)
            pb_lat = lat0 + tb * (lat1 - lat0)

            dist = haversine((pa_lat, pa_lon), (pb_lat, pb_lon), unit=Unit.MILES)
            add(col, row, dist)

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    ORIGIN = "3000 Telegraph Ave, Berkeley, CA 94705"
    DEST = "920 Heinz Ave, Berkeley, CA 94710"
    API_KEY = os.environ.get("OPEN_ROUTE_SERVICE_KEY")

    print(f"Fetching route: {ORIGIN}  →  {DEST}")
    coords = get_route_coords(ORIGIN, DEST, API_KEY)
    print(f"Route has {len(coords)} coordinate points.\n")

    segments = quantize_route(coords)

    total = sum(s.distance_miles for s in segments)
    print(f"{'Col':>4}  {'Row':>4}  {'Miles':>8}")
    print("-" * 22)
    for s in segments:
        print(f"{s.col:>4}  {s.row:>4}  {s.distance_miles:>8.4f}")
    print("-" * 22)
    print(f"{'Total':>10}  {total:>8.4f}")
