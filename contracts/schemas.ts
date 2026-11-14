// Mirror of contracts/schemas.py. Keep the two in step.
export interface Shot { shot_id: string; model_id: string; sweep_id: string; heading_deg: number; image_path: string; property_id: string; room_area_m2?: number; ceiling_m?: number; depth_m?: number; measure_on_site: boolean; score?: number; reason?: string }
export interface Property { property_id: string; address: string; city: string; lat: number; lon: number; type: string; year_built?: number; available: boolean; size_sqft?: number; contact?: string; model_id?: string }
export interface Logistics { property_id: string; truck_spaces: number; car_spaces: number; parking_polygon: number[][]; walk_m?: number; noise_flags: string[]; aerial_image_path?: string; estimated: boolean }
export interface ShotFit { fits: boolean; needed_depth_m: number; have_depth_m?: number; ceiling_m?: number; note: string; status?: "fits" | "tight" | "unknown" }
export interface Pick { rank: number; property: Property; shots: Shot[]; shot_fit: ShotFit; logistics: Logistics; reason: string; skeptic_notes: string[]; evidence?: Evidence[] }
export interface AgentEvent { type: "plan" | "todo" | "subagent_start" | "subagent_result" | "skeptic" | "relaxed" | "final" | "tool" | "error" | "fallback" | "rerank" | "trace"; agent?: string; text: string; ts?: number; ms?: number | null; engine?: "fixed" | "deep" | null }
export interface ScoutResponse { thread_id: string; picks: Pick[]; gave_up: string[]; events: AgentEvent[]; engine?: "fixed" | "deep"; source_mode?: "mock" | "live"; trace_url?: string | null; timings?: Record<string, number> }

export interface Evidence { source: "costar" | "matterport" | "vexcel"; claim: string; status: "measured" | "estimated" | "unknown" }
