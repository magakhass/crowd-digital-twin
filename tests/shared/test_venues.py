# Both venue files are complete and the twin's zone model reads their exits and gates.
import json

import numpy as np

from shared.venue import VENUES, Venue
from sim.venue_example import check
from twin.model import ZoneModel


def test_venue_files_complete():
    for name in ("concert_venue_v1", "festival_hall_v2"):
        assert check(json.loads((VENUES / f"{name}.json").read_text())) == []


def test_two_exits_and_gates():
    v = Venue(VENUES / "festival_hall_v2.json")
    assert [z for z, _ in v.exits()] == ["Z08", "Z11"]
    assert v.gate_behind() == [("Z08", 2.0), ("Z11", 2.0)]
    m = ZoneModel(v, 1.0)
    assert np.count_nonzero(m.width[:, -1]) == 2  # both ways out
    assert m.gate[v.idx["Z06"], v.idx["Z07"]] and m.gate[v.idx["Z01"], v.idx["Z02"]]  # 2 m links: gates and checkpoint


def test_concert_venue_unchanged():
    v = Venue(VENUES / "concert_venue_v1.json")
    assert v.exits() == [("Z07", 3.0)] and v.gate_behind() == [("Z07", 3.0)]
