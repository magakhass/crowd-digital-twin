import numpy as np

from sensors import sketch


def test_count_and_overlap_close_to_truth():
    ids = np.arange(400)
    pos = sketch.hash_positions(ids, salt="t")
    a = np.zeros(400, bool); a[:200] = True
    b = np.zeros(400, bool); b[150:300] = True
    sa, sb = sketch.build(pos, a), sketch.build(pos, b)
    assert abs(sketch.estimate(sa) - 200) < 40
    assert abs(sketch.overlap(sa, sb) - 50) < 40


def test_salt_changes_positions():
    ids = np.arange(50)
    assert not np.array_equal(sketch.hash_positions(ids, "a"), sketch.hash_positions(ids, "b"))
