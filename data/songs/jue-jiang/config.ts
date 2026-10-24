import type { SongConfig } from '@/engine/types';
import { jueJiangPalette } from '@/theme/palettes/jue-jiang';

const config: SongConfig = {
  songId: 'jue-jiang',
  audioSrc: '/audio/jue-jiang.mp3',
  audioInstrumentalSrc: '/audio/jue-jiang.m4a',
  timelineSrc: '/data/songs/jue-jiang/timeline.json',
  palette: jueJiangPalette,
  sceneMap: {
    intro:       'SceneSilence',
    verse1:      'SceneSilence',
    verse2:      'SceneSilence',
    pre_chorus:  'SceneDefyLines',
    chorus1:     'SceneDefyLines',
    chorus2:     'SceneDefyLines',
    chorus_last: 'SceneDefyLines',
    bridge:      'SceneDefyLines',
    outro:       'SceneSilence',
  },
};

export default config;
