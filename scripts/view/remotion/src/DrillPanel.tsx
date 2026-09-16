import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {FramedClip, Source, visibleSize} from './FramedClip';
import {ANNOT, BLUE, entrance, fit, FONT, FPS, HEAD, INK, INK_2, PAPER} from './theme';

export const DRILL_FRAMES = 8 * FPS;

const DRILLS: {source: Source; skill: string}[] = [
  {
    source: {file: 'drill-first-touch.webm', width: 471, height: 575, frames: DRILL_FRAMES, trimBeforeFrames: 2 * FPS},
    skill: 'running and dribbling',
  },
  {
    source: {file: 'drill-close-control.webm', width: 472, height: 521, frames: DRILL_FRAMES, trimBeforeFrames: 2 * FPS},
    skill: 'dribbling',
  },
  {
    // The top 24 rows carry a text sticker from the original post.
    source: {file: 'drill-carrying.webm', width: 472, height: 521, cropTop: 24, frames: DRILL_FRAMES, trimBeforeFrames: 3 * FPS},
    skill: 'running',
  },
];

const COLUMN_W = 560;
const COLUMN_GAP = 60;
const CLIP_MAX_H = 700;

// All three share one height so the row reads as a set; each takes its own width from its aspect.
const CLIP_H = Math.min(...DRILLS.map((d) => fit(visibleSize(d.source).width, visibleSize(d.source).height, COLUMN_W, CLIP_MAX_H).height));

export const DrillPanel: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: PAPER, fontFamily: FONT, color: INK}}>
      <div style={{position: 'absolute', top: 58, width: '100%', textAlign: 'center', fontSize: HEAD, ...entrance(frame, 0)}}>
        Two drills, and a third that combines them.
      </div>
      <div
        style={{
          position: 'absolute',
          top: 160,
          width: '100%',
          height: CLIP_MAX_H,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: COLUMN_GAP,
        }}
      >
        {DRILLS.map((d, i) => {
          const size = fit(visibleSize(d.source).width, visibleSize(d.source).height, COLUMN_W, CLIP_H);
          return (
            <div key={d.skill} style={{width: COLUMN_W, display: 'flex', justifyContent: 'center', ...entrance(frame, 6 + 8 * i)}}>
              <FramedClip source={d.source} width={size.width} height={size.height} />
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', top: 160 + (CLIP_MAX_H + CLIP_H) / 2 + 24, width: '100%', display: 'flex', justifyContent: 'center', gap: COLUMN_GAP}}>
        {DRILLS.map((d, i) => (
          <div key={d.skill} style={{width: COLUMN_W, textAlign: 'center', fontSize: ANNOT, color: INK_2, ...entrance(frame, 18 + 8 * i)}}>
            {d.skill}
          </div>
        ))}
      </div>
      <div style={{position: 'absolute', top: 976, width: '100%', textAlign: 'center', fontSize: HEAD, color: BLUE, ...entrance(frame, Math.round(3.5 * FPS))}}>
        Running and dribbling are drilled apart, then together.
      </div>
    </AbsoluteFill>
  );
};
