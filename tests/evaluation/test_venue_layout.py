import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('verify_layout', ROOT / 'evaluation/verify_layout.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class VenueLayoutTests(unittest.TestCase):
    def test_checked_in_layout_matches_contract(self):
        with contextlib.redirect_stdout(io.StringIO()):
            module.verify(ROOT)

    def fixture(self, directory):
        root = Path(directory)
        target = root / 'shared/venues'
        target.mkdir(parents=True)
        shutil.copy(ROOT / 'shared/venues/concert_venue_v1.json', target)
        return root

    def test_overlap_in_upstream_region_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            path = root / 'shared/venues/concert_venue_v1.json'
            venue = json.loads(path.read_text())
            front = next(z for z in venue['zones'] if z['id'] == 'Z08')
            front['x_min'] = 23
            front['area_m2'] = 60
            path.write_text(json.dumps(venue))
            with self.assertRaisesRegex(AssertionError, 'Overlapping'):
                module.verify(root)

if __name__ == '__main__':
    unittest.main()
