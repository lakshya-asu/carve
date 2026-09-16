import type {CardProps} from './Card';
import type {Source} from './FramedClip';
import {FPS} from './theme';

/** A source clip by its frame count and rate as probed, converted to composition frames. */
const clip = (file: string, width: number, height: number, srcFrames: number, srcFps: number, cropTop: number): Source => ({
  file,
  width,
  height,
  cropTop,
  frames: Math.round((srcFrames / srcFps) * FPS),
});

// Height in source rows of the text band each renderer burns into the top of its clips, read off
// frames with the most text lines showing. Figure panels have a label strip on top and some a
// readout strip below; simulator clips have three to eight lines of test log laid over the scene.
const BAND = {
  depthCameras: 32,
  legSegmentation: 31,
  centreOfGravity: 36,
  realFootage: 28,
  legSegmentationReadout: 36,
  centreOfGravityReadout: 38,
  gripperAlone: 84,
  shankTest: 156,
  trotterTest: 208,
  reach: 108,
  approach: 84,
};

const ANY_HEADING_SECONDS = 40;
const anyHeading: Source = {
  ...clip('approach-b-ur20-tilt0-any.mp4', 960, 540, 5568, 25, BAND.approach),
  frames: (ANY_HEADING_SECONDS * FPS) / 2,
  playbackRate: 2,
};

// Headings and captions are cut down from the figure captions in plan/leg-cell-plan.html.
export const CARDS: Record<string, CardProps> = {
  CameraFeed: {
    heading: 'Two depth cameras, one leg.',
    caption: [
      ['Gemini 335L on top, D455 below: colour with the true outline, height above the belt,'],
      ["and the error against the simulator's exact depth, at three arrival angles."],
    ],
    clips: [{source: clip('depth-cameras.mp4', 1920, 944, 255, 30, BAND.depthCameras)}],
  },
  Segmentation: {
    heading: 'Finding the leg by height.',
    caption: [
      ['The geometric segmenter on simulated legs: the found outline against the true one,'],
      ['the height it reads, and matched, extra and missed pixels. ', {warn: 'Datasheet noise, no edge effects.'}],
    ],
    clips: [{source: {...clip('leg-segmentation.mp4', 1920, 466, 357, 30, BAND.legSegmentation), cropBottom: BAND.legSegmentationReadout}}],
  },
  RealFootageSegmentation: {
    heading: 'Real footage, all 21 frames.',
    caption: [['Two per second: the frame, the colour rule, and Segment Anything plus the colour rule.']],
    clips: [{source: clip('real-footage-segmentation.mp4', 1080, 640, 21, 2, BAND.realFootage)}],
  },
  CentreOfGravityClip: {
    heading: 'Where the mass is.',
    caption: [
      ['Three legs through the camera model with edge effects. White cross: centre of mass.'],
      ['Orange: outline centre. Green: column centroid.'],

    ],
    clips: [{source: {...clip('centre-of-gravity.mp4', 1920, 672, 357, 30, BAND.centreOfGravity), cropBottom: BAND.centreOfGravityReadout}}],
  },
  GripperAlone: {
    heading: 'Jaw gripper, three-finger gripper, on their own.',
    caption: [
      ['Jaw: ', {blue: 'held to 918 N'}, ' against the 720 N it needed.'],
      ['Three-finger: ', {blue: 'held to 229 N'}, ' against the 180 N it needed.'],
    ],
    clips: [
      {source: clip('05-gripper-jaw-alone.mp4', 960, 540, 199, 30, BAND.gripperAlone), label: 'jaw'},
      {source: clip('06-gripper-three-finger-alone.mp4', 960, 540, 198, 30, BAND.gripperAlone), label: 'three-finger'},
    ],
  },
  GripShank: {
    heading: 'Jaw gripper, shank from above, stopped belt.',
    caption: [
      ['UR20: ', {blue: 'success'}, ', the shank rose with the tool.'],
      ['SR-20iA: ', {blue: 'success'}, ', using a lower approach height.'],
    ],
    clips: [
      {source: clip('07-ur20-jaw-grips-the-shank-from-above.mp4', 960, 540, 228, 30, BAND.shankTest), label: 'UR20'},
      {source: clip('08-scara-jaw-grips-the-shank-from-above.mp4', 960, 540, 199, 30, BAND.shankTest), label: 'SR-20iA'},
    ],
  },
  ThreeFingerShank: {
    heading: 'Three-finger gripper, shank from above, stopped belt.',
    caption: [
      ['UR20: ', {warn: 'refused before moving'}, ', 38 mm of spare opening, 40 mm required.'],
      ['SR-20iA: ', {warn: 'refused before moving'}, ', same check.'],
    ],
    clips: [
      {source: clip('09-ur20-three-finger-tries-the-shank-from-above.mp4', 960, 540, 122, 30, BAND.shankTest), label: 'UR20'},
      {source: clip('10-scara-three-finger-tries-the-shank-from-above.mp4', 960, 540, 122, 30, BAND.shankTest), label: 'SR-20iA'},
    ],
  },
  TrotterEndOn: {
    heading: 'Three-finger gripper, trotter end-on, stopped belt.',
    caption: [
      ['UR20: ', {blue: 'success'}, ' with the tool horizontal along the leg.'],
      ['SR-20iA: ', {warn: 'refused before moving'}, ', the arm cannot tilt its tool.'],
    ],
    clips: [
      {source: clip('11-ur20-three-finger-grips-the-trotter-end-on.mp4', 960, 540, 243, 30, BAND.trotterTest), label: 'UR20'},
      {source: clip('12-scara-three-finger-tries-the-trotter-end-on.mp4', 960, 540, 122, 30, BAND.trotterTest), label: 'SR-20iA'},
    ],
  },
  Reach: {
    heading: 'Reach, tool pointing down, a leg upstream for scale.',
    caption: [
      ['UR20: ', {blue: 'all 120 grid points reached'}, ' at all three heights.'],
      ['SR-20iA: 101 of 120 at 50 and 180 mm, ', {warn: 'none at 350 mm'}, '.'],
    ],
    clips: [
      {source: clip('reach-ur20-leg.mp4', 960, 540, 534, 30, BAND.reach), label: 'UR20'},
      {source: clip('reach-scara-leg.mp4', 960, 540, 411, 30, BAND.reach), label: 'SR-20iA'},
    ],
  },
  ApproachAandB: {
    heading: 'Square set, UR20 close-up, three legs.',
    caption: [['A: shank lifted 100 mm. B: shank lifted 20 mm.']],
    clips: [
      {source: clip('approach-a-closeup-ur20-tilt0.mp4', 960, 540, 731, 25, BAND.approach), label: 'A, carried'},
      {source: clip('approach-b-closeup-ur20-tilt0.mp4', 960, 540, 759, 25, BAND.approach), label: 'B, turned'},
    ],
  },
  BestPick: {
    heading: 'Approach B on the UR20, any-orientation set.',
    caption: [['Leg 14 of 20, camera tracking the leg.']],
    clips: [{source: clip('approach-b-closeup-ur20-tilt0-any-leg13.mp4', 960, 540, 278, 25, BAND.approach)}],
  },
  AnyHeading: {
    heading: 'Any orientation, approach B, UR20, tool vertical.',
    caption: [
      ['Every leg arrives at a different heading. The arm reads the heading, grips the shank across it,'],
      ['turns the leg by whatever it needs, ', {blue: 'up to 180°'}, ', checks the result and corrects it.'],
    ],
    clips: [{source: anyHeading}],
    note: 'played at double speed',
  },
  LoinTransfer: {
    heading: "The leg cell's turn skill on a loin.",
    caption: [
      ['UR20, wide-jaw placeholder, camera tracking the piece: gripped at its centre of gravity, turned,'],
      ['set with the bone edge ', {blue: '0.2 mm from the datum at 0.4°'}, '.'],
    ],
    clips: [{source: clip('loin-approach-b-closeup-ur20-tilt0-leg0.mp4', 960, 540, 250, 25, BAND.approach)}],
  },
};

export const cardFrames = (card: CardProps): number => Math.max(...card.clips.map((c) => c.source.frames));
