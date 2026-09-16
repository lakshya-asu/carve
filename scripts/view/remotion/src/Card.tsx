import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {FramedClip, Source, visibleSize} from './FramedClip';
import {ANNOT, BLUE, entrance, fit, FONT, HEAD, INK, INK_2, INK_3, PAPER, WARN} from './theme';

/** A caption run: plain description, a result that held (blue), or a failure or limit (warm). */
export type Run = string | {blue: string} | {warn: string};

export type CardProps = {
  heading: string;
  /** At most two lines, broken by hand so identifiers and figures never split. */
  caption: Run[][];
  clips: {source: Source; label?: string}[];
  /** A remark under the footage, right-aligned, such as a playback speed. */
  note?: string;
};

// The heading sits at a fixed top on every card. Below it, footage, labels and caption form one block
// centred in the remaining height, so short, wide clips do not leave the bottom of the frame empty.
// Footage grows to the side margins or to the height left after labels and a two-line caption.
const SIDE_MARGIN = 60;
const HEADING_TOP = 58;
const BODY_TOP = 150;
const PAIR_GAP = 48;
const LABEL_BAND = 14 + Math.ceil(ANNOT * 1.25);
const CAPTION_GAP = 26;
const CAPTION_BAND = Math.ceil(2 * ANNOT * 1.35);
const BOTTOM_MARGIN = 48;

const runStyle = (run: Run): {text: string; color: string} =>
  typeof run === 'string' ? {text: run, color: INK_2} : 'blue' in run ? {text: run.blue, color: BLUE} : {text: run.warn, color: WARN};

export const Card: React.FC<CardProps> = ({heading, caption, clips, note}) => {
  const frame = useCurrentFrame();
  const hasUnderline = clips.some((c) => c.label) || Boolean(note);
  const maxH = 1080 - BODY_TOP - CAPTION_GAP - CAPTION_BAND - BOTTOM_MARGIN - (hasUnderline ? LABEL_BAND : 0);
  const maxW = (1920 - 2 * SIDE_MARGIN - PAIR_GAP * (clips.length - 1)) / clips.length;
  // Pairs share one height so the two halves line up.
  const height = Math.min(...clips.map((c) => fit(visibleSize(c.source).width, visibleSize(c.source).height, maxW, maxH).height));

  return (
    <AbsoluteFill style={{backgroundColor: PAPER, fontFamily: FONT, color: INK}}>
      <div
        style={{
          position: 'absolute',
          top: HEADING_TOP,
          left: SIDE_MARGIN,
          right: SIDE_MARGIN,
          textAlign: 'center',
          fontSize: HEAD,
          lineHeight: 1.2,
          ...entrance(frame, 0),
        }}
      >
        {heading}
      </div>
      <div
        style={{
          position: 'absolute',
          top: BODY_TOP,
          bottom: BOTTOM_MARGIN,
          left: SIDE_MARGIN,
          right: SIDE_MARGIN,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div style={{display: 'flex', gap: PAIR_GAP, ...entrance(frame, 6)}}>
          {clips.map((c) => {
            const own = visibleSize(c.source);
            const width = Math.round((own.width * height) / own.height);
            return (
              <div key={c.source.file} style={{display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
                <FramedClip source={c.source} width={width} height={height} />
                {c.label ? (
                  <div style={{fontSize: ANNOT, color: INK_3, marginTop: 14, lineHeight: 1.25}}>{c.label}</div>
                ) : null}
                {note ? (
                  <div style={{alignSelf: 'flex-end', fontSize: ANNOT, color: INK_3, marginTop: 14, lineHeight: 1.25}}>{note}</div>
                ) : null}
              </div>
            );
          })}
        </div>
        <div
          style={{
            marginTop: CAPTION_GAP,
            textAlign: 'center',
            fontSize: ANNOT,
            lineHeight: 1.35,
            whiteSpace: 'nowrap',
            ...entrance(frame, 18),
          }}
        >
          {caption.map((line, i) => (
            <div key={i}>
              {line.map((run, j) => {
                const {text, color} = runStyle(run);
                return (
                  <span key={j} style={{color}}>
                    {text}
                  </span>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};
