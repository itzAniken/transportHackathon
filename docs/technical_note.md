# Technical Note: Delhi Bus Traffic Model & Journey Planner

**Transport Stack Hackathon 2026 / Phase 1**  
**Author:** Engineering Team  

---

## 1. Network Representation & Map-Matching Architecture

### The Problem with Generic Road Map-Matching
Typical transportation models project bus GPS pings onto generic OpenStreetMap (OSM) road networks. In Delhi, this approach introduces severe errors:
1. Buses often run on dedicated Bus Rapid Transit (BRT) lanes, service roads, or elevated flyovers where road geometry diverges from public map edges.
2. DTC buses follow strict GTFS route shapes (`shapes.txt`) and stop sequences (`stop_times.txt`).

### Our Approach: Shape-Constrained Linear Referencing
Instead of arbitrary road network matching, we map-match bus GPS pings directly to **GTFS route shape polylines**:
1. **Corridor Bounding & Noise Cleansing**:
   - Filter pings outside the Delhi NCR bounding box ($28.30^\circ\text{N} \le \text{lat} \le 28.95^\circ\text{N}$, $76.80^\circ\text{E} \le \text{lon} \le 77.45^\circ\text{E}$).
   - Discard unphysical speeds ($v < 0$ or $v > 90\text{ km/h}$) and non-monotonic timestamps per `vehicle_id`.
2. **Linear Referencing onto Route Polylines**:
   - For each bus ping $P = (\text{lat}, \text{lon})$ assigned to `route_id`, compute its orthogonal projection onto the route's 2D piecewise linear polyline $\mathcal{L}_r$.
   - This assigns each ping a scalar position $L \in [0, \text{Length}(\mathcal{L}_r)]$ in meters along the route.
3. **Stop-to-Stop Segment Extraction**:
   - GTFS stops $S_1, S_2, \dots, S_N$ define contiguous directed segments $(S_k, S_{k+1})$.
   - Consecutive GPS pings with linear coordinates $L(S_k) \le L \le L(S_{k+1})$ yield the actual traversal duration $\Delta t = t(S_{k+1}) - t(S_k)$.

---

## 2. Decomposing Running Time vs. Stop Dwell Time

Buses in Delhi experience two distinct delays:
1. **Running Delay (Link Congestion)**: Slow vehicle speed due to roadway traffic and intersection signals.
2. **Dwell Delay (Boarding & Alighting)**: Stationary time spent at official stops while passengers board.

$$T_{\text{segment}}(S_i, S_j) = T_{\text{run}}(S_i, S_j) + T_{\text{dwell}}(S_i)$$

### Dwell Time Extraction ($T_{\text{dwell}}$)
- For every stop $S_i$, we define a spatial buffer of radius $R_{\text{dwell}} = 35\text{ meters}$.
- When a bus enters this buffer with speed $v < 3\text{ km/h}$, dwell time is measured as:
  $$T_{\text{dwell}} = \min\left(300\text{ s}, \max(0, t_{\text{exit}} - t_{\text{enter}})\right)$$
- Dwell times are aggregated by `(stop_id, hour_of_day)`. Terminals (e.g., Kashmere Gate ISBT, Nehru Place, Anand Vihar) exhibit high dwell during peak hours ($45\text{–}60\text{ s}$), whereas intermediate stops average $15\text{–}25\text{ s}$.

### Running Speed Estimation ($T_{\text{run}}$)
- Link running time is determined strictly from in-motion progress between stops:
  $$v_{\text{run}} = \frac{d(S_i, S_{j})}{T_{\text{segment}} - T_{\text{dwell}}}$$

---

## 3. Handling Data Sparsity: Hierarchical Shrinkage Model

A core failure mode of naive empirical averages is data sparsity: certain routes or outer-ring road segments have few or no bus trips during late night (e.g., 2:00 AM) or midday troughs.

To guarantee robust predictions under sparse or missing data, we implement a **4-Tier Hierarchical Bayesian Shrinkage Model**:

$$\hat{v}(S, d, h) = w_1 \bar{v}_{\text{segment}}(S, d, h) + w_2 \bar{v}_{\text{route}}(r, d, h) + w_3 \bar{v}_{\text{city}}(d, h) + w_4 v_{\text{scheduled}}$$

- **Tier 1 (Segment-Level)**: If observed sample size $N_{\text{seg}} \ge 5$, empirical segment speed is prioritized.
- **Tier 2 (Route Corridor)**: If $N_{\text{seg}} < 5$, borrow strength from the overall route corridor speed at that hour.
- **Tier 3 (City-Wide Hourly Prior)**: If route data is absent, utilize the empirical Delhi hourly traffic curve (e.g., 8:30 AM city speed $\approx 13.5\text{ km/h}$, 11:00 PM $\approx 27.5\text{ km/h}$).
- **Tier 4 (Static GTFS Timetable)**: Absolute fallback if historical data is completely unavailable.

---

## 4. Combining Live (GTFS-RT) and Historical Data

When real-time GTFS-RT vehicle position updates are ingested, the system computes a corridor-level **Live Congestion Ratio**:

$$\alpha_r(t) = \frac{\bar{v}_{\text{live}}(r, t)}{\bar{v}_{\text{hist}}(r, \text{hour})}$$

- The dynamic travel time prediction blends the historical prior with the live signal using an exponential / Kalman filter weighting:
  $$v_{\text{dynamic}} = \lambda \cdot v_{\text{live}} + (1 - \lambda) \cdot \hat{v}_{\text{historical}}$$
- If a route experiences sudden gridlock (e.g., $\alpha = 0.6$), downstream segment speeds are throttled accordingly. If live pings fail to arrive, the model gracefully relaxes $\lambda \to 0$ without disruption.

---

## 5. Transit Journey Planning Engine: RAPTOR

Instead of expanding large time-dependent graphs with Dijkstra or A*, we implemented **RAPTOR (Round-Based Public Transit Routing)**:
- **Round 0**: Discover candidate boarding stops within walking distance ($R_{\text{walk}} \le 800\text{ m}$) from origin coordinates.
- **Round 1 (Direct Trips)**: Traverse all routes serving boarding stops; update earliest arrival times at destination stops using our **Dynamic Speed Matrix**.
- **Round 2 (1-Transfer Trips)**: Transfer at intersecting hubs (e.g., Mandi House, Lajpat Nagar, AIIMS) to evaluate transfer journeys.
- **Last Mile**: Compute walking duration ($v_{\text{walk}} = 1.1\text{ m/s}$) to exact destination coordinates.
- **Quiet-Hour Baseline**: Concurrently re-evaluates the chosen journey under free-flow conditions ($h=23$) to explicitly compute and report the **Traffic Delay Penalty ($\Delta T_{\text{traffic}}$)** to the commuter.
