import asyncio
import math
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from engine import JatayuReasoningEngine, ProbabilisticOccupancyGrid, State

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

grid = None
engine = None
drone_state = None
is_playing = False
last_latency = 0

def init_simulation():
    global grid, engine, drone_state, is_playing, last_latency
    grid = ProbabilisticOccupancyGrid(size_km=5, resolution_m=100)
    engine = JatayuReasoningEngine(grid)
    drone_state = State(base_x=0, base_y=0)
    is_playing = False
    last_latency = 0

init_simulation()

def get_state_payload():
    prob_grid = 1.0 / (1.0 + np.exp(-grid.grid))
    
    return {
        "drones": [
            {
                "id": d.id,
                "type": d.type,
                "x": d.x,
                "y": d.y,
                "soc": d.soc,
                "action": d.action,
                "trail": d.trail,
                "distance_to_base": math.hypot(d.x - drone_state.base_x, d.y - drone_state.base_y),
                "utilities": d.utilities
            } for d in drone_state.drones
        ],
        "base_x": drone_state.base_x,
        "base_y": drone_state.base_y,
        "anomalies": drone_state.anomalies,
        "logs": drone_state.logs,
        "grid": prob_grid.tolist(),
        "obstacles": grid.obstacles.tolist(),
        "grid_resolution": grid.resolution,
        "grid_size_m": grid.size_m,
        "latency_ms": last_latency
    }

async def simulation_loop(websocket: WebSocket):
    global is_playing, last_latency
    import time
    while True:
        if is_playing:
            t0 = time.time()
            engine.step(drone_state, dt=1.0)
            last_latency = (time.time() - t0) * 1000
            await websocket.send_json({"type": "state", "data": get_state_payload()})
        await asyncio.sleep(0.5) # 500ms real-time step

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global is_playing
    await websocket.accept()
    
    # Send initial state
    await websocket.send_json({"type": "state", "data": get_state_payload()})
    
    # Start simulation loop for this client
    loop_task = asyncio.create_task(simulation_loop(websocket))
    
    try:
        while True:
            data = await websocket.receive_json()
            cmd = data.get("action")
            
            if cmd == "play":
                is_playing = True
            elif cmd == "pause":
                is_playing = False
            elif cmd == "step":
                engine.step(drone_state, dt=1.0)
                await websocket.send_json({"type": "state", "data": get_state_payload()})
            elif cmd == "reset":
                init_simulation()
                await websocket.send_json({"type": "state", "data": get_state_payload()})
            elif cmd == "inject":
                x = data.get("x")
                y = data.get("y")
                priority = data.get("priority", 0.95)
                drone_state.anomalies.append({
                    "x": x,
                    "y": y,
                    "priority": priority,
                    "status": "active"
                })
                # Add strong log odds
                grid_x = int(x / grid.resolution)
                grid_y = int(y / grid.resolution)
                if 0 <= grid_x < grid.grid_size and 0 <= grid_y < grid.grid_size:
                    grid.update_log_odds(grid_x, grid_y, 0.95)
                await websocket.send_json({"type": "state", "data": get_state_payload()})
                
    except WebSocketDisconnect:
        loop_task.cancel()
        print("Client disconnected")

@app.get("/state")
def get_state():
    return get_state_payload()
