import { Composition } from 'remotion';
import { LyricMV } from './Composition';

/**
 * Remotion entry. Render the PoC clip via:
 *   npm run remotion:render
 *
 * Phase 4 PoC scope: a 12s window of 一直很安靜 (starting at the first sung
 * line) on the frame-based SceneSilenceView, to validate the export path
 * before converting the remaining scenes. Final pipeline is 1080p / 60fps;
 * this runs at 30fps for faster iteration.
 */
const POC_FPS = 30;
const POC_DURATION_SEC = 12;
const POC_START_SEC = 24;

export function RemotionRoot() {
  return (
    <Composition
      id="LyricMV"
      component={LyricMV}
      durationInFrames={POC_FPS * POC_DURATION_SEC}
      fps={POC_FPS}
      width={1920}
      height={1080}
      defaultProps={{ startSec: POC_START_SEC }}
    />
  );
}
