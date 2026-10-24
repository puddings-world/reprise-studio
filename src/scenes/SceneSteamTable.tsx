import { useMemo } from 'react';
import type { SceneProps } from '@/engine/types';
import { tokens } from '@/theme/tokens';
import { BaseScene } from './_BaseScene';
import styles from './SceneSteamTable.module.css';

/**
 * SceneSteamTable — 「半夜對著空椅子」
 *
 * Visualizes the chorus of 一葷一素 (毛不易): 「月兒明 風兒輕 可是你在敲打
 * 我的窗欞 / 其實我過的還可以」. A late-night kitchen scene addressed to
 * someone no longer there — the force of the frame is in the absence: no
 * face, no hands, no food, no plates. Just a dark table edge, three slow
 * columns of steam rising into a low warm lamp glow.
 *
 * Pattern mirrors SceneNameless: every visual constant pushed from React
 * through CSS custom properties; CSS module derives tints via `color-mix()`.
 * No literal hex / rgba. No wound, no blush — palette stays sun + paper
 * (memory, not blood).
 *
 * Imagery (per brief):
 *   1. Table silhouette band — low dark horizontal strip at ~74% vertical
 *   2. Three steam columns — slow vertical drift, sine-wave horizontal sway
 *   3. Warm lamp glow — soft radial ellipse, upper-right, looking down
 *
 * Energy bindings:
 *   brightness         = 0.5 + energy * 0.2
 *   steam alpha        = min(0.4 + energy * 0.2, 0.6)
 *   steam rise speed   = 1 + energy * 0.3
 *   lamp glow          = 0.6 + energy * 0.15
 */
export function SceneSteamTable({ energy, palette }: SceneProps) {
  // Restrained brightness curve — memory glow, not celebration.
  const sceneBrightness = 0.5 + energy * 0.2;

  // Steam body alpha. Capped at 0.6 per brief: when the music swells the
  // steam reads more, but never becomes solid.
  const steamAlpha = Math.min(0.4 + energy * 0.2, 0.6);

  // Multiplier on the slow rise animation. The base keyframe period (in
  // CSS) is divided by this value, so energy 1.0 → 1.3× speed = ~23% shorter
  // period. Floor at 1.0 to keep the slowest end stable.
  const steamRiseSpeedMul = 1 + energy * 0.3;

  // Warm lamp halo intensity. Breathes lightly with energy.
  const lampGlow = 0.6 + energy * 0.15;

  const cssVars = useMemo(
    () =>
      ({
        '--scene-primary': palette.primary,
        '--scene-accent': palette.accent,
        '--scene-ink': tokens.color.ink,
        '--scene-paper': tokens.color.paper,
        '--scene-warm': tokens.color.warm,
        '--scene-sun': tokens.color.sun,
        '--scene-brightness': sceneBrightness,
        '--scene-vignette': tokens.layout.vignetteIntensity,
        '--scene-steam-alpha': steamAlpha,
        '--scene-steam-speed': steamRiseSpeedMul,
        '--scene-lamp-glow': lampGlow,
      }) as React.CSSProperties,
    [
      palette.primary,
      palette.accent,
      sceneBrightness,
      steamAlpha,
      steamRiseSpeedMul,
      lampGlow,
    ],
  );

  return (
    <BaseScene id="steam-table">
      <div className={styles.scene} style={cssVars}>
        <div className={styles.background} aria-hidden />
        {/*
          Warm lamp glow — upper-right ellipse, low saturation, very soft edge.
          Symbolises a kitchen lamp left on. Sits above the steam in DOM so
          its halo washes over the rising columns.
        */}
        <div className={styles.lamp} aria-hidden />
        {/*
          Three steam columns rising from the table edge. Each has its own
          rise + sway animation with staggered start (negative delays) so
          they never sync. Periods are 7s / 9s / 8s (rise) and 6s / 8s / 7s
          (sway) — all ≥ 3s per AGENT_PROTOCOL invariant 7.
        */}
        <div className={`${styles.steam} ${styles.steamA}`} aria-hidden>
          <div className={styles.steamSway}>
            <div className={styles.steamRise} />
          </div>
        </div>
        <div className={`${styles.steam} ${styles.steamB}`} aria-hidden>
          <div className={styles.steamSway}>
            <div className={styles.steamRise} />
          </div>
        </div>
        <div className={`${styles.steam} ${styles.steamC}`} aria-hidden>
          <div className={styles.steamSway}>
            <div className={styles.steamRise} />
          </div>
        </div>
        {/*
          Table silhouette band — a dark horizontal strip with feathered top
          and bottom edges. Sits above the steam so the columns appear to
          rise FROM the table, not behind it. No legs, no plates, no food.
        */}
        <div className={styles.table} aria-hidden />
        <div className={styles.vignette} aria-hidden />
      </div>
    </BaseScene>
  );
}
