"""FastAPI app: starts the MAVLink reader and serves the state to the browser."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.mavlink_link import get_state_dict, start_reader, submit_mission
from app.mission import build_mission_items

SEND_INTERVAL_S = 0.2  # 5 updates per second to each browser
MIN_ALT_M = 1    # waypoint altitude limits, metres above home
MAX_ALT_M = 120


# The JSON shape POST /api/mission accepts. FastAPI checks every request
# against these and replies 422 with the reason if something doesn't fit.
class WaypointIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    alt_m: float = Field(ge=MIN_ALT_M, le=MAX_ALT_M)


class MissionIn(BaseModel):
    waypoints: list[WaypointIn] = Field(min_length=1)


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
    the result appears later as mission_status in the telemetry."""
    if get_state_dict()["link"] != "ok":
        raise HTTPException(status_code=409, detail="No link to the drone")
    items = build_mission_items([wp.model_dump() for wp in mission.waypoints])
    if not submit_mission(items):
        raise HTTPException(status_code=409, detail="An upload is already running")
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
