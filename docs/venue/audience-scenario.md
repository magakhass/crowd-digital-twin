# Audience behaviour handoff

Status: agreed design for the next pedestrian integration; not an implemented agent controller.

## Agent states

1. Arriving: spawn at the configured entrance and navigate to an assigned reachable target inside Z02, Z03 or Z04. Avoid clustering every agent at a single centre point; sample targets and validate capacity/clearance.
2. Watching: after reaching that target, remain for a configurable dwell duration. The dwell timer starts on arrival, not at spawn. Collision/physical response must still be handled by the pedestrian model.
3. Departing: after dwell completion, navigate through Z05 → Z08 → Z06 to the configured exit. A coordinated release may end dwell early for a scheduled end-of-concert scenario.
4. Exited: remove the agent once its exit criterion is met and stop logging it.

Dwell time distribution, event duration, release window, arrivals and agent speed are calibration parameters stored in experiment configuration, with fixed seeds. No timing values are claimed validated at this stage. Use staggered departure for normal flow and a shorter release window for a surge; freeze values before test runs.

## Evaluation implications

Measure actual occupancy and residence time in each audience zone. During the watching phase those zones are treated as standing areas. During arrival/departure, report phase and movement conditions explicitly; do not silently interpret a static-zone density threshold as validating moving-crowd safety. Any phase-specific threshold policy must be agreed in the shared venue contract, not hard-coded in Unity.

Record Z08 upstream accumulation separately from Z06 passage density. Confirm that a surge can increase occupancy before the passage while outflow remains capacity-limited. Do not require congestion to occur in every run: inspect the measured speed/flow/density relationship and calibrate the model using the planned validation procedure.

## Agent integration checks

- An agent reaches a valid audience target and stays there until dwell completion or release.
- Dwell begins at target arrival and is reproducible with the configured seed.
- Agents do not depart before either condition is met.
- On release, agents follow the open route to the exit without crossing walls.
- The same run logs arrivals, dwell, release and departure so density can be interpreted by phase.
- Half-open membership assigns boundary points to at most one zone; trajectory output uses shared X/Z coordinates.

These checks remain pending until agents exist.
