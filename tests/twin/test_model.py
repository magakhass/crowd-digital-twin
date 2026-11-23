import numpy as np

from shared.venue import Venue
from twin.model import KC, VF, ZoneModel, weidmann


def test_weidmann_limits():
    assert abs(weidmann(np.array([0.01]))[0] - VF) < 1e-6
    assert weidmann(np.array([KC]))[0] == 0


def run_model(m, standing, rates, seconds):
    rng = np.random.default_rng(0)
    walking = np.zeros_like(standing)
    total0, left = standing.sum(), 0.0
    for _ in range(seconds):
        before = standing.sum() + walking.sum()
        standing, walking, _ = m.step(standing, walking, rates, rng, noise=False)
        left += before + rates[0, 2 * m.na] - (standing.sum() + walking.sum())  # + arrivals
    return standing, walking, total0, left


def test_half_gate_halves_the_flow_out():
    v = Venue()
    m = ZoneModel(v, capacity=1.0, kmax=np.full(len(v.zone_ids), 3.0))  # storage like the calibrated twin
    out = []
    for g in (1.0, 0.5):
        standing = np.zeros((1, m.nz)); standing[0, m.audience] = 300
        rates = np.zeros((1, m.n_rates())); rates[0, :m.na] = 5.0; rates[0, -1] = g
        out.append(run_model(m, standing, rates, 300)[3])
    assert 0.4 * out[0] < out[1] < 0.6 * out[0]  # about half


def test_egress_conserves_people_and_respects_the_exit():
    m = ZoneModel(Venue(), capacity=1.0)
    standing = np.zeros((1, m.nz)); standing[0, m.audience] = 100
    rates = np.zeros((1, m.n_rates())); rates[0, :m.na] = 2.0; rates[0, -1] = 1.0  # gate factor 1
    standing, walking, total0, left = run_model(m, standing, rates, 200)
    assert left >= 0
    assert abs(standing.sum() + walking.sum() + left - total0) < 1e-6
    assert left <= 200 * 1.0 * 3.0 + 1e-6  # the exit caps the flow out


def test_ingress_fills_the_audience():
    v = Venue()
    turning = (ZoneModel(v, capacity=1.0).width > 0).astype(float)
    turning[:, -1] = 0  # nobody walks out of the venue while arriving
    m = ZoneModel(v, capacity=1.0, turning=turning)
    standing = np.zeros((1, m.nz))
    rates = np.zeros((1, m.n_rates())); rates[0, m.na:2 * m.na] = 0.05; rates[0, 2 * m.na] = 2.0; rates[0, -1] = 1.0
    standing, walking, _, left = run_model(m, standing, rates, 300)
    assert abs(left) < 1e-6  # nobody leaves while arriving
    assert abs(standing.sum() + walking.sum() - 600) < 1e-6
    assert standing[0, m.audience].sum() > 0
