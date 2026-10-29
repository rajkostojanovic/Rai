# Audio Visual Variant Roadmap

This note captures the target workflow for the next pass.

## Target Direction

The app should move from manually staged objects toward a shared-image variant system:

- one uploaded core image on black background
- multiple derived visual sets based on the same acrylic source
- seamless transforms between sets without losing the core identity
- audio analysis split into rhythmic low-end, tonal atmosphere, and high transient texture

## Audio Lanes

Use three independent control lanes instead of a single generic beat driver:

- `rhythm lane`
  - drives kick, snare, impact pulses
  - primary inputs: low-band energy plus transient spikes
  - visual mapping: big vs small brush mass, pulse scale, impact timing
- `atmosphere lane`
  - drives bass and melody mood
  - primary inputs: low-mid and mid-band sustained energy
  - visual mapping: warm, cool, neon, melancholic palette shifts
- `texture lane`
  - drives hi-hats and upper percussion
  - primary inputs: high-band energy and fast transient motion
  - visual mapping: brush slope, fine stroke angle, shimmer, accent density

## Image Variant Model

Each visual family should share the same base asset:

- `core`
  - unchanged silhouette or anchor image
  - always preserved during transforms
- `variant shell`
  - stylized layer derived from the same base image
  - changes stroke size, angle, density, color atmosphere, and edge treatment
- `transition state`
  - supports cross-set morphing from one shell to another while keeping the core stable

## Required Data Model

Add a new scene object type for imported imagery:

- `kind="image_variant"`
- `core_image_path`
- `core_mask_path` or alpha from source image
- `variant_sets`
- `current_variant`
- `transition_variant`
- `transition_progress`

Each `variant_set` should be parameter-driven, not stored as a completely unrelated image:

- `stroke_scale`
- `stroke_angle`
- `stroke_density`
- `palette_mode`
- `edge_glow`
- `blend_strength`

## Rendering Goal

Full transform should mean:

- the core image remains visually continuous
- the outer shell can interpolate between variant parameter sets
- transforms are not limited to object `transform` and `color`
- transition drawing can blend masks, stroke fields, and palette states together

## Practical Next Step

After the audio-source and band-analysis pass, the next implementation block should be:

1. import a source image as a new `image_variant` object
2. render its unchanged core on black background
3. generate two or more parameterized shells from the same image
4. crossfade and parameter-interpolate between shells in the existing render loop

Only after that should the beat matrix be extended so different objects or variant groups can listen to different audio lanes.
