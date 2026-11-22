"""Validate the shared venue geometry."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def verify(root=ROOT):
    venue = json.loads((root / 'shared/venues/concert_venue_v1.json').read_text())
    zones = venue['zones']
    by_id = {z['id']: z for z in zones}
    assert len(by_id) == len(zones) == 8, 'Expected eight unique zones'
    for z in zones:
        assert z['x_min'] < z['x_max'] and z['y_min'] < z['y_max']
        assert math.isclose((z['x_max']-z['x_min'])*(z['y_max']-z['y_min']), z['area_m2'])
        assert 0 < z['amber_persons_m2'] < z['red_persons_m2']
    for i, a in enumerate(zones):
        for b in zones[i+1:]:
            assert not (max(a['x_min'], b['x_min']) < min(a['x_max'], b['x_max']) and
                        max(a['y_min'], b['y_min']) < min(a['y_max'], b['y_max'])), 'Overlapping zone interiors'
    for link in venue['links']:
        a, b = by_id[link['from']], by_id[link['to']]
        assert a['x_max'] == b['x_min'], 'Disconnected route zones'
        opening = min(a['y_max'], b['y_max']) - max(a['y_min'], b['y_min'])
        assert 0 < link['width_m'] <= opening
    assert by_id['Z08']['x_max'] - by_id['Z08']['x_min'] == 4
    assert by_id['Z08']['x_max'] == by_id['Z06']['x_min']
    assert sum(z['area_m2'] for z in zones) == 1194
    for key in ['spawn_points', 'exit_points']:
        for point in venue[key]:
            assert sum(z['x_min'] <= point['x'] < z['x_max'] and
                       z['y_min'] <= point['y'] < z['y_max'] for z in zones) == 1
    print('PASS: shared venue has eight zones; areas total 1,194 m².')
    print('PASS: 4 m upstream Z08; contiguous links; unique half-open zone footprints.')

if __name__ == '__main__':
    verify()
