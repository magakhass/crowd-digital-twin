# How visitors move

Visitors enter at Z01, walk to an assigned position in Z02, Z03 or Z04, and wait 14 simulation seconds. Then they join the queue in Z08 or Z05 and leave through Z06 and Z07. Visitors approach along different paths and keep their assigned waiting spots until they leave the queue. They leave the queue at least 0.60 simulation seconds apart.

- **Normal flow:** 1.5 arrivals per second.
- **Gradual rise:** starts at 0.8 arrivals per second and increases by 0.055 each second, up to 8 arrivals per second.
- **Sudden surge:** 1.5 arrivals per second for 12 seconds, then 20 per second until all 360 visitors enter.

Entrance lanes, audience positions and walking speeds (1.2–1.8 m/s) vary. The same seed (305) makes runs repeatable. The passage uses the same speed and queue release rule in every scenario.

These rates are demo settings. Visitors follow simple routes and can overlap while walking. The model does not simulate physical contact or crowd pressure.
