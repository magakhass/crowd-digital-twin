using System;
using System.IO;
using System.Linq;
using UnityEngine;

namespace CrowdVenue
{
    public class VenueCamera : MonoBehaviour
    {
        static readonly Color Background = Hex(0xf2f3f5), Panel = Hex(0xffffff), Border = Hex(0xc8cdd4);
        static readonly Color White = Hex(0x222831), Muted = Hex(0x505c6b), Cyan = Hex(0x006b73);
        static readonly Color Amber = Hex(0x805000), Red = Hex(0xa7252a), Green = Hex(0x256447);
        static readonly string[] Names = { "Normal flow", "Gradual rise", "Sudden surge" };
        static readonly Color SensorBlue = Hex(0x0073ee);
        const float Width = 1440, Height = 664;

        VenueSimulation model;
        public bool IsReady => model != null;
        ArrivalScenario scenario;
        int speed = 4;
        bool running;
        float accumulator;
        string message;
        Texture2D dot;

        static Color Hex(int c) => new Color32((byte)(c >> 16), (byte)(c >> 8), (byte)c, 255);

        void Start()
        {
            try
            {
                var venue = VenueRuntime.Current ?? throw new InvalidDataException("The shared venue file could not be loaded.");
                MonitoringZone.ValidateScene(venue);
                Reset(false);
            }
            catch (Exception error) { message = error.Message; Debug.LogError(error.Message); }
        }

        void Reset(bool play)
        {
            model = new VenueSimulation(VenueRuntime.Current, scenario);
            running = play;
            accumulator = 0;
            message = null;
        }

        void Update()
        {
            if (!running || model == null) return;
            accumulator += Mathf.Min(Time.unscaledDeltaTime, .15f) * speed;
            while (accumulator >= VenueSimulation.StepSeconds && !model.Finished)
            {
                model.Tick();
                accumulator -= VenueSimulation.StepSeconds;
            }
            if (model.Finished) running = false;
        }

        void OnDestroy() { if (dot != null) Destroy(dot); }

        void OnGUI()
        {
            if (!Application.isPlaying) return;
            GUI.color = Color.white;
            Box(new Rect(0, 0, Screen.width, Screen.height), Background);
            float scale = Mathf.Min(Screen.width / Width, Screen.height / Height);
            var previous = GUI.matrix;
            GUI.matrix = Matrix4x4.TRS(new Vector3((Screen.width - Width * scale) / 2,
                (Screen.height - Height * scale) / 2, 0), Quaternion.identity, new Vector3(scale, scale, 1));

            Label(28, 28, 1050, 40, "Crowd monitoring in Unity", 29, White, true);
            Label(29, 74, 970, 25, "Choose an arrival scenario and press Start run.", 17, Muted);

            if (model == null)
                Label(30, 140, 1350, 40, message ?? "Loading venue…", 19, Red);
            else
            {
                Controls();
                DrawMap();
                Readings();
            }
            GUI.matrix = previous;
        }

        void Controls()
        {
            Card(28, 119, 1384, 63);
            for (int i = 0; i < Names.Length; i++)
                if (Button(42 + i * 169, 133, 159, 35, Names[i], (int)scenario == i))
                { scenario = (ArrivalScenario)i; Reset(false); }
            if (Button(574, 133, 125, 35, model.Finished ? "Run again" : running ? "Pause" : model.Seconds == 0 ? "Start run" : "Resume", true))
            {
                if (model.Finished) Reset(true);
                else running = !running;
            }
            if (Button(707, 133, 80, 35, "Reset")) Reset(false);
            if (Button(794, 133, 80, 35, speed + "× speed")) speed = speed == 1 ? 4 : speed == 4 ? 12 : 1;
            Label(903, 133, 280, 35, $"{model.Seconds:0.0} s  ·  {model.Arrived} / {VenueSimulation.Visitors} entered", 18, White);
        }

        static Vector2 Map(float x, float z) => new Vector2(76 + (x + 28) * 12f, 422 - z * 12f);
        static Vector2 Map(Vector2 p) => Map(p.x, p.y);

        void DrawMap()
        {
            Card(28, 195, 940, 431);
            Label(48, 208, 550, 30, "Venue plan", 19, White, true);
            Label(571, 210, 376, 26, "1 Unity unit = 1 m   ·   4 virtual sensors", 14, Muted, false, TextAnchor.MiddleRight);
            Vector2 stage = Map(-8, 17.5f);
            Box(new Rect(stage.x, stage.y, 192, 56), Hex(0xe4dcec));
            Label(stage.x, stage.y, 192, 56, "STAGE", 18, White, true, TextAnchor.MiddleCenter);

            foreach (var reading in model.Zones)
            {
                var zone = reading.Zone;
                var top = Map(zone.x_min, zone.y_max);
                float w = zone.Size.x * 12, h = zone.Size.y * 12;
                var fill = reading.Reference == AlertLevel.Red ? Hex(0xf4c9c9) :
                    reading.Reference == AlertLevel.Amber ? Hex(0xffe2aa) :
                    zone.id == "Z08" || zone.id == "Z06" ? Hex(0xd9e4e9) :
                    zone.type == "static" ? Hex(0xdde7f0) : Hex(0xddebe6);
                Box(new Rect(top.x, top.y, w, h), fill);
                Outline(top.x, top.y, w, h, Border);
                if (w >= 100)
                {
                    Label(top.x + 6, top.y + 7, w - 12, 24, zone.id, 17, White, true, TextAnchor.MiddleCenter);
                    Label(top.x + 2, top.y + 29, w - 4, 18, zone.name, 13, Muted, false, TextAnchor.MiddleCenter);
                }
                else if (zone.id == "Z05" || zone.id == "Z08")
                    Label(top.x, top.y + 7, w, 22, zone.id, 14, White, true, TextAnchor.MiddleCenter);
            }

            Label(46, 473, 166, 22, "Entry →", 15, Cyan, true);
            Label(838, 503, 112, 24, "Exit →", 15, Cyan, true, TextAnchor.MiddleRight);
            Label(230, 546, 380, 22, "Audience area", 14, Muted, true, TextAnchor.MiddleCenter);

            foreach (var person in model.People)
                if (!person.Exited)
                {
                    var p = Map(person.Position);
                    Circle(p.x, p.y, 4, White);
                }
            foreach (var reading in model.Zones)
            {
                if (reading.Sensor == null) continue;
                var z = reading.Zone;
                var p = Map(z.Centre.x, z.Centre.z + z.Size.y *
                    (z.id == "Z01" || z.id == "Z07" ? -.25f : .18f));
                SensorMarker(p.x, p.y);
                if (z.id == "Z01" || z.id == "Z07")
                    Label(p.x + 10, p.y - 9, 38, 18, reading.Sensor, 13, Cyan, true);
            }

            Box(new Rect(47, 588, 899, 1), Border);
            Circle(60, 605, 5, White);
            Label(72, 594, 115, 24, "Visitor", 14, Muted);
            SensorMarker(169, 605);
            Label(181, 594, 154, 24, "Virtual sensor", 14, Muted);
            Label(345, 594, 237, 24, "Amber / red: threshold reached", 14, Muted);
            Label(619, 594, 326, 24, "Enter → watch → queue → exit", 14, White, false, TextAnchor.MiddleRight);
        }

        void Readings()
        {
            Card(984, 195, 428, 431);
            Label(1004, 208, 386, 30, "Zone density", 19, White, true);
            Label(1004, 240, 386, 24, $"Sample: {model.SampleTime:0.0} s  ·  Density in people/m²", 15, Muted);
            Label(1005, 273, 156, 21, "Zone", 12, Muted, true);
            Label(1164, 273, 65, 21, "Area (m²)", 12, Muted, true, TextAnchor.MiddleCenter);
            Label(1229, 273, 79, 21, "Reference", 12, Muted, true, TextAnchor.MiddleRight);
            Label(1299, 273, 92, 21, "Sampled", 12, Muted, true, TextAnchor.MiddleRight);
            int i = 0;
            foreach (var r in model.Zones.OrderBy(row => row.Zone.id, StringComparer.Ordinal))
            {
                float y = 301 + i * 33;
                if (i % 2 == 0) Box(new Rect(997, y, 401, 31), Hex(0xf1f3f5));
                Label(1005, y, 156, 31, r.Zone.id + "  " + r.Zone.name, 14, White);
                Label(1164, y, 65, 31, $"{r.Zone.area_m2:0.##}", 14, White, false, TextAnchor.MiddleCenter);
                Label(1229, y, 79, 31, $"{r.Density:0.00}", 17, AlertColor(r.Reference), true, TextAnchor.MiddleRight);
                Label(1294, y, 97, 31, r.Sensor == null ? "—" : $"{r.SampleDensity:0.00}", 17,
                    r.Sensor == null ? Muted : AlertColor(r.Observed), true, TextAnchor.MiddleRight);
                i++;
            }
            Label(1005, 577, 385, 22, "—  No sensor in this zone", 14, Muted);
            var front = model.Zones.Single(r => r.Zone.id == "Z08").Zone;
            Label(1005, 599, 385, 20,
                $"Z08: amber ≥ {front.amber_persons_m2:0.##}  ·  red ≥ {front.red_persons_m2:0.##} people/m²", 13, Muted);
        }

        static Color AlertColor(AlertLevel level) => level == AlertLevel.Red ? Red : level == AlertLevel.Amber ? Amber : Green;

        static void Card(float x, float y, float w, float h)
        { Box(new Rect(x, y, w, h), Border); Box(new Rect(x + 1, y + 1, w - 2, h - 2), Panel); }
        static void Outline(float x, float y, float w, float h, Color c)
        {
            Box(new Rect(x, y, w, 1), c); Box(new Rect(x, y + h - 1, w, 1), c);
            Box(new Rect(x, y, 1, h), c); Box(new Rect(x + w - 1, y, 1, h), c);
        }
        static void Box(Rect r, Color color)
        {
            Color old = GUI.color; GUI.color = color;
            GUI.DrawTexture(r, Texture2D.whiteTexture);
            GUI.color = old;
        }
        static void SensorMarker(float x, float y)
        {
            Box(new Rect(x - 7, y - 7, 14, 14), Panel);
            Box(new Rect(x - 5, y - 5, 10, 10), SensorBlue);
        }

        void Circle(float x, float y, float d, Color color)
        {
            if (dot == null)
            {
                dot = new Texture2D(16, 16, TextureFormat.RGBA32, false);
                for (int i = 0; i < 16; i++)
                    for (int j = 0; j < 16; j++)
                        dot.SetPixel(i, j, (i - 7.5f) * (i - 7.5f) + (j - 7.5f) * (j - 7.5f) < 56
                            ? Color.white : Color.clear);
                dot.Apply();
            }
            Color old = GUI.color; GUI.color = color;
            GUI.DrawTexture(new Rect(x - d / 2, y - d / 2, d, d), dot);
            GUI.color = old;
        }

        static GUIStyle Style(int size, Color color, bool bold, TextAnchor alignment)
        {
            var style = new GUIStyle(GUI.skin.label) { fontSize = size, alignment = alignment,
                fontStyle = bold ? FontStyle.Bold : FontStyle.Normal, clipping = TextClipping.Clip, padding = new RectOffset() };
            style.normal.textColor = color;
            return style;
        }

        static void Label(float x, float y, float w, float h, string value, int size, Color color,
            bool bold = false, TextAnchor alignment = TextAnchor.MiddleLeft) =>
            GUI.Label(new Rect(x, y, w, h), value, Style(size, color, bold, alignment));

        static bool Button(float x, float y, float w, float h, string value, bool active = false)
        {
            var rect = new Rect(x, y, w, h);
            Box(rect, active ? Hex(0xd5e9e9) : Hex(0xe9ebee));
            return GUI.Button(rect, value, Style(16, active ? Cyan : White, true, TextAnchor.MiddleCenter));
        }
    }
}
