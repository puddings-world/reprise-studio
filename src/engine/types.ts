/**
 * Core data types for the timeline-driven MV engine.
 *
 * Timeline JSON is the single source of truth. Scenes consume these
 * types only — they never read raw JSON.
 */

export type SectionType =
  | 'intro'
  | 'verse1'
  | 'verse2'
  | 'verse3'
  | 'pre_chorus'
  | 'chorus1'
  | 'chorus2'
  | 'chorus_last'
  | 'bridge'
  | 'solo'
  | 'outro';

export type Mood =
  | 'still'
  | 'soft'
  | 'ache'
  | 'open'
  | 'defy'
  | 'fin';

export type CueType =
  | 'flash-warm'
  | 'flash-cold'
  | 'color-flip'
  | 'shake-subtle'
  | 'iris-open'
  | 'iris-close'
  | 'static-burst';

export interface TimelineMeta {
  song_id: string;
  title: string;
  artist: string;
  duration: number;
  bpm: number;
  key: string;
  created_at: string;
  version: number;
  /** Provenance of the timeline data (written by the intake adapter). */
  source?: {
    dataset: string;
    youtube_url?: string;
    lyricist?: string;
    composer?: string;
    album?: string;
  };
  /**
   * Intake alignment-doctor result: vocal onset (from the dataset's vocals
   * stem) vs the first lyric timestamp. `warn` means the first lyric line
   * PRECEDES the vocal onset beyond the dataset gate's 0.5s tolerance —
   * fix upstream in MandpopDataPipeline, never by editing timestamps here.
   * (Vocals starting before the first lyric line is normal: hums/adlibs.)
   */
  alignment?: {
    vocal_onset_sec?: number;
    first_lyric_sec?: number;
    delta_sec?: number;
    verdict: 'ok' | 'warn' | 'skipped';
  };
}

export interface Section {
  t: number;
  end: number;
  type: SectionType;
  mood: Mood;
}

export interface TimelineEntry {
  t: number;
  end: number;
  text: string;
  emphasis?: string[];
  text_en?: string;
  text_romaji?: string;
}

export interface Cue {
  t: number;
  type: CueType;
  label?: string;
}

export interface Timeline {
  meta: TimelineMeta;
  sections: Section[];
  lyrics: TimelineEntry[];
  cues: Cue[];
  beats?: number[];
}

export interface PaletteEntry {
  primary: string;
  accent: string;
  mood: Mood;
}

export type Palette = Record<Mood, PaletteEntry>;

export interface SongConfig {
  songId: string;
  /**
   * Primary audio for design preview. Defaults to the original recording
   * (vocals + instrumental) so the designer can hear the song while
   * iterating on visuals.
   */
  audioSrc: string;
  /**
   * Optional instrumental-only track (AAC m4a from MandpopDataset).
   * Toggled on when the user wants to record their cover over the MV.
   */
  audioInstrumentalSrc?: string;
  timelineSrc: string;
  palette: Palette;
  sceneMap: Partial<Record<SectionType, string>>;
  /**
   * Static offset (in seconds) added to `audio.currentTime` when looking
   * up timeline events. MandpopDataset's alignment gate guarantees ≤ 0.5s
   * accuracy, so for most songs this stays 0. Use the live-nudge in the
   * scrubber only as a tie-breaker, then commit the value here.
   */
  lyricOffsetSec?: number;
}

export interface SceneProps {
  progress: number;
  energy: number;
  section: Section;
  palette: PaletteEntry;
  lyric: TimelineEntry | null;
  /**
   * Absolute timeline time in seconds (already offset-adjusted). Optional so
   * existing scenes need not consume it, but scenes with ambient motion should
   * derive it from here rather than CSS `@keyframes` / Motion transitions:
   * those run on the browser's wall-clock and freeze under Remotion's
   * frame-by-frame render. Reading `timeSec` keeps a scene deterministic in
   * both the live preview and the MP4 export.
   */
  timeSec?: number;
}
