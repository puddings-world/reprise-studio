import type { SongConfig } from '@/engine/types';
import { yiZhiHenAnJingPalette } from '@/theme/palettes/yi-zhi-hen-an-jing';

const config: SongConfig = {
  songId: 'yi-zhi-hen-an-jing',
  audioSrc: '/audio/yi-zhi-hen-an-jing.mp3',
  audioInstrumentalSrc: '/audio/yi-zhi-hen-an-jing.m4a',
  timelineSrc: '/data/songs/yi-zhi-hen-an-jing/timeline.json',
  palette: yiZhiHenAnJingPalette,
  sceneMap: {
    intro:       'SceneSilence',
    verse1:      'SceneSilence',
    verse2:      'SceneSilence',
    chorus1:     'SceneNameless',
    chorus2:     'SceneNameless',
    chorus_last: 'SceneNameless',
    bridge:      'SceneSilence',
    solo:        'SceneSilence',
  },
};

export default config;
