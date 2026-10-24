import { useEffect, useState } from 'react';
import { SongLoader } from '@/engine/SongLoader';
import { listSongIds } from '@/engine/songs';
import { Preview } from '@/preview/Preview';

const FALLBACK_SONG = 'yi-zhi-hen-an-jing';

export default function App() {
  const route = useHashRoute();
  const songId = useSongIdFromQuery();

  if (route === 'preview') return <Preview />;
  if (!songId) return <SongPicker />;
  return <SongLoader songId={songId} />;
}

function useSongIdFromQuery(): string | null {
  const [songId, setSongId] = useState(() => readQuerySong());
  useEffect(() => {
    const handler = () => setSongId(readQuerySong());
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, []);
  return songId;
}

function readQuerySong(): string | null {
  const params = new URLSearchParams(window.location.search);
  const explicit = params.get('song');
  if (explicit) return explicit;
  const available = listSongIds();
  if (available.length === 0) return null;
  if (available.includes(FALLBACK_SONG)) return FALLBACK_SONG;
  return available[0];
}

function useHashRoute(): string {
  const [route, setRoute] = useState(() => window.location.hash.slice(1));
  useEffect(() => {
    const onChange = () => setRoute(window.location.hash.slice(1));
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return route;
}

function SongPicker() {
  const ids = listSongIds();
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'grid',
        placeItems: 'center',
        background: '#0b0f14',
        color: '#f5efe3',
        fontFamily: '"Cormorant Garamond", serif',
      }}
    >
      <div style={{ textAlign: 'center', maxWidth: 480 }}>
        <div style={{ fontStyle: 'italic', letterSpacing: '0.2em', opacity: 0.7, marginBottom: 16 }}>
          no songs found in data/songs/
        </div>
        <div style={{ opacity: 0.5, fontSize: 13, lineHeight: 1.7 }}>
          run intake on a song first, then visit{' '}
          <code style={{ color: '#ffd27d' }}>/?song=&lt;id&gt;</code>.
          {ids.length > 0 && (
            <>
              <br /><br />
              available: {ids.map((id) => (
                <a key={id} href={`/?song=${id}`} style={{ color: '#f2a65a', marginRight: 8 }}>
                  {id}
                </a>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
