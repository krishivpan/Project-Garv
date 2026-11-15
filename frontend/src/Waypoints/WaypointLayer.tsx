import { Marker, Polyline, useMapEvents } from "react-leaflet";
import type { Waypoint } from "./useWaypoints";
import L from "leaflet";

// Picks the marker style for waypoint `index` from the mission progress.
function iconClass(index: number, currentIndex: number | null, reachedUpTo: number | null) {
    if (index === currentIndex) return "wp-icon wp-current"; // flying to it now
    if (reachedUpTo !== null && index <= reachedUpTo) return "wp-icon wp-reached"; // done (in order)
    return "wp-icon"; // not reached yet
}

// Only small values (numbers) go in as progress props, never the whole
// telemetry object: this component then only redraws when progress actually
// changes, not 5 times a second. A redraw mid-drag would cancel the drag.
export default function WaypointLayer({
    waypoints,
    addWaypoint,
    moveWaypoint,
    currentIndex,
    reachedUpTo,
}: {
    waypoints: Waypoint[];
    addWaypoint: (lat: number, lon: number) => void;
    moveWaypoint: (id: string, lat: number, lon: number) => void;
    currentIndex: number | null; // waypoint the drone is flying to, if shown
    reachedUpTo: number | null; // last waypoint reached, if shown
}) {
    useMapEvents({
        click(e) {
            addWaypoint(e.latlng.lat, e.latlng.lng);
        },
    });

    // All of the [lat, lon] pairs from all the waypoints
    const linePoints = waypoints.map(
        (waypoint) => [waypoint.lat, waypoint.lon] as [number, number],
    );

    return (
        <>
            {waypoints.map((waypoint, index) => {
                const markerIcon = L.divIcon({
                    html: `<div>${index + 1}</div>`,
                    className: iconClass(index, currentIndex, reachedUpTo),
                    iconSize: [24, 24],
                    iconAnchor: [12, 12],
                });

                return (
                    <Marker
                        key={waypoint.id}
                        position={[waypoint.lat, waypoint.lon]}
                        icon={markerIcon}
                        eventHandlers={{ 
                            click: () => {}, 
                            dragend: (e) => {
                                const target = e.target
                                const newLatLng = target.getLatLng()
                                moveWaypoint(waypoint.id, newLatLng.lat, newLatLng.lng)
                            }
                        }}
                        bubblingMouseEvents={false}
                        draggable={true}
                    />
                );
            })}

            {linePoints.length > 1 && <Polyline positions={linePoints} />}
        </>
    );
}
