# Shared conventions

These apply to every component. Change them only through a reviewed pull request.

- **Units:** metres, seconds, persons/m².
- **Coordinates:** the venue file's x (west to east) and y (south to north). JuPedSim uses the same plane.
- **IDs:** zones `Z01`–`Z99`, candidate sensor spots `C00`–`C99`, runs `{scenario}-s{seed:02d}` (e.g. `surge-s07`).
- **Zone membership:** half-open intervals, `x_min <= x < x_max` and `y_min <= y < y_max`, so a point on a boundary belongs to exactly one zone.
- **Single source of truth:** zone geometry and alert thresholds live only in `shared/venues/*.json`. The simulator, the sensors and the twin all read this file through `shared/venue.py`; nobody hard-codes them.
- **Time:** simulation seconds since run start in all messages and logs.
- **Seeds:** 1–2 for calibration only, 3–8 for testing. Held-out scenarios (`counterflow`, `blockage`) use test seeds only and are never used for tuning.
