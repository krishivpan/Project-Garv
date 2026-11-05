import { CircleMarker, Marker, Polyline, useMapEvents } from "react-leaflet";
import type { Waypoint } from "./useWaypoints";
import L from "leaflet";

export default function WaypointLayer({
    waypoints,
    addWaypoint,
}: {
    waypoints: Waypoint[];
    addWaypoint: (lat: number, lon: number) => void;
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
                    className: "wp-icon",
                    iconSize: [24, 24],
                    iconAnchor: [12, 12],
                })

                return (
                    <Marker
                        key={waypoint.id}
                        position={[waypoint.lat, waypoint.lon]}
                        icon={markerIcon}
                        eventHandlers={{ click: () => {} }} 
                        bubblingMouseEvents={false}
                    />
                );
            })}

            {linePoints.length > 1 && <Polyline positions={linePoints} />}
        </>
    );
}
