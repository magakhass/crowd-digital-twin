using System;
using System.Linq;
using System.IO;
using CrowdVenue;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

[InitializeOnLoad]
public static class ValidateVenueDemo
{
    const string Pending = "VenueDemoSmokePending";
    const string Exiting = "VenueDemoSmokeExitCode";
    static int frames;

    static ValidateVenueDemo()
    {
        EditorApplication.playModeStateChanged += OnState;
        if (SessionState.GetBool(Pending, false)) EditorApplication.update += Poll;
    }

    public static void Begin()
    {
        EditorSceneManager.OpenScene("Assets/Scenes/ConcertVenue.unity");
        SessionState.SetBool(Pending, true);
        SessionState.SetInt(Exiting, -1);
        EditorApplication.update -= Poll;
        EditorApplication.update += Poll;
        EditorApplication.isPlaying = true;
    }

    static void OnState(PlayModeStateChange state)
    {
        if (state != PlayModeStateChange.EnteredEditMode) return;
        int code = SessionState.GetInt(Exiting, -1);
        if (code < 0) return;
        SessionState.EraseInt(Exiting);
        if (Application.isBatchMode) EditorApplication.Exit(code);
    }

    static void Poll()
    {
        if (!EditorApplication.isPlaying || !SessionState.GetBool(Pending, false)) return;
        var camera = UnityEngine.Object.FindAnyObjectByType<VenueCamera>();
        if ((camera == null || !camera.IsReady) && ++frames < 180) return;
        EditorApplication.update -= Poll;
        SessionState.SetBool(Pending, false);
        int code = 0;
        try
        {
            if (camera == null || !camera.IsReady) throw new Exception("Unity did not start the venue monitor.");
            RunScenarios();
        }
        catch (Exception error) { Debug.LogException(error); code = 1; }
        SessionState.SetInt(Exiting, code);
        EditorApplication.isPlaying = false;
    }

    static void RunScenarios()
    {
        var venue = VenueRuntime.Current;
        MonitoringZone.ValidateScene(venue);
        var changed = JsonUtility.FromJson<VenueDefinition>(JsonUtility.ToJson(venue));
        changed.Zone("Z08").x_min += .25f;
        bool rejected = false;
        try { MonitoringZone.ValidateScene(changed); }
        catch (InvalidOperationException) { rejected = true; }
        if (!rejected) throw new Exception("A stale scene was accepted.");
        changed = JsonUtility.FromJson<VenueDefinition>(JsonUtility.ToJson(venue));
        changed.Zone("Z08").red_persons_m2 += .25f;
        MonitoringZone.ValidateScene(changed);
        var baseline = new float[3];
        var values = (ArrivalScenario[])Enum.GetValues(typeof(ArrivalScenario));
        if (values.Length != 3) throw new Exception("Expected exactly three scenarios.");
        foreach (var scenario in values)
        {
            var model = new VenueSimulation(venue, scenario);
            if (model.Zones.Count(r => r.Sensor != null) != 4)
                throw new Exception("Expected four sampled zones.");
            int watching = 0;
            while (!model.Finished && model.Seconds < 550)
            {
                model.Tick();
                if (model.Zones.Sum(r => r.Count) != model.Arrived - model.Departed)
                    throw new Exception("A visitor is outside the accessible venue.");
                watching = Math.Max(watching, model.Watching);
                if (model.Zones.Any(r => r.Sensor == null && r.Sample >= 0))
                    throw new Exception("An unsensed zone has a sample.");
            }
            if (!model.Finished || watching == 0) throw new Exception("Scenario did not complete enter/watch/leave.");
            var front = model.Zones.Single(r => r.Zone.id == "Z08");
            var passage = model.Zones.Single(r => r.Zone.id == "Z06");
            if (front.Level(front.Zone.amber_persons_m2) != AlertLevel.Amber ||
                front.Level(front.Zone.red_persons_m2) != AlertLevel.Red)
                throw new Exception("Threshold boundary mismatch.");
            baseline[(int)scenario] = front.Peak;
            var path = Environment.GetEnvironmentVariable("VENUE_SMOKE_RESULTS");
            if (!string.IsNullOrEmpty(path)) model.Export(path);
            Debug.Log(FormattableString.Invariant(
                $"VENUE_DEMO_PASS {scenario}: {model.Departed} exited in {model.Seconds:0.0}s; max watching {watching}; Z08 peak {front.Peak:0.00} / sampled {front.SamplePeak:0.00}; Z08 first red {front.FirstRed:0.00} / sampled {front.FirstSampleRed:0.00}; Z06 peak {passage.Peak:0.00}"));
        }
        if (!(baseline[0] < baseline[1] && baseline[1] < baseline[2]))
            throw new Exception("Expected progressively higher bottleneck-front peaks.");
        Debug.Log("VENUE_PLAY_MODE_SMOKE_PASS: three scenarios, counts conserved, shared thresholds, sparse sampling and stale geometry guard.");
    }
}
