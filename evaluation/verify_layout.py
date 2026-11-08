"""Validate shared venue geometry and the checked-in Unity scene without Unity."""
import json
import math
import re
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
    scene = (root / 'ConcertVenue/Assets/Scenes/ConcertVenue.unity').read_text()
    ids = re.findall(r'^--- !u!\d+ &(\d+)$', scene, re.M)
    assert len(ids) == len(set(ids)), 'Duplicate serialized object ID'
    for value in re.findall(r'\{fileID: (\d+)\}', scene):
        assert value == '0' or value in ids, 'Unresolved local reference: ' + value
    asset_guids = set()
    for meta in (root / 'ConcertVenue/Assets').rglob('*.meta'):
        asset_guids.update(re.findall(r'^guid: (\w+)$', meta.read_text(), re.M))
    for value in re.findall(r'guid: (\w+)', scene):
        assert value in asset_guids or value.startswith('0000000000000000')
    blocks = re.split(r'(?=^--- !u!)', scene, flags=re.M)
    transforms = {}
    objects = {}
    for block in blocks:
        if block.startswith('--- !u!1 '):
            objects[re.search(r'&(\d+)', block)[1]] = re.search(r'^  m_Name: (.*)$', block, re.M)[1]
        elif block.startswith('--- !u!4 '):
            go = re.search(r'm_GameObject: \{fileID: (\d+)\}', block)[1]
            def vector(field):
                values = re.search(field + r': \{x: ([^,]+), y: ([^,]+), z: ([^}]+)\}', block)
                return tuple(float(v) for v in values.groups())
            transforms[go] = vector('m_LocalPosition'), vector('m_LocalScale')
    for z in zones:
        name = z['id'] + ' ' + z['name'] + ' Floor'
        go = next(g for g, n in objects.items() if n == name)
        position, size = transforms[go]
        assert position == ((z['x_min']+z['x_max'])/2, -.15, (z['y_min']+z['y_max'])/2), name
        assert size == (z['x_max']-z['x_min'], .3, z['y_max']-z['y_min']), name
    scene_zone_ids = re.findall(r'^  zoneId: (\w+)$', scene, re.M)
    assert len(scene_zone_ids) == len(set(scene_zone_ids)) == len(zones)
    assert set(scene_zone_ids) == set(by_id)
    assert 'movingZone:' not in scene and 'sizeMetres:' not in scene
    print('PASS: shared venue and eight scene zones agree; areas total 1,194 m².')
    print('PASS: 4 m upstream Z08; contiguous links; unique half-open zone footprints.')
    print('PASS: zone floor transforms, serialized IDs and asset references.')
    print('Outside this structural check: Unity compilation, rendering, Play mode, agents and navigation.')

if __name__ == '__main__':
    verify()
