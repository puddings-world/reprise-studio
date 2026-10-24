import { useEffect, useRef, useState } from 'react';
import type { TimelineEntry } from '@/engine/types';

interface Props {
  lyrics: TimelineEntry[];
  /** Raw audio time, BEFORE offset is applied. */
  currentTime: number;
  /** Current global lyric offset (seconds). */
  offsetSec: number;
  /** Update the global offset. */
  onOffsetChange: (next: number) => void;
  /** Seek the audio to `t` seconds. */
  onSeek: (t: number) => void;
}

/**
 * Right-side overlay listing every lyric line with its (offset-adjusted)
 * timestamp. Click a row to seek to it. The +/- buttons at the top change
 * the global lyric offset — the entire list visibly shifts so the effect
 * is no longer abstract.
 *
 * Dev-only. Toggle with the button at the top-right or press `L`.
 */
export function LyricInspector({ lyrics, currentTime, offsetSec, onOffsetChange, onSeek }: Props) {
  const [open, setOpen] = useState(true);
  const listRef = useRef<HTMLOListElement | null>(null);

  // Find the lyric whose [t, end) window contains the current adjusted time.
  // adjusted = currentTime + offsetSec, mirroring Player's lookup.
  const adjusted = currentTime + offsetSec;
  const activeIdx = lyrics.findIndex((l) => adjusted >= l.t && adjusted < l.end);

  // Auto-scroll the active row into the middle of the list.
  useEffect(() => {
    if (activeIdx < 0 || !listRef.current) return;
    const row = listRef.current.querySelectorAll<HTMLLIElement>('li')[activeIdx];
    row?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [activeIdx]);

  // `L` key toggles the panel — but don't swallow other shortcuts.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === 'l' || e.key === 'L') {
        setOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div
      style={{
        position: 'absolute',
        right: 0,
        top: 0,
        bottom: 0,
        width: open ? 320 : 0,
        background: 'rgba(11,15,20,0.78)',
        backdropFilter: 'blur(10px)',
        borderLeft: open ? '1px solid rgba(245,239,227,0.1)' : 'none',
        color: '#f5efe3',
        fontFamily: '"Cormorant Garamond", serif',
        fontSize: 13,
        zIndex: 90,
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s ease',
        overflow: 'hidden',
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title="toggle lyric inspector (L)"
        style={{
          position: 'absolute',
          right: open ? 8 : 'auto',
          left: open ? 'auto' : -34,
          top: 12,
          width: 28,
          height: 28,
          padding: 0,
          background: 'rgba(11,15,20,0.9)',
          color: '#f5efe3',
          border: '1px solid rgba(245,239,227,0.25)',
          borderRadius: 4,
          cursor: 'pointer',
          fontFamily: 'inherit',
          fontStyle: 'italic',
          fontSize: 13,
          zIndex: 1,
        }}
      >
        {open ? '×' : 'L'}
      </button>

      {open && (
        <>
          <header style={{ padding: '12px 16px 8px', borderBottom: '1px solid rgba(245,239,227,0.08)' }}>
            <div style={{ opacity: 0.55, fontSize: 11, letterSpacing: '0.18em', textTransform: 'uppercase' }}>
              Lyric Inspector
            </div>
            <div style={{ marginTop: 10, fontSize: 12, opacity: 0.7, fontStyle: 'italic' }}>
              audio: {currentTime.toFixed(2)}s &nbsp;·&nbsp; lookup: {adjusted.toFixed(2)}s
            </div>

            <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 11, opacity: 0.6, marginRight: 4 }}>歌詞 offset</span>
              <Btn onClick={() => onOffsetChange(round(offsetSec - 0.5))}>−.5</Btn>
              <Btn onClick={() => onOffsetChange(round(offsetSec - 0.05))}>−</Btn>
              <span
                style={{
                  minWidth: 70,
                  textAlign: 'center',
                  fontSize: 13,
                  fontStyle: 'italic',
                  color: offsetSec === 0 ? undefined : '#ffd27d',
                  opacity: offsetSec === 0 ? 0.55 : 1,
                  padding: '0 4px',
                }}
              >
                {offsetSec >= 0 ? '+' : ''}{offsetSec.toFixed(2)}s
              </span>
              <Btn onClick={() => onOffsetChange(round(offsetSec + 0.05))}>+</Btn>
              <Btn onClick={() => onOffsetChange(round(offsetSec + 0.5))}>+.5</Btn>
              <Btn onClick={() => onOffsetChange(0)} disabled={offsetSec === 0}>↺</Btn>
            </div>
            <div style={{ marginTop: 8, fontSize: 11, opacity: 0.5, lineHeight: 1.55 }}>
              按 +/− 整列「fires @ audio」會即時位移。<br />
              歌詞慢了 → <code>+</code>（早一點出來）·歌詞早了 → <code>−</code>（晚一點出來）
            </div>
          </header>

          <div
            style={{
              padding: '6px 14px 4px',
              fontSize: 10,
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              opacity: 0.45,
              display: 'grid',
              gridTemplateColumns: '54px 1fr',
              gap: 10,
            }}
          >
            <span>fires @ audio</span>
            <span>lyric (LRC t)</span>
          </div>
          <ol
            ref={listRef}
            style={{
              listStyle: 'none',
              padding: '0 0 6px',
              margin: 0,
              overflowY: 'auto',
              flex: 1,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {lyrics.map((l, i) => {
              const active = i === activeIdx;
              const past = i < activeIdx;
              // Effective fire-time in the audio timeline.
              // adjusted = audioT + offset, so lyric fires when audioT = l.t - offset.
              const fireAt = Math.max(0, l.t - offsetSec);
              const shifted = offsetSec !== 0;
              return (
                <li key={`${l.t}-${i}`}>
                  <button
                    type="button"
                    onClick={() => onSeek(fireAt)}
                    title={`seek to ${fireAt.toFixed(2)}s of audio (LRC t=${l.t.toFixed(2)})`}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '54px 1fr',
                      gap: 10,
                      width: '100%',
                      padding: '5px 14px',
                      textAlign: 'left',
                      background: active ? 'rgba(255,210,125,0.12)' : 'transparent',
                      border: 'none',
                      borderLeft: active ? '2px solid #ffd27d' : '2px solid transparent',
                      color: active ? '#ffd27d' : past ? 'rgba(245,239,227,0.4)' : '#f5efe3',
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      fontSize: 13,
                      lineHeight: 1.5,
                    }}
                  >
                    <span
                      style={{
                        fontStyle: 'italic',
                        opacity: shifted ? 1 : 0.7,
                        color: shifted && !active ? '#ffd27d' : undefined,
                        fontSize: 12,
                      }}
                    >
                      {fireAt.toFixed(2)}
                    </span>
                    <span style={{ fontFamily: '"Noto Serif TC", serif' }}>
                      {l.text}
                      {shifted && (
                        <span
                          style={{
                            marginLeft: 8,
                            opacity: 0.35,
                            fontSize: 10,
                            fontStyle: 'italic',
                            fontFamily: '"Cormorant Garamond", serif',
                          }}
                        >
                          lrc {l.t.toFixed(2)}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </>
      )}
    </div>
  );
}

function Btn({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        minWidth: 26,
        height: 22,
        padding: '0 6px',
        background: 'transparent',
        border: '1px solid rgba(245,239,227,0.35)',
        borderRadius: 3,
        color: '#f5efe3',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.25 : 0.9,
        fontFamily: 'inherit',
        fontSize: 12,
        lineHeight: 1,
      }}
    >
      {children}
    </button>
  );
}

function round(t: number): number {
  return Math.round(t * 100) / 100;
}
