import { CircleMarker, Polyline, useMapEvents } from "react-leaflet";
import type { Waypoint } from "./useWaypoints";

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
            {waypoints.map((waypoint) => {
                return (
                    <CircleMarker
                        key={waypoint.id}
                        center={[waypoint.lat, waypoint.lon]}
                        radius={8}
                        pathOptions={{ color: "#008000" }}
                        eventHandlers={{ click: () => {} }} 
                        bubblingMouseEvents={false}
                    />
                );
            })}

            {linePoints.length > 1 && <Polyline positions={linePoints} />}
        </>
    );
}
