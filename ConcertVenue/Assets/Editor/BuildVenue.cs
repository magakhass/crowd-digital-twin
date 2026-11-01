using System.IO;
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
        // Collider geometry is ready for an optional AI Navigation surface.
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
        Directory.CreateDirectory("Assets/Scenes"); Directory.CreateDirectory("Assets/Materials");
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var root = new GameObject("Concert Venue v1.0").transform;
        var geometry = new GameObject("Walkable geometry").transform; geometry.SetParent(root);
        var barriers = new GameObject("Walls and barriers").transform; barriers.SetParent(root);
        var zones = new GameObject("Monitoring zones").transform; zones.SetParent(root);
        var marks = new GameObject("Labels and route markers").transform; marks.SetParent(root);
        var floor=Mat("Audience navy",new Color(.08f,.16f,.23f));
        var transit=Mat("Transit teal",new Color(.06f,.34f,.36f));
        var risk=Mat("Bottleneck amber",new Color(.75f,.38f,.06f));
        var wall=Mat("Barriers",new Color(.32f,.39f,.45f));
        var stage=Mat("Stage",new Color(.18f,.12f,.3f));
        // Contiguous rectangles; accessible areas exclude walls and the stage.
        string[] ids={"Z01 Entrance","Z02 Audience west","Z03 Audience centre","Z04 Audience east","Z05 Approach","Z06 Bottleneck","Z07 Exit apron"};
        float[] xs={-23,-12,0,12,23,29,36};
        float[] widths={10,12,12,12,10,2,12};
        float[] depths={6,24,24,24,12,3,12};
        Material[] materials={transit,floor,floor,floor,transit,risk,transit};
        var csv="zone_id,centre_x_m,centre_z_m,width_m,depth_m,accessible_area_m2,type,amber_persons_m2,red_persons_m2\n";
        for(int i=0;i<ids.Length;i++)
        {
            Box(ids[i]+" Floor",new Vector3(xs[i],-.15f,0),new Vector3(widths[i],.3f,depths[i]),materials[i],geometry);
            var z=new GameObject(ids[i]); z.transform.SetParent(zones); z.transform.position=new Vector3(xs[i],0,0);
            var zone=z.AddComponent<MonitoringZone>(); zone.zoneId="Z0"+(i+1); zone.sizeMetres=new Vector2(widths[i],depths[i]); zone.movingZone=(i==0||i>=4);
            csv+=$"{zone.zoneId},{xs[i]},0,{widths[i]},{depths[i]},{zone.AccessibleArea},{(zone.movingZone?"dynamic":"static")},3,{zone.RedThreshold.ToString(System.Globalization.CultureInfo.InvariantCulture)}\n";
            Label("Z0"+(i+1),xs[i],0,i==5?.3f:.65f,marks);
        }
        // Wall centres offset by half thickness so declared floor areas remain accessible.
        float thick=.3f;
        System.Action<string,float,float,float,float> barrier=(n,x,z,w,d)=>Box(n,new Vector3(x,1,z),new Vector3(w,2,d),wall,barriers);
        barrier("Audience north",0,12.15f,36.6f,thick); barrier("Audience south",0,-12.15f,36.6f,thick);
        foreach(float z in new[]{-7.5f,7.5f}) barrier("Entrance shoulder",-18.15f,z,thick,9);
        foreach(float z in new[]{-9f,9f}) barrier("Audience exit shoulder",18.15f,z,thick,6);
        foreach(float z in new[]{-3.15f,3.15f}) barrier("Entrance side",-23,z,10,thick);
        foreach(float z in new[]{-6.15f,6.15f}) {barrier("Approach side",23,z,10,thick);barrier("Exit apron side",36,z,12,thick);}
        foreach(float z in new[]{-3.75f,3.75f}) {barrier("Bottleneck entry shoulder",28.15f,z,thick,4.5f);barrier("Bottleneck exit shoulder",29.85f,z,thick,4.5f);}
        foreach(float z in new[]{-1.65f,1.65f}) barrier("Bottleneck side",29,z,2,thick);
        Box("Stage (outside accessible zones)",new Vector3(0,.6f,15),new Vector3(16,1.2f,5),stage,root);
        Label("STAGE",0,15,.8f,marks); Label("ENTRANCE",-23,-2,.3f,marks); Label("EXIT",38,-4,.5f,marks);
        for(int x=-24;x<=39;x+=4) Label(">",x,-.9f,.3f,marks);
        var spawn=new GameObject("Entrance spawn marker"); spawn.transform.SetParent(root); spawn.transform.position=new Vector3(-27,0,0);
        var exit=new GameObject("Exit destination marker");exit.transform.SetParent(root);exit.transform.position=new Vector3(41,0,0);
        var cam=new GameObject("Main Camera");cam.tag="MainCamera";cam.transform.position=new Vector3(6,65,2);cam.transform.rotation=Quaternion.Euler(90,0,0);
        var c=cam.AddComponent<Camera>();c.orthographic=true;c.orthographicSize=25;c.backgroundColor=new Color(.025f,.04f,.065f);c.clearFlags=CameraClearFlags.SolidColor;cam.AddComponent<VenueCamera>();cam.AddComponent<AudioListener>();
        var light=new GameObject("Sun");light.AddComponent<Light>().type=LightType.Directional;light.GetComponent<Light>().intensity=1.2f;light.transform.rotation=Quaternion.Euler(60,-20,0);
        RenderSettings.ambientLight=new Color(.65f,.65f,.65f);
        Directory.CreateDirectory("Documentation");File.WriteAllText("Documentation/zones.csv",csv);
        EditorSceneManager.SaveScene(UnityEngine.SceneManagement.SceneManager.GetActiveScene(),"Assets/Scenes/ConcertVenue.unity");
        EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene("Assets/Scenes/ConcertVenue.unity",true)};
        AssetDatabase.SaveAssets();Debug.Log("VENUE_BUILD_SUCCESS: 7 zones, 3 metre bottleneck, scene saved.");
    }
}
