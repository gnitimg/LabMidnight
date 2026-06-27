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

## Screen Layout

| Area | Position | Description |
|---|---|---|
| Left toolbar | Left | Tools, doors, save/reload/clear, object rotation |
| Center canvas | Center | Tile map editing area with scrollbars |
| Right panel | Right | Floor selector, map size, player config, object assets, room/object properties |
| Status bar | Bottom | Current status and hovered grid cell coordinates |

The left toolbar and right panel have independent vertical scrolling. The center canvas has its own map scroll and bottom horizontal scrollbar.

## Floors

Use the floor buttons in the right panel to edit floors `1` through `4`.

| Feature | Description |
|---|---|
| Auto-save | Switching floors auto-saves the current floor |
| Layout file | `data/floors/floor_N.txt` |
| Metadata file | `data/floors/floor_N_rooms.json` |
| Legacy sync | Floor 4 also updates `data/map_layout.txt` and `data/map_rooms.json` |

## View Zoom

One base map cell is one floor tile: `60 cm x 60 cm`.

Use the mouse wheel over the center canvas to zoom the editor view. This changes only the on-screen cell size and does not alter saved map data.

Zoom range: `8` to `48` pixels per cell, with step factor `1.14`.

## Tools

### Select

| Action | Effect |
|---|---|
| Click | Select a room, door, object, or start point |
| Drag selected room | Move the room |
| Drag room's bottom-right handle | Resize the room |
| `Ctrl` + drag | Box-select rooms, doors, objects, overrides, and start point |
| Drag inside box selection | Move all selected items |
| `Delete` | Delete selected item or area |

Box selection captures the top layer: objects → doors → start/overrides → rooms.

### Room

Drag on the canvas to create a rectangular room.

Room size must be at least `3 x 3` tiles. Room borders become walls (`#`) and room interiors become floor (`.`).

### Wall

Paints wall overrides (`#`) on the map.

### Window

Paints wall-height window overrides (`W`) on the map. Window cells block movement like walls but render with `assets/textures/window.png`.

### Erase

Paints floor overrides (`.`) on the map.

### Start

Places the player spawn point (`@`). The start point must be inside a room or corridor.

### Door

Choose a door type from the toolbar, then click or drag onto a wall. The editor snaps the door to the nearest valid wall cell next to floor.

| Symbol | Type | Texture |
|---|---|---|
| `G` | Guard-room door | `door.png` |
| `L` | Lab door | `door_lab.png` |
| `M` | Machine/server door | `door_lab.png` (uses lab visuals) |
| `C` | Classroom door | `door_classroom.png` |
| `P` | Power-room door | `door_power.png` |
| `E` | Exit door | `door_exit.png` |

### Object

Choose `Object`, then use the `Object Asset` dropdown in the right panel.

| Source | Listing |
|---|---|
| Custom objects | `assets/objects/` folder names (e.g., `blackboard`, `desk`) |
| Legacy objects | `Legacy 1` through `Legacy 9` |

Number keys `1-9` select legacy story objects.

Click on a valid floor cell to place the current object. Custom objects render automatically when their directional textures exist.

**Auto wall snap** places the object on the nearest valid floor cell beside a wall and rotates it toward that wall. Turn it off for free floor placement.

#### Instance Placement Fields

When an object is selected, the right panel exposes:

| Field | Description |
|---|---|
| `X` / `Y` | Object anchor cell coordinates |
| `Len` | Unrotated length along the map x-axis (tiles) |
| `Wid` | Unrotated width along the map y-axis (tiles) |
| `H` | Rendered object height (tiles) |
| `Z` | Placement height above the floor (tiles) |

Changing `Len` and `Wid` changes the object's occupied footprint. The editor rejects values that would overlap walls, doors, the start point, or another object.

#### Object Rotation

| Action | Effect |
|---|---|
| `Q` key | Rotate counter-clockwise 90 degrees |
| `E` key | Rotate clockwise 90 degrees |
| `Rotate CCW` button | Rotate counter-clockwise 90 degrees |
| `Rotate CW` button | Rotate clockwise 90 degrees |

If an object is selected, rotation applies to that object. Otherwise it applies to the next object placement.

### Element Binding

Selected objects can be configured as gameplay elements in the right panel.

| Element Type | Description |
|---|---|
| `story_required` | Fixed plot objects. Can grant items and set flags. |
| `pickup` | Optional pickable objects. Supports random drop with Count. |
| `trigger` | Custom trigger events with trigger ID. |
| `decoration` | Non-interactive decoration. |

| Field | Description |
|---|---|
| `Item` | Inventory ID granted (e.g., `flashlight`, `fuse`, `access_card`) |
| `Flag` | Player flag set (e.g., `got_blackboard_clue`) |
| `Prompt` | Custom on-screen interaction prompt |
| `Message` | Custom message shown after interaction |
| `Need Item` | Required inventory item before interaction |
| `Need Flag` | Required player flag before interaction |
| `Fail Msg` | Message when required item/flag is missing |
| `Remove after pickup` | Hide object after successful interaction |
| `Random drop` | Enable random drop (配合 Count 使用) |
| `Trigger ID` | Custom trigger identifier |
| `Trigger once` | Only trigger once per game |
| `Resource role` | `required` / `optional` / `decor` |

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

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | string | folder name | Display name |
| `length` | float | 1.0 | Size along the map x-axis |
| `width` | float | 1.0 | Size along the map y-axis |
| `height` | float | 1.0 | Vertical size |
| `placement_height` | float | 0.0 | Distance above the floor (for wall-mounted objects) |
| `solid` | bool | true | Whether the object blocks player movement |

Missing metadata or textures fall back safely.

## Save And Reload

| Shortcut | Action |
|---|---|
| `Ctrl+S` | Save the current floor |
| `Ctrl+Z` | Undo the previous edit |
| `Ctrl+Shift+Z` | Redo the previous undone edit |
| `Ctrl+L` | Reload the current floor from disk |
| `Delete` | Delete selected item |
| `Clear Map` | Reset current floor to 3x3 start room (not auto-saved) |

## Default Map Config

The editor loads initial player config from `data/map_config.json`:

```json
{
  "initial_player": {
    "hp": 100,
    "sanity": 100,
    "flashlight_power": 100,
    "speed": 6.0
  }
}
```

Default grid size: `40 x 24` tiles. Minimum: `12 x 12`.

## Runtime Notes

- Floors `2-4` require the access card to use the safety exit.
- Opening a safety exit on floors `2-4` shows the floor-transition prompt.
- Choosing to leave moves the player to the next lower floor.
- Floor `1` exit triggers the success sequence when the player leaves through the open exit.
- The player's `speed` field in `data/map_config.json` controls movement speed (default `6.0`).
