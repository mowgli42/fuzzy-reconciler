"""Pydantic models for entities, matching config, and results."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Classification(str, Enum):
    EXACT_MATCH = "exact_match"
    STRONG_FUZZY_MATCH = "strong_fuzzy_match"
    TEMPORAL_VARIANT = "temporal_variant"
    SPATIAL_PROXIMITY_CANDIDATE = "spatial_proximity_candidate"
    AMBIGUOUS = "ambiguous"
    WEAK_CANDIDATE = "weak_candidate"
    UNMATCHED = "unmatched"
    CONFIRMED_MATCH = "confirmed_match"
    CONFIRMED_TEMPORAL = "confirmed_temporal"
    MARKED_DISTINCT = "marked_distinct"


class Entity(BaseModel):
    id: str | int | None = None
    name: str = ""
    lat: float | None = None
    lon: float | None = None
    analyzed_at: datetime | None = None
    category: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    original_row: dict[str, Any] = Field(default_factory=dict)
    source_list: str | None = None  # "A" or "B"

    @field_validator("analyzed_at", mode="before")
    @classmethod
    def parse_analyzed_at(cls, v: Any) -> datetime | None:
        if v is None or v == "":
            return None
        if isinstance(v, datetime):
            return v
        from dateutil import parser as date_parser

        return date_parser.isoparse(str(v))


class MatchWeights(BaseModel):
    geo: float = 0.35
    name: float = 0.30
    attr: float = 0.25
    temporal: float = 0.10

    @model_validator(mode="after")
    def normalize_sum(self) -> MatchWeights:
        total = self.geo + self.name + self.attr + self.temporal
        if total <= 0:
            raise ValueError("weights must sum to a positive value")
        # Allow slight drift; normalize for scoring
        if abs(total - 1.0) > 0.02:
            self.geo /= total
            self.name /= total
            self.attr /= total
            self.temporal /= total
        return self


class MatchConfig(BaseModel):
    max_geo_distance_m: float = Field(default=500, ge=0, le=5000)
    min_name_similarity: float = Field(default=70, ge=0, le=100)
    min_attr_similarity: float = Field(default=0.55, ge=0, le=1)
    date_tolerance_days: float = Field(default=14, ge=0, le=365)
    composite_threshold: float = Field(default=0.78, ge=0, le=1)
    min_candidate_score: float = Field(default=0.4, ge=0, le=1)
    weights: MatchWeights = Field(default_factory=MatchWeights)
    require_category_match: bool = False
    name_scorer: str = "token_set_ratio"  # or WRatio / partial_ratio


class ScoreBreakdown(BaseModel):
    geo_score: float
    name_score: float
    attr_score: float
    temporal_score: float
    composite_score: float
    geo_distance_m: float | None = None
    date_diff_days: float | None = None
    name_similarity_pct: float | None = None


class MatchPair(BaseModel):
    pair_id: str
    entity_a: Entity
    entity_b: Entity
    classification: Classification
    scores: ScoreBreakdown
    decision: str | None = None
    notes: str | None = None
    decided_at: datetime | None = None


class CompareSummary(BaseModel):
    total_a: int
    total_b: int
    pair_count: int
    counts: dict[str, int]
    avg_composite: float | None = None
    elapsed_ms: float | None = None


class CompareResult(BaseModel):
    summary: CompareSummary
    matches: list[MatchPair]
    unmatched_a: list[Entity]
    unmatched_b: list[Entity]
    config: MatchConfig


class IngestSideMetrics(BaseModel):
    total_rows: int = 0
    column_count: int = 0
    geo_valid: int = 0
    geo_missing: int = 0
    named: int = 0
    missing_name: int = 0
    with_analyzed_at: int = 0
    warning_count: int = 0
    categories: dict[str, int] = Field(default_factory=dict)
    mapped_fields: dict[str, str] = Field(default_factory=dict)


class IngestPreview(BaseModel):
    list_label: str
    row_count: int
    columns: list[str]
    preview_rows: list[dict[str, Any]]
    entities: list[Entity]
    validation_warnings: list[str] = Field(default_factory=list)
    source_format: str | None = None
    source_filename: str | None = None
    detected_mapping: dict[str, str] = Field(default_factory=dict)
    metrics: IngestSideMetrics | None = None


class IngestResponse(BaseModel):
    list_a: IngestPreview
    list_b: IngestPreview


class CompareRequest(BaseModel):
    list_a: list[Entity]
    list_b: list[Entity]
    config: MatchConfig = Field(default_factory=MatchConfig)


class Preset(BaseModel):
    id: str
    name: str
    description: str
    config: MatchConfig


class DecisionRequest(BaseModel):
    pair_id: str
    action: str  # confirm_match | confirm_temporal | mark_distinct
    notes: str = ""


class DemoSampleResponse(BaseModel):
    list_a: list[Entity]
    list_b: list[Entity]
    meta: dict[str, Any] = Field(default_factory=dict)
