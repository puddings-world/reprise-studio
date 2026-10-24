import { color } from '@/theme/tokens';
import type { Palette } from '@/engine/types';

/**
 * 一葷一素 — 「半夜對著空椅子」frame.
 *
 * Warm-dominant throughout. Chorus is warmer than verse but in a
 * candle-light way, not bright celebration. Critical departure from the
 * default `ache`: this song's "ache" is 月光 + 蒸氣 + 思念, not wound /
 * blood. Use sun + paper (gold light meeting steam), never wound.
 *
 * Active moods: still (intro / solo), soft (verse), ache (chorus), fin (outro).
 * defy / open kept as warm-leaning fallbacks.
 */
export const yiHunYiSuPalette: Palette = {
  // intro / solo — 暗木桌、燈未亮、夜風吹過
  still: { primary: color.ink,   accent: color.warm,  mood: 'still' },

  // verse — 暖光剛點起，木桌紋理浮現
  soft:  { primary: color.warm,  accent: color.paper, mood: 'soft'  },

  // chorus「月兒明 風兒輕」— 月光金、蒸氣紙白
  // NOT wound, NOT blush. 這場戲沒有血色，只有思念。
  ache:  { primary: color.sun,   accent: color.paper, mood: 'ache'  },

  // outro — 燈漸熄，木桌留下
  fin:   { primary: color.warm,  accent: color.ink,   mood: 'fin'   },

  // unused — warm-leaning fallbacks
  open:  { primary: color.sun,   accent: color.warm,  mood: 'open'  },
  defy:  { primary: color.warm,  accent: color.sun,   mood: 'defy'  },
};
