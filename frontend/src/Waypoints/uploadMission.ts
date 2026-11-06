import type { Waypoint } from "./useWaypoints";

const MISSION_URL = "http://localhost:8000/api/mission";

// Copies of the backend's limits (backend/app/mission.py), used here only
// for early feedback. The backend enforces them, so keep the two in step.
export const MIN_ALT_M = 5;
export const MAX_ALT_M = 120;
export const MAX_WAYPOINTS = 50;

// Sends the waypoints to the backend, which uploads them to the drone.
// Returns null if the backend accepted the request, or an error message.
// The upload result itself arrives later as telemetry.mission_status.
export async function uploadMission(waypoints: Waypoint[]): Promise<string | null> {
    let response: Response;
    try {
        response = await fetch(MISSION_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            // Only send what the backend needs; the ids are frontend-only.
            body: JSON.stringify({
                waypoints: waypoints.map((wp) => ({ lat: wp.lat, lon: wp.lon, alt_m: wp.alt_m })),
            }),
        });
    } catch {
        return "Backend not reachable";
    }
    if (response.ok) {
        return null;
    }

    let detail;
    try {
        detail = (await response.json()).detail;
    } catch {
        detail = null; // not JSON
    }
    // Our own 409/422 replies have a plain-text reason.
    if (typeof detail === "string") {
        return detail;
    }
    // Pydantic's 422 is a list of errors; loc looks like
    // ["body", "waypoints", 2, "alt_m"], where 2 is the waypoint's index.
    if (Array.isArray(detail) && detail.length > 0) {
        const index = detail[0].loc?.find((part: unknown) => typeof part === "number");
        return index === undefined ? detail[0].msg : `Waypoint ${index + 1}: ${detail[0].msg}`;
    }
    return `Upload refused (HTTP ${response.status})`;
}
