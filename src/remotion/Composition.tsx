import {
  AbsoluteFill,
  Audio,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { SceneSilenceView } from '@/scenes/SceneSilence';
import { tokens } from '@/theme/tokens';
import { yiZhiHenAnJingPalette } from '@/theme/palettes/yi-zhi-hen-an-jing';
import type { Mood } from '@/engine/types';
import timeline from '@data/songs/yi-zhi-hen-an-jing/timeline.json';
import energyCurve from '@data/songs/yi-zhi-hen-an-jing/energy.json';

/**
 * Phase 4 PoC composition.
 *
 * Proves the full frame-based export path end-to-end on ONE scene
 * (SceneSilenceView) and ONE song (一直很安靜): timeline lookup → scene +
 * lyric, all driven by `useCurrentFrame()` (deterministic), with the audio
 * track muxed in for sync verification.
 *
 * Deliberately NOT reused from Player here: Player wraps scenes in BaseScene
 * and LyricLayer, both of which animate via Motion's wall-clock `initial →
 * animate`, which freezes under Remotion. The fades below are frame-based
 * (`interpolate`) replacements. Generalizing this to all scenes + the full
 * Player is the decision the PoC informs.
 */
export type LyricMVProps = {
  /** Where in the song this PoC window begins (seconds). */
  startSec: number;
};

interface EnergyCurve {
  rate: number;
  values: number[];
}

/**
 * Sample the intake-precomputed RMS curve at time `t`, smoothed with a
 * ±0.3s box filter so scene breathing follows musical dynamics rather than
 * per-window jitter (the live path gets similar smoothing from its
 * AnalyserNode low-pass). Pure function of (curve, t) → deterministic frames.
 */
function sampleEnergy(curve: EnergyCurve, t: number): number {
  const half = Math.round(curve.rate * 0.3);
  const center = t * curve.rate;
  const from = Math.floor(center - half);
  const to = Math.floor(center + half);
  let sum = 0;
  let n = 0;
  for (let i = from; i <= to; i += 1) {
    const clamped = Math.max(0, Math.min(curve.values.length - 1, i));
    sum += curve.values[clamped];
    n += 1;
  }
  return n > 0 ? sum / n : 0;
}

export function LyricMV({ startSec }: LyricMVProps) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const time = startSec + frame / fps;

  const section =
    timeline.sections.find((s) => time >= s.t && time < s.end) ??
    timeline.sections[timeline.sections.length - 1];
  const palette = yiZhiHenAnJingPalette[section.mood as Mood];

  const lyric =
    timeline.lyrics.find((l) => time >= l.t && time < l.end && l.text.trim() !== '') ?? null;

  // Real offline energy: 20 Hz RMS curve precomputed at intake from the same
  // audio the preview plays (data/songs/<id>/energy.json). Deterministic per
  // frame — no live AnalyserNode needed.
  const energy = sampleEnergy(energyCurve, time);

  // Scene fade-in over the first second (Remotion-native, replaces BaseScene).
  const sceneOpacity = interpolate(frame, [0, fps], [0, 1], { extrapolateRight: 'clamp' });

  // Lyric fade in/out, replacing LyricLayer's Motion transition.
  let lyricOpacity = 0;
  let lyricY = 12;
  if (lyric) {
    const fadeIn = Math.min(1, (time - lyric.t) / tokens.motion.lyricFadeIn);
    const fadeOut = Math.min(1, (lyric.end - time) / tokens.motion.lyricFadeOut);
    lyricOpacity = Math.max(0, Math.min(fadeIn, fadeOut));
    lyricY = interpolate(fadeIn, [0, 1], [12, 0]);
  }

  return (
    <AbsoluteFill style={{ backgroundColor: tokens.color.ink }}>
      <div style={{ position: 'absolute', inset: 0, opacity: sceneOpacity }}>
        <SceneSilenceView timeSec={time} energy={energy} palette={palette} />
      </div>

      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: tokens.layout.lyricSafeBottom,
          display: 'flex',
          justifyContent: 'center',
        }}
      >
        {lyric && (
          <div
            style={{
              opacity: lyricOpacity,
              transform: `translateY(${lyricY}px)`,
              fontFamily: tokens.typography.lyricMain.fontFamily,
              fontWeight: tokens.typography.lyricMain.weight,
              fontSize: tokens.typography.lyricMain.sizeClamp,
              lineHeight: tokens.typography.lyricMain.lineHeight,
              letterSpacing: tokens.typography.lyricMain.letterSpacing,
              color: tokens.color.paper,
              maxWidth: tokens.layout.lyricMaxWidth,
              textAlign: 'center',
              textShadow: '0 2px 18px rgba(0,0,0,0.45)',
            }}
          >
            {lyric.text}
          </div>
        )}
      </div>

      <Audio src={staticFile('audio/yi-zhi-hen-an-jing.mp3')} startFrom={Math.round(startSec * fps)} />
    </AbsoluteFill>
  );
}
