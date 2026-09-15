---
title: What the line videos show
date: 2026-09-14
tags: [customer, videos, pork-line, saw, field]
status: draft
source: field-notes/customer/meat-men/videos/
---

# What the line videos show

Four phone clips Neil sent to the Meat Men group, 720 x 1280 portrait, 30 fps, all with audio.
Watched as frame contact sheets on 2026-09-14. Context: [[neil-requirements]].

| Clip | Sent | Length | What it shows |
|---|---|---|---|
| IMG_1005 | 2026-09-13 | 16.4 s | The leg station. Whole bone-in legs hand-placed across a white modular belt, trotter tip at the open right-hand edge; a sloped steel wall on the left side, a low lip on the right, workers standing on the right. Pixel-identical to the 2026-09-11 clip. |
| IMG_1008 | 2026-09-13 | 26.1 s | The same kind of station, busier. Faced hams with trotters arrive touching and overlapping; workers push and turn them one-handed so trotters reach the right edge. |
| IMG_1003 | 2026-09-14 | 16.4 s | Upstream: half-carcass sides pulled from the hanging rail with hooks onto a wide belt, hind leg overhanging the near belt edge. |
| IMG_1004 | 2026-09-14 | 8.9 s | A worker cuts a foot off each side with a handheld circular saw hung from an overhead balancer, at the far belt edge; cut pieces lie on the belt. |

## Observations that change the model

- Legs touching is the normal state in IMG_1008, not an edge case. The segmenter currently
  refuses touching pieces, so singulation or a touching-piece split is needed.
- Leg yaw on arrival runs from square to the belt to about 45 degrees off (IMG_1005).
- Trotter tips sit at the belt edge or slightly past it after the human step (IMG_1005,
  IMG_1008). How far past is not measurable from the clips.
- The foot saw seen is a circular blade, hand-held. Blade diameter looks like 250 to 300 mm
  (from field, unverified: estimated against the operator's hand). Whether IMG_1004 removes
  front or hind feet is not visible in 9 seconds.

## Not in the clips

- A saw at the leg station itself. Lakshya reports a saw on the right side at the downstream end
  that cuts the trotters off; it is modelled from that description as a pass-through circular
  blade just outside the open edge, cutting at the hock joint (decided 2026-09-14).
- Belt speed and travel direction. Measurable later from IMG_1005 by tracking belt texture.

## Metadata

- Audio: a steady plant noise floor around -22 dBFS in every clip, no speech bursts in the
  per-second levels. Not transcribed.
- GPS in the file metadata places all four clips in north-central Iowa. Lakshya confirmed on
  2026-09-15 that the plant is Prestage Foods of Iowa near Eagle Grove, Wholestone's joint-venture
  partner, and that the cell will be set up there.
