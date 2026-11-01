# Venue design decisions — v1.0

## Purpose and scope

Provide the venue foundation assigned to Inna for the Week 5–6 milestone. This is a synthetic experimental venue, not a reconstruction of a real concert site. Dimensions are design assumptions to be calibrated by the team.

## Flat geometry in a 3D scene

Movement is constrained conceptually to the XZ plane. A top-down orthographic camera preserves a 2D presentation while colliders support later integration with Unity navigation. Vertical crowd movement is outside scope.

## Explicit congestion location

The 12 m-wide approach narrows to a 3 m passage before reopening into a 12 m-wide exit apron. This supports later controlled experiments with arrival rates and bottleneck capacity. The geometry alone does not establish that simulated crowd dynamics are realistic.

## Zone-level observation

The audience area is divided into three 12 × 24 m zones. Entrance, approach, bottleneck and exit have separate zone IDs. Accessible areas exclude the stage and boundary walls. The same IDs and coordinate system should be used in future reference logs and sensor coverage maps.

## Geometry before decoration

Simple meshes and colour-coded floors make dimensions, connections and obstacles easy to inspect. External concert asset packs were omitted to avoid extra dependencies and obstacles that would silently change accessible areas.

## Alternatives considered

A sprite-based 2D layout would match a strict XY implementation, but would require a different navigation approach from the proposed NavMesh workflow. A detailed imported venue model would improve appearance, but introduces unnecessary scale, licensing and geometry-cleanup work at this milestone. A flat 3D layout was selected as the integration foundation.

## Limits

No agents, NavMesh bake, density estimates, privacy claims about actual sensor hardware or validated crowd-safety behaviour are included. NavMesh compatibility and physical crowd realism must be assessed during pedestrian integration. Zone-average density can conceal small local hotspots; later experiments must acknowledge this limitation.
