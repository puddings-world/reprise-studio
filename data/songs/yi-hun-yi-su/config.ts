import type { SongConfig } from '@/engine/types';
import { yiHunYiSuPalette } from '@/theme/palettes/yi-hun-yi-su';

const config: SongConfig = {
  songId: 'yi-hun-yi-su',
  audioSrc: '/audio/yi-hun-yi-su.mp3',
  audioInstrumentalSrc: '/audio/yi-hun-yi-su.m4a',
  timelineSrc: '/data/songs/yi-hun-yi-su/timeline.json',
  palette: yiHunYiSuPalette,
  sceneMap: {
    intro:       'SceneSilence',
    verse1:      'SceneSilence',
    verse2:      'SceneSilence',
    pre_chorus:  'SceneSilence',
    chorus1:     'SceneSteamTable',
    chorus2:     'SceneSteamTable',
    chorus_last: 'SceneSteamTable',
    solo:        'SceneSilence',
    outro:       'SceneSilence',
  },
};

export default config;
