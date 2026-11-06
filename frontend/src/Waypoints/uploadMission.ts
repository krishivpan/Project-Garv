import type { Waypoint } from "./useWaypoints";

const MISSION_URL = "http://localhost:8000/api/mission";

// Sends the waypoints to the backend, which uploads them to the drone.
// Returns null if the backend accepted the request, or an error message.
// The upload result itself arrives later as telemetry.mission_status.
export async function uploadMission(waypoints: Waypoint[]): Promise<string | null> {
    try {
        const response = await fetch(MISSION_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            // Only send what the backend needs; the ids are frontend-only.
            body: JSON.stringify({
                waypoints: waypoints.map((wp) => ({ lat: wp.lat, lon: wp.lon, alt_m: wp.alt_m })),
            }),
        });
        if (response.ok) {
            return null;
        }
        const body = await response.json();
        // 409 replies have a plain text reason; 422 (validation) has a list.
        return typeof body.detail === "string"
            ? body.detail
            : "Invalid mission (altitudes must be 1–120 m)";
    } catch {
        return "Backend not reachable";
    }
}
