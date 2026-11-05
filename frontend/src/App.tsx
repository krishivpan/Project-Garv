import { useEffect, useRef } from "react";
import { CircleMarker, MapContainer, TileLayer, useMap } from "react-leaflet";
import { useTelemetry } from "./useTelemetry";
import { useWaypoints } from "./Waypoints/useWaypoints";
import WaypointLayer from "./Waypoints/WaypointLayer";

// MAVLink GPS fix_type numbers -> short labels (index = fix_type).
const GPS_FIX_NAMES = [
    "No GPS",
    "No fix",
    "2D",
    "3D",
    "DGPS",
    "RTK float",
    "RTK fixed",
];

// Show a number with a fixed number of decimals and a unit, or "—" if unknown.
function show(value: number | null, decimals: number, unit: string) {
    return value === null ? "—" : `${value.toFixed(decimals)} ${unit}`;
}

// Moves the map to the drone the first time we get a position, then never again,
// so you can pan and zoom freely afterwards. Must be inside <MapContainer>.
function CenterOnFirstPosition({ lat, lon }: { lat: number; lon: number }) {
    const map = useMap();
    const hasCentered = useRef(false);

    useEffect(() => {
        if (!hasCentered.current) {
            map.setView([lat, lon], 17);
            hasCentered.current = true;
        }
    }, [map, lat, lon]);

    return null;
}

export default function App() {
    const { telemetry, connected } = useTelemetry();
    const { waypoints, addWaypoint, moveWaypoint } = useWaypoints();

    const hasPosition =
        telemetry !== null && telemetry.lat !== null && telemetry.lon !== null;
    const linkLost = telemetry?.link === "lost";
    const warning = !connected || linkLost;

    return (
        <>
            {/* Starts zoomed out on the whole world until the first position arrives. */}
            <MapContainer center={[0, 0]} zoom={2} className="map">
                <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                />
                {hasPosition && (
                    <>
                        <CenterOnFirstPosition
                            lat={telemetry.lat!}
                            lon={telemetry.lon!}
                        />
                        <CircleMarker
                            center={[telemetry.lat!, telemetry.lon!]}
                            radius={8}
                            eventHandlers={{ click: () => {} }} 
                            bubblingMouseEvents={false}
                        />
                    </>
                )}
                <WaypointLayer
                    waypoints={waypoints}
                    addWaypoint={addWaypoint}
                    moveWaypoint={moveWaypoint}
                />
            </MapContainer>

            <div className={warning ? "panel warning" : "panel"}>
                {!connected && (
                    <div className="alert">Backend disconnected</div>
                )}
                {connected && linkLost && (
                    <div className="alert">Drone link lost</div>
                )}
                <table>
                    <tbody>
                        <tr>
                            <td># of Waypoints</td>
                            <td>{waypoints.length}</td>
                        </tr>
                        <tr>
                            <td>Link</td>
                            <td>{telemetry?.link ?? "—"}</td>
                        </tr>
                        <tr>
                            <td>Mode</td>
                            <td>{telemetry?.mode ?? "—"}</td>
                        </tr>
                        <tr>
                            <td>Armed</td>
                            <td>
                                {telemetry?.armed == null
                                    ? "—"
                                    : telemetry.armed
                                      ? "ARMED"
                                      : "disarmed"}
                            </td>
                        </tr>
                        <tr>
                            <td>Altitude</td>
                            <td>
                                {show(telemetry?.alt_rel_m ?? null, 1, "m")}
                            </td>
                        </tr>
                        <tr>
                            <td>Speed</td>
                            <td>
                                {show(
                                    telemetry?.groundspeed_ms ?? null,
                                    1,
                                    "m/s",
                                )}
                            </td>
                        </tr>
                        <tr>
                            <td>Battery</td>
                            <td>
                                {show(telemetry?.battery_v ?? null, 2, "V")}{" "}
                                {telemetry?.battery_pct != null &&
                                    `(${telemetry.battery_pct}%)`}
                            </td>
                        </tr>
                        <tr>
                            <td>GPS fix</td>
                            <td>
                                {telemetry?.gps_fix == null
                                    ? "—"
                                    : (GPS_FIX_NAMES[telemetry.gps_fix] ??
                                      telemetry.gps_fix)}
                            </td>
                        </tr>
                        <tr>
                            <td>Satellites</td>
                            <td>{telemetry?.satellites ?? "—"}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </>
    );
}
