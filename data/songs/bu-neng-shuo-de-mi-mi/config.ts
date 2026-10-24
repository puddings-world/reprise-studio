import type { SongConfig } from '@/engine/types';
import { buNengShuoDeMiMiPalette } from '@/theme/palettes/bu-neng-shuo-de-mi-mi';

const config: SongConfig = {
  songId: 'bu-neng-shuo-de-mi-mi',
  audioSrc: '/audio/bu-neng-shuo-de-mi-mi.mp3',
  audioInstrumentalSrc: '/audio/bu-neng-shuo-de-mi-mi.m4a',
  timelineSrc: '/data/songs/bu-neng-shuo-de-mi-mi/timeline.json',
  palette: buNengShuoDeMiMiPalette,
  sceneMap: {
    intro:       'SceneSilence',
    verse1:      'SceneSilence',
    verse2:      'SceneSilence',
    pre_chorus:  'SceneDustLight',
    chorus1:     'SceneDustLight',
    chorus_last: 'SceneDustLight',
    bridge:      'SceneDustLight',
    solo:        'SceneSilence',
    outro:       'SceneSilence',
  },
};

export default config;
