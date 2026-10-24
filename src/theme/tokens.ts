/**
 * Design tokens — single source of truth for visual constants.
 *
 * Anything hardcoded in a scene is a bug. Add a token here first, then
 * reference it from the scene. See docs/DESIGN.md for the philosophy.
 */

export const color = {
  ink: '#0b0f14',
  paper: '#f5efe3',
  mist: '#dce4ea',
  cold: '#6b8ca8',
  warm: '#f2a65a',
  sun: '#ffd27d',
  blush: '#e8b8a0',
  wound: '#3a1e24',
} as const;

export const motion = {
  sceneTransition: 2.0,
  // Lyric crossfade — kept SHORT because lines come 2-5s apart in pop;
  // anything ≥1s makes the lyric chronically lag the vocal.
  lyricFadeIn: 0.35,
  lyricFadeOut: 0.25,
  cueFlashIn: 0.15,
  cueFlashOut: 0.6,
  paletteShift: 5.0,
  breathPeriod: 5.0,
} as const;

export const easing = {
  lyricIn: [0.2, 0.7, 0.2, 1] as const,
  lyricOut: [0.4, 0, 0.6, 1] as const,
  sceneCross: [0.4, 0, 0.2, 1] as const,
} as const;

export const typography = {
  lyricMain: {
    fontFamily: '"Noto Serif TC", serif',
    weight: 400,
    sizeClamp: 'clamp(28px, 4.2vw, 56px)',
    lineHeight: 1.9,
    letterSpacing: '0.1em',
  },
  lyricEmphasis: {
    fontFamily: '"Noto Serif TC", serif',
    weight: 600,
    letterSpacing: '0.12em',
  },
  subtitle: {
    fontFamily: '"Cormorant Garamond", serif',
    weight: 300,
    fontStyle: 'italic',
    sizeClamp: 'clamp(14px, 1.4vw, 20px)',
  },
} as const;

export const layout = {
  lyricSafeBottom: '18vh',
  lyricMaxWidth: '70ch',
  vignetteIntensity: 0.35,
  grainOpacity: 0.06,
} as const;

export const tokens = {
  color,
  motion,
  easing,
  typography,
  layout,
} as const;

export type Tokens = typeof tokens;
