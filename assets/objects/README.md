# LabMidnight Object Assets

Place each object in its own folder:

```text
assets/objects/<object_id>/
```

Directional texture names:

```text
<object_id>_front.png
<object_id>_back.png
<object_id>_left.png
<object_id>_right.png
<object_id>_top.png
```

Each folder may include `object.json`:

```json
{
  "name": "Lab Desk",
  "length": 2.0,
  "width": 1.0,
  "height": 1.2,
  "placement_height": 0.0,
  "solid": true,
  "prompt": "Press Space to inspect Lab Desk",
  "description": "Optional interaction text."
}
```

`length`, `width`, `height`, and `placement_height` use map tile units. One map tile is 60 cm. Missing textures or metadata fall back safely.
