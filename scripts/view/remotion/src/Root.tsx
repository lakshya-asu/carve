import {Composition} from 'remotion';
import {Card} from './Card';
import {CARDS, cardFrames} from './cards';
import {DRILL_FRAMES, DrillPanel} from './DrillPanel';
import {FPS, HEIGHT, WIDTH} from './theme';

export const Root: React.FC = () => (
  <>
    <Composition id="DrillPanel" component={DrillPanel} durationInFrames={DRILL_FRAMES} fps={FPS} width={WIDTH} height={HEIGHT} />
    {Object.entries(CARDS).map(([id, card]) => (
      <Composition
        key={id}
        id={id}
        component={Card}
        defaultProps={card}
        durationInFrames={cardFrames(card)}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
    ))}
  </>
);
