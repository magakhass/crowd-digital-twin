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
        const int MovementSeed = 305;
        enum Phase { Entering, Watching, Approaching, Queued, Funnel, Passage, Exiting, Exited }

        public sealed class Person
        {
            public Vector2 Position { get; internal set; }
            public bool Exited { get; internal set; }
            internal Vector2 Seat;
            internal float LeaveAt;
            internal float Lane;
            internal float EntryLane;
            internal float WalkingSpeed;
            internal int State;
            internal int QueueSlot;
            internal Reading CurrentZone;
            public AlertLevel ZoneAlert => CurrentZone?.Reference ?? AlertLevel.Clear;
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
        readonly Vector2[] queueSlots, seats;
        readonly SortedSet<int> freeSlots;
        readonly System.Random random = new System.Random(MovementSeed);
        readonly VenueZone approach, front, passage, apron, firstAudience, entranceZone;
        readonly VenuePoint entrance, exit;
        int tick, nextGateTick;
        float arrivals;

        public VenueSimulation(VenueDefinition venue, ArrivalScenario scenario)
        {
            Venue = venue; Scenario = scenario;
            approach = venue.Zone("Z05"); front = venue.Zone("Z08");
            passage = venue.Zone("Z06"); apron = venue.Zone("Z07"); firstAudience = venue.Zone("Z02");
            entrance = venue.spawn_points.Single(); exit = venue.exit_points.Single();
            entranceZone = venue.Zone("Z01");
            seats = AudienceSeats();
            Zones = venue.zones.Select(z => new Reading(z, z.id == "Z01" ? "S01" :
                z.id == "Z08" ? "S02" : z.id == "Z06" ? "S03" : z.id == "Z07" ? "S04" : null)).ToArray();
            var queueRandom = new System.Random(MovementSeed + 1);
            queueSlots = Slots(front, queueRandom).Concat(Slots(approach, queueRandom)).ToArray();
            if (queueSlots.Length < Visitors) throw new InvalidDataException("Venue queue layout is too small for this demonstration.");
            freeSlots = new SortedSet<int>(Enumerable.Range(0, queueSlots.Length));
            SampleCounts();
        }

        static IEnumerable<Vector2> Slots(VenueZone zone, System.Random offsets)
        {
            const float spacing = .44f;
            int across = Mathf.FloorToInt(zone.Size.y / spacing);
            int rows = Mathf.FloorToInt(zone.Size.x / spacing);
            for (int row = 0; row < rows; row++)
                for (int i = 0; i < across; i++)
                {
                    int column = (across - 1) / 2 + (i % 2 == 0 ? -i / 2 : (i + 1) / 2);
                    float x = zone.x_max - (row + .5f) * spacing;
                    float z = zone.Centre.z + (column - (across - 1) * .5f) * spacing;
                    yield return new Vector2(x + ((float)offsets.NextDouble() - .5f) * .32f,
                        z + ((float)offsets.NextDouble() - .5f) * .24f);
                }
        }

        float Rate() => Scenario == ArrivalScenario.Normal ? 1.5f :
            Scenario == ArrivalScenario.Gradual ? Mathf.Min(8f, .8f + .055f * Seconds) :
            Seconds < 12 ? 1.5f : 20f;

        Vector2[] AudienceSeats()
        {
            var slots = new Vector2[Visitors];
            for (int id = 0; id < slots.Length; id++)
            {
                var zone = Venue.Zone(id % 3 == 0 ? "Z02" : id % 3 == 1 ? "Z03" : "Z04");
                int slot = id / 3;
                slots[id] = new Vector2(
                    zone.x_min + 1.4f + (slot % 12) * (zone.Size.x - 2.8f) / 11f,
                    zone.y_min + 1.8f + (slot / 12) * (zone.Size.y - 3.6f) / 9f);
            }
            for (int i = slots.Length - 1; i > 0; i--)
            {
                int j = random.Next(i + 1);
                var seat = slots[i];
                slots[i] = slots[j];
                slots[j] = seat;
            }
            return slots;
        }

        float Between(float min, float max) => Mathf.Lerp(min, max, (float)random.NextDouble());

        void Admit()
        {
            float entryLane = Mathf.Lerp(
                Mathf.Max(entranceZone.y_min, firstAudience.y_min),
                Mathf.Min(entranceZone.y_max, firstAudience.y_max), Between(.2f, .8f));
            people.Add(new Person
            {
                Position = new Vector2(entrance.x, entryLane),
                EntryLane = entryLane,
                Seat = seats[people.Count] + new Vector2(Between(-.22f, .22f), Between(-.45f, .45f)),
                Lane = Mathf.Lerp(passage.y_min, passage.y_max, Between(.2f, .8f)),
                WalkingSpeed = Between(1.2f, 1.8f)
            });
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
                        if (p.Position.x < firstAudience.x_min + .1f)
                            Move(p, new Vector2(firstAudience.x_min + .1f, p.EntryLane), p.WalkingSpeed);
                        else if (Move(p, p.Seat, p.WalkingSpeed)) { p.State = (int)Phase.Watching; p.LeaveAt = Seconds + DwellSeconds; }
                        break;
                    case Phase.Watching:
                        if (Seconds >= p.LeaveAt) p.State = (int)Phase.Approaching;
                        break;
                    case Phase.Approaching:
                        float laneOffset = (p.EntryLane - entranceZone.Centre.z) / entranceZone.Size.y;
                        var queueEntry = new Vector2(approach.x_min + .18f, approach.Centre.z + laneOffset * .45f * approach.Size.y);
                        if (Move(p, queueEntry, p.WalkingSpeed))
                        {
                            p.QueueSlot = freeSlots.Min;
                            freeSlots.Remove(p.QueueSlot);
                            p.State = (int)Phase.Queued;
                            queue.Add(p);
                        }
                        break;
                    case Phase.Funnel:
                        if (Move(p, new Vector2(passage.x_min - .05f, p.Lane), 1.1f)) p.State = (int)Phase.Passage;
                        break;
                    case Phase.Passage:
                        if (Move(p, new Vector2(apron.x_min + .15f, p.Lane), 1.1f)) p.State = (int)Phase.Exiting;
                        break;
                    case Phase.Exiting:
                        if (Move(p, new Vector2(exit.x, exit.y), p.WalkingSpeed))
                        { p.State = (int)Phase.Exited; p.Exited = true; Departed++; }
                        break;
                }

            foreach (var waiting in queue) Move(waiting, queueSlots[waiting.QueueSlot], 1.5f);
            if (queue.Count > 0 && tick >= nextGateTick &&
                Vector2.Distance(queue[0].Position, queueSlots[queue[0].QueueSlot]) < .10f)
            {
                var first = queue[0]; queue.RemoveAt(0);
                freeSlots.Add(first.QueueSlot);
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
                    if (reading.Zone.Contains(point)) { reading.Count++; person.CurrentZone = reading; break; }
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
