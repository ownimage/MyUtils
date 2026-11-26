# SnakeTape

SnakeTape 0.4.0 generates finite-thickness masking tape over a selected cardboard
rim in **Blender 4.4.3**. The overhang is slit into irregular flaps and folded onto
one or both edges, with local relief where flaps overlap. The cardboard mesh is preserved.

## Test and preview without opening the Blender workspace

Double-click `Run_Tests.cmd` to run all automated checks and build the installable
extension ZIP. Double-click `Gen_Previews.cmd` to generate the offline HTML gallery,
PNG images, measurements and inspectable `.blend` scenes. Each launcher prints the
output location and pauses at the end. They can be run from any working directory.
Double-click **Build.cmd** to build and validate the ZIP without running tests.
Its default output is `generated/packages/snake_tape-0.4.0.zip`; use
`Build.cmd --no-pause --output "P:\some folder\packages"` for a different location.
Build logs are saved separately under `generated/builds/`.

For unattended use from PowerShell:

```powershell
& 'P:\git\MyUtils\Blender\SnakeTape\Run_Tests.cmd' --no-pause
& 'P:\git\MyUtils\Blender\SnakeTape\Gen_Previews.cmd' --no-pause
& 'P:\git\MyUtils\Blender\SnakeTape\Build.cmd' --no-pause
```

Use `Gen_Previews.cmd --no-pause --quick` for the first two cases at reduced image
size. Use `--output "P:\some folder\new-run"` to choose a new preview run directory.
The default output is a timestamped folder under `generated/previews/`; open its
`index.html`. Generated files are ignored by Git. Earlier failed runs are retained
with their own measurements; use the path printed by the latest invocation.

The launchers look for `C:\Program Files\Blender Foundation\Blender 4.4\blender.exe`,
then PATH. To override it, set `SNAKETAPE_BLENDER` to the full executable path.
Version 4.4.3 is checked before tests or previews run. No pip packages or system
Python are required. Exit code 0 means success; nonzero means failure. A gallery
with a failed case also returns failure. A fresh Blender process uses factory
startup and isolated user-resource paths; existing workspaces/preferences are not
changed.

## Install and operate

1. Run `Run_Tests.cmd`. A successful run builds
   `generated/packages/snake_tape-0.4.0.zip` and validates the ZIP.
   Use `Build.cmd` for subsequent packaging without rerunning the tests.
2. In Blender choose **Edit > Preferences > Get Extensions**, open the top-right
   dropdown and choose **Install from Disk...**. Select the ZIP and enable SnakeTape
   if it is not enabled automatically.
3. Select the cardboard mesh, press **Tab** for Edit Mode, and use face selection.
   Select **one connected row of quad faces across the cut edge**. The two long
   boundaries of that row become the two folds. For one quad, the shorter edges
   are treated as the width; subdivide along the rim to disambiguate square faces.
4. Open **3D Viewport > Sidebar (N) > SnakeTape**. Set the dimensions, then click
   **Create Tape once**. It adds thickness, extends, cuts and folds in one operation.
   The same command is under
   **Mesh > SnakeTape > Create Tape** and **F3 > SnakeTape: Create Tape**.
5. The separate tape object becomes selected. Change its settings in the same
   panel and choose **Update Tape**. Settings, source pointer, selected face indices
   and a topology signature are saved in the `.blend` file. Renaming the source is
   supported. Source topology changes require a new face selection and Create Tape.

The four construction stages are internal. **Create Tape** and **Update Tape**
always generate the complete folded result. Intermediate stages remain available
only to the offline preview generator and geometry scripts; a stage saved by an
older add-on version cannot stop Create/Update at an intermediate result.
Updating changes only generated tape; failure retains the previous result. Regeneration rebuilds
the tape and its thickness, so manual tape edits are replaced.
Moving/deforming the source requires Update Tape; this is not a live modifier.

## Controls

| Control | Meaning |
| --- | --- |
| Wrap mode | Both edges preserves the original sealing behaviour. One edge wraps only the chosen boundary. |
| Overall width / Wrap depth | One edge only: flat tape width including bend material / finished depth on the adjacent surface. |
| Edge A / Edge B / Swap Edge | Select the wrapped boundary. Swap Edge rebuilds an existing tape immediately; before Create it changes the choice. |
| Thickness | Outward tape thickness, default 0.1 mm; clearance is separate. |
| Width mode / Width | Default: add 10 mm per side. Total mode includes the original selected band. |
| Cut spacing | Nominal mean spacing, default 3 mm. The interval partition includes the full rim. |
| Spacing randomness | Bounded independent spacing variation. |
| Cut angle variation | Maximum angular variation; cuts are constrained to avoid crossing. |
| Uncut root | Mean distance left joined between the fold line and each cut tip, in mm. Default 0 reaches the fold. |
| Depth variation | Seeded plus/minus variation of Uncut root, in mm. Negative samples become zero (full depth). |
| Wave strength / length | Smooth runs of closer/further spacing and more aligned cut angles. Closed loops use periodic noise. |
| Seed | Reproduce exactly the same geometry for unchanged inputs/settings. |
| Fold radius | Leave at zero for automatic sizing from tape thickness, physical rim width and available overhang. Larger explicit radii introduce a lifted crease and need more material to bend and settle. |
| Mesh detail | Optimized (default) reduces the finished solid; Detailed keeps the construction mesh. Create and Update still perform all four operations in one click. |
| Shape tolerance | Advanced: maximum checked simplification distance, default 0.02 mm. More geometry is retained when needed for shape or contacts. |
| Paper bump | Advanced: physical height of procedural paper grain, default 0.003 mm; zero disables it. It adds no polygons and needs no image files or UVs. |
| Reverse direction | Reverse the rim traversal and overlap placement order. |
| Contact clearance | Small geometric separation from the cardboard; extra local relief is added at overlapping strips. |
| Cut gap | Narrow visible slit width, tapering to zero at its root. |
| Mesh spacing | Maximum requested cell size; folded geometry refines automatically to at most 0.65 mm and four cells per nominal flap. |

### One-edge wrapping in 0.4

Choose **Wrap mode > One edge**, enter **Overall width** and **Wrap depth**, then
click **Create Tape**. Tape covers part of the selected row and folds over its
chosen boundary. Choose **Edge A** or **Edge B**; if the wrong edge is wrapped,
click **Swap Edge** on the generated tape to rebuild it on the other boundary.
**Reverse direction** changes overlap order while keeping the same physical edge.
Changing the A/B selector alone takes effect when you click **Update Tape**.

Overall width measures the original flat material, including the quarter-circle
bend. Wrap depth measures the finished distance along the adjacent surface after
the bend; it excludes bend allowance. The remaining flat width is
`overall width - wrap depth - pi * fold radius / 2` and must fit inside the
selected row. The tape is anchored at the chosen edge; its other edge lies flat
on that row. For example, a 10 mm tape with a 3 mm wrap and automatic 0.2 mm radius
leaves approximately 6.686 mm on the cylinder's 8 mm side-face band. On a 4 mm
band, 6 mm overall / 3 mm wrap leaves approximately 2.686 mm flat. If it cannot
fit, reduce overall width, increase wrap depth, or select a wider row.
The adjacent surface must also be deep enough for the entered wrap depth.
Contact relief and finite thickness can slightly change the final measured envelope.

### Copy settings for support

Click **Copy Settings** at the bottom of the SnakeTape panel, then paste the text
into your problem report. It includes all current settings, add-on/Blender versions,
scene scale, source dimensions/transform and face selection, plus the last build's
settings and geometry diagnostics. Pending changes are marked so a screenshot
of an older result is not confused with newly entered values. It works before
Create, on generated tape, and with no active object. The blend filename is
included without its directory path; no scene geometry is exported.

For a mix of full and slightly shorter cuts, start with **Uncut root = 0 mm** and
**Depth variation = 1 mm**. To leave every cut short, try **0.75 mm / 0.25 mm**
(0.5–1 mm remains joined). Both controls at zero preserve the previous geometry.
Depth noise is independent on each side and does not reshuffle spacing or angles;
Seed reproduces the pattern. Uncut root must be less than the available overhang.
Variation is clamped to leave at least one tape thickness of slit; short cuts need
a positive Cut gap. These distances are measured along the flat tape from its fold
line, before bending.

Short cuts leave a real connected web. It bends as one sheet near the rim; free
flaps are released gradually and receive overlap relief. This needs a slightly
longer raised settling region than full-depth cuts. Local triangulation follows
the slit outlines, and a closed shell supplies thickness without unstable normals
at the small tips. The old full-depth path continues to use Solidify.

The sealing band stays connected. Fold arc length consumes the overhang, so the
adhered side length is slightly less than the entered flat overhang width. The
folded band has a small raised shoulder at each crease and rests lower at its
centre where the rim is wide enough. Narrow rims are bridged without a tight
centre dip. A sampling/contact margin and local overlap relief keep the final solid
outside the object; clearance is not a promise that every point is exactly that
distance from the source.

## Lower polygon count and surface detail

Leave **Mesh detail = Optimized**, then click **Update Tape** on an existing tape.
SnakeTape first solves the complete dense tape, then tries progressively gentler
reductions of the finished solid. Each candidate is checked for manifoldness,
source penetration, tape/source and tape/tape intersections, and distance from the
dense surface. Candidates must also reduce the polygon count. The first acceptable result is used; if none is safe, the original
mesh is retained. The panel shows the actual triangle count and percentage saved.
**Detailed** provides the original dense geometry for comparison or manual editing.

Cuts, thickness, silhouette and overlaps remain real geometry. Smooth normals from
the detailed mesh are transferred to the reduced mesh's corners. Fine paper grain
comes from a procedural **Bump** node in the material, with **Paper bump (mm)** as
its height control. This is shading detail; it needs no subdivision or true
geometric displacement. It is not a texture bake of every fold. The main folds and
slit outlines remain in the reduced mesh. Cut-tip and shoulder vertices are locked
during reduction so it cannot pull the slit into a sideways notch. This can retain
more polygons around curved overlaps than earlier versions. Normals and material nodes are saved in
the `.blend` file, with no external textures to manage.

The default **Shape tolerance = 0.02 mm** is checked at every vertex and triangle centre
on both meshes. This sampling is not a mathematical bound over every surface point;
the full triangle contact checks are separate. Reductions vary with the source and
settings. Generation still computes the dense contact solution and can take longer;
the saved/viewport/render geometry is smaller.

## Tests and preview interpretation

The tests cover physical dimensions, scene units, transforms, deterministic cuts,
periodic waves, sealing-band connectivity, final-shell manifoldness, source
preservation, triangle intersections, contact, reverse traversal, saved settings,
safe failed updates, stale topology, launcher failures, gallery output and a real
PNG render. Several seeds are checked on straight, curved, S-shaped and closed-loop
rims. Validation evaluates the finished solid tape, including its thickness.

Previews contain all stages, front/back/top views, diagnostic flap colours and a
12 mm close-up. The seventh case tests automatic radius on a 0.3 mm curved rim.
The eighth uses all side faces of a 32-sided cylinder at scale 0.010, 0.010, 0.004
with default tape settings. This folds tape onto both end caps and tests changing
surface normals, original polygon corners and overlapping flaps near the centre.
Two further cases show mixed full/short cuts on a straight band and the scaled
cylinder, including an 8 mm close-up of the cut tips before folding and a Detailed reference
render alongside the optimized result. Triangle counts and checked shape error
appear in the gallery. A further cylinder case reproduces Optimized mode with
Uncut root 0 mm / Depth variation 0.48 mm and includes a shoulder close-up.
Three one-edge cases show a straight 6 mm tape with 3 mm finished wrap and both
cylinder edge choices at 10 mm / 3 mm, including reversed overlap order on Edge B.
They include bottom views and a profile view of the straight tape.
The corrugated example uses visible liners/flutes with a hidden
solid contact/selection proxy; this shows the tape bridging the exposed flutes.
Use the same proxy technique for a highly detailed cardboard model without a
continuous selectable rim band. The proxy should follow the outer paper skins.

On a cylinder, leave the object's positive scale as it is; applying scale is not
required. Select the vertical side-face loop, then Create Tape once. The cylinder
regressions cover 16/32/64 sides, applied/unapplied scale, different seeds and reverse
traversal. The tape mesh retains the original rim corners, so its faces cannot
take a shortcut through a faceted source between otherwise valid offset vertices.

Artistic acceptance and actual-window installation, panel interaction and undo/redo
are separate from the background tests. Reports do not count these as automated
passes. Reference cases passing does not establish support for every possible mesh.

## Supported input and limitations

- One open or closed, non-branching row of quads, connected through opposite edges.
  Multi-row selections, triangles and arbitrary patches are rejected clearly.
- Apply geometry/deformation modifiers on a duplicate before selecting the rim.
  Mirrored/zero object scales must be applied and outward normals recalculated.
  Positive non-uniform scales and scene unit scales are supported.
- Flaps conform to the adjacent side surfaces. Avoid overhangs that run beyond
  the available side or around the bottom of the cardboard; underside wrapping is
  outside this version's scope.
- This is a deterministic geometric construction with constrained contact relief,
  not a cloth/material simulation. Fine paper crumpling, tearing and adhesive
  mechanics are not simulated. Unsupported tight bends fail instead of publishing
  an intersecting folded result.

## Source layout

`snake_tape/` contains the extension and geometry pipeline, including clipboard
support reports; `tests/` contains
synthetic fixtures and independent measurements; `tools/` runs tests and previews.
Tests and previews use the production generator. Build and tests share the same
native extension validation/packaging helper. Keep Blender project decisions and
validation results in the parent `Blender/Agents.md`.

## Cut-tip and fold correction in 0.3.1

This fixes artificial kinks and tear-like notches near the fold. The material is
triangulated across the bend, with local connections at slit tips and straight
interior sampling columns. The connected web is held during contact repair, with
a gradual transition into free-flap relief. Optimization locks the cut-tip collar
instead of moving its vertices to meet a lower polygon target. Keep your existing
settings and click **Update Tape** after installing the update.

The regression reproduces **Optimized / Uncut root 0 / Depth variation 0.48 mm**.
Tests check geometric shoulder normals, retained cut-tip positions, connected
closed solids, contacts and remaining polygon savings. The curved reference uses
a less aggressive performance budget to preserve the repaired outline.
