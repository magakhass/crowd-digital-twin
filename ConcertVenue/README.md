# CSIT305 — Concert Venue

Version 1.0. A flat concert-venue layout for the crowd-monitoring research testbed.
The environment uses 3D colliders on the XZ plane with an overhead camera. One Unity unit represents one metre.

## Open the project

1. Activate a Unity Editor licence through Unity Hub if required.
2. In Unity Hub choose **Add > Add project from disk** and select this `ConcertVenue` directory.
3. Open with **Unity 6000.0.23f1**, using the Built-in Render Pipeline.
4. Open `Assets/Scenes/ConcertVenue.unity`.
5. Use Scene view to inspect the layout. Select a monitoring-zone object to see its dimensions in the Inspector. Press Play for the overhead layout and information panel.

The scene is included. No external assets, downloads or paid packages are required for the venue geometry. Unity may resolve its built-in module dependencies on first import.

To recreate the scene with ground labels and route markers, save any other work first, then choose **Crowd Venue > Rebuild venue (replaces current scene)**. This intentionally replaces the active scene and saves the result to `Assets/Scenes/ConcertVenue.unity`.

## Layout

The route runs west to east: entrance → audience area → approach → bottleneck → exit apron.
The stage sits north of the audience area, outside the accessible monitoring zones. The main standing area measures 36 × 24 m and is divided into three adjacent zones. The bottleneck is 2 m long and 3 m wide. Its width is an experimental layout choice, not a recommendation for a real venue.

Seven non-overlapping monitoring zones and their accessible areas are recorded in `Documentation/zones.csv`. Total accessible floor area is **1,194 m²**, excluding the stage and perimeter barriers. Zone boundaries are virtual: they do not prevent pedestrian movement.

## Components and integration

- `MonitoringZone`: stable zone identifier, dimensions, accessible area, zone classification and point-membership helper. Coordinates use XZ; Y is elevation. The helper includes boundary points, so downstream counting must assign a boundary point to exactly one zone using a deterministic tie-break.
- `VenueCamera`: overhead view and a small runtime information panel.
- `BuildVenue`: Editor-only scene generator, materials, labels, barriers and spawn/destination markers.
- `Entrance spawn marker`: (-27, 0, 0).
- `Exit destination marker`: (41, 0, 0).

All walking surfaces have their top face at Y = 0. Barriers have BoxColliders. Agents, density logging, sensor emulation, MQTT and forecasting are future integration work. The zone threshold properties reflect the proposal's experimental alert settings; they do not implement an alert system or certify safety.

## Navigation handoff

The project contains collider geometry; a NavMesh has **not** been baked. When pedestrian integration begins, install a compatible Unity AI Navigation package through Package Manager, create a NavMeshSurface and collect the walkable floor and obstacle geometry. Keep monitoring-zone empty objects and text labels out of the geometry collection. Bake for the chosen agent radius and inspect the 3 m bottleneck and both transitions. Verify an agent can travel between the two markers before adding a crowd.

## Verification status

The included scene and metadata were generated and checked for unique object IDs, valid internal references, seven contiguous zone footprints, non-overlapping zone interiors and the total accessible area. See `Documentation/verification.txt`.

A batch-mode Editor launch was attempted, but stopped at **No valid Unity Editor license found** before project import. Therefore C# compilation, rendering, Play mode and navigation have not been verified in Unity. Opening and checking the project in an activated Editor is required before claiming a working demonstration.

## Evidence to retain after the first Editor run

Capture the complete venue, selected Z06 dimensions, and the Game view. Save the Console output, record the actual date and commit hash, and update the evidence log with observed results. Do not mark unperformed checks as passed.
