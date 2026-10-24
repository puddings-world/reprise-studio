import type { ComponentType } from 'react';
import type { SceneProps } from '@/engine/types';
import { SceneSilence } from './SceneSilence';
import { SceneUnderstanding } from './SceneUnderstanding';
import { SceneBrokenWings } from './SceneBrokenWings';
import { SceneSunrise } from './SceneSunrise';
import { SceneRainSnow } from './SceneRainSnow';
import { SceneSkyward } from './SceneSkyward';
import { SceneFin } from './SceneFin';
import { SceneNameless } from './SceneNameless';
import { SceneSteamTable } from './SceneSteamTable';
import { SceneDefyLines } from './SceneDefyLines';
import { SceneDustLight } from './SceneDustLight';

export const sceneRegistry: Record<string, ComponentType<SceneProps>> = {
  SceneSilence,
  SceneUnderstanding,
  SceneBrokenWings,
  SceneSunrise,
  SceneRainSnow,
  SceneSkyward,
  SceneFin,
  SceneNameless,
  SceneSteamTable,
  SceneDefyLines,
  SceneDustLight,
};
