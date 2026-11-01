using UnityEngine;

namespace CrowdVenue
{
    public class VenueCamera : MonoBehaviour
    {
        private void OnGUI()
        {
            GUI.Box(new Rect(16,16,380,100), "CONCERT VENUE | v1.0");
            GUI.Label(new Rect(30,42,350,65), "Scale: 1 unit = 1 metre\nEntrance > audience area > 3 m bottleneck > exit\nLayout prototype | no crowd estimation running");
        }
    }
}
