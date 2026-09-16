import {Freeze, OffthreadVideo, staticFile, useCurrentFrame} from 'remotion';
import {RULE} from './theme';

export type Source = {
  file: string;
  width: number;
  height: number;
  /**
   * Source rows hidden at the top. The simulator burns a text band into its clips that is
   * unreadable at card size, and the card's own caption carries that information instead.
   */
  cropTop?: number;
  /** Source rows hidden at the bottom, for figures that also carry a readout strip there. */
  cropBottom?: number;
  /** Composition frames of footage to show, after trimming and speed-up. */
  frames: number;
  trimBeforeFrames?: number;
  playbackRate?: number;
};

/** The source's visible size once the burned-in band is removed. */
export const visibleSize = (source: Source) => ({width: source.width, height: source.height - (source.cropTop ?? 0) - (source.cropBottom ?? 0)});

type Props = {source: Source; width: number; height: number};

/**
 * A clip shown at `width` x `height` (its visible, cropped size) inside a thin rule. When the card
 * outlasts the clip, the clip holds a frame two frames before its end, because the decoder can
 * return nothing on the very last one.
 */
export const FramedClip: React.FC<Props> = ({source, width, height}) => {
  const frame = useCurrentFrame();
  const scale = width / source.width;
  const holdFrom = Math.max(0, source.frames - 2);
  return (
    <div style={{width, height, outline: `2px solid ${RULE}`, overflow: 'hidden', position: 'relative'}}>
      <Freeze frame={holdFrom} active={frame >= holdFrom}>
        <OffthreadVideo
          src={staticFile(source.file)}
          trimBefore={source.trimBeforeFrames}
          playbackRate={source.playbackRate ?? 1}
          muted
          style={{
            position: 'absolute',
            top: -(source.cropTop ?? 0) * scale,
            left: 0,
            width,
            height: source.height * scale,
            display: 'block',
          }}
        />
      </Freeze>
    </div>
  );
};
