# IV. Results

## A. Realism of the simulated crowd

Across the twelve gradual and surge test runs, the peak specific flow through the 3 m bottleneck was 66.8 ± 1.3 persons/m/min (range 64.7–68.7), measured with PedPy over 30 s windows. This is below the 82 persons/m/min maximum used in crowd safety guidance for level surfaces (Still, 2014), so our bottleneck is on the conservative side. The queue forms in the approach zone (Z05), where true densities reached 4.1–5.0 persons/m² in the gradual and surge runs. In the normal scenario no zone exceeded 1.2 persons/m². The test runs contain 13 critical events (7 gradual, 6 surge, none normal), all in Z05.

## B. Early warning against the baselines

Table I compares the twin with the baselines on the three core scenarios, pooled over sensing mode, placement strategy and budget. With true zone counts the twin detected all 13 events in time with no false alarms, with a median lead of 62 s. With count-only sensors it detected 79 % of events (option A) and 82 % (option B) at fewer than one false alarm per hour. Raising alerts from the current readings alone caught only 17 % of events in time. It caught more events late (102) than in time (53), at 17 false alarms per hour. Extending the recent trend in a straight line caught 40 %, but at 35 false alarms per hour. The flow model, rather than the sensors alone, is what turns sparse counts into usable warnings.

In the normal scenario, where no event occurs, the twin raised 0.08 false alarms per hour.

Fig. 2 shows a typical surge run. The twin's estimate lags the true density by about 20 s, mostly because of the 60 s phone window, but the forecast probability rises as soon as the show ends, and the red alert fires before the true density crosses the threshold.

The lead times are short in absolute terms. Even with perfect information, the median lead was 62 s overall. In surge runs it was only 25–41 s, because the density reaches red 40–55 s after the show ends and nothing before that moment signals the surge. In gradual runs it was 62–240 s. The two-minute lead target in our plan is therefore out of reach for sudden surges with any sensing, and reachable only in some gradual build-ups.

## C. Placement and number of sensors

Table II gives the detection rate, false alarms per hour and median lead for each placement strategy and budget. Detection rates rose from 0.72 with two sensors to 0.82 with four and 0.87 with six. Placement mattered more than the number of sensors: bottleneck-focused placement detected 0.92 of events on average and greedy mutual information 0.88, against 0.78 for random placement and 0.63 for placing sensors at the entrance and exit. With four sensors, bottleneck-focused placement reached 0.98 and greedy mutual information 0.94, both at about one false alarm per hour.

The greedy mutual-information placement (Liebig, Xu and May, 2013) used only the covariance of readings from calibration runs and no knowledge of where the bottleneck is. It nevertheless came close to the placement chosen by hand from the venue design, and on the held-out scenarios it produced fewer false alarms (Section E). Placing sensors at the flow boundaries performed worst: they see people entering and leaving but not the queue that forms between them.

## D. Sensing mode and privacy-preserving sketches

BLE tags outperformed phones (Table III): detection 0.81–0.87 against 0.76–0.77, with far fewer late warnings (14 against 60 over all configurations) and a lower density error in sensed zones (0.44–0.45 against 0.61–0.65 persons/m²). Tags are heard every second and use a 10 s window, so their counts follow the true occupancy closely, whereas the 60 s phone window also counts people who have already moved on.

Adding sketches (option B) raised the detection rate from 0.81 to 0.87 for tags and barely changed it for phones (0.76 to 0.77). Its clearest effect was on zones outside sensor coverage, where the density error fell from 1.34 to 0.80 persons/m² for tags. The overlap counts tell the twin how many people sit where two ranges intersect, which helps it place people correctly. The benefit is smaller for phones because their identifiers are re-salted every minute, so overlaps can only be resolved within the same minute. Option B never sends identifiers and its false-alarm rate was similar to option A.

## E. Held-out scenarios

Neither held-out scenario was used for calibration, and the twin's venue model knows nothing about counterflow or the partial blockage. Table IV shows that it still detected most events: 0.78 in counterflow and 0.69 in blockage at four sensors. With bottleneck-focused placement it reached 1.00 and 0.82; with greedy mutual information 0.94 and 0.82, at lower false-alarm rates than bottleneck-focused placement. The baselines again performed poorly (0.06–0.46). Counterflow produced more false alarms (3.2 per hour), as the twin's one-directional flow model cannot represent people walking against the stream. This matches our earlier observation that count-only sensing can estimate net flow but not opposing flows.

## F. Sensor failure

When every sensor covering the approach, bottleneck front and bottleneck went offline 90 s before the first event, the twin warned in none of the six surge runs, in any sensing condition. The failure itself is detected within 10 s, since two consecutive 5 s reports are missing. With bottleneck-focused placement, however, all four sensors cover those zones, so the twin is left blind just before the surge starts and has no evidence that it is coming. The test therefore fails our pass criteria. It shows that a placement which concentrates every sensor on the risk area creates a single point of failure. Spreading sensors upstream, as the greedy mutual-information placement does, keeps some information flowing, and the twin should treat loss of coverage over a known risk zone as an alert in its own right.

## G. Against our acceptance thresholds

- Detection rate ≥ 0.90: met by bottleneck-focused placement with four or six sensors and by greedy mutual information with four sensors; not met on average (0.80).
- At most 1 false alarm per hour: met on average (0.91 per hour) and in the normal scenario (0.08), not in counterflow.
- Median lead ≥ 2 min: not met (31–72 s across placements). Even perfect information gives 62 s, and surges allow only 25–41 s.
- Density RMSE ≤ 0.5 persons/m² in sensed zones: met with BLE tags (0.44–0.45), not with phones (0.61–0.65).
- Latency: not measured end to end in live mode. Offline, one twin update including the two-minute ensemble forecast took about 20 ms on a two-core cloud machine.
- Failure test: not passed (Section F).

# V. Discussion and limitations

Our results suggest that a privacy-preserving twin can turn a handful of count-only sensors into warnings that are far more useful than reading the sensors directly. Where the sensors are placed matters more than how many there are, and a placement learned from simulation alone performs almost as well as one chosen by hand. Small privacy-preserving sketches add a measurable benefit with tags.

The results hold under stated simulated conditions only. The crowd model is validated against corridor experiments (Xu, Chraibi and Seyfried, 2021), but not for densities above 4.5 persons/m², where its agents keep pushing instead of standing still. Our bottleneck flow is below the guidance value. The sensor parameters marked as assumptions need field calibration. The test set contains 13 core events, so one missed event changes the detection rate by about 0.08. The twin models only one direction of flow. We plan to replay real trajectories from the Jülich pedestrian dynamics data archive (Forschungszentrum Jülich, n.d.-b) through the same pipeline and to add two-directional groups to the flow model.
