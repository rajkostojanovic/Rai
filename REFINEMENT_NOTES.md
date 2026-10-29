# Rai refinement notes

- Background contains two labeled image preview buttons, A and B, and a manual opacity crossfade. Click a slot to select it and choose its replacement. Existing transform/state/circle controls remain below the slots. Foreground rendering remains independent.
- Object import replaces the current image object while retaining the session's scene settings, transforms, saved states, and circle position. Background replacement retains the chosen slot's settings. No per-image state is saved to disk or restored from a previous file.
- Choosing an image opens a preparation preview. Image preparation runs in a worker thread. Apply switches the source; Cancel leaves the current image playing. The existing acrylic-core extraction for foreground images is preserved.
- Sources are shared by states; foreground sources are bounded to 1600 pixels on the longest edge and background sources to 2048. Only one preparation runs at a time. Applying a source clears undo history so superseded source assets can be released; subsequent scene edits retain normal undo behavior.
- The dashed editor rectangle defines the projector region: centered half width and half height, one quarter of canvas area. This region alone is scaled to fill the projector, including different output aspect ratios (which can stretch the image). Editor controls and overlays are excluded.
- Existing microphone capture and soundcard loopback support were preserved. No additional audio backend was introduced.

## Validation

Run `.venv\Scripts\python.exe test_refinements.py` for offscreen checks of state-preserving replacement, Apply/Cancel, two background slots, crossfade endpoint and midpoint pixels, projector crop coordinates, worker preparation, and construction/rendering of the real UI. Syntax compilation also passed. The test writes `rai-refinement-preview.png`.

Physical microphone capture, internal sound-card capture, and a connected projector were not tested. Source code is updated; existing packaged EXE/installer files have not been rebuilt.
