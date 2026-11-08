using System;
using System.IO;
using System.Linq;
using UnityEngine;

namespace CrowdVenue
{
    [Serializable] public class VenueZone
    {
        public string id, name, type;
        public float x_min, x_max, y_min, y_max, area_m2;
        public float amber_persons_m2, red_persons_m2;
        public Vector2 Size => new Vector2(x_max - x_min, y_max - y_min);
        public Vector3 Centre => new Vector3((x_min + x_max) / 2, 0, (y_min + y_max) / 2);
        public bool Contains(Vector3 point) => point.x >= x_min && point.x < x_max && point.z >= y_min && point.z < y_max;
    }
    [Serializable] public class VenueLink { public string from, to; public float width_m; }
    [Serializable] public class VenuePoint { public string id; public float x, y; }
    [Serializable] public class VenueDefinition
    {
        public string venue_id, version, units;
        public VenueZone[] zones;
        public VenueLink[] links;
        public VenuePoint[] spawn_points, exit_points;

        public VenueZone Zone(string id) => zones.FirstOrDefault(z => z.id == id)
            ?? throw new InvalidDataException("Unknown venue zone: " + id);

        public static string DefaultPath => Path.GetFullPath(Path.Combine(Application.dataPath,
            "../../shared/venues/concert_venue_v1.json"));

        public static VenueDefinition Load()
        {
            string path = Environment.GetEnvironmentVariable("VENUE_FILE");
            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length; i++)
                if (args[i] == "-venue")
                {
                    if (i + 1 >= args.Length) throw new ArgumentException("-venue requires a JSON path");
                    path = args[++i];
                }
            if (string.IsNullOrWhiteSpace(path)) path = DefaultPath;
            var venue = JsonUtility.FromJson<VenueDefinition>(File.ReadAllText(path));
            if (venue == null || venue.units != "metres" || venue.zones == null || venue.zones.Length == 0)
                throw new InvalidDataException("Invalid venue or unsupported units: " + path);
            var ids = new System.Collections.Generic.HashSet<string>();
            foreach (var zone in venue.zones)
            {
                if (zone == null || string.IsNullOrWhiteSpace(zone.id) || !ids.Add(zone.id) ||
                    zone.x_max <= zone.x_min || zone.y_max <= zone.y_min ||
                    Mathf.Abs(zone.Size.x * zone.Size.y - zone.area_m2) > .001f ||
                    (zone.type != "static" && zone.type != "dynamic") ||
                    !(zone.amber_persons_m2 > 0 && zone.red_persons_m2 > zone.amber_persons_m2))
                    throw new InvalidDataException("Invalid venue zone in " + path);
            }
            if (venue.links == null || venue.spawn_points == null || venue.exit_points == null)
                throw new InvalidDataException("Venue links and route points are required");
            foreach (var link in venue.links)
                if (!ids.Contains(link.from) || !ids.Contains(link.to) || !(link.width_m > 0))
                    throw new InvalidDataException("Invalid venue link");
            return venue;
        }
    }

    public static class VenueRuntime
    {
        public static VenueDefinition Current { get; private set; }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        public static void Initialize()
        {
            Current = null;
            Current = VenueDefinition.Load();
        }
    }
}
