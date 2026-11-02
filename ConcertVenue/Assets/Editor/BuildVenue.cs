using System.IO;
using System.Linq;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using CrowdVenue;

public static class BuildVenue
{
    static Material Mat(string name, Color color)
    {
        var existing = AssetDatabase.LoadAssetAtPath<Material>("Assets/Materials/" + name + ".mat");
        if (existing != null) return existing;
        var m = new Material(Shader.Find("Standard")); m.color = color;
        AssetDatabase.CreateAsset(m, "Assets/Materials/" + name + ".mat"); return m;
    }
    static GameObject Box(string name, Vector3 pos, Vector3 scale, Material m, Transform parent)
    {
        var g = GameObject.CreatePrimitive(PrimitiveType.Cube); g.name = name;
        g.transform.SetParent(parent); g.transform.position = pos; g.transform.localScale = scale;
        g.GetComponent<Renderer>().sharedMaterial = m;
        // Collider geometry is ready for an optional navigation surface.
        g.isStatic = true;
        return g;
    }
    static void Label(string value, float x, float z, float size, Transform parent)
    {
        var g = new GameObject(value); g.transform.SetParent(parent);
        g.transform.position = new Vector3(x,.08f,z); g.transform.rotation = Quaternion.Euler(90,0,0);
        var t = g.AddComponent<TextMesh>(); t.text=value; t.anchor=TextAnchor.MiddleCenter;
        t.alignment=TextAlignment.Center; t.characterSize=size; t.fontSize=64; t.color=Color.white;
    }
    [MenuItem("Crowd Venue/Rebuild venue (replaces current scene)")]
    public static void Create()
    {
        var venue = VenueDefinition.Load();
        Directory.CreateDirectory("Assets/Scenes"); Directory.CreateDirectory("Assets/Materials");
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var root = new GameObject("Concert Venue v1.1").transform;
        var geometry = new GameObject("Walkable geometry").transform; geometry.SetParent(root);
        var barriers = new GameObject("Walls and barriers").transform; barriers.SetParent(root);
        var zones = new GameObject("Monitoring zones").transform; zones.SetParent(root);
        var marks = new GameObject("Labels and route markers").transform; marks.SetParent(root);
        var floor=Mat("Audience navy",new Color(.08f,.16f,.23f));
        var transit=Mat("Transit teal",new Color(.06f,.34f,.36f));
        var risk=Mat("Bottleneck amber",new Color(.75f,.38f,.06f));
        var wall=Mat("Barriers",new Color(.32f,.39f,.45f));
        var stage=Mat("Stage",new Color(.18f,.12f,.3f));
        foreach (var definition in venue.zones)
        {
            var material = definition.id == "Z06" || definition.id == "Z08" ? risk :
                definition.type == "static" ? floor : transit;
            Box(definition.id + " " + definition.name + " Floor", definition.Centre + Vector3.down * .15f,
                new Vector3(definition.Size.x, .3f, definition.Size.y), material, geometry);
            var z = new GameObject(definition.id + " " + definition.name);
            z.transform.SetParent(zones); z.transform.position = definition.Centre;
            z.AddComponent<MonitoringZone>().zoneId = definition.id;
            Label(definition.id, definition.Centre.x, definition.Centre.z,
                definition.id == "Z06" ? .1f : definition.Size.x <= 6 ? .18f : .25f, marks);
        }
        const float thickness = .3f;
        System.Action<string, float, float, float, float> barrier = (n, x, z, w, d) =>
            Box(n, new Vector3(x, 1, z), new Vector3(w, 2, d), wall, barriers);
        foreach (var zone in venue.zones)
        {
            barrier(zone.id + " north", zone.Centre.x, zone.y_max + thickness / 2, zone.Size.x, thickness);
            barrier(zone.id + " south", zone.Centre.x, zone.y_min - thickness / 2, zone.Size.x, thickness);
        }
        // Vertical shoulders close the wider side around each shared opening.
        foreach (var link in venue.links)
        {
            var a = venue.Zone(link.from); var b = venue.Zone(link.to);
            if (a.x_max != b.x_min)
                throw new InvalidDataException("Venue fixture generator requires west-to-east adjacent links");
            float low = Mathf.Max(a.y_min, b.y_min), high = Mathf.Min(a.y_max, b.y_max);
            if (Mathf.Abs(high - low - link.width_m) > .001f)
                throw new InvalidDataException("Link width does not match the geometric opening");
            foreach (var side in new[] { a, b })
            {
                float x = a.x_max + (side == a ? thickness / 2 : -thickness / 2);
                if (side.y_min < low)
                    barrier(side.id + " lower shoulder", x, (side.y_min + low) / 2, thickness, low - side.y_min);
                if (side.y_max > high)
                    barrier(side.id + " upper shoulder", x, (side.y_max + high) / 2, thickness, side.y_max - high);
            }
        }
        Box("Stage (outside accessible zones)",new Vector3(0,.6f,15),new Vector3(16,1.2f,5),stage,root);
        Label("STAGE",0,15,.35f,marks); Label("ENTRANCE",-23,-2,.12f,marks); Label("EXIT",38,-4,.2f,marks);
        foreach (var zone in venue.zones)
            Label(zone.type == "static" ? "WATCH / DWELL" : ">", zone.Centre.x,
                zone.Centre.z - 1, zone.id == "Z06" ? .08f : .12f, marks);
        foreach (var point in venue.spawn_points.Concat(venue.exit_points))
        {
            var marker = new GameObject(point.id + " route marker"); marker.transform.SetParent(root);
            marker.transform.position = new Vector3(point.x, 0, point.y);
        }
        var cam=new GameObject("Main Camera");cam.tag="MainCamera";cam.transform.position=new Vector3(6,65,2);cam.transform.rotation=Quaternion.Euler(90,0,0);
        var c=cam.AddComponent<Camera>();c.orthographic=true;c.orthographicSize=25;c.backgroundColor=new Color(.025f,.04f,.065f);c.clearFlags=CameraClearFlags.SolidColor;cam.AddComponent<VenueCamera>();cam.AddComponent<AudioListener>();
        var light=new GameObject("Sun");light.AddComponent<Light>().type=LightType.Directional;light.GetComponent<Light>().intensity=1.2f;light.transform.rotation=Quaternion.Euler(60,-20,0);
        RenderSettings.ambientLight=new Color(.65f,.65f,.65f);
        EditorSceneManager.SaveScene(UnityEngine.SceneManagement.SceneManager.GetActiveScene(),"Assets/Scenes/ConcertVenue.unity");
        EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene("Assets/Scenes/ConcertVenue.unity",true)};
        AssetDatabase.SaveAssets();Debug.Log("VENUE_BUILD_SUCCESS: shared configuration loaded, scene saved.");
    }
}
