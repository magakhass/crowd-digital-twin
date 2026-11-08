# Venue evidence log

## Version 1.0 — 2026-11-01

Scope: initial concert-venue geometry, seven zone definitions, stage, perimeter barriers, bottleneck, spawn/exit markers and overhead camera.

Decision record: `design-decisions.md`.
Geometry record (revision 1.1 onward): `/shared/venues/concert_venue_v1.json`.
Verification record: `verification.txt`.

Editor launch outcome: blocked before import because an active Unity Editor licence was not available. No Play mode or rendered screenshot is claimed.

Initial integration: PR #1, https://github.com/magakhass/crowd-digital-twin/pull/1.
Review by Inna: pending opening, inspection and any required changes in Unity.
Tutor feedback and subsequent revision: pending.

## Next evidence entry

Record the real inspection date, Editor version, screenshot filenames, Console result, navigation checks if performed, changes made after review, and the resulting GitHub commit. Keep course-required tool-use and individual-contribution declarations accurate and consistent with actual work.

## Revision 1.1 — 2026-11-02

Review response: move venue documentation to `/docs/venue` and structural evaluation to `/evaluation`; replace the derived CSV with the shared venue contract; isolate the final 4 m before the passage as Z08; resolve all Unity thresholds and zone dimensions from the shared JSON; specify arrive/watch/leave behaviour for pedestrian integration.

Shared dependency: `shared/venue-and-schemas`, with its existing zone IDs retained. Z05 shrinks from 120 to 72 m² and Z08 adds 48 m²; total accessible area is unchanged.

Verification: `python3 evaluation/verify_layout.py` checks eight scene zones against the shared JSON, adjacency, non-overlap, area, link widths and serialized references. Unity 6000.0.23f1 import, C# compilation, scene generation and rendering passed after enabling the built-in JSON module. Editor integration checks passed for shared thresholds, eight zone definitions and half-open membership, including an altered threshold supplied through a temporary external JSON. Three Python checks passed, including rejection of stale scene geometry and overlapping upstream zones. Play mode, navigation and audience behaviour remain unverified. The audience handoff is a design specification, not evidence of implemented agents.
