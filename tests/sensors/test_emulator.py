import numpy as np

from sensors import emulator


def standing_crowd(tmp_path, n=60, seconds=300):
    # n people standing within 3 m of the first candidate spot, written at 5 fps
    rng = np.random.default_rng(0)
    cx, cy = emulator.CANDIDATES[0]
    xy = np.c_[cx + rng.uniform(-3, 3, n), cy + rng.uniform(-3, 3, n)]
    rows = [(i, f, *xy[i]) for f in range(0, seconds * 5, 5) for i in range(n)]
    (tmp_path / "trajectories").mkdir()
    np.savetxt(tmp_path / "trajectories" / "test-s01.csv", rows, delimiter=",", header="id,frame,x,y", comments="")


def test_more_noise_means_fewer_detections_and_more_lost_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(emulator, "DATA", tmp_path)
    standing_crowd(tmp_path)
    for mode in ("phones", "tags"):
        heard, lost = [], []
        for noise in emulator.NOISE_LEVELS:
            obs = emulator.observe("test-s01", mode, noise)
            heard.append(obs["seen"][-20:, 0].sum(1).mean())
            lost.append(emulator.readings(obs, [0])["lost"].mean())
        assert heard[0] >= heard[1] > heard[2], (mode, heard)
        assert lost[0] < lost[1] < lost[2], (mode, lost)
