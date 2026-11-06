import { useState } from "react";
import type { DroneMission, Telemetry } from "../useTelemetry";
import { MAX_ALT_M, MAX_WAYPOINTS, MIN_ALT_M, uploadMission } from "./uploadMission";
import type { Waypoint } from "./useWaypoints";

function altitudeOk(alt_m: number) {
    return alt_m >= MIN_ALT_M && alt_m <= MAX_ALT_M;
}

// True if the drone holds exactly the waypoints on the map (allowing for
// the drone rounding positions to 1e-7 degrees and altitudes to 1 cm).
function sameAsDrone(waypoints: Waypoint[], drone: DroneMission) {
    return (
        drone.standard &&
        drone.waypoints.length === waypoints.length &&
        drone.waypoints.every(
            (d, i) =>
                Math.abs(d.lat - waypoints[i].lat) < 1e-7 &&
                Math.abs(d.lon - waypoints[i].lon) < 1e-7 &&
                Math.abs(d.alt_m - waypoints[i].alt_m) < 0.05,
        )
    );
}

// One line saying how the map compares with what the drone would fly.
function syncText(waypoints: Waypoint[], drone: DroneMission | null) {
    if (drone === null) return "Mission on drone: unknown";
    if (drone.item_count <= 1) return "No mission on the drone";
    // e.g. uploaded from another app, or an older upload without return-home.
    if (!drone.standard) return "Drone has a different kind of mission; upload to replace it";
    if (sameAsDrone(waypoints, drone)) return "Map matches the drone's mission";
    return "Map differs from the drone's mission";
}

// Side panel listing every waypoint, with an altitude box and a delete button,
// plus the upload button. It sits outside <MapContainer>, so clicks here never
// add waypoints.
export default function WaypointList({
    waypoints,
    setAltitude,
    removeWaypoint,
    clearWaypoints,
    telemetry,
    connected,
}: {
    waypoints: Waypoint[];
    setAltitude: (id: string, alt_m: number) => void;
    removeWaypoint: (id: string) => void;
    clearWaypoints: () => void;
    telemetry: Telemetry | null;
    connected: boolean;
}) {
    // Error from the request itself (e.g. "Drone is armed"). The upload's
    // own result comes from telemetry.mission_status instead.
    const [requestError, setRequestError] = useState<string | null>(null);
    const [sending, setSending] = useState(false); // request in flight

    const missionStatus = telemetry?.mission_status ?? null;

    // The first reason the upload button is disabled, or null if it's allowed.
    // The backend checks all of this again; this is for clear feedback.
    function uploadBlockedReason(): string | null {
        if (waypoints.length === 0) return "Add waypoints first";
        if (waypoints.length > MAX_WAYPOINTS) return `At most ${MAX_WAYPOINTS} waypoints`;
        if (!waypoints.every((wp) => altitudeOk(wp.alt_m))) return `Altitudes must be ${MIN_ALT_M}–${MAX_ALT_M} m`;
        if (!connected || telemetry === null) return "Backend disconnected";
        if (telemetry.link !== "ok") return "No link to the drone";
        if (telemetry.armed !== false) return "Drone is armed (or state unknown)";
        if (sending || missionStatus === "uploading" || missionStatus === "verifying") return "Upload in progress";
        return null;
    }
    const blockedReason = uploadBlockedReason();

    async function handleUpload() {
        const highest = Math.max(...waypoints.map((wp) => wp.alt_m));
        const confirmed = window.confirm(
            `Upload ${waypoints.length} waypoint(s) to the drone?\n\n` +
                "This replaces the mission on the drone.\n" +
                `Highest altitude: ${highest} m above home (hills and buildings are not taken into account).\n` +
                "After the last waypoint the drone returns home and lands.",
        );
        if (!confirmed) return;
        setSending(true);
        setRequestError(await uploadMission(waypoints));
        setSending(false);
    }

    const statusClass =
        missionStatus === "ok" ? "status-ok" : missionStatus?.startsWith("failed") ? "status-failed" : "";

    return (
        <div className="waypoint-list">
            <div className="waypoint-list-header">
                <button onClick={handleUpload} disabled={blockedReason !== null}>
                    Upload mission
                </button>
            </div>
            {blockedReason && <div className="wp-note">{blockedReason}</div>}
            {requestError && <div className="status-failed">{requestError}</div>}
            <div className={statusClass}>Last upload: {missionStatus ?? "—"}</div>
            <div className="wp-note">{syncText(waypoints, telemetry?.drone_mission ?? null)}</div>

            <div className="waypoint-list-header">
                <strong>Waypoints</strong>
                {/* Pass the function itself; React calls it on click. */}
                <button onClick={clearWaypoints} disabled={waypoints.length === 0}>
                    Clear all
                </button>
            </div>

            {waypoints.length === 0 && <div>Click the map to add waypoints</div>}

            {waypoints.map((waypoint, index) => (
                // Red when the altitude is outside the allowed range.
                <div key={waypoint.id} className={altitudeOk(waypoint.alt_m) ? "waypoint-row" : "waypoint-row wp-invalid"}>
                    {/* Same number as the marker on the map. */}
                    <span>{index + 1}</span>

                    <label>
                        Alt{" "}
                        <input
                            type="number"
                            min={MIN_ALT_M}
                            max={MAX_ALT_M}
                            value={waypoint.alt_m}
                            onChange={(e) => {
                                // e.target.value is always a string, so convert it.
                                // Any non-negative number is stored (so typing "1" on
                                // the way to "15" works); out-of-range ones show red
                                // and block the upload.
                                const alt = Number(e.target.value);
                                if (Number.isFinite(alt) && alt >= 0) {
                                    setAltitude(waypoint.id, alt);
                                }
                            }}
                        />{" "}
                        m
                    </label>

                    {/* Wrapped in an arrow function so it only runs on click,
                        not while drawing. */}
                    <button onClick={() => removeWaypoint(waypoint.id)}>Delete</button>
                </div>
            ))}
        </div>
    );
}
