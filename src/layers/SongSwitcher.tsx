import { listSongIds } from '@/engine/songs';

interface Props {
  currentSongId: string;
}

// Placeholder demos from the initial scaffold that have no bundled audio.
// Skip them in the switcher so users don't click into a silent player.
const HIDDEN = new Set(['seeing-farthest']);

/**
 * Top-left chip list of every song discovered under `data/songs/`. Click a
 * chip to navigate via full reload (avoids tearing down the Player + audio
 * graph mid-flight). Dev-only convenience — Remotion ignores this layer.
 */
export function SongSwitcher({ currentSongId }: Props) {
  const ids = listSongIds().filter((id) => !HIDDEN.has(id) || id === currentSongId);
  if (ids.length <= 1) return null;
  return (
    <div
      style={{
        position: 'absolute',
        top: 12,
        left: 16,
        zIndex: 100,
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap',
        maxWidth: '60vw',
        fontFamily: '"Cormorant Garamond", serif',
        fontSize: 12,
        fontStyle: 'italic',
        letterSpacing: '0.05em',
      }}
    >
      {ids.map((id) => {
        const active = id === currentSongId;
        return (
          <a
            key={id}
            href={`/?song=${id}`}
            style={{
              color: active ? '#ffd27d' : '#f5efe3',
              opacity: active ? 1 : 0.55,
              padding: '4px 10px',
              border: active ? '1px solid #ffd27d80' : '1px solid #f5efe340',
              borderRadius: 999,
              textDecoration: 'none',
              backdropFilter: 'blur(6px)',
              background: 'rgba(11,15,20,0.45)',
              pointerEvents: 'auto',
            }}
          >
            {id}
          </a>
        );
      })}
    </div>
  );
}
