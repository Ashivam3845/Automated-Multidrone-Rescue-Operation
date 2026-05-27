import numpy as np
import math
import time
import heapq

# --- A* Pathfinding Helper ---
def astar_path(start, goal, obstacles):
    # Returns (cost, path_nodes)
    grid_size = obstacles.shape[0]
    
    def heuristic(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])
        
    frontier = []
    heapq.heappush(frontier, (0, start))
    came_from = {start: None}
    cost_so_far = {start: 0}
    
    while frontier:
        _, current = heapq.heappop(frontier)
        
        if current == goal:
            break
            
        for dx, dy in [(0,1), (1,0), (0,-1), (-1,0), (1,1), (-1,1), (1,-1), (-1,-1)]:
            nx, ny = current[0] + dx, current[1] + dy
            if 0 <= nx < grid_size and 0 <= ny < grid_size:
                if obstacles[nx, ny]:
                    continue
                step_cost = math.hypot(dx, dy)
                new_cost = cost_so_far[current] + step_cost
                next_node = (nx, ny)
                if next_node not in cost_so_far or new_cost < cost_so_far[next_node]:
                    cost_so_far[next_node] = new_cost
                    priority = new_cost + heuristic(goal, next_node)
                    heapq.heappush(frontier, (priority, next_node))
                    came_from[next_node] = current
                    
    if goal not in came_from:
        return float('inf'), []
        
    # Reconstruct path
    curr = goal
    path = []
    while curr != start:
        path.append(curr)
        curr = came_from[curr]
    path.reverse()
    return cost_so_far[goal], path


class DroneState:
    def __init__(self, id_str, drone_type, x, y, soc):
        self.id = id_str
        self.type = drone_type # 'recon' or 'relief'
        self.x = x
        self.y = y
        self.soc = soc
        self.trail = []
        self.action = "Standby"
        self.last_action = None
        self.committed_target = None
        self.utilities = {}
        self.latency_ms = 0.0

class State:
    def __init__(self, base_x, base_y):
        self.base_x = base_x
        self.base_y = base_y
        self.drones = []
        self.anomalies = []
        self.logs = []
        self.drone_counter = 0
        self.spawn_drone('recon', base_x, base_y, 1.0)
        
    def spawn_drone(self, drone_type, x, y, soc):
        d = DroneState(f"drone_{self.drone_counter}", drone_type, x, y, soc)
        self.drones.append(d)
        self.drone_counter += 1
        self.log(f"[SYS] Spawned {drone_type.upper()} {d.id}")
        return d
        
    def log(self, message):
        self.logs.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        if len(self.logs) > 50:
            self.logs.pop(0)

class ProbabilisticOccupancyGrid:
    def __init__(self, size_km=5, resolution_m=100):
        self.size_m = size_km * 1000
        self.resolution = resolution_m
        self.grid_size = int(self.size_m / self.resolution)
        
        prior_prob = 0.1
        self.prior_log_odds = np.log(prior_prob / (1.0 - prior_prob))
        self.grid = np.full((self.grid_size, self.grid_size), self.prior_log_odds)
        
        self.obstacles = np.zeros((self.grid_size, self.grid_size), dtype=bool)
        np.random.seed(42)
        for _ in range(8):
            ox = np.random.randint(5, self.grid_size - 5)
            oy = np.random.randint(5, self.grid_size - 5)
            w = np.random.randint(2, 8)
            h = np.random.randint(2, 8)
            if ox < 10 and oy < 10: continue
            self.obstacles[ox:ox+w, oy:oy+h] = True
            
        self.grid[self.obstacles] = np.log(1e-5 / (1.0 - 1e-5))

    def update_log_odds(self, grid_x, grid_y, prob_measurement):
        if self.obstacles[grid_x, grid_y]: return
        prob_measurement = np.clip(prob_measurement, 1e-5, 1 - 1e-5)
        log_odds_update = np.log(prob_measurement / (1.0 - prob_measurement))
        self.grid[grid_x, grid_y] += log_odds_update

class JatayuReasoningEngine:
    def __init__(self, grid):
        self.grid = grid
        self.weights = {'rtb': 1.0, 'search': 1.0, 'investigate': 1.5}
        
        # 5000 meters (5km) takes exactly 0.50 (50%) battery
        self.base_energy_drain = 0.50 / 5000.0  # 0.0001
        
        # Reduce buffers so the drone doesn't RTB too early and can explore the far corners
        self.safe_soc_margin = 0.05 
        self.wind_vector = (1.5, 0.5) 
        
    def get_effective_drain(self, heading_x, heading_y):
        mag = math.hypot(heading_x, heading_y)
        if mag == 0: return self.base_energy_drain
        nx, ny = heading_x / mag, heading_y / mag
        
        dot = nx * self.wind_vector[0] + ny * self.wind_vector[1]
        wind_factor = 1.0 - (dot * 0.05) 
        return max(0.00005, self.base_energy_drain * wind_factor)

    def calculate_path_and_dist(self, start_m, target_m):
        sx = int(start_m[0] / self.grid.resolution)
        sy = int(start_m[1] / self.grid.resolution)
        tx = int(target_m[0] / self.grid.resolution)
        ty = int(target_m[1] / self.grid.resolution)
        
        sx = np.clip(sx, 0, self.grid.grid_size-1)
        sy = np.clip(sy, 0, self.grid.grid_size-1)
        tx = np.clip(tx, 0, self.grid.grid_size-1)
        ty = np.clip(ty, 0, self.grid.grid_size-1)
        
        cost, path = astar_path((sx, sy), (tx, ty), self.grid.obstacles)
        if cost == float('inf'):
            return float('inf'), []
        return cost * self.grid.resolution, path

    def U_RTB(self, state, drone):
        dist, _ = self.calculate_path_and_dist((drone.x, drone.y), (state.base_x, state.base_y))
        if dist == float('inf'): return 0.0
        
        worst_drain = self.base_energy_drain * 1.2
        required_soc = dist * worst_drain
        buffer_soc = drone.soc - required_soc - self.safe_soc_margin
        
        if buffer_soc <= 0: return 10000.0 
        return np.exp(-20 * buffer_soc)
        
    def U_Investigate(self, drone, target_x, target_y, priority):
        dist, _ = self.calculate_path_and_dist((drone.x, drone.y), (target_x, target_y))
        if dist == float('inf'): return 0.0
        if dist < 10: return priority * 100000.0 
        
        # Base utility of 100 guarantees it will always beat Search (which caps around 5.0).
        # Adding (10000 / dist) ensures that if multiple anomalies exist, the nearest one always wins.
        return 100.0 + ((priority * 10000.0) / dist)
        
    def evaluate_ppwgs_search(self, drone):
        current_grid_x = int(drone.x / self.grid.resolution)
        current_grid_y = int(drone.y / self.grid.resolution)
        
        best_util = 0.0
        best_target = None
        search_radius = 10 
        
        x_min = max(0, current_grid_x - search_radius)
        x_max = min(self.grid.grid_size, current_grid_x + search_radius + 1)
        y_min = max(0, current_grid_y - search_radius)
        y_max = min(self.grid.grid_size, current_grid_y + search_radius + 1)
        
        subgrid_log_odds = self.grid.grid[x_min:x_max, y_min:y_max]
        subgrid_probs = 1.0 / (1.0 + np.exp(-subgrid_log_odds))

        for i in range(x_min, x_max):
            for j in range(y_min, y_max):
                if self.grid.obstacles[i, j]: continue
                if i == current_grid_x and j == current_grid_y: continue
                    
                poc = subgrid_probs[i - x_min, j - y_min]
                dist = math.hypot(drone.x - (i * self.grid.resolution), drone.y - (j * self.grid.resolution))
                
                path_weighted_utility = poc / (dist + 1.0)
                if path_weighted_utility > best_util:
                    best_util = path_weighted_utility
                    best_target = (i * self.grid.resolution + self.grid.resolution/2, j * self.grid.resolution + self.grid.resolution/2)
                    
        return best_util * 5000, best_target

    def decide_recon_action(self, state, drone):
        start_time = time.time()
        utilities = {}
        
        utilities['RTB'] = self.weights['rtb'] * self.U_RTB(state, drone)
        
        for i, anomaly in enumerate(state.anomalies):
            if anomaly.get('status', 'active') == 'active':
                util = self.weights['investigate'] * self.U_Investigate(drone, anomaly['x'], anomaly['y'], anomaly['priority'])
                utilities[f'Investigate_Anomaly_{i}'] = util
            
        best_search_util, best_sector = self.evaluate_ppwgs_search(drone)
        if best_sector: utilities['Search'] = self.weights['search'] * best_search_util
        else: utilities['Search'] = 0.0
            
        best_action = max(utilities, key=utilities.get)
        
        target_coords = None
        if best_action == 'RTB': 
            target_coords = (state.base_x, state.base_y)
        elif best_action == 'Search':
            # Anti-thrashing commitment
            if drone.last_action == 'Search' and drone.committed_target is not None:
                dist_to_committed = math.hypot(drone.committed_target[0] - drone.x, drone.committed_target[1] - drone.y)
                if dist_to_committed > self.grid.resolution:
                    target_coords = drone.committed_target
                else:
                    target_coords = best_sector
                    drone.committed_target = best_sector
            else:
                target_coords = best_sector
                drone.committed_target = best_sector
        elif best_action.startswith('Investigate'):
            idx = int(best_action.split('_')[-1])
            if idx < len(state.anomalies):
                target_coords = (state.anomalies[idx]['x'], state.anomalies[idx]['y'])
                
        drone.latency_ms = (time.time() - start_time) * 1000
        drone.utilities = utilities
        
        if drone.last_action != best_action:
            if best_action == 'RTB' and utilities.get('RTB', 0) > 1000:
                state.log(f"[WARN] {drone.id} Bingo Fuel. Returning to base.")
                # Orchestration: Launch secondary recon if this is the only active one
                active_recons = [d for d in state.drones if d.type == 'recon' and d.action != 'RTB' and d.id != drone.id]
                if len(active_recons) == 0:
                    state.spawn_drone('recon', state.base_x, state.base_y, 1.0)
            else:
                state.log(f"[{drone.id}] Action shifted to: {best_action}")
            drone.last_action = best_action
            
        drone.action = best_action
        return target_coords

    def step(self, state, dt=1.0):
        # Update anomalies decay
        for anomaly in state.anomalies:
            if anomaly['status'] == 'active':
                anomaly['priority'] -= 0.005 * dt 
                if anomaly['priority'] < 0.1:
                    anomaly['status'] = 'decayed'

        drones_to_remove = []
        
        # Process each drone
        for drone in state.drones:
            target_coords = None
            speed = 25.0 
            
            if drone.type == 'recon':
                target_coords = self.decide_recon_action(state, drone)
            elif drone.type == 'relief':
                speed = 35.0 # Relief drones are faster
                # If it has a committed target, go there. Otherwise RTB.
                if drone.committed_target:
                    target_coords = drone.committed_target
                    drone.action = "Delivering Supply"
                else:
                    target_coords = (state.base_x, state.base_y)
                    drone.action = "RTB"

            # Move Drone
            distance_to_move = speed * dt
            
            if len(drone.trail) == 0 or math.hypot(drone.x - drone.trail[-1][0], drone.y - drone.trail[-1][1]) > 10.0:
                drone.trail.append((drone.x, drone.y))
                if len(drone.trail) > 50:
                    drone.trail.pop(0)
            
            if target_coords:
                dist_to_target, path = self.calculate_path_and_dist((drone.x, drone.y), target_coords)
                
                if dist_to_target > 0 and len(path) > 0:
                    next_node = path[0]
                    tx = next_node[0] * self.grid.resolution + self.grid.resolution/2
                    ty = next_node[1] * self.grid.resolution + self.grid.resolution/2
                    
                    node_dist = math.hypot(tx - drone.x, ty - drone.y)
                    if node_dist < speed * dt and len(path) > 1:
                        next_node = path[1]
                        tx = next_node[0] * self.grid.resolution + self.grid.resolution/2
                        ty = next_node[1] * self.grid.resolution + self.grid.resolution/2
                else:
                    tx, ty = target_coords

                local_dist = math.hypot(tx - drone.x, ty - drone.y)
                if local_dist > 0:
                    move_dist = min(distance_to_move, local_dist)
                    dx = (tx - drone.x) / local_dist
                    dy = (ty - drone.y) / local_dist
                    
                    drone.x += dx * move_dist
                    drone.y += dy * move_dist
                    drain = self.get_effective_drain(dx, dy)
                    drone.soc -= move_dist * drain
                    
            # Post-move grid tracking
            current_grid_x = int(drone.x / self.grid.resolution)
            current_grid_y = int(drone.y / self.grid.resolution)
            current_grid_x = np.clip(current_grid_x, 0, self.grid.grid_size - 1)
            current_grid_y = np.clip(current_grid_y, 0, self.grid.grid_size - 1)
            
            # Recon-specific interaction
            if drone.type == 'recon':
                if drone.action == 'Search':
                    self.grid.update_log_odds(current_grid_x, current_grid_y, 0.05)
                    
                if drone.action.startswith('Investigate'):
                     idx = int(drone.action.split('_')[-1])
                     anomaly = state.anomalies[idx]
                     if anomaly['status'] == 'active':
                         dist_to_anom = math.hypot(anomaly['x'] - drone.x, anomaly['y'] - drone.y)
                         if dist_to_anom < 100.0:
                             state.log(f"[NAV] {drone.id} Reached Anomaly {idx}. Verifying...")
                             anomaly['status'] = 'resolved'
                             if 'image_url' not in anomaly:
                                 anomaly['image_url'] = f'/recon/recon_{np.random.randint(0, 3)}.png'
                                 anomaly['resolved_at'] = time.time()
                             self.grid.update_log_odds(current_grid_x, current_grid_y, 0.99)
                             # Orchestration: Spawn Relief Drone!
                             rd = state.spawn_drone('relief', state.base_x, state.base_y, 1.0)
                             rd.committed_target = (anomaly['x'], anomaly['y'])
                     
                # Recharge if at base
                if math.hypot(state.base_x - drone.x, state.base_y - drone.y) < 50.0:
                    if drone.soc < 0.95:
                        drone.soc = 1.0
                        state.log(f"[SYS] {drone.id} recharged at base.")
                        
            # Relief-specific interaction
            elif drone.type == 'relief':
                if drone.action == 'Delivering Supply':
                    dist_to_target = math.hypot(drone.committed_target[0] - drone.x, drone.committed_target[1] - drone.y)
                    if dist_to_target < 50.0:
                        state.log(f"[RELIEF] {drone.id} dropped supplies at target! RTB.")
                        drone.committed_target = None # Trigger RTB
                elif drone.action == 'RTB':
                    dist_to_base = math.hypot(state.base_x - drone.x, state.base_y - drone.y)
                    if dist_to_base < 50.0:
                        state.log(f"[RELIEF] {drone.id} safely returned and despawned.")
                        drones_to_remove.append(drone)

        for d in drones_to_remove:
            state.drones.remove(d)

        return

def run_simulation():
    grid = ProbabilisticOccupancyGrid(size_km=5, resolution_m=100)
    engine = JatayuReasoningEngine(grid)
    state = State(base_x=0, base_y=0)
    engine.step(state)

if __name__ == '__main__':
    run_simulation()
