from pymavlink import mavutil
from fastapi import FastAPI, WebSocket
import asyncio
import json
import time

app = FastAPI()
master = mavutil.mavlink_connection('udpin:127.0.0.1:14552')

master.wait_heartbeat()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Frontend connected!")

    try:
        while True:
            position = master.recv_match(type='GLOBAL_POSITION_INT', blocking=False)

            if position:
                data = {"message": position.relative_alt / 1000}
                await websocket.send_text(json.dumps(data))

            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"Connection closed: {e}")
