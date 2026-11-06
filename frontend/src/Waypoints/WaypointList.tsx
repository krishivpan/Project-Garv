import { useState } from "react";
import { uploadMission } from "./uploadMission";
import type { Waypoint } from "./useWaypoints";

// Side panel listing every waypoint, with an altitude box and a delete button.
// It sits outside <MapContainer>, so clicks here never add waypoints.
export default function WaypointList({
    waypoints,
    setAltitude,
    removeWaypoint,
    clearWaypoints,
    missionStatus,
}: {
    waypoints: Waypoint[];
    setAltitude: (id: string, alt_m: number) => void;
    removeWaypoint: (id: string) => void;
    clearWaypoints: () => void;
    missionStatus: string | null; // null until telemetry arrives
}) {
    // Error from the request itself (e.g. no drone link). The upload's
    // own result comes from missionStatus instead.
    const [requestError, setRequestError] = useState<string | null>(null);

    async function handleUpload() {
        setRequestError(await uploadMission(waypoints));
    }

    const canUpload =
        waypoints.length > 0 && missionStatus !== null && missionStatus !== "uploading";

    return (
        <div className="waypoint-list">
            <div className="waypoint-list-header">
                <button onClick={handleUpload} disabled={!canUpload}>
                    Upload mission
                </button>
                <span>{requestError ?? `Last upload: ${missionStatus ?? "—"}`}</span>
            </div>

            <div className="waypoint-list-header">
                <strong>Waypoints</strong>
                {/* Pass the function itself; React calls it on click. */}
                <button onClick={clearWaypoints} disabled={waypoints.length === 0}>
                    Clear all
                </button>
            </div>

            {waypoints.length === 0 && <div>Click the map to add waypoints</div>}

            {waypoints.map((waypoint, index) => (
                <div key={waypoint.id} className="waypoint-row">
                    {/* Same number as the marker on the map. */}
                    <span>{index + 1}</span>

                    <label>
                        Alt{" "}
                        <input
                            type="number"
                            min={0}
                            value={waypoint.alt_m}
                            onChange={(e) => {
                                // e.target.value is always a string, so convert it.
                                // Ignore anything that isn't a real, non-negative number.
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
