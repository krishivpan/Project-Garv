import { useEffect, useState } from 'react'

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
