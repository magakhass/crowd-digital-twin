# Venue design decisions — revision 1.1

## Scope

A synthetic concert venue for controlled experiments. Geometry is expressed in metres on Unity's XZ plane with an overhead view. Dimensions and scenario timing are experimental design assumptions, not real-venue safety recommendations.

## Review response: upstream accumulation

The former 10 × 12 m Z05 is split into a 6 × 12 m approach (Z05) and a 4 × 12 m bottleneck-front region (Z08). The 2 × 3 m passage remains Z06. Monitoring the front separately avoids averaging upstream accumulation into the entire approach and preserves existing zone IDs. No floor space is added: accessible area remains 1,194 m². A 48 m² average can still conceal smaller hotspots; the resolution must be assessed in later safety experiments.

## Shared venue is authoritative

Only the shared venue JSON defines zone geometry, classification, areas and alert thresholds. Unity zone objects contain IDs only. Both the Editor generator and runtime reader use that file. The scene retains derived meshes for opening/inspection; structural evaluation checks their footprints against the source. Generated CSV threshold copies are removed.

## Audience dwell rather than direct transit

The intended concert scenario includes a watching phase in Z02–Z04 before release to the exit. This makes standing-zone classification meaningful and creates a plausible departure surge for later evaluation. Dwell and departure are specified for integration, not claimed as implemented: there are no agents yet. Calibration must set timing before held-out runs, and the report must distinguish standing and moving phases.

## Repository conventions

All venue documentation resides under `/docs/venue`; the structural checker lives under `/evaluation`. Shared contract edits are submitted for review alongside the Unity consumer changes. This revision depends on the team's `shared/venue-and-schemas` branch.

## Alternatives and limits

Extending Z06 alone would measure more of the passage without isolating the upstream crowd. Splitting the approach was selected instead. Flat 3D colliders retain compatibility with the planned navigation workflow; decorative asset packs remain unnecessary. Neither collider geometry nor a validated file format establishes pedestrian-model realism. Agents, NavMesh baking, MQTT and forecasting remain outside this venue revision.
