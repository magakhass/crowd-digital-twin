# Venue design decisions

- **Keep the plan readable.** One Unity unit equals one metre. The 2D view shows the stage, entrance, exit, eight monitoring zones and four virtual sensors.
- **Measure the queue separately.** Z08 covers the final 4 × 12 m before the bottleneck. Z06 is the 2 × 3 m passage. Keeping them separate shows whether people are building up before the passage or inside it. The total accessible area is still 1,194 m².
- **Use one shared layout.** Zone geometry and thresholds come from the shared JSON. Unity checks zone positions, floor sizes and route markers on startup and asks for a rebuild if they differ.
- **Keep the comparison simple.** All three runs use the same layout and visitor count. We compare full counts with five-second samples using the same thresholds. Sensor locations are demo choices, not placement recommendations.
