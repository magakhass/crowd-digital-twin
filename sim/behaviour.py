"""How simulated people head for a gate and get out of gridlocks.

Shared by the venue runs (sim/run_sim.py) and the calibration runs on the Jülich experiments
(sim/calibrate_avm.py), so the settings we calibrate are the ones we use. The geometry is always
oriented so that people leave in the +x direction through gates spanning y = lo..hi at x = gate_x.
A venue can have several gates (each with its own exit); everyone is given one of them.
"""
import jupedsim as jps
import numpy as np
from shapely.geometry import Point

DT = 0.05
# AVM parameters validated by Xu, Chraibi and Seyfried (2021, Transp. Res. C), Table 3, unchanged: the
# Jülich bottleneck runs are used to test them, not tune them (evidence log D5)
AVM = dict(radius=0.18, strength_neighbor_repulsion=6.0, range_neighbor_repulsion=0.01,
           reaction_time=0.3, anticipation_time=0.75)
TIME_GAP = 0.5
COUNTERFLOW_EXTRA = 0.1  # s: longer time gap with people walking against the flow (0.6 in Xu et al.)
LANES = 5            # people aim at one of these points spread across the gate, not its centre
LANE_MARGIN = 0.4    # m: no gate points closer than this to the gate's sides
STUCK_CHECK = 2.0    # s: how often we look for people who have set off but are not moving
STUCK_WINDOW = 4.0   # s: moved less than STUCK_MOVE over this long counts as stuck
STUCK_MOVE = 0.1     # m
SIDESTEP = 1.5       # m: in a head-on standoff a stuck person steps this far to their right
CORNER = 1.2         # m: a stuck person this close to a wall corner steps round it
ARRIVE_NEAR = 2.0    # m: an arriving person blocked this close to their spot just stands where they are
SETTLE_DEPTH = 3.0   # m: ...or anywhere at least this far into the hall
GIVE_UP = 5          # times stuck before an arriving person stands wherever they are


def desired_speed(rng):
    # free walking speed N(1.55, 0.18^2) m/s, as in Xu et al. (2021), from the Jülich corridor experiments
    # of Zhang et al. (2012); clipped to 0.8-2.2 m/s (ours)
    return float(np.clip(rng.normal(1.55, 0.18), 0.8, 2.2))


class Gate:
    """One way out: points spread across the gate at x, then the exit area behind it."""

    def __init__(self, sim, exit_id, x, lo, hi, corners):
        self.exit_id, self.x, self.axis, self.corners = exit_id, x, (lo + hi) / 2, corners
        self.lanes = []
        wide = hi - lo > 2 * LANE_MARGIN
        for y in np.linspace(lo + LANE_MARGIN, hi - LANE_MARGIN, LANES) if wide else [(lo + hi) / 2]:  # narrow gate: one point
            wp = sim.add_waypoint_stage((x, float(y)), 0.5)
            jd = jps.JourneyDescription([wp, exit_id])
            jd.set_transition_for_stage(wp, jps.Transition.create_fixed_transition(exit_id))
            self.lanes.append((sim.add_journey(jd), wp))


class Crowd:
    def __init__(self, sim, walkable, gates, rng, dt, bar_id=None, mouth=None, door=None):
        # gates: (exit stage, gate x, lo, hi, corners) per way out
        # mouth: (x, y, half width) where the entrance opens into the hall
        # door: (x from, x to, y, half width) of an entry checkpoint arrivals pass before heading to their spot
        self.sim, self.rng, self.bar_id = sim, rng, bar_id
        self.gates = [Gate(sim, *g) for g in gates]
        self.gate_of = {}  # person -> gate index (default 0)
        self.inner = walkable.buffer(-0.4)
        self.every = int(round(STUCK_CHECK / dt))
        self.door, self.via = door, {}  # arrivals still on their way through the checkpoint -> (stage, lane offset)
        self.moving, self.walking_in, self.hist, self.paused = set(), set(), {}, {}
        self.detours, self.detour_ids, self.unjams = {}, set(), 0
        self.spots, self.aside, self.settled = {}, {}, 0  # arrivals: where each is heading, sidestep end times
        self.times_stuck = {}
        self.mouth = mouth

    @property
    def lanes(self):
        return [ln for g in self.gates for ln in g.lanes]

    def arrive(self, aid, spot):
        """Someone who has just come in and walks to a standing spot (direct steering),
        through the checkpoint first if there is one."""
        if self.door:
            # line up in front of the checkpoint first (walking straight at it pins people on its corners)
            x0, _, dy, half = self.door
            off = float(self.rng.uniform(-half + 0.4, half - 0.4))
            self.sim.agent(aid).target = (x0 - 0.6, dy + off)
            self.via[aid] = (0, off)
        else:
            self.sim.agent(aid).target = spot
        self.spots[aid] = spot
        self.moving.add(aid)

    def through(self):
        """Checkpoint arrivals (every step): in front of it -> walk through -> head for their spot."""
        x0, x1, dy, half = self.door
        for aid, (stage, off) in list(self.via.items()):
            x = self.sim.agent(aid).position[0]
            if stage == 0 and x >= x0 - 1.0:
                self.sim.agent(aid).target = (x1 + 1.0, dy + off)
                self.via[aid] = (1, off)
            elif stage == 1 and x >= x1 - 0.2:
                del self.via[aid]
                if aid not in self.aside:
                    self.sim.agent(aid).target = self.spots[aid]

    def _settle(self, aid):
        a = self.sim.agent(aid)
        a.target = a.position  # stands where they are now
        a.model.desired_speed = 0.0
        self.paused.pop(aid, None)
        self.moving.discard(aid)
        self.spots.pop(aid, None)
        self.aside.pop(aid, None)
        self.settled += 1

    def _arrivals(self, aid, x, y, stuck, t):
        """Arrivals stand still at their spot, or close to it when the way is blocked; otherwise
        a stuck one gives way for a moment or steps to their right for a moment."""
        sx, sy = self.spots[aid]
        dist = np.hypot(sx - x, sy - y)
        mx, my, half = self.mouth
        if aid in self.via:  # still queueing for the checkpoint: nobody stops here for good
            if stuck and self.rng.random() < 0.5:
                m = self.sim.agent(aid).model
                self.paused[aid] = (t + STUCK_CHECK, m.desired_speed)
                m.desired_speed = 0.0
            return
        if stuck:
            self.times_stuck[aid] = self.times_stuck.get(aid, 0) + 1
        if dist < 0.5 or (stuck and (dist < ARRIVE_NEAR or x > mx + SETTLE_DEPTH or self.times_stuck[aid] >= GIVE_UP)):
            self._settle(aid)
            return
        if not stuck:
            return
        self.unjams += 1
        if x < mx + 0.5 and abs(y - my) > half - 1.2:
            # pinned on a corner of the entrance: step straight into the hall first
            self.sim.agent(aid).target = (mx + 1.0, my + float(np.sign(y - my)) * (half - 0.5))
            self.aside[aid] = t + STUCK_CHECK
            return
        if self.rng.random() < 0.5:
            m = self.sim.agent(aid).model
            self.paused[aid] = (t + STUCK_CHECK, m.desired_speed)
            m.desired_speed = 0.0
            return
        hx, hy = (sx - x) / dist, (sy - y) / dist
        for side in (1.0, -1.0):  # right first
            q = (x + 0.5 * hx + side * hy, y + 0.5 * hy - side * hx)
            if self.inner.contains(Point(q)):
                self.sim.agent(aid).target = q
                self.aside[aid] = t + STUCK_CHECK
                return

    def lane(self, g=0):
        lanes = self.gates[g].lanes
        return lanes[self.rng.integers(len(lanes))]

    def start(self, aid, inbound=False):
        self.moving.add(aid)
        if inbound:
            self.walking_in.add(aid)

    def _detour(self, q, inbound, g=0):
        gate = self.gates[g]
        lane = -1 if inbound else int(self.rng.integers(len(gate.lanes)))
        key = (q, g, lane)
        if key not in self.detours:
            wp = self.sim.add_waypoint_stage(q, 0.5)
            nxt = self.bar_id if inbound else gate.lanes[lane][1]
            jd = jps.JourneyDescription([wp, nxt] if inbound else [wp, nxt, gate.exit_id])
            jd.set_transition_for_stage(wp, jps.Transition.create_fixed_transition(nxt))
            if not inbound:
                jd.set_transition_for_stage(nxt, jps.Transition.create_fixed_transition(gate.exit_id))
            self.detours[key] = (self.sim.add_journey(jd), wp)
            self.detour_ids.add(self.detours[key][0])
        return self.detours[key]

    def unjam(self, iteration, t):
        """Gridlock breaker: a stuck person steps round a corner, steps right in a head-on standoff,
        or otherwise gives way for a moment / aims at another point of the gate."""
        if self.via:
            self.through()
        if iteration % self.every:
            return
        sim = self.sim
        present = {a.id: a.position for a in sim.agents()}
        self.moving &= present.keys()
        for aid in list(self.paused):
            if aid in present and t >= self.paused[aid][0]:
                sim.agent(aid).model.desired_speed = self.paused[aid][1]
                del self.paused[aid]
        for aid in [a for a, until in self.aside.items() if t >= until]:
            self.sim.agent(aid).target = self.spots[aid]  # sidestep over, back to the spot
            del self.aside[aid]
        incomers = np.array([present[i] for i in self.walking_in if i in present]).reshape(-1, 2)
        for aid in list(self.moving):
            x, y = present[aid]
            hist = self.hist.setdefault(aid, [])
            hist.append((x, y))
            full = len(hist) > int(STUCK_WINDOW / STUCK_CHECK)
            stuck = full and np.hypot(x - hist[0][0], y - hist[0][1]) < STUCK_MOVE and aid not in self.paused
            if full:
                hist.pop(0)
            if aid in self.spots:
                if aid not in self.aside:
                    self._arrivals(aid, x, y, stuck, t)
                if stuck:
                    hist.clear()
                continue
            if not stuck:
                continue
            inbound = aid in self.walking_in
            g = self.gate_of.get(aid, 0)
            gate = self.gates[g]
            if not inbound and x > gate.x - 0.5:
                continue  # already in or through the gate
            hist.clear()
            self.unjams += 1
            step = None
            near = [c for c in gate.corners if 0 < c[0] - x and np.hypot(c[0] - x, c[1] - y) < CORNER]
            corner = bool(near) and not inbound
            if corner:
                cx, cy = near[0]
                step = (cx - 0.4, cy - 0.8 * np.sign(cy - gate.axis))  # back off the corner on the open side
            elif inbound or (len(incomers) and np.min(np.hypot(*(incomers - (x, y)).T)) < 2.0):
                q = (x - 0.5, y + SIDESTEP) if inbound else (x + 0.5, y - SIDESTEP)  # keep right
                if self.inner.contains(Point(q)):
                    step = q
            if step is not None and not (corner and sim.agent(aid).journey_id in self.detour_ids):
                q = (round(float(step[0]), 1), round(float(step[1]), 1))
                sim.switch_agent_journey(aid, *self._detour(q, inbound, g))
            elif self.rng.random() < 0.5:
                m = sim.agent(aid).model
                self.paused[aid] = (t + STUCK_CHECK, m.desired_speed)
                m.desired_speed = 0.0
            elif not inbound:
                sim.switch_agent_journey(aid, *self.lane(g))
