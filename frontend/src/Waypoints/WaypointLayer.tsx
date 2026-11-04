import { CircleMarker, useMapEvents } from "react-leaflet"
import { useState } from "react"
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
        
    </>
}