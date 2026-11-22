# III. Methodology

## A. Testbed venue and crowd scenarios

We use a simulated concert venue of 1,194 m² divided into eight monitoring zones (Fig. 1): an entrance (Z01), three standing audience zones (Z02–Z04, 288 m² each), an approach (Z05), a bottleneck front (Z08), a 3 m wide bottleneck (Z06) and an exit apron (Z07). Audience zones are treated as static and use a red threshold of 4.7 persons/m²; all other zones are dynamic with a red threshold of 4 persons/m², and amber is 3 persons/m² everywhere (Still, 2014).

The crowd is simulated with JuPedSim 1.4.2 (Forschungszentrum Jülich, n.d.-a) using the Anticipation Velocity Model with the parameters validated against bidirectional corridor experiments by Xu, Chraibi and Seyfried (2021): desired speed N(1.55, 0.18²) m/s, radius 0.18 m, time gap 0.5 s (0.6 s with counterflow), reaction time 0.3 s and anticipation time 0.75 s, with a time step of 0.05 s. We moved from our earlier Unity prototype to JuPedSim because in Unity the queue in front of the bottleneck was scripted, while here capacity and queues emerge from a validated model.

All scenarios are end-of-show egress. People stand in the audience zones until their departure time and then walk to the exit through the bottleneck. Three scenarios are used for calibration and testing: *normal* (600 people leaving at a steady 1 person/s), *gradual* (1,300 people, departure rate rising linearly over 300 s) and *surge* (1,200 people, 20 % leaving early and the rest when the show ends at 300 s). Two further scenarios are held out and never used for tuning: *counterflow* (1,100 leaving while 60 people walk in against the stream through the bottleneck) and *blockage* (half of the bottleneck blocked; the twin's venue file is not changed). Seeds 1–2 are used only for calibration and seeds 3–8 for testing, giving 36 simulation runs. Trajectories are written at 5 frames per second.

## B. Sensing

Sensors are emulated from the trajectories. Each sensor has a fixed position and an effective range of 10 m, which corresponds to the density of about one sensor per 400 m² reported for dense crowds by Determe et al. (2022). Ranges therefore overlap several zones, and a zone is rarely covered by exactly one sensor. Every 5 s a sensor reports the number of distinct devices it detected during its window; no positions or identities leave the sensor.

We model two sensing modes. *Phones*: 85 % of people carry a detectable phone, phones send probe bursts as a Poisson process and each burst is received with probability 0.9. The rates are set so that a person standing in range for 60 s is counted with probability about 0.67, matching the extrapolation factor reported by Determe et al. (2022); the window is 60 s, since phones probe roughly once per minute when idle (Schauer, Werner and Marcus, 2014). *BLE tags*: 80 % of people wear a venue-issued tag that advertises once per second (the default interval of commercial badges), each advertisement is received with probability 0.5, and the window is 10 s. In both modes 5 % of messages are lost and sensors can be switched off for failure tests. Parameters not taken from a source are stated as assumptions.

We compare two sensing options. **Option A** sends only the count. **Option B** additionally sends linear-counting sketches (Kamp et al., 2013): each sensor sets bits in 16 arrays of 128 bits using a salted hash of each device ID, with the salt shared by all sensors and rotated every minute for phones (Determe et al., 2022). The twin can estimate how many devices two sensors saw in common, which resolves overlapping ranges, but it never receives an identifier.

## C. Digital twin

The twin receives only sensor messages and the venue file. Its process model is a zone-level version of the pedestrian cell transmission model of Hänseler et al. (2014). Each zone holds standing and walking people. Walking people move to the next zone at the speed given by Weidmann's fundamental diagram (free speed 1.34 m/s, jam density 5.4 persons/m²), limited by the link capacity (persons per metre per second × link width) and by the space left in the receiving zone. Standing people start walking at an unknown release rate per audience zone, which the filter estimates. Two quantities were calibrated on calibration runs only: the bottleneck capacity (0.89 persons/m/s, i.e. 53 persons/m/min, measured as the peak 30 s flow into the exit apron; this is an effective value for the zone model and lower than the line-measured flow reported in Section IV-A) and an effective storage density per zone, because a queue never fills a zone corner to corner.

The observation model maps the zone state to each reading. Because a windowed count includes people who passed through as well as people present, each reading is modelled as a non-negative combination of the window-mean occupancy and the window inflow of each zone, fitted by non-negative least squares on calibration runs, in the same way Determe et al. (2022) fit their extrapolation factor against a reference count. Under option B each sensor pair adds one overlap reading.

State estimation uses an ensemble Kalman filter with 100 members, updated with every report. Missing messages are skipped. After each update the ensemble is run 120 s ahead and, for each zone, the share of members that reach the red (or amber) threshold is taken as the probability of a critical density within the horizon. A red alert fires when this probability exceeds τ for two consecutive reports. τ = 0.7 was chosen on calibration runs as the value with the highest detection rate at no more than one false alarm per hour.

We do not reconstruct individuals. Earlier work found agent-level assimilation hard to scale, since the number of particles needed grows exponentially with the number of agents (Malleson et al., 2020), and our counts carry no identities.

## D. Baselines

*Full observability* feeds the true zone counts into the same twin and is the best case. *Sensor-only* inverts the current readings to zone densities and alerts when a density is already above red. *Trend* extrapolates the sensor-only densities over the last 30 s in a straight line for 120 s, automating Still's fill-predictor approach.

## E. Sensor placement

Sensors are placed on 20 candidate spots with budgets of 2, 4 and 6 sensors, using four strategies: random (a new layout per run), entrance and exit first, bottleneck-focused, and greedy mutual information. The last follows Liebig, Xu and May (2013): spots are added one at a time to maximise the mutual information about the readings at the remaining spots, using only the covariance of readings from calibration runs, so no test data and no observations of the event are needed.

## F. Evaluation

A critical event is a period of at least 10 s in which the true density of a zone is at or above its red threshold. An event counts as detected in time if a red alert for that zone fires before it starts and no more than 5 min earlier; the lead time is the difference. A red alert that is not followed by an event in that zone within 150 s (the forecast horizon plus 30 s) is a false alarm. We report the detection rate, the median lead time, false alarms per simulated hour and the density RMSE, separately for zones inside and outside sensor coverage. The acceptance thresholds set in our plan are a detection rate of at least 0.90, a median lead of at least 2 min, at most one false alarm per hour and an RMSE of at most 0.5 persons/m².

For the failure test, all sensors covering the approach, bottleneck front and bottleneck go offline 90 s before the first critical event in each surge test run.

Before the experiments we checked the simulated crowd with PedPy (Forschungszentrum Jülich, n.d.-a): the peak specific flow through the bottleneck was compared with the 82 persons/m/min guidance value (Still, 2014).
