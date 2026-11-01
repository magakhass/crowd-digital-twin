# Shared conventions

These apply to every component. Change them only through a reviewed pull request.

- **Units:** metres, seconds, persons/m². One Unity unit = 1 m.
- **Coordinates:** x = Unity X, y = Unity Z. Unity Y (elevation) is ignored.
- **IDs:** zones `Z01`–`Z99`, sensors `S01`–`S99`, runs `{scenario}-s{seed}` (e.g. `surge-s07`).
- **Zone membership:** half-open intervals, `x_min <= x < x_max` and `y_min <= y < y_max`, so a point on a boundary belongs to exactly one zone.
- **Single source of truth:** zone geometry and alert thresholds live only in `shared/venues/*.json`. Unity, the sensors and the twin all read this file; nobody hard-codes them.
- **Time:** simulation seconds since run start in all messages and logs.
- **Unity version:** 6000.0.23f1, Built-in Render Pipeline.
