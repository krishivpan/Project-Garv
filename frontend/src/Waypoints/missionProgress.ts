import type { DroneMission, Telemetry } from "../useTelemetry";
import type { Waypoint } from "./useWaypoints";

// How close the map and the drone's mission must be to count as "the same".
const MATCH_DISTANCE_M = 1;
const MATCH_ALT_M = 1;
const METRES_PER_DEGREE = 111_320; // one degree of latitude, roughly

// Approximate distance in metres between two nearby points. Fine for the
// ~1 m comparison below; not for long distances.
function metresApart(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
    const north = (a.lat - b.lat) * METRES_PER_DEGREE;
    // A degree of longitude gets shorter away from the equator.
    const east = (a.lon - b.lon) * METRES_PER_DEGREE * Math.cos((a.lat * Math.PI) / 180);
    return Math.hypot(north, east);
}

// True if the drone holds the waypoints on the map: same count, in our
// layout, each within ~1 m and altitude within ~1 m. Progress is only drawn
// on the map when this is true; otherwise index 1 on the drone might be a
// different point from marker 2 on the map.
export function mapMatchesDrone(waypoints: Waypoint[], drone: DroneMission | null) {
    return (
        drone !== null &&
        drone.standard &&
        drone.waypoints.length === waypoints.length &&
        drone.waypoints.every(
            (d, i) =>
                metresApart(d, waypoints[i]) <= MATCH_DISTANCE_M &&
                Math.abs(d.alt_m - waypoints[i].alt_m) <= MATCH_ALT_M,
        )
    );
}

// The drone is flying its mission (ArduPilot's mission mode is AUTO).
export function isMissionRunning(t: Telemetry | null) {
    return t !== null && t.mode === "AUTO";
}

// True once the drone has finished the final item (return home + landed).
// ArduCopter sends MISSION_ITEM_REACHED for every item including the last,
// and the last item is seq mission_count - 1 (count includes home at seq 0).
// The mission_current check stops an old "complete" showing when the same
// mission is flown again: a restarted mission goes back to a lower seq.
export function isMissionComplete(t: Telemetry | null) {
    if (t === null || t.last_reached === null || t.mission_count === null) return false;
    const finalSeq = t.mission_count - 1;
    return t.last_reached === finalSeq && (t.mission_current === null || t.mission_current >= finalSeq);
}

// Text for the status panel, or null when there's nothing to say.
// Uses the backend's waypoint indexes, so no seq arithmetic here.
export function progressText(t: Telemetry | null) {
    if (t === null) return null;
    if (isMissionComplete(t)) return "Mission complete";
    if (!isMissionRunning(t) || t.drone_mission === null) return null;
    if (t.current_waypoint_index !== null) {
        return `Waypoint ${t.current_waypoint_index + 1} of ${t.drone_mission.waypoints.length}`;
    }
    // Not heading to a waypoint: before the first one it's the takeoff,
    // after any waypoint was reached it's the final return home.
    return t.last_reached_waypoint_index === null ? "Taking off" : "Returning home";
}
