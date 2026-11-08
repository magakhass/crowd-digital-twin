# Week 7 — Unity progress

In Week 6, the venue was a static map. It now runs three scenarios from the project proposal: normal flow, gradual rise and sudden surge. Each run has 360 visitors. The arrival rate changes, but the venue, time spent watching and exit capacity stay the same.

Visitors are shown as dots. They enter, stop in the audience area and then leave through the bottleneck. The 2D view labels the entrance, stage, exit, all eight zones and four virtual sensors.

## What we compare

**Reference** is the current number of visitors in a zone divided by its area. **Sampled** uses the same count, but updates only every five seconds in Z01, Z08, Z06 and Z07. The other zones have no sample. The shared venue file sets amber at 3 people/m² and red at 4 in moving zones or 4.7 in standing zones. The demo flags current conditions without forecasting.

## What we found

All 360 visitors exited in each Play mode test.

- **Normal flow:** Z08 peaked at **0.38 people/m²** and did not reach red.
- **Gradual rise:** Z08 peaked at **4.44 people/m²**. The first red reading was at **149.55 s** in the reference and **155.00 s** in the sample.
- **Sudden surge:** Z08 peaked at **5.17 people/m²**. The first red reading was at **70.55 s** in the reference and **75.00 s** in the sample.

The queue built up in **Z08, before the passage**. Z06, the passage itself, stayed at or below 1.00 people/m² in all three runs. In the surge, the sampled reading picked up red 4.45 seconds after the reference. These results describe the simplified Unity model with idealised sensor counts. Real sensors and crowd behaviour have not been validated.

In the saved CSV files, times are simulation seconds and densities are people/m². A blank sensor field means the zone has no sensor; `-1` means the red threshold was never reached.

[Unity screenshot](week-7-results/surge-dashboard.png) · [Play mode output](week-7-results/play-mode.txt) · [Surge summary](week-7-results/surge-summary.csv)
