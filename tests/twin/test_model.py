import numpy as np

from shared.venue import Venue
from twin.model import KC, VF, ZoneModel, weidmann


def test_weidmann_limits():
    assert abs(weidmann(np.array([0.01]))[0] - VF) < 1e-6
    assert weidmann(np.array([KC]))[0] == 0


def test_flow_model_conserves_people():
    v = Venue()
    m = ZoneModel(v, capacity=1.0)
    rng = np.random.default_rng(0)
    standing = np.zeros((1, m.nz)); standing[0, m.audience] = 300
    walking = np.zeros((1, m.nz))
    lam = np.full((1, len(m.audience)), 2.0)
    total0, left = standing.sum(), 0.0
    for _ in range(200):
        before = standing.sum() + walking.sum()
        standing, walking, _ = m.step(standing, walking, lam, rng, noise=False)
        left += before - (standing.sum() + walking.sum())
    assert left >= 0
    assert abs(standing.sum() + walking.sum() + left - total0) < 1e-6
    # the bottleneck caps the exit flow
    assert left <= 200 * 1.0 * 3.0 + 1e-6
