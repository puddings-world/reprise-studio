import { color } from '@/theme/tokens';
import type { Palette } from '@/engine/types';

/**
 * 倔強 — 「逆風衝刺」frame.
 *
 * Ink-dominated background as the resistance / world; sun (gold) as the
 * defying light cutting through. chorus_last opens up to warm — 「啦啦啦
 * 大聲唱」那種共感釋放。Avoid cold tones entirely; the cold here would
 * read as resignation, the opposite of the song's stance.
 *
 * Active moods: still (intro), defy (verse / pre_chorus / chorus1 / chorus2 /
 * verse2 / bridge), open (chorus_last), fin (outro).
 * ache / soft kept as ink-leaning fallbacks.
 */
export const jueJiangPalette: Palette = {
  // intro — 黑底、電吉他暗光蓄勢
  still: { primary: color.ink,   accent: color.cold,  mood: 'still' },

  // verse / chorus / bridge — 倔強的金光衝破黑色
  defy:  { primary: color.ink,   accent: color.sun,   mood: 'defy'  },

  // chorus_last — 「啦啦啦」共感、邊界打開
  open:  { primary: color.sun,   accent: color.warm,  mood: 'open'  },

  // outro — 漸漸收回，餘溫
  fin:   { primary: color.warm,  accent: color.ink,   mood: 'fin'   },

  // unused — ink-leaning fallbacks
  soft:  { primary: color.ink,   accent: color.warm,  mood: 'soft'  },
  ache:  { primary: color.ink,   accent: color.warm,  mood: 'ache'  },
};
