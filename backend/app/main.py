"""FastAPI app: starts the MAVLink reader and serves the state to the browser."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.mavlink_link import get_state_dict, start_reader

SEND_INTERVAL_S = 0.2  # 5 updates per second to each browser


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
    allow_methods=["GET"],
)


@app.get("/api/state")
def read_state():
    """The current state as JSON, handy for checking things in a browser."""
    return get_state_dict()


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
