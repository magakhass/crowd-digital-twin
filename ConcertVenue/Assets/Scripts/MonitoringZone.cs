using UnityEngine;

namespace CrowdVenue
{
    public class MonitoringZone : MonoBehaviour
    {
        public string zoneId;
        public VenueZone Definition => (VenueRuntime.Current ?? throw new System.InvalidOperationException(
            "Shared venue configuration has not loaded")).Zone(zoneId);
        public Vector2 SizeMetres => Definition.Size;
        public float AccessibleArea => Definition.area_m2;
        public bool MovingZone => Definition.type == "dynamic";
        public float AmberThreshold => Definition.amber_persons_m2;
        public float RedThreshold => Definition.red_persons_m2;
        public bool Contains(Vector3 point) => Definition.Contains(point);

        public static void ValidateScene(VenueDefinition venue)
        {
            var objects = FindObjectsByType<MonitoringZone>(FindObjectsSortMode.None);
            var seen = new System.Collections.Generic.HashSet<string>();
            foreach (var item in objects)
            {
                var zone = venue.Zone(item.zoneId);
                var floor = GameObject.Find(zone.id + " " + zone.name + " Floor");
                var scale = new Vector3(zone.Size.x, .3f, zone.Size.y);
                if (!seen.Add(item.zoneId) || floor == null || (item.transform.position - zone.Centre).sqrMagnitude > .000001f ||
                    (floor.transform.position - (zone.Centre + Vector3.down * .15f)).sqrMagnitude > .000001f ||
                    (floor.transform.localScale - scale).sqrMagnitude > .000001f)
                    throw new System.InvalidOperationException("Scene geometry differs from the shared venue. Rebuild the venue before running.");
            }
            if (seen.Count != venue.zones.Length)
                throw new System.InvalidOperationException("Scene zone list differs from the shared venue. Rebuild the venue before running.");
            foreach (var point in System.Linq.Enumerable.Concat(venue.spawn_points, venue.exit_points))
            {
                var marker = GameObject.Find(point.id + " route marker");
                if (marker == null || (marker.transform.position - new Vector3(point.x, 0, point.y)).sqrMagnitude > .000001f)
                    throw new System.InvalidOperationException("Route markers differ from the shared venue. Rebuild the venue before running.");
            }
        }
    }
}
