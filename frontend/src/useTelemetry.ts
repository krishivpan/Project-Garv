import { useEffect, useState } from 'react'

// The mission last read back from the drone (backend: mission.summarize).
// standard = shaped like ours: takeoff, waypoints, return home.
export type DroneMission = {
  waypoints: { lat: number; lon: number; alt_m: number }[]
  standard: boolean
  item_count: number // includes the home item
}

// Same keys as the backend's JSON. null means "unknown".
export type Telemetry = {
  armed: boolean | null
  mode: string | null
  lat: number | null
  lon: number | null
  alt_rel_m: number | null
  heading_deg: number | null
  groundspeed_ms: number | null
  battery_v: number | null
  battery_pct: number | null
  gps_fix: number | null
  satellites: number | null
  mission_status: string // "idle", "uploading", "verifying", "ok" or "failed: <reason>"
  drone_mission: DroneMission | null // null = we don't know what's on the drone
  // Mission progress as seq numbers (seq 0 = home). Don't turn these into
  // waypoint numbers here; use the *_waypoint_index fields below.
  mission_count: number | null // items on the drone, including home
  mission_current: number | null // seq the drone is working on
  last_reached: number | null // seq the drone last finished
  // The same progress as indexes into the map's waypoint list (0 = first
  // waypoint), worked out by the backend. null when not on a waypoint
  // (takeoff, return home) or the drone's mission isn't in our layout.
  current_waypoint_index: number | null
  last_reached_waypoint_index: number | null
  commands_enabled: boolean // COMMANDS_ENABLED in backend/.env
  link: 'waiting' | 'ok' | 'lost'
}

const TELEMETRY_URL = 'ws://localhost:8000/ws/telemetry'
const RECONNECT_DELAY_MS = 2000

// Keeps a WebSocket open to the backend and returns the latest telemetry,
// plus whether the WebSocket itself is currently connected.
export function useTelemetry() {
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    let socket: WebSocket
    let retryTimer: ReturnType<typeof setTimeout> | undefined
    let stopped = false // set when the component unmounts

    function connect() {
      socket = new WebSocket(TELEMETRY_URL)
      socket.onopen = () => setConnected(true)
      socket.onmessage = (event) => setTelemetry(JSON.parse(event.data))
      // onclose fires when the connection drops or fails to open at all
      // (a failure fires onerror first, then onclose), so retry from here.
      socket.onclose = () => {
        setConnected(false)
        if (!stopped) retryTimer = setTimeout(connect, RECONNECT_DELAY_MS)
      }
    }

    connect()

    // Cleanup: stop retrying and close the socket when the page goes away.
    return () => {
      stopped = true
      clearTimeout(retryTimer)
      socket.close()
    }
  }, []) // [] = run once when the component first appears

  return { telemetry, connected }
}
