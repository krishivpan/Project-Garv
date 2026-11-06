"""FastAPI app: starts the MAVLink reader and serves the state to the browser."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.mavlink_link import get_state_dict, start_reader, submit_mission
from app.mission import MAX_ALT_M, MAX_WAYPOINTS, MIN_ALT_M, build_mission_items, check_mission

SEND_INTERVAL_S = 0.2  # 5 updates per second to each browser
GPS_3D_FIX = 3         # GPS_RAW_INT fix_type for a 3D fix


# The JSON shape POST /api/mission accepts. FastAPI checks every request
# against these and replies 422 with the reason if something doesn't fit.
# allow_inf_nan=False: Python's JSON reader accepts NaN and Infinity, which
# must never reach the drone.
class WaypointIn(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    alt_m: float = Field(ge=MIN_ALT_M, le=MAX_ALT_M, allow_inf_nan=False)


class MissionIn(BaseModel):
    waypoints: list[WaypointIn] = Field(min_length=1, max_length=MAX_WAYPOINTS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code before "yield" runs once when the server starts.
    start_reader()
    yield


app = FastAPI(lifespan=lifespan)

# Let the Vite dev server (and nothing else) call our HTTP routes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    # The browser sends JSON with a Content-Type header, which needs allowing.
    allow_headers=["Content-Type"],
)


@app.get("/api/state")
def read_state():
    """The current state as JSON, handy for checking things in a browser."""
    return get_state_dict()


@app.post("/api/mission", status_code=202)
def upload(mission: MissionIn):
    """Queue a mission for upload. 202 means "accepted, not finished yet":
    the result appears later as mission_status in the telemetry.

    409 = the drone isn't in a state to accept a mission right now.
    422 = the mission itself is unsafe or malformed.
    """
    drone = get_state_dict()
    if drone["link"] != "ok":
        raise HTTPException(status_code=409, detail="No link to the drone")
    # "is not False" also refuses None: if we don't know, assume armed.
    if drone["armed"] is not False:
        raise HTTPException(status_code=409, detail="Drone is armed (or its state is unknown). Disarm before uploading")
    if drone["lat"] is None or drone["lon"] is None:
        raise HTTPException(status_code=409, detail="Drone position unknown")
    if drone["gps_fix"] is None or drone["gps_fix"] < GPS_3D_FIX:
        raise HTTPException(status_code=409, detail="Drone needs a 3D GPS fix")

    waypoints = [wp.model_dump() for wp in mission.waypoints]
    problems = check_mission(waypoints, drone["lat"], drone["lon"])
    if problems:
        raise HTTPException(status_code=422, detail="; ".join(problems))

    if not submit_mission(build_mission_items(waypoints)):
        raise HTTPException(status_code=409, detail="An upload is already in progress")
    return {"status": "uploading"}


@app.websocket("/ws/telemetry")
async def telemetry(websocket: WebSocket):
    """Each connected browser gets its own copy of this loop."""
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(get_state_dict())
            await asyncio.sleep(SEND_INTERVAL_S)
    except WebSocketDisconnect:
        # The browser closed the tab or the connection dropped.
        # Returning ends this client's loop; other clients are unaffected.
        pass
