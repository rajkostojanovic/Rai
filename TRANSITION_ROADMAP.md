# Transition Roadmap

This file is the handoff note for the next transition pass.

## Current State

The app currently supports these beat transition modes:

- `cut` / `Immediate`
- `fade`
- `linear`
- `ease_in`
- `ease_out`
- `ease_in_out`
- `wipe_horizontal`
- `wipe_vertical`

Current limitation:

- A beat transition is stored as a single string in `beat_transitions`.
- That string currently mixes two different concepts:
  - interpolation curve (`linear`, `ease_in`, `ease_out`, `ease_in_out`)
  - visual effect (`cut`, `fade`, `wipe_horizontal`, `wipe_vertical`)
- The stage engine only interpolates `transform` and `color`.
- There is no separate transition state for geometry-driven effects like particle dissolve, scanline reconstruction, slice-and-reassemble, or mesh warp.

## Goal For Next Pass

Split transition behavior into two layers:

1. Timing / easing
2. Visual effect

That allows combinations like:

- `effect=fade` + `easing=ease_out`
- `effect=wipe_horizontal` + `easing=linear`
- `effect=scanline_reconstruct` + `easing=ease_in_out`
- `effect=particle_dissolve` + `easing=ease_out`

## Recommended Data Model

Replace the current single string mode with a transition spec object per beat edge.

Suggested shape:

```python
{
    "effect": "cut",
    "easing": "linear",
    "duration_scale": 0.55,
    "params": {},
}
```

Possible `effect` values:

- `cut`
- `fade`
- `wipe_horizontal`
- `wipe_vertical`
- `scanline_reconstruct`
- `particle_dissolve`
- `slice_reassemble`

Possible `easing` values:

- `linear`
- `ease_in`
- `ease_out`
- `ease_in_out`

Optional future params:

```python
{
    "fragmentation": 0.5,
    "randomness": 0.3,
    "glow": 0.2,
    "preserve_center": True,
    "preserve_scale": True,
    "preserve_rotation": False,
}
```

## Migration Plan

Keep backward compatibility with existing saved objects.

When old data contains:

```python
"beat_transitions": ["fade", "linear", "cut", "wipe_vertical"]
```

map it to:

```python
[
    {"effect": "fade", "easing": "linear", "duration_scale": 0.55, "params": {}},
    {"effect": "interpolate", "easing": "linear", "duration_scale": 0.55, "params": {}},
    {"effect": "cut", "easing": "linear", "duration_scale": 0.0, "params": {}},
    {"effect": "wipe_vertical", "easing": "linear", "duration_scale": 0.55, "params": {}},
]
```

For compatibility, the old `linear` / `ease_*` strings should initially map to:

- `effect="interpolate"`
- `easing=<old mode>`

`interpolate` means:

- use existing transform/color interpolation
- no special draw effect

## First Implementation Target

Do not attempt all advanced effects at once.

Recommended order:

1. Refactor to `transition spec`
2. Preserve existing effects through the new model
3. Add `scanline_reconstruct`
4. Add `particle_dissolve`

Why this order:

- `scanline_reconstruct` fits the current draw pipeline well
- it is readable on stage
- it does not require full geometry morphing
- `particle_dissolve` is also strong, but needs more effect-specific sampling/state

## Proposed Code Changes

### 1. Replace String Mode Accessors

Current code uses a string-returning helper:

- `_object_transition_mode(...)`

Replace with something like:

```python
def _object_transition_spec(self, obj, slot_index: int):
    ...
```

And add helpers:

```python
def _normalize_transition_spec(self, value):
    ...

def _default_transition_spec(self):
    ...
```

### 2. Separate Duration From Effect

Current duration path:

- `_beat_transition_duration_for_mode(...)`

Replace with:

```python
def _beat_transition_duration_for_spec(self, spec, interval: float):
    ...
```

This should use:

- `spec["effect"]`
- `spec["duration_scale"]`

### 3. Keep Easing Focused On Curves Only

Current easing path:

- `_ease_beat_transition(...)`

Keep it, but make it operate only on:

- `spec["easing"]`

Do not overload it with effect choice.

### 4. Centralize Effect Rendering

Current transition drawing is embedded in:

- `_draw_object(...)`

Extract effect rendering into one dispatcher:

```python
def _draw_transition_effect(self, p, obj, start_snapshot, end_snapshot, spec, progress):
    ...
```

Then branch inside it:

- `cut`
- `interpolate`
- `fade`
- `wipe_horizontal`
- `wipe_vertical`
- `scanline_reconstruct`
- `particle_dissolve`

### 5. Add Effect-Specific Render Helpers

Suggested helpers:

```python
def _draw_fade_transition(...):
    ...

def _draw_wipe_transition(...):
    ...

def _draw_scanline_transition(...):
    ...

def _draw_particle_dissolve_transition(...):
    ...
```

## Scanline Reconstruction Design

This is the best next advanced effect to implement first.

Suggested behavior:

- old snapshot remains visible ahead of the scan
- a moving scan band travels left-to-right or top-to-bottom
- behind the band, draw the new snapshot
- optional bright scanline accent at the boundary

Suggested params:

```python
{
    "direction": "horizontal",
    "band_px": 24,
    "glow": 0.25,
}
```

Implementation strategy:

- draw old snapshot clipped to the not-yet-revealed region
- draw new snapshot clipped to the revealed region
- draw a bright translucent line at the scan edge

This can be done with the current QPainter pipeline and clip rectangles.

## Particle Dissolve Design

Suggested behavior:

- sample points from the object bounds or rasterized mask
- fade or scatter particles from old snapshot
- gather particles into the new snapshot

Implementation note:

- this likely needs a lightweight offscreen raster or cached sampling per object/snapshot
- do not start here unless the transition spec refactor is already done

## Relevant Code Entry Points

Main transition definitions:

- `main.py` top-level `BEAT_TRANSITION_OPTIONS`

Control panel normalization and beat table:

- `main.py` `ControlPanel._clean_beat_transition_mode`
- `main.py` `ControlPanel._normalize_beat_row`
- `main.py` `ControlPanel._rebuild_beat_table`

Canvas transition state:

- `main.py` `CanvasWidget.on_beat`
- `main.py` `CanvasWidget._clear_beat_transition`
- `main.py` `CanvasWidget._clean_beat_transition_mode`
- `main.py` `CanvasWidget._object_transition_mode`
- `main.py` `CanvasWidget._beat_transition_duration_for_mode`
- `main.py` `CanvasWidget._beat_transition_progress`
- `main.py` `CanvasWidget._ease_beat_transition`

Snapshot and interpolation path:

- `main.py` `CanvasWidget._make_stage_snapshot`
- `main.py` `CanvasWidget._interpolate_snapshot`
- `main.py` `CanvasWidget._object_snapshot_for_beat_slot`
- `main.py` `CanvasWidget._object_visual_snapshot`

Transition drawing:

- `main.py` `CanvasWidget._snapshot_with_alpha_scale`
- `main.py` `CanvasWidget._transition_clip_rect`
- `main.py` `CanvasWidget._draw_snapshot_object`
- `main.py` `CanvasWidget._draw_object`

Object serialization defaults:

- `main.py` object creation blocks that initialize `"beat_transitions"`

## Minimal Next-Session Checklist

1. Add `transition spec` helpers and backward-compat parsing
2. Change beat row storage from string mode to spec object
3. Update UI model so effect and easing are separate controls
4. Keep current effects working through the new dispatcher
5. Implement `scanline_reconstruct`

## Notes

- Do not label advanced effects in the UI until there is actual rendering support.
- Avoid fake names for transitions that still only lerp `transform` and `color`.
- Keep migration logic in place until old saved content is no longer relevant.
