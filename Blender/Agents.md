# Blender directory agent notes

## Scope and maintenance

- `P:\git\MyUtils\Blender\` is the home for Blender-related projects and topics
  in MyUtils. Windows resolves the user's `blender` spelling to this directory.
- Keep this `Agents.md` up to date in the same change whenever Blender projects,
  architecture, requirements, workflows, commands, decisions, or limitations change.
  Correct superseded information instead of accumulating contradictory notes.
- Record verified behaviour separately from proposals and untested assumptions.
- Keep Blender details here. The root `P:\git\MyUtils\AGENTS.md` contains the
  directory pointer and requires no further updates for Blender-only work.
- Blender add-ons use Blender's bundled Python and native UI. Do not introduce
  per-project pip environments or integrate the MyUtils Qt launcher without a reason.
- The user prefers **TDD**: write behavioural tests first, verify the intended
  failure, implement, and refactor. Test independent measurements and outcomes,
  rather than reproducing generator logic or checking incidental vertex counts.

## Directory map

| Path | Responsibility |
| --- | --- |
| `SnakeTape/Run_Tests.cmd` | Run every automated suite, validate/build/validate the extension ZIP; nonzero failure exit. |
| `SnakeTape/Gen_Previews.cmd` | Generate an offline HTML gallery, stage renders, measurements and inspectable scenes. |
| `SnakeTape/Build.cmd` | Validate/build/validate the extension ZIP without running tests. |
| `SnakeTape/snake_tape/core.py` | Settings, millimetre conversion, deterministic cuts and periodic/correlated variation. |
| `SnakeTape/snake_tape/geometry.py` | Quad-rim analysis, staged tape surfaces, flap folding, contact and final-shell intersection repair. |
| `SnakeTape/snake_tape/short_cuts.py` | Partly joined overhangs, local slit-outline triangulation and thickness from material-frame normals. |
| `SnakeTape/snake_tape/optimization.py` | Validated reduction of finished solids, surface-distance checks and transfer of smooth corner normals. |
| `SnakeTape/snake_tape/validation.py` | Independent measurements on evaluated solid geometry, source contact and triangle intersections. |
| `SnakeTape/snake_tape/ui.py` | Native settings, panel, menus and atomic Create/Update operators. |
| `SnakeTape/snake_tape/support.py` | Clipboard settings/version/source context and last-build diagnostics. |
| `SnakeTape/snake_tape/blender_manifest.toml` | Blender extension metadata, version 0.4.0. |
| `SnakeTape/tests/` | Synthetic reference meshes and core, geometry, persistence, launcher and preview tests. |
| `SnakeTape/tools/launch.cmd` | Shared Blender discovery, isolated profile setup and process exit forwarding. |
| `SnakeTape/tools/run_tests.py` | Standard-library test discovery, timestamped logs/JSON and extension packaging. |
| `SnakeTape/tools/build.py` | Build-only entry point and timestamped build logs/results. |
| `SnakeTape/tools/packaging.py` | Shared native Blender extension validation/building. |
| `SnakeTape/tools/gen_previews.py` | Production-generator renders, gallery, JSON measurements and framed `.blend` scenes. |
| `SnakeTape/README.md` | Installation, controls, launchers and supported input/limitations. |
| `SnakeTape/generated/` | Ignored test reports, preview runs and built extension packages. |

## SnakeTape requirements and agreed decisions

- Target **Blender 4.4.3**. Installed executable:
  `C:\Program Files\Blender Foundation\Blender 4.4\blender.exe`.
- The user agreed to the architecture and TDD/preview approach on 2026-11-25,
  then requested the implementation. The add-on and test/preview/build launchers exist.
- Start from selected connected rim faces of corrugated cardboard. Seal the
  exposed edge with masking tape whose excess width is slit and folded down.
- Stage 1: x mm outward tape thickness, typically 0.1 mm. Thickness is added once;
  geometric contact clearance is a separate control.
- Stage 2: y mm added on each side (default 10 mm), or y as total tape width,
  including the selected band. Reject an insufficient total width.
- Stage 3: nominal z mm cuts (default 3 mm, expected use 2-5 mm). Randomise spacing
  and cut angles with a repeatable seed plus smooth waves of more closely spaced
  and/or more aligned cuts. Preserve the uncut central sealing band.
- Stage 4: fold finite-thickness flaps onto the chosen edge or both sides. Relief at bends lifts a
  flap over previously placed tape rather than allowing solid intersections.
- Generate a separate tape object. Preserve the source mesh. Save generator
  settings, source pointer, selected face indices and topology signature for updates.
- Use the same production generator for add-on operations, tests and previews.
  There are no external runtime Python packages, simulations or network calls.

## Geometry and update architecture

- Source input is one open or closed, non-branching **single row of quad faces**,
  connected through opposite edges. A single quad uses its shorter edges as width.
  For ambiguous square faces, subdivide along the intended rim direction first.
- `analyze_rim` traverses the selected face graph and builds two aligned rails.
  Local tangent/across/normal frames follow the rim instead of global Z.
- Solve in millimetres around a nearby origin, accounting for scene scale and the
  source world transform. The generated object has unit scale. Positive non-uniform
  scale is supported; mirrored/zero scales require Apply Scale/recalculated normals.
- Cut positions partition the complete rim with positive widths. Closed loops use
  periodic waves and angle continuity. Bound angular displacement to prevent cuts
  from crossing; taper the slit gap to zero at its root.
- Flaps preserve the tangential spread of the unrolled overhang when bent, allowing
  curvature to create overlaps. A quarter-circle bend consumes overhang material.
  Zero fold radius sizes the bend automatically from thickness, physical rim width
  and available material. Prefer twice the thickness, adapt down to 1.5 times on
  narrow rims, and retain the minimum needed for a stable finite-thickness bend.
  Explicit radii are limited by overhang needed to bend and settle, not an arbitrary
  fraction of band width. Dimension errors include measured millimetre values.
- The folded centre band rests lower in the middle when there is sufficient width.
  Narrow rims bridge smoothly between the shoulders, avoiding an intersecting dip.
  Subdivide the bend angularly. Folded meshes refine to at most 0.65 mm cell spacing
  and four cells per nominal flap, even when a coarser maximum was requested.
- Interpolate section tangents before constructing normals, including the closed
  seam, so the fold frame is continuous when band normals vary around a cylinder.
- Where adjacent source band faces change normal, preserve their original section
  positions as mesh anchors and subdivide the intervals between anchors. This
  prevents offset triangles from chording through source polygon corners. Skip
  anchors extremely close to cut ends (min(0.005 mm, mesh spacing * 0.01)) to avoid
  unstable sliver faces. Coplanar band faces need no extra anchors.
- Spatial queries first fit flaps to the source and earlier strips. Conservative
  nearby-edge support and one-sided slope relief handle overlaps narrower than a
  sampling cell. Full-depth cuts use a centred Solidify shell; short cuts use explicit
  shells with material-frame normals, preserving the connected web and thickness.
- After adding thickness, test non-adjacent triangle pairs on the evaluated shell and
  intersections against the source. Locally raise the later flap where needed,
  preserving pinned roots. Fail and clean up if the finite iteration limit cannot
  resolve the contacts; never publish a known intersecting folded result.
- Contact clearance is a requested minimum, not a uniform exact distance. A small
  sampling margin and overlap relief can raise portions of the tape further.
- Update checks the source topology signature and generates a replacement before
  deleting the old tape. Failed validation retains the prior result. Renaming the
  source is supported through its saved object pointer. Topology changes require
  reselection and Create Tape. Manual tape edits/modifier changes are regenerated.

## UI and user workflow

- In Edit Mode select rim faces, then **Mesh > SnakeTape > Create Tape**, or use
  **F3 > SnakeTape: Create Tape**.
- **3D Viewport > Sidebar (N) > SnakeTape** contains thickness, width mode/value,
  cut spacing/randomness/angle, Uncut root/Depth variation, wave strength/length, seed, fold radius,
  Mesh detail, Reverse Direction and advanced clearance/cut gap/mesh spacing,
  Shape tolerance and Paper bump. The selected tape shows actual triangles saved.
- The four stages (Base, Extended, Cut and Folded) are internal. One **Create Tape**
  click performs all four. **Update Tape** also rebuilds the complete folded tape.
  Intermediate stages are only for offline previews/geometry scripts. The legacy
  stage property is hidden and ignored by Create/Update for older saved files.
  Merely changing a setting does not trigger a costly rebuild.
- Selecting generated tape exposes its saved settings and **Update Tape**.
- Install `generated/packages/snake_tape-0.3.1.zip` through **Edit > Preferences >
  Get Extensions > top-right dropdown > Install from Disk...**.

## Commands and previews

```powershell
& 'P:\git\MyUtils\Blender\SnakeTape\Run_Tests.cmd' --no-pause
& 'P:\git\MyUtils\Blender\SnakeTape\Gen_Previews.cmd' --no-pause
& 'P:\git\MyUtils\Blender\SnakeTape\Gen_Previews.cmd' --no-pause --quick
```

- Double-click use pauses at the end; `--no-pause` must be the first argument for
  unattended runs. Paths resolve relative to each launcher, independent of cwd.
- `SNAKETAPE_BLENDER` overrides executable discovery. Otherwise try the installed
  Blender 4.4 path, then PATH. Require 4.4.3 before performing the requested work.
- Create explicit, existing `BLENDER_USER_CONFIG`, `BLENDER_USER_SCRIPTS`,
  `BLENDER_USER_EXTENSIONS` and `BLENDER_USER_DATAFILES` directories in an isolated
  TEMP profile before launching Blender. A nonexistent config path can make Blender
  fall back to the real profile. `BLENDER_USER_RESOURCES` alone did not isolate
  Blender 4.4.3; do not use it as the sole protection for preferences.
- Test runs produce timestamped `generated/tests/<run>/tests.log` and `results.json`.
  A failed suite does not build a new release ZIP. Package manifests and successful
  ZIPs are checked using Blender's extension CLI.
- Preview runs produce `generated/previews/<run>/index.html`, 106 PNGs, eleven
  `inspect.blend` scenes, JSON measurements and native renderer logs. `--quick`
  renders the first two cases at smaller resolution. `--output` chooses a new or
  empty folder; existing results must not be overwritten.
- The eleven gallery cases are straight, convex/concave, S bend, closed loop/seam,
  rotated/non-uniformly scaled edge, corrugated cardboard, a 0.3 mm curved rim,
  a cylinder side-face band at the reported scale, and two mixed full/short-cut
  examples (straight and cylinder). Each has four stages, front/back/top views,
  diagnostic flap colours and a 12 mm overlap close-up. The short-cut cases also
  have an 8 mm cut-tip view before folding and a Detailed reference render. The
  gallery reports triangle reduction and checked shape error. An additional cylinder
  reproduces root 0 / depth variation 0.48 mm and shows its shoulder at close range.
- The corrugated example has visible liners/flutes and a hidden solid rim/contact
  proxy. This supports a continuous tape bridge over flute openings. Use a similar
  guide/proxy for detailed cardboard without a continuous selectable quad rim.
- Generated outputs and bytecode are ignored by Git. Keep source, launchers and
  fixtures tracked. Preserve failures in galleries and return a nonzero exit code.

## Validation on 2026-11-25

- The initial test run failed because the geometry core was absent, establishing
  the initial TDD red stage. Later tests exposed source and tape intersections that
  simple vertex/manifold checks missed; evaluated-shell contact repair resolved them.
- Initial 0.1.0 automated suite: **31 tests, no failures/errors/skips** in Blender 4.4.3,
  including parameterised cut seeds and twelve seed/rim contact combinations.
- Initial 0.1.0 gallery: **6 passing cases / 54 PNGs**, with zero detected tape self
  intersections, tape/source triangle intersections and penetrating source vertices
  in the displayed folded results. Gallery run: `generated/previews/20261125-084143-137913`.
- Native window scripted smoke check verified Create, Update, Undo removing tape,
  Redo restoring it and drawing the native settings panel. Panel labels were
  shortened after visual inspection. Artistic acceptance still belongs to the user.
- Packaged extension was installed, enabled and reloaded through an isolated local
  repository/profile. Core CLI supports build and validate on this exact Blender.
- Both launchers were tested for missing executable overrides without hanging.
  A complete earlier 29-test suite also passed from another working directory and
  a copy whose path contained spaces. The final suite additionally checks that
  explicitly requested user-resource directories exist and are used.
- The MyUtils root guidance retains only the previously requested Blender pointer;
  no further root guidance changes were made for this implementation.

## Known limits

- Triangles, multi-row bands, branching selections and arbitrary patches are not
  supported in 0.3.1. Use a simple quad guide/proxy instead of changing detailed art.
- Apply geometry/deformation modifiers on a duplicate before capturing its rim.
- Overhang should fit the available side surface. Wrapping around the underside,
  arbitrary very tight/complex bends, torn paper and adhesive physics are outside
  this version. Unsupported contact configurations produce a useful failure.
- This is a deterministic geometric construction with contact relief, not a cloth
  or paper material simulation. Collision tests establish the tested cases, not a
  proof for all meshes/settings. Fine crumpling and artistic realism require review.
- Moving/deforming the source requires Update Tape. This is not a continuously
  evaluated geometry modifier. Global object transforms must be refreshed before
  calling the low-level generator directly from scripts.

## Blender references

- <https://docs.blender.org/manual/en/4.4/editors/preferences/extensions.html>
- <https://docs.blender.org/manual/en/4.4/advanced/command_line/extension_arguments.html>
- <https://docs.blender.org/api/4.4/mathutils.bvhtree.html>
- <https://docs.blender.org/manual/en/4.4/modeling/modifiers/generate/solidify.html>

## Version 0.1.1 fixes on 2026-11-25

- The user reported the radius error with **0 / automatic**. Reproduced the faulty
  guard on a 0.3 mm rim: the old code chose 0.2 mm, then rejected bands below 0.5 mm.
  Added regression tests and observed their failure before changing the generator.
- Automatic radius now adapts safely; narrow sealing bands avoid a tight central
  dip. Keep the planned outward settling transition instead of abruptly projecting
  a large bend onto the side surface. Final-solid contact checks remain enforced.
- Only folded geometry validates bend material requirements; unused radius settings
  cannot block Base/Extended/Cut diagnostic generation.
- The user clarified that all four operations belong to **one button**. Create and
  Update now force the complete folded result, including files with a saved older
  preview stage. No Stage dropdown appears in the normal panel.
- **38 automated tests passed**, including narrow straight/bent/closed rims, scene
  plus object scale, explicit-radius material limits and one-action Create/Update.
  Report: `generated/tests/20261125-160742-277872`.
- **7 preview cases / 63 PNGs passed**, including the narrow curved rim. Folded cases
  have zero detected tape/source or tape/tape triangle intersections.
  Gallery: `generated/previews/20261125-160804-043725`.
- Version 0.1.1 ZIP installed/enabled in an isolated repository. Tested the installed
  extension on a 0.3 mm curved rim, including a stale Base stage followed by a stale
  Cut stage on Update: both produced complete folded tape with no intersections.
- Package filenames are derived from the manifest version in `run_tests.py`.
  Do not hard-code a release version in the test/build runner.

## Version 0.1.2 cylinder fix on 2026-11-25

- User reported a triangle-intersection error selecting the vertical side-face loop
  of a cylinder. Their screenshot showed scale X/Y 0.010, Z 0.004 and default tape
  settings. Reproduced the error on a default 32-sided primitive (radius 1, depth 2,
  scene unit scale 1: physical diameter 20 mm and height 8 mm).
- The source corners could lie between tape samples: complete triangles crossed
  the source even when all their vertices were outside. The old diagnostic combined
  tape/source and tape/tape intersections under a misleading self-intersection error.
- Added failing cylinder geometry and frame-continuity tests first. The fix retains
  relevant original source corners, keeps a continuous frame around the barrel,
  and subdivides between constraints without generating tiny near-cut triangles.
  Contact validation remains enabled; source and self-contact errors are now distinct.
- **41 automated tests passed**, including all previous cases and 16/32/64-sided
  cylinders, applied/unapplied scale, different seeds and reverse overlap order.
  Report: `generated/tests/20261125-163246-285241`.
- **8 preview cases / 72 PNGs passed** with zero detected tape/tape and tape/source
  intersections in the displayed folded results. Cylinder flaps fold onto both
  end caps. Gallery: `generated/previews/20261125-163306-788208`.
- The 0.1.2 ZIP was installed/enabled/reloaded in an isolated Blender 4.4.3 profile.
  The installed extension created the complete tape in one action on the scaled
  cylinder using the reported defaults, with zero measured intersections. The
  source scale and original geometry were preserved.
- No Stage control or extra operation button was introduced. Create and Update
  still run the entire four-stage construction. No root AGENTS.md update was made.

## Version 0.2.0 irregular cut depth on 2026-11-25

- User requested some cuts to stop short instead of all reaching the underlying
  edge. Added **Uncut root (mm)** (mean material left between fold and tip) and
  **Depth variation (mm)** (seeded plus/minus). Defaults 0/0 preserve the previous
  path. Try 0/1 for mixed full and short cuts, or 0.75/0.25 for 0.5–1 mm of web.
- Depth noise uses an independent stream per side, so depth changes preserve
  spacing/angles and closed seams repeat. Negative samples become full-depth cuts.
  Uncut root must be less than available overhang; variation is capped to retain
  at least one thickness of slit. Short cuts require a positive kerf.
- The web is welded actual material. Short-cut geometry bends coherently until
  the deepest tip, releases into independent flaps gradually, and settles over a
  longer shoulder before contact fitting. It preserves overlap and contact checks.
- Triangulate the actual concave slot outlines with Blender's constrained Delaunay
  API; moving vertices of a triangulated rectangle can bridge across slit tips.
  Keep local anchors rather than putting every tip row through the full tape.
- Short cuts use explicit closed shells offset by stable material-frame normals.
  Solidify averaging on narrow tip triangles caused inverted rims; full-depth
  geometry still uses its existing Solidify path. Contact repair moves both sides
  of explicit shells together. Thickness and manifoldness are measured independently.
- Weld within max(0.00001 mm, thickness * 0.001) on the short-cut path to remove
  float32/CDT near-duplicate points and false internal caps. The original full-depth
  path retains its original welding. Total width supports a varying source band.
- New settings persist through Create, Update and save/reload. Both actions still
  perform all four operations through one button. Root AGENTS.md remains unchanged.
- **50 automated tests passed**, with no failures/errors/skips, using the project
  Run_Tests.cmd in Blender 4.4.3. The initial new tests failed before implementation;
  later regressions caught slot-tip triangles crossing their boundary, unstable
  thickness, and float32 near-duplicate points on varying-width bands.
  Report: `generated/tests/20261125-191139-820646`.
- The 0.2.0 ZIP was installed and enabled in a separate, existing isolated profile
  and repository. The installed operators created and updated mixed-depth tape on
  the scaled cylinder, saved/reloaded both controls, retained the source, and
  produced closed solids with zero measured tape/tape or tape/source intersections.
  No existing Blender workspace or installation was changed.
- **10 preview cases / 92 PNGs passed** with zero measured tape/tape and
  tape/source intersections, source penetration and nonmanifold edges in all folded
  results. Gallery: `generated/previews/20261125-191418-626858`. New CUT-stage close-ups
  visibly show different tip depths; folded views retain joined web and overlaps.

## Version 0.3.0 mesh reduction and material detail on 2026-11-26

- User accepted the shape but reported excessive polygons and asked about using
  normals/displacement. New **Mesh detail = Optimized** is the default. **Detailed**
  retains the construction geometry. Existing tapes receive these defaults when
  updated; no extra operation button is needed.
- Continue solving the dense solid first. Native Decimate collapse trials retain
  25%, 35%, 45%, 60%, 75% or 90% of its triangles. Accept the first candidate with
  one component, no nonmanifold/degenerate geometry, no self/source intersections
  and no penetrating source vertices. Unsafe trials retain the original result.
- Check shape distance at every vertex and triangle centre of both meshes against the
  other BVH, in physical mm. **Shape tolerance** defaults to 0.02 mm (max 0.1 mm).
  These samples do not establish an exact global Hausdorff bound; full triangle
  intersection checks remain separate. If every trial fails, preserve dense geometry.
- Transfer smoothed high-resolution corner normals to the accepted mesh. Keep
  thickness/cut creases sharp in the dense normal source at 45 degrees. Normals
  are stored on the reduced mesh; no duplicate dense object or texture remains.
- **Paper bump** defaults to 0.003 mm and adds native Noise/Bump shader nodes.
  Object coordinates and scene unit scale give physical grain height/spacing.
  Zero disables grain. Materials are keyed by colour, bump height and unit scale
  without exposing internal scaling in their display names. No external images,
  subdivision or true geometric displacement are needed for paper grain.
- This transfers smooth shading and supplies procedural grain; it is not a bake of
  every geometric fold into a texture. Slits, silhouette, thickness and overlap
  remain real geometry. Generation time still includes the dense contact solve.
- Save before/after triangle and polygon counts, percentage reduction and maximum
  checked shape distance in snaketape_metrics. Display triangles saved in the panel
  and gallery. Update and save/reload persist all controls and the corner normals.
- Raw shell-pair thickness regression uses Detailed because reduction changes vertex
  ordering. Optimized regressions separately enforce performance, shape, manifoldness,
  contacts and custom normals. Tests were added and observed failing before coding.
- Do not apply unvalidated planar dissolve as an optimization: probes created
  crossing or degenerate triangles on the thin closed shell. Collapsing to 15% also
  crossed cylinder layers. Trial validation is required, rather than one fixed ratio.
- Sample the actual triangles, not an average of a nonplanar quad's corners.
  That average can lie off the dense surface, falsely rejecting every reduction.
  A failing full-depth performance regression exposed this and verifies the fix.
- Freeze the dense evaluated mesh's loop-triangle diagonals in an isolated trial
  object before Decimate. Its implicit BMesh triangulation otherwise changes
  twisted quads before collapse, even at high ratios. This was the other cause of
  full-depth reductions being falsely rejected. Remove trial objects/meshes on
  every path; publishing occurs only after independent checks.
- Reject high-resolution normal correspondences more than 30 degrees from the
  reduced surface's own smooth normal. Nearest-point matching at slits can choose
  a perpendicular wall or another layer and create dark triangular patches despite
  valid geometry. Fall back to local smooth normals and keep every corner within
  60 degrees of its face. A normal-direction regression and native render verified
  the correction; do not rely only on geometry tests for shading acceptance.
- Accept a reduction only if its polygon count is also lower. A mild collapse
  of a quad mesh can reduce triangles yet increase visible faces after triangulation.
  Keep the original instead; a closed-loop regression covers this case.
- Final project launcher: **56 tests passed**, zero failures/errors/skips in
  Blender 4.4.3. Report: `generated/tests/20261125-202950-589569` (host timestamp).
- Final gallery: **10 passing cases / 94 PNGs**, all with zero measured tape/tape,
  tape/source intersections, source penetration and nonmanifold edges. Gallery:
  `generated/previews/20261125-202948-850957`. Native renders were visually reviewed
  after correcting the normal correspondence at slit walls.
- Irregular cylinder: **59,126 to 23,292 polygons**, 66,552 to 23,292 triangles,
  about 61% fewer faces / 65% fewer triangles; checked surface distance 0.00892 mm.
  Mixed-depth straight band: 27,564 to 7,714 polygons. The closed-loop and full-depth
  cylinder references retained their original meshes when no tested candidate met
  all safety and polygon-count requirements. Never claim a fixed reduction for all
  inputs; the panel/gallery show the actual outcome.
- The final ZIP was installed/enabled in a fresh isolated Blender 4.4.3 profile.
  Create/Update on the scaled cylinder preserved the source, reduced the solid,
  saved/reloaded custom normals and settings, retained the procedural bump, and
  had no detected intersections. The user's active installation was untouched.
- Blender notes and the README are saved as UTF-8; previous local default encoding
  had written an en dash as Windows-1252, which displayed incorrectly in UTF-8 tools.

## Version 0.3.1 cut-tip and shoulder correction on 2026-11-26

- User reported unnatural kinks and tear-like sideways notches at slit tips, worse
  with Optimized than Detailed. Their parameters were Uncut root 0 mm / Depth
  variation 0.48 mm. Preserve the same values and regenerate through Update Tape.
- Two issues combined. Longitudinal-only CDT constraints admitted skinny ears from
  three successive curved column/border points. Also unconstrained decimation
  moved cut-tip/crease vertices, amplifying the defect despite passing volume tests.
- _tip_mesh now constrains transverse rows and connects tip nodes into the interior.
  Interior columns stay at fixed arc positions; only actual slit boundaries move
  with angle/kerf. Drop points outside a slanted outline. Curved interior columns
  can create another class of skinny ear, so do not interpolate all columns with
  the slit warp. Preserve the full perimeter including the upper-left corner.
- Preserve the common web during collision relief. Its displacement weight is zero
  through the deepest tip, then rises smoothly before independent flap lifting.
  Keep final solid intersection checks; do not hide artifacts through shading alone.
- Explicit shells label snaketape_surface on FACE: +1 outer skin, -1 inner skin,
  0 rim. A BOOLEAN POINT snaketape_protect identifies boundary vertices in the
  collar through max(deepest tip, quarter-arc length) + max(0.3 mm, 4 thicknesses).
  These attributes support independent geometry tests and optimization constraints.
- Optimization gives collar vertices zero Decimate weights and the remaining
  vertices unit weight. Blender 4.4.3 explicitly skips edge collapses touching a
  zero-weight vertex. Full-depth legacy meshes use their existing sharp outline
  detection. Slit tips and shoulders are locked; distant flap edges still use the
  existing shape tolerance and full contact checks.
- Pinning entire long cut borders was needlessly expensive. Protect the collar,
  rather than disabling reduction over the whole flap. The curved performance
  regression permits up to 65% of dense triangles/vertices, versus 50% on straight
  tape, so shape preservation takes priority while still requiring real savings.
- Added failing shoulder-normal tests before fixing geometry. They reproduce
  Detailed at 1 mm variation and Optimized at the reported 0.48 mm, plus a landmark
  test retaining cut tips within 0.0005 mm. Restrict the shoulder measurement to
  the outer barrel; settled cap faces can have the same height but are not bends.
- Root AGENTS.md remains unchanged. Runtime still uses only Blender 4.4.3/native
  Python, and Create/Update remain one complete operation.
- Relevant native implementation: https://github.com/blender/blender/blob/v4.4.3/source/blender/bmesh/tools/bmesh_decimate_collapse.cc
- Temporary Decimate vertex-group weights are cleared from each candidate before
  publication; no unnamed group memberships are left in the saved tape.
- Final project launcher: **59 tests passed**, zero failures/errors/skips, in
  Blender 4.4.3. Report: `generated/tests/20261126-081034-978264`.
- Final gallery: **11 cases / 106 PNGs passed**, with zero measured self/source
  intersections, penetration or nonmanifold edges in all folded outputs. Gallery:
  `generated/previews/20261126-081035-977107`. The last case reproduces the exact
  reported 0 / 0.48 mm values and has a dedicated shoulder close-up.
- Reported reference case: 59,530 dense polygons to 30,234 optimized polygons,
  67,188 to 30,234 triangles; checked surface distance about 0.00553 mm. Native
  before/after close-ups were reviewed for the crease/tear-like notch.
- The final 0.3.1 ZIP was installed/enabled in a fresh isolated profile. Installed
  operators created and updated the cylinder at root 0 / variation 0.48, retained
  source geometry/scale, saved/reloaded normals/settings and passed solid/contact
  measurements. The user's active Blender installation and preferences were untouched.

## Version 0.4.0 one-edge wrapping, build and support on 2026-11-26

- Preserve Both edges as the default and retain existing width modes/geometry.
  One edge uses Overall width (the original flat material including the bend)
  and Wrap depth (the finished distance on the adjacent surface after the bend).
  The user explicitly confirmed this definition of finished wrap depth.
- Allocate `flat = overall - depth - pi * radius / 2`. Anchor that flat part at
  the chosen selected-row boundary and trim the other rail inward. It must fit
  inside the selected row. Reject impossible widths/depths with measured values;
  do not silently alter material width or extend across the other corner.
- One edge uses a quarter bend and the existing validated contact/overlap pipeline.
  The unused tape edge lies flat; only the selected fold has a raised shoulder.
  Full-depth and short-cut paths both accept an explicit set of active sides.
  Metrics record flat width, bend allowance, wrap depth and selected physical edge.
- A/B are based on the original (non-reversed) rail ordering. Reverse direction
  changes overlap traversal but keeps the same physical wrapped edge. Swap Edge
  toggles source options before Create, or atomically rebuilds the selected tape
  in Object Mode. Failed swaps restore the old setting and retain the old mesh.
- Example: cylinder side-face band 8 mm, overall 10 mm, finished wrap 3 mm,
  automatic radius 0.2 mm leaves 6.686 mm flat. A 4 mm straight band accepts
  overall 6 mm / finished wrap 3 mm, leaving 2.686 mm flat.
- Persist requested dimensions, not internal effective overhang settings. New
  controls use RNA defaults so older blend files retain Both edges behaviour.
- Copy Settings copies JSON containing every current setting, version, scene
  units, source dimensions/transform/face indices and last-generated settings/
  measurements. Flag pending edits. Include the blend basename without directories.
  Tests substitute a clipboard object; never overwrite the user's clipboard in tests.
- Build.cmd uses the existing isolated launcher; it builds and validates without
  running tests. tools/packaging.py is shared with Run_Tests.cmd. Read archive
  id/version from the manifest. Default archive is generated/packages/
  snake_tape-0.4.0.zip; timestamped build logs/results go under generated/builds/.
  --no-pause and --output support unattended invocation and paths with spaces.
- TDD: the initial nine new behavioural checks failed before implementation, then
  passed. Coverage includes material width/finished depth, both physical edges and
  reversed order, one-sided contact, atomic swap, copy reports and native Build.cmd.
  Further checks cover saved/reloaded controls and copying without an active object.
- Previews add a straight one-edge profile and the scaled cylinder with Edge A
  and Edge B (reversed order), overall 10 mm / depth 3 mm / depth variation 0.48 mm.
  Keep previous cases and timestamped reports for regression comparison.
- Final project Run_Tests.cmd: **70 passed**, zero failures/errors/skips, in
  Blender 4.4.3. Report: `generated/tests/20261126-085508-740412`.
- Final gallery: **14 cases / 137 PNGs passed**, with zero measured self/source
  intersections, penetration or nonmanifold edges. Gallery:
  `generated/previews/20261126-085508-790149`. Straight profile and both cylinder
  choices were visually reviewed. One-edge cylinder reference: 10,690 triangles.
- Standalone Build.cmd built/validated the ZIP without tests. Report:
  `generated/builds/20261126-085744-732684`. The regression also exercises output
  and working-directory paths containing spaces, plus missing-executable failures.
- The packaged 0.4.0 extension was installed/enabled in an isolated profile and
  passed Create/Swap/Update, reverse keeping the same physical edge, save/reload,
  support reporting, source preservation and independent solid/contact checks.
  The real clipboard was not changed by verification. All nine packaged source
  files were byte-checked against the live project. Interactive panel layout and
  undo/redo remain manual checks; they are not counted among automated passes.
