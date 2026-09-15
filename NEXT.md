# Where we are, and what is next

Written 2026-09-12. Read this after `IDENTITY.md` and `memory/MEMORY.md`.

## The project, restated after the customer's video

A pork plant station. Whole bone-in pork legs (ham, hock, trotter attached,
9 to 15 kg, about 720 mm long) arrive hand-placed on a 700 mm white modular
belt. Operators orient each leg so its **trotter hangs off the near edge** of
the belt, which is why that side has no rail. That orientation is the task.

It is an orient-in-plane job, not a pick and place, unless the cutter turns out
to need the leg lifted. That is the single unanswered question that picks the
robot.

## What is built and measured

- **The cell.** Endless belt (the joint is rewound every step so the surface
  never travels), integrating encoder, 700 mm white belt, one rail on the far
  side only, overhead camera at 950 mm.
- **The product.** `product.py` generates a leg as a lofted mesh with a flat
  underside, in process, from a nine-row profile table. `leg_population(n, seed)`
  samples a batch: correlated size, ham bulk against hock slenderness, hock
  bend, handedness. Rides the belt with zero slip, drift or tilt over a metre.
- **Sensing, frames, perception, tracking.** All gated and measured. See
  `library/topics/perception-ingestion.md`.
- **Depth-first segmentation** (`evidence.py`): geometry proposes, appearance
  refines the boundary, colour confirms. 0.033 mm on clean frames at 29.6 ms.
- **Four research notes**: the pork line with 89 verified videos, arm selection,
  segmentation state of the art, depth-primary methods.

## What is broken, and known to be

The pose estimator, the grasp rule and the tracking model were all written for a
symmetric rigid slab. None survives a pork leg: 47 mm centroid error, 19 degrees
of axis error, confidence 0.215. The slab is kept as the control arm.

Two scene faults still open: the arm sits in the overhead camera's field and
occludes it, and the spawn yaw limit of 35 degrees is a guess from the video.

## Next, in order

1. **Finish the scene.** Needs four numbers from the customer: belt width, belt
   speed, piece spacing, and what the trotter hanging off the edge feeds into.
2. **The robot.** Build a SCARA alongside the UR in the same cell and compare
   them on the real task. The literature already says push-to-orient cannot hold
   the tolerance (2000 repeats of one push gave 3.4 to 11.7 mm of spread), so the
   comparison should be grasp-and-pivot against fence-and-datum.
3. **Perception, rebuilt for this product.** The estimator has to find the hock,
   not an area centroid.
4. **Learning.** Not started, deliberately.

## Numbers worth not re-deriving

- Mass centre sits 104 mm from the centre of the outline on a leg. On a slab they
  coincide, which is what the old code assumed without saying so.
- Depth axial noise above about 2 mm at 0.57 m makes the pipeline refuse every
  frame. That is a sensor purchasing requirement.
- A belt reference image cancels the camera's own warp, which spans 29.57 mm on a
  RealSense D415, the size of the product.
- 5 mm of cut-position accuracy is worth over US$300k a year on a 180 carcass per
  hour pork line. The business case is accuracy, not labour.
- Industry uptime on comparable automation: "less than 80 percent is not
  uncommon and sometimes as low as 50 percent", utilisation "may be only 30
  percent".
