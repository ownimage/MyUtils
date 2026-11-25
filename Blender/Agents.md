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
| `SnakeTape/snake_tape/core.py` | Settings, millimetre conversion, deterministic cuts and periodic/correlated variation. |
| `SnakeTape/snake_tape/geometry.py` | Quad-rim analysis, staged tape surfaces, flap folding, contact and final-shell intersection repair. |
| `SnakeTape/snake_tape/validation.py` | Independent measurements on evaluated solid geometry, source contact and triangle intersections. |
| `SnakeTape/snake_tape/ui.py` | Native settings, panel, menus and atomic Create/Update operators. |
| `SnakeTape/snake_tape/blender_manifest.toml` | Blender extension metadata, version 0.1.2. |
| `SnakeTape/tests/` | Synthetic reference meshes and core, geometry, persistence, launcher and preview tests. |
| `SnakeTape/tools/launch.cmd` | Shared Blender discovery, isolated profile setup and process exit forwarding. |
| `SnakeTape/tools/run_tests.py` | Standard-library test discovery, timestamped logs/JSON and extension packaging. |
| `SnakeTape/tools/gen_previews.py` | Production-generator renders, gallery, JSON measurements and framed `.blend` scenes. |
| `SnakeTape/README.md` | Installation, controls, launchers and supported input/limitations. |
| `SnakeTape/generated/` | Ignored test reports, preview runs and built extension packages. |

## SnakeTape requirements and agreed decisions

- Target **Blender 4.4.3**. Installed executable:
  `C:\Program Files\Blender Foundation\Blender 4.4\blender.exe`.
- The user agreed to the architecture and TDD/preview approach on 2026-11-25,
  then requested the implementation. The add-on and both launchers now exist.
- Start from selected connected rim faces of corrugated cardboard. Seal the
  exposed edge with masking tape whose excess width is slit and folded down.
- Stage 1: x mm outward tape thickness, typically 0.1 mm. Thickness is added once;
  geometric contact clearance is a separate control.
- Stage 2: y mm added on each side (default 10 mm), or y as total tape width,
  including the selected band. Reject an insufficient total width.
- Stage 3: nominal z mm cuts (default 3 mm, expected use 2-5 mm). Randomise spacing
  and cut angles with a repeatable seed plus smooth waves of more closely spaced
  and/or more aligned cuts. Preserve the uncut central sealing band.
- Stage 4: fold finite-thickness flaps onto both sides. Relief at bends lifts a
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
  sampling cell. A centred Solidify shell on the offset surface supplies physical
  thickness while keeping the tape outside the cardboard.
- After Solidify, test non-adjacent triangle pairs on the evaluated shell and
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
  cut spacing/randomness/angle, wave strength/length, seed, fold radius,
  Reverse Direction and advanced clearance/cut gap/mesh spacing.
- The four stages (Base, Extended, Cut and Folded) are internal. One **Create Tape**
  click performs all four. **Update Tape** also rebuilds the complete folded tape.
  Intermediate stages are only for offline previews/geometry scripts. The legacy
  stage property is hidden and ignored by Create/Update for older saved files.
  Merely changing a setting does not trigger a costly rebuild.
- Selecting generated tape exposes its saved settings and **Update Tape**.
- Install `generated/packages/snake_tape-0.1.2.zip` through **Edit > Preferences >
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
- Preview runs produce `generated/previews/<run>/index.html`, 72 PNGs, eight
  `inspect.blend` scenes, JSON measurements and native renderer logs. `--quick`
  renders the first two cases at smaller resolution. `--output` chooses a new or
  empty folder; existing results must not be overwritten.
- The eight gallery cases are straight, convex/concave, S bend, closed loop/seam,
  rotated/non-uniformly scaled edge, corrugated cardboard, a 0.3 mm curved rim
  and a cylinder side-face band at the reported scale. Each has four stages,
  front/back/top views, diagnostic flap colours and a 12 mm overlap close-up.
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
  supported in 0.1.2. Use a simple quad guide/proxy instead of changing detailed art.
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
