using UnityEngine;

namespace CrowdVenue
{
    public class MonitoringZone : MonoBehaviour
    {
        // This identifier is the only zone configuration serialized in the scene.
        public string zoneId;
        public VenueZone Definition => (VenueRuntime.Current ?? throw new System.InvalidOperationException(
            "Shared venue configuration has not loaded")).Zone(zoneId);
        public Vector2 SizeMetres => Definition.Size;
        public float AccessibleArea => Definition.area_m2;
        public bool MovingZone => Definition.type == "dynamic";
        public float AmberThreshold => Definition.amber_persons_m2;
        public float RedThreshold => Definition.red_persons_m2;
        public bool Contains(Vector3 point) => Definition.Contains(point);

        private void Start()
        {
            var zone = Definition;
            transform.position = zone.Centre;
            var floor = GameObject.Find(zone.id + " " + zone.name + " Floor");
            if (floor == null) throw new System.InvalidOperationException("Rebuild venue: missing floor " + zone.id);
            floor.transform.position = zone.Centre + Vector3.down * .15f;
            floor.transform.localScale = new Vector3(zone.Size.x, .3f, zone.Size.y);
        }
    }
}
