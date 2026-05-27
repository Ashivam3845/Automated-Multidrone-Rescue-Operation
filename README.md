# Automated Multidrone Rescue Operation (Jatayu Engine)

An advanced, real-time Multi-Agent Drone Swarm Orchestration Engine Simulation. This project simulates an autonomous drone swarm executing search and rescue operations across a probabilistic grid, featuring complex battery economics, A* pathfinding, and dynamic multi-drone dispatching.

## Features

- **Multi-Agent Orchestration**: The engine manages a swarm of independent drones. When a `Recon` drone's battery runs low, the base dispatches a replacement. When a target is found, a `Relief Supply` drone is instantly deployed to the exact coordinates.
- **Bayesian Log-Odds Search Grid**: The `Recon` drones utilize mathematical Path-Probability Weighted Grid Search (PPWGS) to autonomously map the most probable locations of anomalies.
- **A* Pathfinding & No-Fly Zones**: Drones dynamically route themselves through procedurally generated obstacle fields (No-Fly Zones).
- **Live Recon Intelligence**: When a drone successfully navigates to a thermal anomaly, it captures a synthetic "photograph" of the target (e.g. Forest FLIR, Urban Thermal) and beams it back to the command center.
- **Real-Time WebSockets**: The Python FastAPI backend streams simulation telemetry at 2Hz directly to the React frontend.
- **Cyberpunk Tactical UI**: A stunning React/Vite dashboard featuring glowing neon aesthetics, smooth Canvas interpolations, and live `recharts` telemetry graphs tracking swarm battery and utility decision states.

## Architecture

* **Backend (`/backend`)**: Python, FastAPI, WebSockets, Numpy. Contains the `JatayuReasoningEngine` which runs the autonomous logic loop.
* **Frontend (`/frontend`)**: React, Vite, Canvas API, Recharts, es-toolkit. Renders the tactical map and multi-agent dashboard.

## Installation & Setup

### 1. Backend Setup
Navigate into the `backend` directory, install dependencies, and start the FastAPI server:
```bash
cd backend
pip install fastapi uvicorn websockets numpy
uvicorn server:app --reload
```
The server will start on `http://127.0.0.1:8000` with the WebSocket endpoint at `/ws`.

### 2. Frontend Setup
Open a new terminal, navigate to the `frontend` directory, install the Node dependencies, and start the Vite development server:
```bash
cd frontend
npm install
npm run dev
```
The dashboard will usually be available at `http://localhost:5174` (check your terminal output).

## Usage
1. Open the frontend in your browser.
2. Click **Play** in the Jatayu Swarm controls panel to start the engine.
3. **Inject Anomalies**: Click anywhere on the dark grid map to simulate a thermal anomaly.
4. Watch the Swarm autonomously dispatch drones, pathfind around obstacles, manage their battery SoC (State of Charge), and deploy Relief Supply drones upon target acquisition!
