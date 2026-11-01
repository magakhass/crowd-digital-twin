using UnityEngine;

namespace CrowdVenue
{
    public class MonitoringZone : MonoBehaviour
    {
        public string zoneId;
        public bool movingZone;
        public Vector2 sizeMetres;
        public float AccessibleArea => sizeMetres.x * sizeMetres.y;
        public float RedThreshold => movingZone ? 4f : 4.7f;
        public bool Contains(Vector3 point)
        {
            Vector3 p = transform.InverseTransformPoint(point);
            return Mathf.Abs(p.x) <= sizeMetres.x / 2 && Mathf.Abs(p.z) <= sizeMetres.y / 2;
        }
        private void OnDrawGizmosSelected()
        {
            Gizmos.color = Color.cyan;
            Gizmos.DrawWireCube(transform.position, new Vector3(sizeMetres.x, .15f, sizeMetres.y));
        }
    }
}
