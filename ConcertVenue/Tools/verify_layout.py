"""Check the delivered layout without requiring an activated Unity Editor."""
import csv
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
scene = (root / 'Assets/Scenes/ConcertVenue.unity').read_text()
rows = list(csv.DictReader((root / 'Documentation/zones.csv').open()))
assert len(rows) == 7
assert len({r['zone_id'] for r in rows}) == 7
assert sum(float(r['accessible_area_m2']) for r in rows) == 1194
for r in rows:
    assert float(r['width_m']) * float(r['depth_m']) == float(r['accessible_area_m2'])
for a, b in zip(rows, rows[1:]):
    assert float(a['centre_x_m']) + float(a['width_m'])/2 == float(b['centre_x_m']) - float(b['width_m'])/2
assert float(rows[5]['depth_m']) == 3
ids = re.findall(r'^--- !u!\d+ &(\d+)$', scene, re.M)
assert len(ids) == len(set(ids))
# All local nonzero references must point to an existing serialized object.
for value in re.findall(r'\{fileID: (\d+)\}', scene):
    assert value == '0' or value in ids, value
asset_guids = set()
for meta in (root / 'Assets').rglob('*.meta'):
    asset_guids.update(re.findall(r'^guid: (\w+)$', meta.read_text(), re.M))
for value in re.findall(r'guid: (\w+)', scene):
    assert value in asset_guids or value.startswith('0000000000000000'), value
print('PASS: 7 unique monitoring zones; 1,194 m² accessible area.')
print('PASS: adjoining X intervals; 3 m bottleneck width; zone area calculations.')
print('PASS: unique serialized IDs; resolved local object and asset references.')
print('NOT VERIFIED: Unity import, C# compilation, rendering, Play mode, navigation.')
