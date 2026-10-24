import { type ComponentType } from 'react';
import type { SceneProps, SongConfig, Section, TimelineEntry } from './types';

interface SceneRouterProps {
  config: SongConfig;
  sceneRegistry: Record<string, ComponentType<SceneProps>>;
  section: Section | null;
  lyric: TimelineEntry | null;
  energy: number;
  currentTime: number;
}

/**
 * Picks the scene component for the current section and renders it.
 *
 * Crossfade between scenes is handled by Motion's <AnimatePresence> in
 * the parent — this router just resolves which component to mount.
 */
export function SceneRouter({
  config,
  sceneRegistry,
  section,
  lyric,
  energy,
  currentTime,
}: SceneRouterProps) {
  if (!section) return null;

  const sceneName = config.sceneMap[section.type];
  if (!sceneName) {
    return <FallbackScene reason={`No scene mapped for section "${section.type}"`} />;
  }

  const Scene = sceneRegistry[sceneName];
  if (!Scene) {
    return <FallbackScene reason={`Scene "${sceneName}" not found in registry`} />;
  }

  const palette = config.palette[section.mood];
  const progress = (currentTime - section.t) / Math.max(0.001, section.end - section.t);

  return (
    <Scene
      progress={Math.max(0, Math.min(1, progress))}
      energy={energy}
      section={section}
      palette={palette}
      lyric={lyric}
      timeSec={currentTime}
    />
  );
}

function FallbackScene({ reason }: { reason: string }) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'grid',
        placeItems: 'center',
        background: '#0b0f14',
        color: 'rgba(245, 239, 227, 0.4)',
        fontStyle: 'italic',
        letterSpacing: '0.1em',
      }}
    >
      {reason}
    </div>
  );
}
