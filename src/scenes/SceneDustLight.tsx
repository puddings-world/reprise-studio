import { useMemo } from 'react';
import type { SceneProps } from '@/engine/types';
import { tokens } from '@/theme/tokens';
import { BaseScene } from './_BaseScene';
import styles from './SceneDustLight.module.css';

/**
 * SceneDustLight — 「廢棄琴房裡的一道斜光」
 *
 * Visualizes the pre_chorus / chorus1 / bridge / chorus_last of
 * 不能說的秘密. A single diagonal sepia beam falls across an abandoned
 * piano room; suspended dust motes drift slowly inside the beam while
 * the rest of the frame is washed in warm vignette. Time is held still.
 *
 * Pattern follows SceneNameless: every visual constant flows through
 * CSS custom properties set on a wrapper from React; the CSS module
 * derives tints via `color-mix()` from those vars. No literal hex / rgba.
 *
 * Imagery (per brief & docs/DESIGN.md):
 *   1. Diagonal beam — a single shaft of warm light, top-left to bottom-right
 *   2. Dust motes — 16 hand-authored points that drift only within the beam
 *   3. Sepia vignette — warm-leaning radial glow + edge darken
 *
 * Palette uses only `wound` / `paper` / `warm` — explicitly NO `cold`,
 * NO `sun`. No piano keys (avoided literalism per brief §6).
 */
export function SceneDustLight({ energy, palette }: SceneProps) {
  // Beam alpha breathes with energy: 0.5 → 0.75 between quiet and peak.
  const beamAlpha = 0.5 + energy * 0.25;

  // Dust visibility scales with energy too — quiet verses leave them
  // ghostly, choruses bring them just-visible.
  const dustVisibility = 0.6 + energy * 0.3;

  // Drift speed multiplier: brief says `1 + energy * 0.4`. We invert it
  // when feeding `animation-duration` (faster speed → shorter duration),
  // hence dividing 1 by the multiplier in the var.
  const dustDriftSpeedMul = 1 + energy * 0.4;
  const dustDurationScale = 1 / dustDriftSpeedMul;

  // Brightness curve (per brief §4).
  const sceneBrightness = 0.5 + energy * 0.2;

  const cssVars = useMemo(
    () =>
      ({
        '--scene-primary': palette.primary,
        '--scene-accent': palette.accent,
        '--scene-ink': tokens.color.ink,
        '--scene-paper': tokens.color.paper,
        '--scene-warm': tokens.color.warm,
        '--scene-wound': tokens.color.wound,
        '--scene-brightness': sceneBrightness,
        '--scene-vignette': tokens.layout.vignetteIntensity,
        '--scene-beam-alpha': beamAlpha,
        '--scene-dust-visibility': dustVisibility,
        '--scene-dust-duration-scale': dustDurationScale,
      }) as React.CSSProperties,
    [
      palette.primary,
      palette.accent,
      sceneBrightness,
      beamAlpha,
      dustVisibility,
      dustDurationScale,
    ],
  );

  // 16 dust motes — count is fixed at component level so React never
  // re-randomizes between renders. Positions, drift delays, and per-mote
  // durations live in the CSS module via :nth-child rules.
  const motes = Array.from({ length: 16 });

  return (
    <BaseScene id="dust-light">
      <div className={styles.scene} style={cssVars}>
        <div className={styles.background} aria-hidden />
        {/* The beam itself — alpha breathes, no translate. */}
        <div className={styles.beam} aria-hidden />
        {/*
          Dust field is rotated to match the beam, then masked with a
          horizontal gradient so motes are only visible along the central
          strip of the rotated coordinate space (i.e. inside the beam).
          Each mote rides its own slow translate keyframe (period 5–9s).
        */}
        <div className={styles.dustField} aria-hidden>
          {motes.map((_, i) => (
            <span key={i} className={styles.mote} />
          ))}
        </div>
        <div className={styles.vignette} aria-hidden />
      </div>
    </BaseScene>
  );
}
