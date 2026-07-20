"""Pure-Python geospatial helpers."""

from __future__ import annotations

import math


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two WGS84 points."""
    r = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def grid_cell(lat: float, lon: float, cell_m: float) -> tuple[int, int]:
    """Coarse grid key for spatial blocking (~cell_m meters)."""
    # approximate degrees
    lat_deg = cell_m / 111_320.0
    lon_deg = cell_m / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return (int(math.floor(lat / lat_deg)), int(math.floor(lon / lon_deg)))
