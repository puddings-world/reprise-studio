import { useMemo } from 'react';
import type { SceneProps } from '@/engine/types';
import { tokens } from '@/theme/tokens';
import { BaseScene } from './_BaseScene';
import styles from './SceneDefyLines.module.css';

/**
 * SceneDefyLines — 「逆風衝刺」
 *
 * Carries every voiced section of 倔強 (pre_chorus / chorus1 / chorus2 /
 * verse2 / bridge / chorus_last). Imagery: diagonal speed lines streaking
 * from lower-right to upper-left across an ink field, a low horizon glow
 * implying the direction being charged toward, and sparse drifting dust
 * motes. Palette is sun-on-ink (defy) or sun/warm (open) — never cold,
 * never wound.
 *
 * Pattern follows SceneNameless: every visual constant flows through CSS
 * custom properties set on a wrapper from React; the CSS module derives
 * tints via `color-mix()` from those vars. No literal hex / rgba.
 *
 * Energy bindings (per brief):
 *   - lineCount      = floor(4 + sectionEnergy * 3)   in [4, 7]
 *                      Discretized per section — recomputed only when the
 *                      section's `t` (boundary) changes, not per frame.
 *   - lineSpeedMul   = 1 + energy * 0.8               drives keyframe distance
 *   - horizonAlpha   = 0.3 + energy * 0.4
 *   - brightness     = 0.7 + energy * 0.25
 *
 * Notes:
 *   - Speed lines run with `animation-duration` between ~1.5s and ~3s,
 *     staggered via `animation-delay`. The AGENT_PROTOCOL §二 invariant on
 *     ≥3s loops is for ambient motion; speed lines here are cue-driven
 *     streaks and the brief explicitly carves out this exception. Density
 *     comes from stagger, not from going faster.
 *   - Horizon glow and dust motes stay ≥ 3s.
 */
export function SceneDefyLines({ energy, section, palette }: SceneProps) {
  // Discretized line count — only changes when the section boundary changes.
  // Using `section.t` as the dependency key gives us a stable value within a
  // section (no per-frame recalculation despite `energy` updating constantly).
  const lineCount = useMemo(() => {
    // sectionEnergy approximated by energy at section-entry — clamped 0..1
    // just in case the analyser hasn't warmed up yet.
    const sectionEnergy = Math.max(0, Math.min(1, energy));
    return Math.floor(4 + sectionEnergy * 3);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section.t]);

  const lineSpeedMul = 1 + energy * 0.8;
  const horizonAlpha = 0.3 + energy * 0.4;
  const sceneBrightness = 0.7 + energy * 0.25;

  const cssVars = useMemo(
    () =>
      ({
        '--scene-primary': palette.primary,
        '--scene-accent': palette.accent,
        '--scene-ink': tokens.color.ink,
        '--scene-brightness': sceneBrightness,
        '--scene-vignette': tokens.layout.vignetteIntensity,
        '--scene-line-speed-mul': lineSpeedMul,
        '--scene-horizon-alpha': horizonAlpha,
      }) as React.CSSProperties,
    [palette.primary, palette.accent, sceneBrightness, lineSpeedMul, horizonAlpha],
  );

  // Pre-computed per-line stagger / variation. Index-derived so deterministic
  // across renders, but the visual feel is "hand-thrown" rather than gridded.
  // Each line gets:
  //   - a vertical offset on its starting band (`--line-y`)
  //   - a duration in [1.5s, 3.0s] scaled inversely by lineSpeedMul (faster
  //     when energy is high), produced from a fixed base sequence so we don't
  //     drift toward "one tempo per render"
  //   - an entry delay so streaks arrive out of phase
  const lines = useMemo(() => {
    // Fixed base durations (seconds) — covers the 1.5–3s envelope without
    // a magic-number cluster: small irrational-ish deltas keep streaks from
    // ever realigning, which is what would read as "industrial bar".
    const baseDurations = [2.6, 1.8, 2.9, 1.6, 2.4, 2.1, 1.9];
    const baseDelays = [0, 0.45, 1.1, 0.7, 1.55, 0.25, 1.85];
    const baseYs = [12, 28, 44, 60, 76, 20, 52]; // % of viewport, starting band

    return Array.from({ length: lineCount }, (_, i) => ({
      duration: baseDurations[i % baseDurations.length],
      delay: baseDelays[i % baseDelays.length],
      y: baseYs[i % baseYs.length],
    }));
  }, [lineCount]);

  return (
    <BaseScene id="defy-lines">
      <div className={styles.scene} style={cssVars}>
        <div className={styles.background} aria-hidden />
        <div className={styles.horizon} aria-hidden />
        <div className={styles.lines} aria-hidden>
          {lines.map((ln, i) => (
            <span
              key={i}
              className={styles.line}
              style={
                {
                  '--line-duration': `${ln.duration}s`,
                  '--line-delay': `${ln.delay}s`,
                  '--line-y': `${ln.y}%`,
                } as React.CSSProperties
              }
            />
          ))}
        </div>
        {/*
         * Sparse dust motes — drifting along the streak axis. Always 8,
         * positioned via per-element CSS vars; loop period ≥ 3s.
         */}
        <div className={styles.dust} aria-hidden>
          {DUST_MOTES.map((m, i) => (
            <span
              key={i}
              className={styles.mote}
              style={
                {
                  '--mote-x': `${m.x}%`,
                  '--mote-y': `${m.y}%`,
                  '--mote-duration': `${m.duration}s`,
                  '--mote-delay': `${m.delay}s`,
                } as React.CSSProperties
              }
            />
          ))}
        </div>
        <div className={styles.vignette} aria-hidden />
      </div>
    </BaseScene>
  );
}

// Static dust mote layout — fixed seed so renders are deterministic and the
// "where are the bright specks" question doesn't shift between frames. All
// durations ≥ 3s per AGENT_PROTOCOL §二 invariant on ambient loops.
const DUST_MOTES = [
  { x: 18, y: 32, duration: 5.4, delay: 0.0 },
  { x: 72, y: 18, duration: 6.8, delay: 1.2 },
  { x: 41, y: 64, duration: 4.6, delay: 0.5 },
  { x: 88, y: 48, duration: 7.2, delay: 2.1 },
  { x: 26, y: 76, duration: 5.9, delay: 1.7 },
  { x: 63, y: 28, duration: 6.3, delay: 0.3 },
  { x: 52, y: 56, duration: 4.2, delay: 2.8 },
  { x: 10, y: 50, duration: 5.7, delay: 1.4 },
];
