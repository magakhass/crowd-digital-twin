# Week 7 results

The Unity demo uses the shared venue layout and synthetic visitor data. All three runs use 360 visitors; only the arrival rate changes. Visitor positions, lanes and walking speeds vary, but each scenario uses the same random seed. Four virtual sensors take a count every five seconds. All visitors exited in each run.

- **Normal flow:** Z08 peaked at **0.31 people/m²** and stayed below red.
- **Gradual rise:** Z08 peaked at **4.19 people/m²**. The first red reading was **148.45 s** in the reference and **150.00 s** in the sample.
- **Sudden surge:** Z08 peaked at **5.02 people/m²**. The first red reading was **72.70 s** in the reference and **75.00 s** in the sample.

The red threshold was reached before the passage (Z08) in two runs. Inside the passage (Z06), density stayed at or below **1.17 people/m²**. Sensor S03 counted up to seven people in one sample, below the amber threshold of 18. In the surge, the sample detected the red threshold **2.30 s** after the reference. These are simulation results with idealised sensor counts, not measurements from a real event.

In the CSV files, time is in simulation seconds and density is in people/m². A blank sensor field means no sensor is present; `-1` means no red threshold crossing was recorded.

[Unity screenshot](week-7-results/surge-dashboard.png) · [Play mode output](week-7-results/play-mode.txt) · [Surge summary](week-7-results/surge-summary.csv)
