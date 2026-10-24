import { useState, type ComponentType } from 'react';
import { AnimatePresence } from 'motion/react';
import type { SceneProps, SongConfig, Timeline } from './types';
import { useTimeline } from './useTimeline';
import { SceneRouter } from './SceneRouter';
import { LyricLayer } from '@/layers/LyricLayer';
import { CueFlashLayer } from '@/layers/CueFlashLayer';
import { GrainLayer } from '@/layers/GrainLayer';
import { TimeScrubber } from '@/layers/TimeScrubber';
import { SongSwitcher } from '@/layers/SongSwitcher';
import { LyricInspector } from '@/layers/LyricInspector';
import type { Clock } from './clock';

export type PlayerMode = 'audio' | 'scrubber';

interface PlayerProps {
  config: SongConfig;
  timeline: Timeline;
  sceneRegistry: Record<string, ComponentType<SceneProps>>;
  clock: Clock;
  energy: number;
  mode: PlayerMode;
}

/**
 * Top-level orchestrator: clock + timeline → scene + lyric + cue + grain.
 *
 * `clock` is shape-compatible with both `useAudioClock` (real audio) and
 * `useScrubber` (dev). The Player itself doesn't care which.
 *
 * `offsetSec` shifts where in the timeline we look up events relative to
 * audio time. Useful when the LRC was timed against a different recording
 * than the one playing (common with karaoke covers). Live-nudgeable from
 * the scrubber overlay; user copies the locked-in value into config.ts
 * once it sounds right.
 */
export function Player({ config, timeline, sceneRegistry, clock, energy, mode }: PlayerProps) {
  const [offsetSec, setOffsetSec] = useState(config.lyricOffsetSec ?? 0);
  const adjusted = clock.currentTime + offsetSec;
  const { currentLyric, currentSection, recentCue } = useTimeline(adjusted, timeline);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <AnimatePresence mode="wait">
        <SceneRouter
          key={currentSection?.type ?? 'none'}
          config={config}
          sceneRegistry={sceneRegistry}
          section={currentSection}
          lyric={currentLyric}
          energy={energy}
          currentTime={adjusted}
        />
      </AnimatePresence>

      <GrainLayer />
      <CueFlashLayer recentCue={recentCue} currentTime={adjusted} />
      <LyricLayer lyric={currentLyric} />
      <SongSwitcher currentSongId={config.songId} />
      <LyricInspector
        lyrics={timeline.lyrics}
        currentTime={clock.currentTime}
        offsetSec={offsetSec}
        onOffsetChange={setOffsetSec}
        onSeek={clock.seek}
      />
      <TimeScrubber
        clock={clock}
        sections={timeline.sections}
        currentSectionType={currentSection?.type}
        mode={mode}
        offsetSec={offsetSec}
        onOffsetChange={setOffsetSec}
      />
    </div>
  );
}
