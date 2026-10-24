import { color } from '@/theme/tokens';
import type { Palette } from '@/engine/types';

/**
 * 不能說的秘密 — 「廢棄琴房的斜光」frame.
 *
 * Sepia-dominant — yellowed photograph mood. paper + warm + wound mix to
 * give a darkroom feel. Avoid bright sun (too celebratory) and any cold
 * tone (this song is suspended in warm time, not chilled by it).
 *
 * Active moods: still (intro / solo), soft (verse), ache (pre_chorus /
 * chorus1 / bridge), open (chorus_last), fin (outro).
 * defy kept as sepia-leaning fallback.
 */
export const buNengShuoDeMiMiPalette: Palette = {
  // intro / solo — 暗室、光柱微微亮起
  still: { primary: color.ink,   accent: color.warm,  mood: 'still' },

  // verse「冷咖啡離開了杯墊」— 泛黃桌面、斜光落下
  soft:  { primary: color.wound, accent: color.blush, mood: 'soft'  },

  // pre_chorus / bridge — 記憶湧現、時間慢動作
  ache:  { primary: color.wound, accent: color.warm,  mood: 'ache'  },

  // chorus_last「飄落後才發現」— 紙頁泛白、最後一次抓住
  open:  { primary: color.paper, accent: color.warm,  mood: 'open'  },

  // outro — 慢慢收暗
  fin:   { primary: color.wound, accent: color.paper, mood: 'fin'   },

  // unused — sepia-leaning fallback
  defy:  { primary: color.ink,   accent: color.warm,  mood: 'defy'  },
};
