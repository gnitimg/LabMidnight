# LabMidnight Map Editor Guide

This document describes the developer map editor used by LabMidnight.

## Run

Run the editor from the project root:

```bash
python map_editor.py
```

The editor saves runtime maps under `data/floors/`. The game entry point is still:

```bash
python main.py
```

## Screen Areas

- Left toolbar: choose tools, doors, save/reload/clear, and rotate object placement.
- Center canvas: edit the tile map.
- Right properties panel: edit floor, map size, initial player values, object asset selection, selected room metadata, and selected object placement.
- Bottom status bar: current status and hovered grid cell.

The left toolbar and right properties panel have independent vertical scrolling. The center canvas has its own map scroll and bottom horizontal scrollbar.

## Floors

Use the floor buttons in the right panel to edit floors `1` through `4`.

- Switching floors auto-saves the current floor first.
- Floor text layouts are saved as `data/floors/floor_N.txt`.
- Floor metadata is saved as `data/floors/floor_N_rooms.json`.
- Floor 4 also updates the legacy files `data/map_layout.txt` and `data/map_rooms.json` for compatibility.

## Tools

### Select

- Click a room, door, object, or selection to select it.
- Drag a selected room to move it.
- Drag a selected room's bottom-right handle to resize it.
- Hold `Ctrl` and drag on the canvas to box-select rooms, doors, objects, overrides, and the start point.
- Drag inside a box selection to move all selected items.
- Box selection only captures the top layer inside the selected rectangle: objects first, then doors, start/overrides, then rooms.
- Press `Delete` to delete the selected item or selected area.

### Room

Drag on the canvas to create a rectangular room.

Room size must be at least `3 x 3` tiles. Room borders become walls and room interiors become floor.

### Wall

Paints wall overrides (`#`) on the map.

### Erase

Paints floor overrides (`.`) on the map.

### Start

Places the player spawn point (`@`). The start point must be inside a room or corridor.

### Door

Choose a door type from the toolbar, then click or drag onto a wall. The editor snaps the door to the nearest valid wall cell next to floor.

Door symbols:

| Symbol | Meaning |
|---|---|
| `L` | Lab door |
| `M` | Machine/server door, using lab-door visuals |
| `C` | Classroom door |
| `G` | Guard-room door |
| `P` | Power-room door |
| `E` | Exit door |

### Object

Choose `Object`, then use the `Object Asset` dropdown in the right panel.

- Custom object folders under `assets/objects/` are listed by folder name, such as `blackboard`.
- Legacy story objects are listed as `Legacy 1` through `Legacy 9`.
- Number keys `1-9` still select legacy story objects.

Click on a valid floor cell to place the current object. Custom objects render automatically when their directional textures exist.

`Auto wall snap` places the object on the nearest valid floor cell beside a wall and rotates it toward that wall. Turn it off for free floor placement.

When an object is selected, the right panel exposes instance placement fields:

| Field | Meaning |
|---|---|
| `X` / `Y` | object anchor cell |
| `Len` | unrotated length along the map x-axis |
| `Wid` | unrotated width along the map y-axis |
| `H` | rendered object height |
| `Z` | placement height above the floor |

Changing `Len` and `Wid` changes the object's occupied footprint. The editor rejects values that would overlap walls, doors, the start point, or another object.
The occupied footprint is filled on the canvas and the object's symbol is drawn at the center of that footprint.

Rotate object placement:

- `Rotate CCW` button: rotate counter-clockwise by 90 degrees.
- `Rotate CW` button: rotate clockwise by 90 degrees.
- `Q`: rotate counter-clockwise by 90 degrees.
- `E`: rotate clockwise by 90 degrees.

If an object is selected, rotation applies to that object. Otherwise it applies to the next object placement.

## Object Assets

Custom object assets live under:

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

Units are map tiles. One tile is `60 cm`.

- `length`: size along the map x-axis.
- `width`: size along the map y-axis.
- `height`: vertical size.
- `placement_height`: distance above the floor. Use this for wall-mounted objects such as blackboards.
- `solid`: whether the object blocks player movement.

Missing metadata or textures fall back safely.

## Save And Reload

- `Ctrl+S` or `Save Ctrl+S`: save the current floor.
- `Reload Ctrl+L`: reload the current floor from disk.
- `Clear Map`: reset the current floor to one `3 x 3` start room, one spawn point, and walls elsewhere. This does not save until you explicitly save.

## Runtime Notes

- Floors `2-4` require the access card to use the safety exit.
- Opening a safety exit on floors `2-4` shows the floor-transition prompt.
- Choosing to leave moves the player to the next lower floor.
- Floor `1` exit triggers the success sequence when the player leaves through the open exit.
