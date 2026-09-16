---
title: Leg cell talk, narration script
date: 2026-09-16
tags: [talk, video, narration, meat-cell, skills]
status: draft
---

# Leg cell talk, narration script

Spoken over the silent cut, one block per scene in the order the talk is assembled. The on-screen line says what is showing when it is time to move on. Targets are at 140 words a minute; where a target runs longer than the scene, keep talking over its last frame. Scene length is the drawn scene's animation time or the footage card's clip length.

## 1. Opening: the pig and the leg

### Title

On screen: "Aligning pork legs to the trotter saw" and "Synphony Robotics, for Prestage Foods of Iowa" while a leg crosses the belt behind them.
Scene: about 5 s. Target: 15 s

I'm Lakshya. This is the leg alignment cell I built and tested in simulation for Prestage Foods of Iowa, and the aim behind it: skills that compose and carry to new robots and new jobs.

Source: plan title block and section 1 (Prestage Foods of Iowa); box "Why an arm, when a bar would do" (the aim).

### Pig

On screen: a hog side in outline with shoulder, loin, belly and leg named; the leg fills in and "It arrives with the foot still on." appears.
Scene: about 16 s. Target: 18 s

A hog is split into two sides, and each side into primals: shoulder, loin, belly and leg. Each primal goes down its own line. This cell works on the leg, which is sold as ham, while the foot is still attached.

Source: plan section 0 and Figure 0.1; Table 0.1 (leg, ham; trotter still attached at this station).

### Anatomy

On screen: "One leg: 722 mm, 11 kg, the shape the simulator uses." with the axis, the centre of gravity, the hock at 76 percent, and "The saw takes the foot off at or just above that joint."
Scene: about 12 s. Target: 26 s

This is the simulator's leg, 722 millimetres and 11 kilos, with its axis and its centre of gravity. The hock sits at 76 percent of the length, by my reading of the line videos. The saw cuts in one fixed plane, and the job is to present the hock to that plane so the foot comes off at the joint.

Source: plan Figure 0.2 (722 mm, 11.0 kg, hock at 76 percent, to be calipered); Table 0.1 (cut at or slightly above the hock joint); 3.2 (centroid in the ham); section 1 (the saw's blade plane).

### Handle

On screen: "Where the jaws can hold a leg." The 180 mm jaw opening laid against the ham, trotter and shank widths, the jaws closing on the shank, then "So the cell holds the shank, seven tenths along."
Scene: about 12 s. Target: 17 s

The jaws open 180 millimetres. The ham is about 250 across. The trotter is thin and swings on its joint. The shank is bone, 78 to 110 millimetres across, so the grip goes there, at 0.70 of the length.

Source: plan section 6, "Open decision" (ham about 250 mm, jaw 180 mm); Table 0.1 (shank); 14.2 (shank 78 to 110 mm); 11.7 (0.70 of the length).

## 2. Why skills

### WhySkills

On screen: "A crossbar could square these." and "It needs no camera and no teaching." over squared legs; "Squaring a leg is one job." and the mission lines; then "align a piece on a belt" feeding a six-axis arm and a SCARA, ending on "The same skill, written once, run on either."
Scene: about 23 s. Target: 36 s

A crossbar angled across the belt could square these legs with no camera. Squaring a leg is one job. The arm is here for the larger aim: a physical system that meets a new job by composing skills it already has, and keeps taking in new ones as we teach them. Aligning a piece on a belt is one basic skill that other stations need too. I wrote the turn once, and it runs unchanged on a six-axis arm and on a SCARA.

Source: plan box "Why an arm, when a bar would do" (bar, no camera, not tried; the aim); "What this plan proposes" (one turn skill on both arms); 8.1 (orient_on_belt among the composed skills); 14.6 (loin).

### Definition

On screen: "What I mean by a skill." A box titled "close the jaws on the shank" with five rows, "The success test is what separates a skill from a function.", then a rule, a planner and a trained model inside the same contract.
Scene: about 14 s. Target: 30 s

This is what I mean by a skill, using the grasp. It needs a grasp target on the moving shank. Before it starts, the jaws must open 40 millimetres wider than the shank. It gives back the opening it closed to and its lift proof. It knows it worked when the leg rose with the tool, within 2 millimetres. Whatever runs inside can change while the contract stays the same.

Source: plan 3.1 (acquire_shank: shank_grasp input, 40 mm spare opening, grip_opening_m and lift_proof outputs); 11.7 (lag at most 2 mm on the 5 mm proof lift); 3.2 and 13.4 (the contract does not change with the implementation).

### Drill panel

On screen: "Three drills, one skill each." First touch, close control and carrying at speed side by side, then "Learned at different times."
Scene: about 8 s. Target: 12 s

Here a player drills a first touch, close control through cones, and carrying the ball at speed, each on its own and usually in a different session.

Source: talk footage, scripts/view/remotion/src/DrillPanel.tsx; plan box "Why an arm, when a bar would do" (skills learned in different places and at different times).

### Fuse

On screen: the drills feed "take the ball past a defender at speed"; "Learned over enough variation, a skill carries."; then the cell's three results: centre of gravity 1.2 mm median on 20 held-out legs, one turn skill on the UR20 and the SR-20iA, the same skills on a loin 20 of 20 near square.
Scene: about 22 s. Target: 31 s

In a match all three run at once, and taking the ball past a defender at speed is a skill made from them during play. A skill learned over enough variation also carries to new conditions. In this cell the centre-of-gravity model is 1.2 millimetres off, median, on 20 legs it never trained on. One turn skill runs on two arms, and the same skills aligned 20 of 20 loins arriving near square.

Source: plan box "Why an arm, when a bar would do" (footballer); 11.4 and Table 13.1 (1.2 mm median, trained on 100 other legs); "What this plan proposes" (one skill, two arms); 14.6 (20 of 20 square arrivals, wide-jaw placeholder).

### Compose

On screen: "Four skills align one leg." building "align a leg for the saw"; then "How big a skill can be." with "a command, no test of its own" at the bottom and "Any size that states what it needs and tests whether it worked."
Scene: about 15 s. Target: 22 s

The cell has the same shape: four skills compose into aligning a leg for the saw. A single joint command has no test of its own, so it sits below the line. Anything larger that states what it needs and checks its own result is a skill, up to a whole job.

Source: plan 13.7 (primitive, composed skill, job; a contract's success checks as its goal condition); Figure 4 (the alignment graph).

## 3. The workflow in code

### Plan

On screen: "Four skills and a judge, camera to cut." with class names and each skill's declared outcomes, "Every outcome is routed.", the runner's two added outcomes, then pick_and_place and rotate_on_belt and "I built both, and ran both on the same 20 legs."
Scene: about 17 s. Target: 33 s

In the code that is four skills and a judge. Each skill declares what it can return, the graph routes every outcome to a next skill or a stop, and the runner adds precondition failed and success not verified to every skill. The move step has two versions. Approach A raises the shank 100 millimetres and carries the leg. Approach B raises it 20 and swings the leg, which in this rigid simulation is still a low carry.

Source: plan Figure 4 and 3.1 (every outcome routed, runner adds precondition_failed and success_not_verified); 11.6 (A at 100 mm, B at 20 mm, rigid leg leaves the belt, a low carry); Table 11.7 (20 legs per condition).

## 4. Perception

### Cameras

On screen: "A depth camera, 950 mm over the belt." with the depth error formula and about 1.2 mm at 0.95 m; then the Gemini 335L row (0.94 mm, 7,531 pixels, 158 of 180 in view, IP65) and "I took the Gemini 335L for its IP65 rating and hardware sync."
Scene: about 16 s. Target: 34 s

The camera is a stereo depth camera 950 millimetres over the belt, with about 1.2 millimetres of error at the belt. I modelled the Gemini 335L and the RealSense D455 on 20 legs in 9 poses, and their noise came out 6 percent apart. With the long side across the belt, both keep every leg that fits on the belt in view, 158 and 157 of 180 frames. I chose the Gemini for its IP65 rating and hardware sync.

Source: plan 11.1 and Table 11.1 (950 mm, about 1.2 mm, 20 legs in 9 poses, 6 percent, 158/180 and 157/180 long side across, clipped frames legs through the rail, IP65 and hardware sync); Table 9.0, decision 1.

### CameraFeed

On screen: "Two depth cameras, one leg." Gemini 335L on top, D455 below: colour with the true outline, height above the belt, and the error against the simulator's exact depth, at three arrival angles.
Scene: about 9 s. Target: 7 s

The raw feed from both, Gemini above and D455 below, as a leg passes at three angles.

Source: plan 11.1, Video 11.1; section 12, "Two depth cameras, one leg".

### Segment

On screen: "First, which pixels are leg." The rule that anything more than 10 mm above the empty belt is a piece, "no training, 93 to 105 ms a frame", two touching legs read as one, plant footage at 14 and 36 of 55, then "So the U-Net segments, and geometry checks it every frame."
Scene: about 17 s. Target: 34 s

Height finds the leg: anything more than 10 millimetres above the empty belt is a piece, with no training, at 93 to 105 milliseconds a frame. It cannot split touching legs. On 21 plant frames graded by eye, a colour rule got 14 of 55 legs out whole, and Segment Anything with that rule got 36. With stereo edge effects modelled, a small U-Net scored 0.984 IoU against geometry's 0.967, so the U-Net segments and geometry checks it every frame.

Source: plan 11.2 (10 to 300 mm above the belt, no training, 93 to 105 ms, edge effects, 0.984 against 0.967, U-Net checked by geometry); 11.3 and Table 11.3 (14 and 36 of 55, 21 frames, graded by eye); Table 7.2 (touching legs normal in IMG_1008).

### Segmentation

On screen: "Finding the leg by height." The geometric segmenter on simulated legs: found outline against the true one, the height it reads, matched, extra and missed pixels. Datasheet noise, no edge effects.
Scene: about 12 s. Target: 7 s

Geometry on simulated legs with no edge effects, so this is the method at its best.

Source: plan 11.2, Video 11.2; section 12, "Finding the leg by height".

### RealFootageSegmentation

On screen: "Real footage, all 21 frames." Two per second: the frame, the colour rule, and Segment Anything plus the colour rule.
Scene: about 11 s. Target: 9 s

The plant frames. Where legs touch, the colour rule merges them into one region and Segment Anything keeps them apart.

Source: plan 11.3, Video 11.3 and Figure 11.3a.

### CentreOfGravity

On screen: "The turn happens about the centre of gravity." The true centre of mass, the outline centre 39.6 mm off and the column centroid 7.9 mm off, the column formula, the learned correction at 1.2 mm median and 4.6 mm worst, and "Zero output is the geometry exactly, so a bad model falls back to it."
Scene: about 19 s. Target: 36 s

The turn pivots on the centre of gravity. The outline's centre misses it by 39.6 millimetres median, pulled toward the light trotter. Counting each pixel as a column of meat from the belt up gets to 7.9. A small network, 208,000 weights, adds a correction: 1.2 millimetres median, 4.6 worst. At zero output it is the geometry, so the deterministic core stays and the network learns only what geometry misses. These legs have uniform density, and real bone and fat will move the point.

Source: plan 11.4 and Table 11.4 (39.6, 7.9, 1.2 and 4.6 mm; uniform density); Table 13.1 (208,002 parameters; zero output reproduces the rule).

### CentreOfGravityClip

On screen: "Where the mass is." Three legs through the camera model with edge effects. White cross centre of mass, orange outline centre, green column centroid.
Scene: about 12 s. Target: 12 s

Three legs through the camera model. This estimate is an input to the perceive skill, with its own gate of 10 millimetres worst case, which I set.

Source: plan 11.4, Video 11.4; 11.5 (centre of gravity carried in LegPerception); Table 9.0, decision 5 (gate 10 mm worst, set by Lakshya).

## 5. Grippers and arms

### Grippers

On screen: "I tested two grippers on the leg." Pull tests, 918 N against 720 N and 229 N against 180 N, "Both pass the pull test."; the three-finger's geometry, shank width at most opening / 2 = 77.5 mm against shanks of 78 to 110 mm; "So the cell uses the parallel jaw on the shank."
Scene: about 17 s. Target: 27 s

I tested a parallel jaw and a centric three-finger gripper, and both pass the pull test. The three-finger only fits a shank up to half its 155 millimetre opening, and these shanks are 78 to 110, so it refuses before the arm moves. Its end-on grasp at the trotter needs a tool that tilts. The cell uses the jaw on the shank.

Source: plan section 12, "Grippers on their own"; alignment-approaches record, amendment "Three-finger gripper on the shank" (half the 155 mm opening, shanks 78 to 110 mm); Table 2.3 (end-on grasp needs tilt).

### GripperAlone

On screen: "Jaw gripper, three-finger gripper, on their own." Jaw held to 918 N against the 720 N it needed; three-finger held to 229 N against the 180 N it needed.
Scene: about 7 s. Target: 3 s

The pull tests, each gripper on its own.

Source: plan section 12, "Grippers on their own".

### GripShank

On screen: "Jaw gripper, shank from above, stopped belt." UR20 success, the shank rose with the tool; SR-20iA success, using a lower approach height.
Scene: about 8 s. Target: 8 s

The jaw on the shank, on a stopped belt. On both arms the shank rises with the tool.

Source: plan Table 2.3; section 12, "Go and grip, stopped belt".

### ThreeFingerShank

On screen: "Three-finger gripper, shank from above, stopped belt." UR20 and SR-20iA both refused before moving, 38 mm of spare opening against 40 mm required.
Scene: about 4 s. Target: 4 s

The three-finger on the shank. Both arms refuse before moving.

Source: plan Table 2.3; section 12, "Go and grip, stopped belt".

### TrotterEndOn

On screen: "Three-finger gripper, trotter end-on, stopped belt." UR20 success with the tool horizontal along the leg; SR-20iA refused before moving, the arm cannot tilt its tool.
Scene: about 8 s. Target: 9 s

End-on at the trotter, the UR20 lays its tool along the leg and holds it. The SCARA cannot tilt, so it refuses.

Source: plan Table 2.3; section 12, "Go and grip, stopped belt".

### Arms

On screen: "A six-axis arm and a SCARA, on the same reach test." Bars for 120 belt points at three heights; the SCARA wrist at 0.6 to 1.6 kg m^2 measured against 0.45 rated; "The SCARA is 0.2 to 0.5 s faster per leg where it reaches."
Scene: about 9 s. Target: 24 s

The UR20 is six-axis and the SR-20iA a SCARA. The UR20 reaches all 120 belt points at three heights, and the SCARA none at 350 millimetres. Carrying a leg puts 0.6 to 1.6 kilogram square metres on the SCARA's wrist, rated for 0.45. Where it reaches, it is 0.2 to 0.5 seconds faster per leg.

Source: plan Table 7.1 (reach, J4 rating 0.45 kg·m²); 7.1, Neil's questions (0.6 to 1.6 kg·m² measured; 0.2 to 0.5 s per leg).

### Reach

On screen: "Reach, tool pointing down, a leg upstream for scale." UR20 all 120 grid points reached at all three heights; SR-20iA 101 of 120 at 50 and 180 mm, none at 350 mm.
Scene: about 18 s. Target: 10 s

The reach test itself, with a leg upstream for scale. The SCARA gets 101 of the 120 points at the two lower heights.

Source: plan section 12, "Arms"; Table 7.1.

## 6. Method

### Method

On screen: "One leg through the cell, drawn to scale." The belt at 0.30 m/s, meet at p(t) = p0 + v t, "met within 1 mm at 0.30 m/s"; the turn to heading −90 degrees with the hock on the blade plane; release into the saw; "any heading, UR20: hock 1.1 mm median, 1.7 mm worst".
Scene: about 25 s. Target: 41 s

The method on one leg. Perception gives the leg, its centre of gravity and a grasp point on the shank. With the belt at an assumed 0.30 metres a second, the arm aims where that point will be and meets it within 1 millimetre. It turns the leg about its centre of gravity until the hock is on the blade plane. Past about 90 degrees the leg lags the jaws by 3 to 5 degrees, so the skill looks again and corrects. Then it lets go and the belt carries the leg to the saw.

Source: plan 10.1 (belt-frame prediction and meeting time); 11.6 (met within 1 mm at 0.30 m/s; the turn about the centre of gravity; lag of 3 to 5 degrees; correction at most twice; 1.1 mm median, 1.7 mm worst); alignment-approaches record, Setup (0.30 m/s assumed).

### ApproachAandB

On screen: "Square set, UR20 close-up, three legs." A, carried, with the shank lifted 100 mm, beside B, turned, with the shank lifted 20 mm.
Scene: about 30 s. Target: 24 s

Square-set close-ups on the UR20. A carries the leg high and B swings it low. Here the hock lands a median 0.9 millimetres from the blade plane with A and 0.5 with B. At any heading those medians are 5.1 and 1.1, because a leg carried high swings more in the jaws through a big turn.

Source: alignment-approaches record, final Results (square set hock at release: A UR20 0.9 mm, B UR20 0.5 mm; any set 5.1 and 1.1 mm); plan 11.6, approach A; section 12 close-up captions.

### BestPick

On screen: "Approach B on the UR20, any-orientation set." Leg 14 of 20, camera tracking the leg.
Scene: about 11 s. Target: 22 s

The largest turn in the set: a 778 millimetre, 14 kilo leg arriving almost trotter-first, turned 162 degrees while riding the belt. The hock goes down 0.3 millimetres from the blade plane, and the saw cuts 0.3 from it. Once the leg is on the belt, nothing is placed by hand.

Source: plan section 12, "One leg, start to finish", Video 12.0.

## 7. Learning

### Teach

On screen: "Three learned parts, two trained so far." Segmenter, centre-of-gravity correction and grasp offsets, the last marked not trained yet; the teaching steps through the contract; the plant's own labels: jaw opening, proof lift, pose at release, the cut.
Scene: about 15 s. Target: 30 s

Three parts of the cell learn. The segmenter and the centre-of-gravity correction are trained, and the grasp offsets are not yet. Each predicts a correction to its rule, and a model replaces the rule only if it wins a paired test written before the run. In the plant, the skill's own checks label its runs, but they score the action taken and never the best one, so that label is weaker.

Source: plan 13.1 and Table 13.1 (two trained and kept, grasp policy not trained, corrections to rules); 13.4 (teaching interface, pre-registered gate); 13.2 (production signals score the action taken).

### Reinforce

On screen: "Reinforcement learning goes in one place: the turn." The scripted turn plus a bounded residual, the reward as every contract check passing, the training ranges, and "One CPU runs about 21 policy steps a second, so 160,000 steps take about 2.1 hours."
Scene: about 14 s. Target: 31 s

Reinforcement learning goes into the turn and nowhere else, because the grip is a one-shot choice the simulator can score for every candidate. The design is a bounded residual on the scripted turn, rewarded 1 when every contract check passes, to be trained over belt friction from 0.15 to 0.5. At about 21 policy steps a second, 160,000 steps take about 2.1 hours on one CPU. Transfer to a real belt is untested.

Source: plan 13.3 (grip needs no exploration, bounded residual, reward equal to the success check, friction 0.15 to 0.5, about 21 policy steps per second, 160,000 steps in about 2.1 hours, sim-to-real untested).

### Foundation

On screen: "A foundation model as a base for new skills." Belt travel during inference, 22 mm for one pi0 inference on a 4090 and 96 mm for an OpenVLA-OFT chunk with three cameras; a 14 to 24 GB GPU; no success test, so the contract adds checks; small models stay at the base for legs, and this is the base worth testing for the plant's next jobs.
Scene: about 13 s. Target: 33 s

A vision-language-action model would bring manipulation before any demonstration on our product, and task switching by a sentence. Published fine-tuning for pi zero used 1 to 5 hours of demonstrations per task. One inference lets the leg move 22 millimetres, and it needs a 14 to 24 gigabyte GPU. It carries no success test, so the contract checks it from outside. For legs the small models stay at the base. For the next jobs it is worth testing.

Source: plan 13.5 and Table 13.4 (two things a VLA gives; pi0 1 to 5 hours of demonstrations per task; 22 mm on a 4090; 14 to 24 GB GPU; no success test; base worth testing for new jobs; none run).

### Hierarchy

On screen: "The whole plant as one graph of sub-goals." A skill as an option (where it may start, its policy, when it ends; Sutton, Precup and Singh, 1999); the leg and loin jobs sharing the graph with different sub-goals; "each level judges the one below by its declared outcome".
Scene: about 16 s. Target: 33 s

A skill with a contract is what hierarchical reinforcement learning calls an option: where it may start, its policy, and when it ends. Stacked, the plant is one graph of sub-goals. The leg and loin jobs share the graph with different sub-goals, and each level judges the one below by its declared outcome. Composing goals is exact only under deterministic dynamics, which a wet leg on a belt is not, so the saw measures the rest.

Source: plan 13.7 (option, Sutton, Precup and Singh 1999; loin changes the sub-goals; judged by outcome); Table 4.2 and 4.1 (exact only under deterministic dynamics; a wet leg is not).

## 8. Transfer

### Transfer

On screen: "The second cell runs the same chain." The leg becomes a loin, "The skills took new targets. The piece and the gripper changed."; 164 to 211 mm against the 180 mm jaws, "Refused, all 80 runs"; run two with a wider jaw, 20 of 20 on both arms near square, 4 and 10 of 20 at any heading, the far-rail note and the placeholder note.
Scene: about 26 s. Target: 35 s

The loin puller infeed runs the same chain with new targets. In run one the loin was 164 to 211 millimetres across, the jaws open 180, and the fit check refused all 80 grasps before the arm moved. With a wider placeholder jaw, force and mass unverified, loins arriving near square went 20 of 20 on both arms. At any heading it was 4 and 10 of 20, because past 40 degrees of turn the loin's ends hit the far rail.

Source: plan 14.6 (run one, 164 to 211 mm, 180 mm jaw, refused; run two, placeholder jaw unverified, 20 of 20 square, 4 and 10 of 20 any heading, ends sweep into the far rail, a layout or planning fix); loin-infeed-transfer record, Results (80 episodes refused; losses on pieces more than 40 degrees off).

### LoinTransfer

On screen: "The leg cell's turn skill on a loin." UR20, wide-jaw placeholder, camera tracking the piece: gripped at its centre of gravity, turned, set with the bone edge 0.2 mm from the datum at 0.4°.
Scene: about 10 s. Target: 8 s

The same turn skill on a loin, gripped at its centre of gravity and set against the datum.

Source: plan 14.6, Video 14.6.

## 9. Numbers

### AnyHeading

On screen: "Any orientation, approach B, UR20, tool vertical." All 20 legs at double speed, each arriving at a different heading and turned up to 180°.
Scene: about 20 s. Target: 9 s

Back to legs: all 20 of the any-heading set on the UR20, at double speed. 17 of them cut within tolerance.

Source: plan 11.6, Video 11.6; section 12 (17 of 20).

### Numbers

On screen: "220 runs in simulation, 20 legs a condition, judged by the saw." Bars for A and B on both arms; the UR20's misses at the rigid hold-down; 10 of the SR-20iA's 11 misses at any heading on reach; the pass definition, both tolerances assumed.
Scene: about 10 s. Target: 44 s

220 runs, judged by the saw. At any heading the UR20 gets 17 of 20 turning and 16 carrying, and the SCARA 9 either way. Ten of the SCARA's 11 misses are reach: a half turn sets the leg down 1.1 to 1.3 metres past the pick, beyond its 1.1 metre reach. So the pilot is six-axis. The UR20's misses are mostly cut angles from the rigid hold-down model. A pass is within 10 millimetres of the hock and 5 degrees of square, both assumed. From the camera, three legs scored 0 of 3, so a landmark method for the hock comes next.

Source: plan Table 11.7 (220 episodes; any set UR20 17 and 16, SR-20iA 9 and 9); 7.1, "The answer" (10 losses on reach, 1.1 to 1.3 m, 1.1 m reach, six-axis); 11.6 (hold-down lead-in; camera run 0 of 3; landmark method); section 1 (tolerances assumed).
