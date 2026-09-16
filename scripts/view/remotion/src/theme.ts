import {loadFont} from '@remotion/fonts';
import {Easing, interpolate, staticFile} from 'remotion';

// The palette of scripts/view/deck_leg_cell.py, so footage and drawn scenes read as one talk.
export const PAPER = '#161616';
export const INK = '#E5E4E0';
export const INK_2 = '#B3B2AC';
export const INK_3 = '#84837D';
export const RULE = '#5D5C58';
export const BLUE = '#8FB0EC';
export const WARN = '#D98A6A';

export const FONT = 'B612';
export const MONO = 'B612 Mono';

// Manim's 42/30/24/20 in pixels, matched by measuring line widths on a frame of
// talk-part2-skills.mp4 against the same strings set in B612.
export const DISPLAY = 79;
export const HEAD = 56;
export const BODY = 45;
export const ANNOT = 37;

export const FPS = 60;
export const WIDTH = 1920;
export const HEIGHT = 1080;

loadFont({family: FONT, url: staticFile('B612-Regular.ttf'), weight: '400'});
loadFont({family: FONT, url: staticFile('B612-Bold.ttf'), weight: '700'});
loadFont({family: MONO, url: staticFile('B612Mono-Regular.ttf'), weight: '400'});

const ENTRANCE_FRAMES = 42;

/**
 * Style for an element entering at `start`: absent before it, then appears partly visible and
 * settles with an exponential ease-out.
 */
export const entrance = (frame: number, start: number): React.CSSProperties => {
  if (frame < start) {
    return {opacity: 0};
  }
  const t = interpolate(frame, [start, start + ENTRANCE_FRAMES], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.exp),
  });
  return {opacity: 0.25 + 0.75 * t, transform: `translateY(${(1 - t) * 14}px)`};
};

/** The largest size with the source's aspect ratio that fits inside `maxW` x `maxH`. */
export const fit = (srcW: number, srcH: number, maxW: number, maxH: number) => {
  const scale = Math.min(maxW / srcW, maxH / srcH);
  return {width: Math.round(srcW * scale), height: Math.round(srcH * scale)};
};
