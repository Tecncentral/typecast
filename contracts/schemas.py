"""Shared shapes. Change only by telling all four owners."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


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


class Logistics(BaseModel):
    property_id: str
    truck_spaces: int
    car_spaces: int
    parking_polygon: list[list[float]] = Field(default_factory=list)  # [[lat, lon], ...]
    walk_m: Optional[float] = None
    noise_flags: list[str] = Field(default_factory=list)
    aerial_image_path: Optional[str] = None
    estimated: bool = True


class ShotFit(BaseModel):
    fits: bool
    needed_depth_m: float
    have_depth_m: Optional[float]
    ceiling_m: Optional[float]
    note: str


class Pick(BaseModel):
    rank: int
    property: Property
    shots: list[Shot]
    shot_fit: ShotFit
    logistics: Logistics
    reason: str                  # one sentence citing CoStar, Matterport and Vexcel
    skeptic_notes: list[str] = Field(default_factory=list)


class ScoutRequest(BaseModel):
    scene: Optional[str] = None
    example_shot_id: Optional[str] = None
    thread_id: Optional[str] = None


class Event(BaseModel):
    type: str   # plan | todo | subagent_start | subagent_result | skeptic | relaxed | final
    agent: Optional[str] = None
    text: str = ""


class ScoutResponse(BaseModel):
    thread_id: str
    picks: list[Pick]
    gave_up: list[str] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
