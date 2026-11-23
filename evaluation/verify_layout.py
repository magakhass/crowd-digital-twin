"""Validate the shared venue geometry (the active venue: CROWDTWIN_VENUE, default the concert venue)."""
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = os.environ.get("CROWDTWIN_VENUE", "concert_venue_v1")


def shared_edge(a, b):
    # length of the edge two zones share (0 if they only touch at a corner or not at all)
    if a['x_max'] == b['x_min'] or b['x_max'] == a['x_min']:
        return min(a['y_max'], b['y_max']) - max(a['y_min'], b['y_min'])
    if a['y_max'] == b['y_min'] or b['y_max'] == a['y_min']:
        return min(a['x_max'], b['x_max']) - max(a['x_min'], b['x_min'])
    return 0


def verify(root=ROOT):
    venue = json.loads((root / f'shared/venues/{ACTIVE}.json').read_text())
    zones = venue['zones']
    by_id = {z['id']: z for z in zones}
    assert len(by_id) == len(zones), 'Zone ids must be unique'
    for z in zones:
        assert z['x_min'] < z['x_max'] and z['y_min'] < z['y_max']
        assert math.isclose((z['x_max']-z['x_min'])*(z['y_max']-z['y_min']), z['area_m2'])
        assert 0 < z['amber_persons_m2'] < z['red_persons_m2']
    for i, a in enumerate(zones):
        for b in zones[i+1:]:
            assert not (max(a['x_min'], b['x_min']) < min(a['x_max'], b['x_max']) and
                        max(a['y_min'], b['y_min']) < min(a['y_max'], b['y_max'])), 'Overlapping zone interiors'
    for link in venue['links']:
        assert 0 < link['width_m'] <= shared_edge(by_id[link['from']], by_id[link['to']]), 'Disconnected linked zones'
    linked = {frozenset((l['from'], l['to'])) for l in venue['links']}
    for i, a in enumerate(zones):
        for b in zones[i+1:]:
            if shared_edge(a, b) > 0:
                assert frozenset((a['id'], b['id'])) in linked, 'Neighbouring zones without a link'
    if ACTIVE == 'concert_venue_v1':  # facts of the concert venue the paper relies on
        assert len(zones) == 8
        assert by_id['Z08']['x_max'] - by_id['Z08']['x_min'] == 4
        assert by_id['Z08']['x_max'] == by_id['Z06']['x_min']
        assert sum(z['area_m2'] for z in zones) == 1194
    for key in ['spawn_points', 'exit_points']:
        for point in venue[key]:
            assert sum(z['x_min'] <= point['x'] < z['x_max'] and
                       z['y_min'] <= point['y'] < z['y_max'] for z in zones) == 1
    print(f"PASS: {venue['venue_id']}: {len(zones)} zones, {sum(z['area_m2'] for z in zones):,.0f} m²; "
          "every shared edge is a link; no overlaps; spawn and exit points inside one zone each.")


if __name__ == '__main__':
    verify()
