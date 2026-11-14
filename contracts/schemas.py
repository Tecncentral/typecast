"""Shared shapes. Change only by telling all four owners."""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


class Shot(BaseModel):
    shot_id: str
    model_id: str            # Matterport model
    sweep_id: str            # scan point
    heading_deg: float       # 0-360, direction the view faces
    image_path: str          # under cache/ or a URL
    property_id: str         # CoStar property
    room_area_m2: Optional[float] = None
    ceiling_m: Optional[float] = None
    depth_m: Optional[float] = None      # distance to the wall along heading
    measure_on_site: bool = False        # geometry was estimated
    score: Optional[float] = None
    reason: Optional[str] = None         # filled by rerank


class Property(BaseModel):
    property_id: str
    address: str
    city: str
    lat: float
    lon: float
    type: str
    year_built: Optional[int] = None
    available: bool = False
    size_sqft: Optional[float] = None
    contact: Optional[str] = None
    model_id: Optional[str] = None
    availability_status: Optional[Literal["available", "not_available", "unknown"]] = None
    availability_reason: Optional[str] = None
    parking_flags: dict[str, bool] = Field(default_factory=dict)
    listing_types: list[Literal["lease", "sale", "auction"]] = Field(default_factory=list)


class Evidence(BaseModel):
    source: Literal["costar", "matterport", "vexcel"]
    claim: str
    status: Literal["measured", "estimated", "unknown"]


class Logistics(BaseModel):
    property_id: str
    truck_spaces: Optional[int] = Field(default=None, ge=0)
    car_spaces: Optional[int] = Field(default=None, ge=0)
    parking_polygon: list[list[float]] = Field(default_factory=list)  # [[lat, lon], ...]
    parking_geometry: Optional[dict] = None  # GeoJSON [lon, lat], preserving holes/multipart
    walk_m: Optional[float] = None
    noise_flags: list[str] = Field(default_factory=list)
    aerial_image_path: Optional[str] = None
    estimated: bool = True
    parking_status: Optional[Literal["measured", "estimated", "unknown"]] = None
    walk_status: Optional[Literal["measured", "estimated", "unknown"]] = None
    noise_status: Optional[Literal["measured", "estimated", "unknown"]] = None
    parking_area_m2: Optional[float] = Field(default=None, ge=0)
    source_notes: list[str] = Field(default_factory=list)
    source_evidence: list[Evidence] = Field(default_factory=list)


class ShotFit(BaseModel):
    fits: bool
    needed_depth_m: float
    have_depth_m: Optional[float]
    ceiling_m: Optional[float]
    note: str
    status: Literal["fits", "tight", "unknown"] = "unknown"

    @model_validator(mode="after")
    def normalize_status(self):
        if self.have_depth_m is None or self.ceiling_m is None:
            self.status, self.fits = "unknown", False
        elif "status" not in self.model_fields_set:
            self.status = "fits" if self.fits else "tight"
        elif self.status != "fits":
            self.fits = False
        return self


class Pick(BaseModel):
    rank: int
    property: Property
    shots: list[Shot]
    shot_fit: ShotFit
    logistics: Logistics
    reason: str                  # one sentence citing CoStar, Matterport and Vexcel
    skeptic_notes: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class ScoutRequest(BaseModel):
    scene: Optional[str] = None
    example_shot_id: Optional[str] = None
    thread_id: Optional[str] = None


class Event(BaseModel):
    type: str   # plan | todo | subagent_start | subagent_result | skeptic | relaxed | final
    agent: Optional[str] = None
    text: str = ""
    ts: float = 0.0
    ms: Optional[float] = None
    engine: Optional[Literal["fixed", "deep"]] = None


class ScoutResponse(BaseModel):
    thread_id: str
    picks: list[Pick]
    gave_up: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    engine: Literal["fixed", "deep"] = "fixed"
    source_mode: Literal["mock", "live"] = "mock"
    trace_url: Optional[str] = None
    timings: dict[str, float] = Field(default_factory=dict)
