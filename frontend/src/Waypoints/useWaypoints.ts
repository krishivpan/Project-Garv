import { useState } from 'react';

export type Waypoint = {
    id: string  // crypto.randomUUID(): a stable React key, so it never keys by array index
    lat: number  // latitude
    lon: number  // longitude
    alt_m: number  // altitude in meters
};

const DEFAULT_ALT_M = 10;  // the number of meters above home for new waypoints


export function useWaypoints() {
    const [waypoints, setWaypoints] = useState<Waypoint[]>([]);

    function addWaypoint(lat: number, lon: number) {
        setWaypoints(old => [
            ...old, 
            {
                id: crypto.randomUUID(),
                lat: lat,
                lon: lon,
                alt_m: DEFAULT_ALT_M,
            },
        ]);
    }

    function moveWaypoint(id: string, lat: number, lon: number) {
        setWaypoints(old => 
            old.map(waypoint => waypoint.id === id ? {...waypoint, lat: lat, lon: lon} : waypoint)
        );
    }

    function setAltitude(id: string, alt_m: number) {
        setWaypoints(old => 
            old.map(waypoint => waypoint.id === id ? {...waypoint, alt_m: alt_m} : waypoint)
        )
    }

    function removeWaypoint(id: string) {
        setWaypoints(old => 
            old.filter(waypoint => waypoint.id !== id)
        )
    }

    function clearWaypoints() {
        setWaypoints([])
    }

    return { waypoints, addWaypoint, moveWaypoint, setAltitude, removeWaypoint, clearWaypoints };

}
