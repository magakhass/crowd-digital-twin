using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using UnityEngine;

namespace CrowdVenue
{
    public enum ArrivalScenario { Normal, Gradual, Surge }
    public enum AlertLevel { Clear, Amber, Red }

    public sealed class VenueSimulation
    {
        public const int Visitors = 360;
        const int StepsPerSecond = 20;
        public const float StepSeconds = 1f / StepsPerSecond;
        public const int SampleEveryTicks = 5 * StepsPerSecond;
        const float DwellSeconds = 14f;
        const float GatePerSecond = 1.8f;
        enum Phase { Entering, Watching, Approaching, Queued, Funnel, Passage, Exiting, Exited }

        public sealed class Person
        {
            public Vector2 Position { get; internal set; }
            public bool Exited { get; internal set; }
            internal Vector2 Seat;
            internal float LeaveAt;
            internal float Lane;
            internal int State;
        }

        public sealed class Reading
        {
            public readonly VenueZone Zone;
            public readonly string Sensor;
            public int Count, Sample = -1;
            public float Peak, SamplePeak;
            public float FirstRed = -1, FirstSampleRed = -1;
            public float AmberSeconds, RedSeconds, SampleRedSeconds;
            public float Density => Count / Zone.area_m2;
            public float SampleDensity => Sample / Zone.area_m2;
            public AlertLevel Reference => Level(Density);
            public AlertLevel Observed => Level(SampleDensity);
            public AlertLevel Level(float density) => density >= Zone.red_persons_m2 ? AlertLevel.Red :
                density >= Zone.amber_persons_m2 ? AlertLevel.Amber : AlertLevel.Clear;
            internal Reading(VenueZone zone, string sensor) { Zone = zone; Sensor = sensor; }
        }

        public readonly VenueDefinition Venue;
        public readonly ArrivalScenario Scenario;
        public readonly Reading[] Zones;
        public IReadOnlyList<Person> People => people;
        public int Arrived => people.Count;
        public int Watching => people.Count(p => p.State == (int)Phase.Watching);
        public int Departed { get; private set; }
        public float Seconds => tick * StepSeconds;
        public float SampleTime { get; private set; }
        public bool Finished => Departed == Visitors;
        readonly List<Person> people = new List<Person>(Visitors);
        readonly List<Person> queue = new List<Person>(Visitors);
        readonly List<string> rows = new List<string>();
        readonly Vector2[] queueSlots;
        readonly VenueZone approach, front, passage, apron, firstAudience;
        readonly VenuePoint entrance, exit;
        int tick, nextGateTick;
        float arrivals;

        public VenueSimulation(VenueDefinition venue, ArrivalScenario scenario)
        {
            Venue = venue; Scenario = scenario;
            approach = venue.Zone("Z05"); front = venue.Zone("Z08");
            passage = venue.Zone("Z06"); apron = venue.Zone("Z07"); firstAudience = venue.Zone("Z02");
            entrance = venue.spawn_points.Single(); exit = venue.exit_points.Single();
            Zones = venue.zones.Select(z => new Reading(z, z.id == "Z01" ? "S01" :
                z.id == "Z08" ? "S02" : z.id == "Z06" ? "S03" : z.id == "Z07" ? "S04" : null)).ToArray();
            queueSlots = Slots(front).Concat(Slots(approach)).ToArray();
            if (queueSlots.Length < Visitors) throw new InvalidDataException("Venue queue layout is too small for this demonstration.");
            SampleCounts();
        }

        static IEnumerable<Vector2> Slots(VenueZone zone)
        {
            const float spacing = .44f;
            int across = Mathf.FloorToInt(zone.Size.y / spacing);
            int rows = Mathf.FloorToInt(zone.Size.x / spacing);
            for (int row = 0; row < rows; row++)
                for (int column = 0; column < across; column++)
                    yield return new Vector2(zone.x_max - (row + .5f) * spacing,
                        zone.Centre.z + (column - (across - 1) * .5f) * spacing);
        }

        float Rate() => Scenario == ArrivalScenario.Normal ? 1.5f :
            Scenario == ArrivalScenario.Gradual ? Mathf.Min(8f, .8f + .055f * Seconds) :
            Seconds < 12 ? 1.5f : 20f;

        void Admit()
        {
            int id = people.Count;
            var zone = Venue.Zone(id % 3 == 0 ? "Z02" : id % 3 == 1 ? "Z03" : "Z04");
            int slot = id / 3;
            var seat = new Vector2(zone.x_min + 1.4f + (slot % 12) * (zone.Size.x - 2.8f) / 11f,
                zone.y_min + 1.8f + (slot / 12) * (zone.Size.y - 3.6f) / 9f);
            people.Add(new Person { Position = new Vector2(entrance.x, entrance.y), Seat = seat,
                Lane = passage.Centre.z + ((id % 3) - 1) * passage.Size.y * .25f });
        }

        static bool Move(Person p, Vector2 target, float speed)
        {
            p.Position = Vector2.MoveTowards(p.Position, target, speed * StepSeconds);
            return p.Position == target;
        }

        public void Tick()
        {
            if (Finished) return;
            tick++;
            arrivals += Rate() * StepSeconds;
            while (people.Count < Visitors && arrivals >= 1f) { Admit(); arrivals -= 1f; }

            foreach (var p in people)
                switch ((Phase)p.State)
                {
                    case Phase.Entering:
                        // Cross the narrower entrance mouth before moving towards the audience target.
                        if (p.Position.x < firstAudience.x_min + .1f)
                            Move(p, new Vector2(firstAudience.x_min + .1f, entrance.y), 1.5f);
                        else if (Move(p, p.Seat, 1.5f)) { p.State = (int)Phase.Watching; p.LeaveAt = Seconds + DwellSeconds; }
                        break;
                    case Phase.Watching:
                        if (Seconds >= p.LeaveAt) p.State = (int)Phase.Approaching;
                        break;
                    case Phase.Approaching:
                        if (Move(p, new Vector2(approach.x_min + .18f, approach.Centre.z), 1.5f))
                        { p.State = (int)Phase.Queued; queue.Add(p); }
                        break;
                    case Phase.Funnel:
                        if (Move(p, new Vector2(passage.x_min - .05f, p.Lane), 1.1f)) p.State = (int)Phase.Passage;
                        break;
                    case Phase.Passage:
                        if (Move(p, new Vector2(apron.x_min + .15f, p.Lane), 1.1f)) p.State = (int)Phase.Exiting;
                        break;
                    case Phase.Exiting:
                        if (Move(p, new Vector2(exit.x, exit.y), 1.5f))
                        { p.State = (int)Phase.Exited; p.Exited = true; Departed++; }
                        break;
                }

            for (int i = 0; i < queue.Count; i++) Move(queue[i], queueSlots[i], 1.5f);
            if (queue.Count > 0 && tick >= nextGateTick &&
                Vector2.Distance(queue[0].Position, queueSlots[0]) < .10f)
            {
                var first = queue[0]; queue.RemoveAt(0);
                first.State = (int)Phase.Funnel;
                nextGateTick = tick + Mathf.CeilToInt(1f / (GatePerSecond * StepSeconds));
            }
            CountPositions();
            if (tick % SampleEveryTicks == 0) SampleCounts();
        }

        void CountPositions()
        {
            foreach (var reading in Zones) reading.Count = 0;
            foreach (var person in people)
            {
                if (person.Exited) continue;
                var point = new Vector3(person.Position.x, 0, person.Position.y);
                foreach (var reading in Zones)
                    if (reading.Zone.Contains(point)) { reading.Count++; break; }
            }
            foreach (var reading in Zones)
            {
                reading.Peak = Mathf.Max(reading.Peak, reading.Density);
                if (reading.Reference == AlertLevel.Amber) reading.AmberSeconds += StepSeconds;
                if (reading.Reference == AlertLevel.Red)
                {
                    reading.RedSeconds += StepSeconds;
                    if (reading.FirstRed < 0) reading.FirstRed = Seconds;
                }
                if (reading.Sensor != null && reading.Observed == AlertLevel.Red) reading.SampleRedSeconds += StepSeconds;
            }
        }

        void SampleCounts()
        {
            SampleTime = Seconds;
            foreach (var reading in Zones)
            {
                if (reading.Sensor != null)
                {
                    reading.Sample = reading.Count;
                    reading.SamplePeak = Mathf.Max(reading.SamplePeak, reading.SampleDensity);
                    if (reading.Observed == AlertLevel.Red && reading.FirstSampleRed < 0)
                        reading.FirstSampleRed = Seconds;
                }
                rows.Add(FormattableString.Invariant(
                    $"{Scenario},{Seconds:0.00},{reading.Zone.id},{reading.Count},{reading.Density:0.000},{reading.Reference},{reading.Sensor ?? ""},{(reading.Sensor == null ? "" : reading.Sample.ToString(CultureInfo.InvariantCulture))},{(reading.Sensor == null ? "" : reading.Observed.ToString())}"));
            }
        }

        public string Export(string directory)
        {
            Directory.CreateDirectory(directory);
            string prefix = Path.Combine(directory, $"venue-{Scenario.ToString().ToLowerInvariant()}-{DateTime.UtcNow:yyyyMMdd-HHmmssfff}");
            File.WriteAllLines(prefix + "-samples.csv",
                new[] { "scenario,seconds,zone,reference_count,reference_density,reference_level,sensor,sampled_count,sampled_level" }.Concat(rows));
            var summary = Zones.Select(r => FormattableString.Invariant(
                $"{Scenario},{Seconds:0.00},{Arrived},{Departed},{r.Zone.id},{r.Peak:0.000},{r.FirstRed:0.00},{r.AmberSeconds:0.00},{r.RedSeconds:0.00},{r.Sensor ?? ""},{Number(r, r.SamplePeak)},{Number(r, r.FirstSampleRed)},{Number(r, r.SampleRedSeconds)}"));
            File.WriteAllLines(prefix + "-summary.csv",
                new[] { "scenario,elapsed_seconds,arrived,departed,zone,reference_peak,reference_first_red_s,reference_amber_s,reference_red_s,sensor,sampled_peak,sampled_first_red_s,sampled_red_s" }.Concat(summary));
            return directory;
        }

        static string Number(Reading r, float value) => r.Sensor == null ? "" : value.ToString("0.000", CultureInfo.InvariantCulture);
    }
}
