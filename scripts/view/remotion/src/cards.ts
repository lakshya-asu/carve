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
    heading: 'Both depth cameras looking at the same leg.',
    caption: [
      ['The Gemini 335L is on top and the D455 below. Each shows colour with the true outline,'],
      ["the height it reads above the belt, and its error against the simulator's exact depth."],
    ],
    clips: [{source: clip('depth-cameras.mp4', 1920, 944, 255, 30, BAND.depthCameras)}],
  },
  Segmentation: {
    heading: 'The geometric segmenter finds the leg by its height.',
    caption: [
      ['The outline it finds is drawn against the true one, with matched, extra and missed pixels.'],
      ['This run uses datasheet noise ', {warn: 'without edge effects'}, '.'],
    ],
    clips: [{source: {...clip('leg-segmentation.mp4', 1920, 466, 357, 30, BAND.legSegmentation), cropBottom: BAND.legSegmentationReadout}}],
  },
  RealFootageSegmentation: {
    heading: 'The same idea on real plant footage.',
    caption: [['Each frame shows the original, the colour rule, and Segment Anything with the colour rule.']],
    clips: [{source: clip('real-footage-segmentation.mp4', 1080, 640, 21, 2, BAND.realFootage)}],
  },
  CentreOfGravityClip: {
    heading: 'Finding where the mass is on a moving leg.',
    caption: [
      ['The white cross is the true centre of mass, orange is the outline centre'],
      ["and green is the column centroid, with the camera's edge effects modelled."],

    ],
    clips: [{source: {...clip('centre-of-gravity.mp4', 1920, 672, 357, 30, BAND.centreOfGravity), cropBottom: BAND.centreOfGravityReadout}}],
  },
  GripperAlone: {
    heading: 'Each gripper pulled on its own.',
    caption: [
      ['The jaw ', {blue: 'held to 918 N'}, ' where it needed 720 N.'],
      ['The three-finger gripper ', {blue: 'held to 229 N'}, ' where it needed 180 N.'],
    ],
    clips: [
      {source: clip('05-gripper-jaw-alone.mp4', 960, 540, 199, 30, BAND.gripperAlone), label: 'jaw'},
      {source: clip('06-gripper-three-finger-alone.mp4', 960, 540, 198, 30, BAND.gripperAlone), label: 'three-finger'},
    ],
  },
  GripShank: {
    heading: 'The jaw gripping the shank from above on a stopped belt.',
    caption: [
      ['On the UR20 it ', {blue: 'succeeded'}, ' and the shank rose with the tool.'],
      ['On the SR-20iA it ', {blue: 'succeeded'}, ' from a lower approach height.'],
    ],
    clips: [
      {source: clip('07-ur20-jaw-grips-the-shank-from-above.mp4', 960, 540, 228, 30, BAND.shankTest), label: 'UR20'},
      {source: clip('08-scara-jaw-grips-the-shank-from-above.mp4', 960, 540, 199, 30, BAND.shankTest), label: 'SR-20iA'},
    ],
  },
  ThreeFingerShank: {
    heading: 'The three-finger gripper trying the shank from above.',
    caption: [
      ['On the UR20 it ', {warn: 'refused before moving'}, ' with 38 mm of spare opening where 40 mm is required.'],
      ['The SR-20iA ', {warn: 'refused'}, ' on the same check.'],
    ],
    clips: [
      {source: clip('09-ur20-three-finger-tries-the-shank-from-above.mp4', 960, 540, 122, 30, BAND.shankTest), label: 'UR20'},
      {source: clip('10-scara-three-finger-tries-the-shank-from-above.mp4', 960, 540, 122, 30, BAND.shankTest), label: 'SR-20iA'},
    ],
  },
  TrotterEndOn: {
    heading: 'The three-finger gripper taking the trotter end-on.',
    caption: [
      ['The UR20 ', {blue: 'succeeded'}, ' with its tool lying along the leg.'],
      ['The SR-20iA ', {warn: 'refused before moving'}, ' because it cannot tilt its tool.'],
    ],
    clips: [
      {source: clip('11-ur20-three-finger-grips-the-trotter-end-on.mp4', 960, 540, 243, 30, BAND.trotterTest), label: 'UR20'},
      {source: clip('12-scara-three-finger-tries-the-trotter-end-on.mp4', 960, 540, 122, 30, BAND.trotterTest), label: 'SR-20iA'},
    ],
  },
  Reach: {
    heading: 'How far each arm reaches with the tool pointing down.',
    caption: [
      ['The UR20 ', {blue: 'reached all 120 grid points'}, ' at all three heights.'],
      ['The SR-20iA reached 101 of 120 at 50 and 180 mm and ', {warn: 'none at 350 mm'}, '.'],
    ],
    clips: [
      {source: clip('reach-ur20-leg.mp4', 960, 540, 534, 30, BAND.reach), label: 'UR20'},
      {source: clip('reach-scara-leg.mp4', 960, 540, 411, 30, BAND.reach), label: 'SR-20iA'},
    ],
  },
  ApproachAandB: {
    heading: 'Approach A and approach B on the same three legs.',
    caption: [['A lifts the shank 100 mm and carries the leg. B lifts it 20 mm and swings it.']],
    clips: [
      {source: clip('approach-a-closeup-ur20-tilt0.mp4', 960, 540, 731, 25, BAND.approach), label: 'A'},
      {source: clip('approach-b-closeup-ur20-tilt0.mp4', 960, 540, 759, 25, BAND.approach), label: 'B'},
    ],
  },
  BestPick: {
    heading: 'A leg arriving nearly backwards, turned and cut.',
    caption: [['This is leg 14 of 20 on the UR20, with the camera following it.']],
    clips: [{source: clip('approach-b-closeup-ur20-tilt0-any-leg13.mp4', 960, 540, 278, 25, BAND.approach)}],
  },
  AnyHeading: {
    heading: 'Twenty legs arriving at any heading.',
    caption: [
      ['Every leg arrives at a different heading. The arm reads the heading, grips the shank across it,'],
      ['turns the leg by whatever it needs, ', {blue: 'up to 180°'}, ', checks the result and corrects it.'],
    ],
    clips: [{source: anyHeading}],
    note: 'played at double speed',
  },
  LoinTransfer: {
    heading: "The leg cell's turn skill working on a loin.",
    caption: [
      ['The UR20 grips the loin at its centre of gravity with a wider jaw, turns it'],
      ['and sets the bone edge ', {blue: '0.2 mm from the datum at 0.4°'}, '.'],
    ],
    clips: [{source: clip('loin-approach-b-closeup-ur20-tilt0-leg0.mp4', 960, 540, 250, 25, BAND.approach)}],
  },
};

export const cardFrames = (card: CardProps): number => Math.max(...card.clips.map((c) => c.source.frames));
