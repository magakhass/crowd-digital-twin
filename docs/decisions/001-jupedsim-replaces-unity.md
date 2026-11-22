# 001: JuPedSim replaces Unity for the crowd simulation

## Context

The Week 7 Unity prototype (`docs/archive/unity-prototype/`) showed the venue, three scenarios
and zone densities, but red alerts were driven by the fixed queue slots in front of the bottleneck,
not by crowd physics. Our methodology (Section 9B) said we would switch to an established pedestrian
model if the agents failed the realism checks.

## Decision

Ground truth now comes from JuPedSim (Forschungszentrum Jülich), Python API, using the
Anticipation Velocity Model with the parameters validated by Xu, Chraibi and Seyfried (2021).
Unity is no longer part of the pipeline.

## Alternatives considered

- Keep Unity NavMesh and calibrate the queue: no published validation, slots would stay scripted.
- Social force model in Unity: more work in C#, still unvalidated in our setup.
- JuPedSim web app: same models but manual; we need scripted, seeded batches.

## Consequences

- Everything is Python: simulation, sensors, twin and evaluation share one code base.
- Bottleneck capacity and queues emerge from the model instead of being scripted.
- Scenarios are reproducible from a seed; batches run headless.
- Live visualisation is a web page instead of a Unity scene.
- The Unity project stays in git history (up to `b1e7453`); its notes and results are archived.
