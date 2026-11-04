import { CircleMarker, Polyline, useMapEvents } from "react-leaflet"
import type { Waypoint } from "./useWaypoints"



export default function WaypointLayer(
    {waypoints, addWaypoint}: {
        waypoints: Waypoint[], 
        addWaypoint: (lat: number, lon: number) => void
    }) {

    useMapEvents({
        click(e) {
            addWaypoint(e.latlng.lat, e.latlng.lng)
        }
    })

    const numPositions = waypoints.filter(waypoint => waypoint.id !== undefined && waypoint.lat !== undefined)
                                .map(waypoint => [waypoint.lat, waypoint.lon] as [number, number])

    return <>

        {waypoints.map(waypoint => {
            if (!waypoint.id && waypoint.lat === undefined && waypoint.lon === undefined) {
                return null;
            }

            return (
            <CircleMarker 
                key={waypoint.id}
                center={[waypoint.lat, waypoint.lon]}
                radius={8}
                pathOptions={{color: "#008000"}}
            />
            )}
        )}

        {numPositions.length > 1 &&
            <Polyline 
                positions={numPositions}
            />
        }

        
    </>
}