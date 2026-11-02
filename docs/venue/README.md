# Concert venue — integration and setup

The Unity project lives in `/ConcertVenue`; use Unity 6000.0.23f1 with the Built-in Render Pipeline. Activate the Editor licence through Unity Hub if required. Add the `ConcertVenue` directory through Hub, then open `Assets/Scenes/ConcertVenue.unity`.

## Shared configuration

`shared/venues/concert_venue_v1.json` is the sole authoritative source of zone geometry, areas, classification, thresholds, links and route points. Its current content revision is 1.1; the filename is retained for compatibility with the shared branch. No generated zone CSV or hard-coded threshold copy is maintained.

`VenueDefinition.Load()` reads that file from the repository on Editor rebuild and on Play mode startup. `MonitoringZone` stores only `zoneId`; its properties resolve the loaded definition. Membership uses global Unity X/Z coordinates and half-open intervals, matching the shared conventions. Configuration is a snapshot for a run: changes require restarting Play mode or rebuilding the scene, rather than silently changing a running experiment.

A standalone desktop build must be supplied with the shared JSON using `-venue /absolute/path/to/venue.json` or `VENUE_FILE`. The file is deliberately not copied into Assets. Missing or invalid configuration fails explicitly without fallback thresholds. Web builds and configuration hot reload are outside scope.

## Scene layout

One Unity unit represents one metre; pedestrians will move on the XZ plane at Y = 0. The audience floor is 36 × 24 m. Total accessible area remains 1,194 m² across eight zones.

West-to-east topology: Z01 entrance → Z02/Z03/Z04 audience → Z05 approach → Z08 bottleneck front → Z06 passage → Z07 exit.

Z05 now covers X = 18–24 m, area 72 m². Z08 covers X = 24–28 m, area 48 m²: the final 4 m immediately upstream of the passage. Z06 remains the 2 m-long, 3 m-wide passage, area 6 m². This separates upstream accumulation from passage occupancy and retains the existing Z06/Z07 IDs. Placement and evaluation should monitor both Z08 and Z06.

Choose **Crowd Venue > Rebuild venue (replaces current scene)** to regenerate floors, zone objects and labels from the shared file. Save other work first: the command replaces the active scene. The checked-in scene is a generated geometry snapshot, not a second configuration source. Rebuild after changing shared geometry and commit the regenerated scene in the same reviewed change. Barriers are derived from zone edges and link openings; the generator rejects non-adjacent links and widths that do not match the shared opening. The stage remains a fixed decorative fixture and requires inspection after layout changes.

## Audience behaviour

There are no agents in this milestone. The arrows are spatial route markers, not a continuous-walking behavioural model. The chosen concert scenario is **arrive → move to a standing target in Z02–Z04 → dwell → leave**. See `audience-scenario.md` for the handoff specification and verification criteria. Standing classification applies to the watching phase; arrival/departure phases need separate reporting because those areas contain moving people then.

## Navigation and validation

Walking surfaces and barriers have BoxColliders; a NavMesh has not been baked. The agent-integration owner must install a compatible navigation package, bake for the selected radius, inspect transitions and test entrance-to-exit reachability before crowd runs. Validate the pedestrian model separately; correct geometry does not establish realistic crowd dynamics.

From repository root run:

```sh
python3 evaluation/verify_layout.py
```

This checks shared geometry, matching serialized floor footprints, non-overlap, link widths, route points and object references. It does not compile C# or render Unity. Unity 6000.0.23f1 import, C# compilation, scene rebuilding and rendering have now passed. Editor integration checks verified all eight zone definitions, half-open membership and an external JSON threshold change. Play mode and agent/navigation behaviour remain unverified. The rendered overview is `venue-overview.png`.

Reproduce the Editor checks with `-batchmode -quit -projectPath ConcertVenue -executeMethod ValidateVenue.RebuildAndCheck`. With graphics available, use `ValidateVenue.RebuildCheckAndCapture` to regenerate the overview too. These are Editor integration checks, not Play mode tests.
