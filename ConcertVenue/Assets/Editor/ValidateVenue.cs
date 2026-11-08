using System;
using System.IO;
using System.Linq;
using CrowdVenue;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class ValidateVenue
{
    public static void Run()
    {
        EditorSceneManager.OpenScene("Assets/Scenes/ConcertVenue.unity");
        VenueRuntime.Initialize();
        var venue = VenueRuntime.Current;
        var zones = UnityEngine.Object.FindObjectsByType<MonitoringZone>(FindObjectsSortMode.None);
        if (zones.Length != venue.zones.Length) throw new Exception("Zone count mismatch");
        foreach (var zone in zones)
        {
            var source = venue.Zone(zone.zoneId);
            if (zone.RedThreshold != source.red_persons_m2 || zone.AmberThreshold != source.amber_persons_m2 ||
                zone.AccessibleArea != source.area_m2) throw new Exception("Shared definition mismatch");
            if (!zone.Contains(source.Centre) || zone.Contains(new Vector3(source.x_max, 0, source.Centre.z)))
                throw new Exception("Half-open membership failed");
        }
        string old = Environment.GetEnvironmentVariable("VENUE_FILE");
        string temporary = Path.GetTempFileName();
        try
        {
            var altered = VenueDefinition.Load();
            altered.Zone("Z08").red_persons_m2 = 4.25f;
            File.WriteAllText(temporary, JsonUtility.ToJson(altered));
            Environment.SetEnvironmentVariable("VENUE_FILE", temporary);
            VenueRuntime.Initialize();
            if (zones.Single(z => z.zoneId == "Z08").RedThreshold != 4.25f)
                throw new Exception("Threshold was not read from external venue");
        }
        finally
        {
            Environment.SetEnvironmentVariable("VENUE_FILE", old);
            File.Delete(temporary);
            VenueRuntime.Initialize();
        }
        Debug.Log("VENUE_INTEGRATION_PASS: 8 zone definitions, half-open membership and external threshold reload.");
    }

    public static void RebuildAndCheck()
    {
        BuildVenue.Create();
        Run();
    }

    public static void RebuildCheckAndCapture()
    {
        RebuildAndCheck();
        Capture();
    }

    public static void Capture()
    {
        EditorSceneManager.OpenScene("Assets/Scenes/ConcertVenue.unity");
        var camera = Camera.main;
        var target = new RenderTexture(1600, 900, 24);
        var image = new Texture2D(1600, 900, TextureFormat.RGB24, false);
        try
        {
            camera.targetTexture = target;
            camera.Render();
            RenderTexture.active = target;
            image.ReadPixels(new Rect(0, 0, 1600, 900), 0, 0);
            image.Apply();
            string path = Path.GetFullPath(Path.Combine(Application.dataPath, "../../docs/venue/venue-overview.png"));
            File.WriteAllBytes(path, image.EncodeToPNG());
            Debug.Log("VENUE_PREVIEW_SAVED: " + path);
        }
        finally
        {
            camera.targetTexture = null;
            RenderTexture.active = null;
            UnityEngine.Object.DestroyImmediate(target);
            UnityEngine.Object.DestroyImmediate(image);
        }
    }
}
