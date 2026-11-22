> **Archived.** This is the Week 7 Unity prototype (Inna). We moved the crowd simulation to
> JuPedSim in Week 9 (see `docs/decisions/001-jupedsim-replaces-unity.md`). The Unity project itself
> is in the git history up to commit `b1e7453`; these notes and results are kept as evidence.

# Unity crowd demo

Open `ConcertVenue` in Unity **6000.0.23f1**. Keep `shared` next to it. Open `Assets/Scenes/ConcertVenue.unity` and press **Play**.

- **Normal flow / Gradual rise / Sudden surge:** choose how visitors arrive. Changing the scenario clears the run.
- **Start run / Pause / Resume / Run again:** control the selected run.
- **Reset:** clear the run without changing the scenario.
- **Speed:** switch between 1×, 4× and 12×.

**Area** is in m². **Reference** is the current density. **Sampled** is the last sensor reading, taken every five seconds. The number in brackets is the sampled headcount. A dash means there is no sensor.

Dots and zone fill show current density. Sensor borders show the last reading and flash when a new sample arrives.

[Results](week-7.md) · [Checks](verification.txt)
