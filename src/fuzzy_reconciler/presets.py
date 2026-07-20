"""Named match-parameter presets."""

from fuzzy_reconciler.models import MatchConfig, MatchWeights, Preset

PRESETS: list[Preset] = [
    Preset(
        id="poi-strict",
        name="POI Strict",
        description="Tight geo + high name similarity for stable POI labels with GPS drift.",
        config=MatchConfig(
            max_geo_distance_m=150,
            min_name_similarity=85,
            min_attr_similarity=0.5,
            date_tolerance_days=7,
            composite_threshold=0.82,
            weights=MatchWeights(geo=0.35, name=0.40, attr=0.15, temporal=0.10),
        ),
    ),
    Preset(
        id="facility-loose",
        name="Facility Loose",
        description="Wider radius for nearby facilities with name drift (spatial candidates).",
        config=MatchConfig(
            max_geo_distance_m=350,
            min_name_similarity=75,
            min_attr_similarity=0.55,
            date_tolerance_days=30,
            composite_threshold=0.72,
            weights=MatchWeights(geo=0.30, name=0.20, attr=0.35, temporal=0.15),
        ),
    ),
    Preset(
        id="sensor-temporal",
        name="Sensor Temporal",
        description="Emphasize temporal windows for sensor/site re-analysis updates.",
        config=MatchConfig(
            max_geo_distance_m=200,
            min_name_similarity=80,
            min_attr_similarity=0.6,
            date_tolerance_days=30,
            composite_threshold=0.75,
            weights=MatchWeights(geo=0.30, name=0.30, attr=0.20, temporal=0.20),
        ),
    ),
    Preset(
        id="default",
        name="Default",
        description="Balanced defaults from the OpenSpec.",
        config=MatchConfig(),
    ),
]


def get_presets() -> list[Preset]:
    return PRESETS


def get_preset(preset_id: str) -> Preset | None:
    for p in PRESETS:
        if p.id == preset_id:
            return p
    return None
