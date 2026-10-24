import { useEffect } from 'react';
import type { Clock } from '@/engine/clock';
import type { Section } from '@/engine/types';

interface Props {
  clock: Clock;
  sections: Section[];
  currentSectionType?: string;
  mode?: 'audio' | 'scrubber';
  offsetSec?: number;
  onOffsetChange?: (next: number) => void;
}

/**
 * Dev-only overlay: play/pause, slider, section markers, keyboard shortcuts.
 *
 *   space        play / pause
 *   ← / ,        -1s
 *   → / .        +1s
 *   [            jump to previous section start
 *   ]            jump to next section start
 *   0..9         jump to N/10 of duration
 *   = / -        nudge timeline offset ±0.05s
 *   + / _        nudge timeline offset ±0.5s   (shifted)
 *   r            reset offset to 0
 */
export function TimeScrubber({
  clock,
  sections,
  currentSectionType,
  mode = 'scrubber',
  offsetSec = 0,
  onOffsetChange,
}: Props) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Only swallow keys when typing into a text-y input. The slider here
      // is a range input which never produces text — let our shortcuts
      // through even when it has focus after a click.
      if (e.target instanceof HTMLTextAreaElement) return;
      if (e.target instanceof HTMLInputElement) {
        const t = e.target.type;
        if (t !== 'range' && t !== 'checkbox' && t !== 'radio' && t !== 'button' && t !== 'submit') return;
      }
      switch (e.key) {
        case ' ':
          e.preventDefault();
          if (clock.isPlaying) clock.pause();
          else clock.play();
          break;
        case 'ArrowLeft':
        case ',':
          e.preventDefault();
          clock.seek(clock.currentTime - 1);
          break;
        case 'ArrowRight':
        case '.':
          e.preventDefault();
          clock.seek(clock.currentTime + 1);
          break;
        case '[': {
          const prev = [...sections].reverse().find((s) => s.t < clock.currentTime - 0.5);
          clock.seek(prev ? prev.t : 0);
          break;
        }
        case ']': {
          const next = sections.find((s) => s.t > clock.currentTime + 0.5);
          if (next) clock.seek(next.t);
          break;
        }
        case '=':
          e.preventDefault();
          onOffsetChange?.(round(offsetSec + 0.05));
          break;
        case '+':
          e.preventDefault();
          onOffsetChange?.(round(offsetSec + 0.5));
          break;
        case '-':
          e.preventDefault();
          onOffsetChange?.(round(offsetSec - 0.05));
          break;
        case '_':
          e.preventDefault();
          onOffsetChange?.(round(offsetSec - 0.5));
          break;
        case 'r':
        case 'R':
          e.preventDefault();
          onOffsetChange?.(0);
          break;
        default:
          if (/^[0-9]$/.test(e.key)) {
            const frac = Number(e.key) / 10;
            clock.seek(clock.duration * frac);
          }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [clock, sections, offsetSec, onOffsetChange]);

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 100,
        padding: '12px 16px',
        background: 'linear-gradient(0deg, rgba(11,15,20,0.95), rgba(11,15,20,0.4))',
        display: 'grid',
        gridTemplateColumns: 'auto 1fr auto',
        gap: 16,
        alignItems: 'center',
        fontFamily: '"Cormorant Garamond", serif',
        color: '#f5efe3',
      }}
    >
      <button
        onClick={clock.isPlaying ? clock.pause : clock.play}
        style={{ minWidth: 56 }}
        title="space"
      >
        {clock.isPlaying ? 'pause' : 'play'}
      </button>

      <div style={{ position: 'relative' }}>
        {/* Section markers behind the slider */}
        <div style={{ position: 'absolute', left: 0, right: 0, top: 14, height: 6, pointerEvents: 'none' }}>
          {sections.map((s) => {
            const left = (s.t / clock.duration) * 100;
            const width = ((s.end - s.t) / clock.duration) * 100;
            return (
              <div
                key={`${s.t}-${s.type}`}
                style={{
                  position: 'absolute',
                  left: `${left}%`,
                  width: `${width}%`,
                  top: 0,
                  bottom: 0,
                  background: moodTint(s.mood),
                  opacity: 0.5,
                }}
              />
            );
          })}
        </div>
        <input
          type="range"
          min={0}
          max={clock.duration}
          step={0.01}
          value={clock.currentTime}
          onChange={(e) => clock.seek(Number(e.target.value))}
          style={{ width: '100%', position: 'relative' }}
        />
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', fontVariantNumeric: 'tabular-nums', fontSize: 14 }}>
        <span style={{ opacity: 0.45, fontStyle: 'italic', fontSize: 12 }}>
          {mode === 'audio' ? 'audio' : 'scrubber'}
        </span>
        {onOffsetChange && (
          <div
            title="lyric offset — kb: =/- ±0.05s · +/_ ±0.5s · r reset"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              padding: '2px 4px',
              border: '1px solid #f5efe340',
              borderRadius: 4,
              fontSize: 12,
              fontStyle: 'italic',
            }}
          >
            <OffsetBtn label="−.5" onClick={() => onOffsetChange(round(offsetSec - 0.5))} />
            <OffsetBtn label="−" onClick={() => onOffsetChange(round(offsetSec - 0.05))} />
            <span
              style={{
                minWidth: 64,
                textAlign: 'center',
                opacity: offsetSec === 0 ? 0.5 : 1,
                color: offsetSec === 0 ? undefined : '#ffd27d',
                padding: '0 4px',
              }}
            >
              ofs {offsetSec >= 0 ? '+' : ''}{offsetSec.toFixed(2)}s
            </span>
            <OffsetBtn label="+" onClick={() => onOffsetChange(round(offsetSec + 0.05))} />
            <OffsetBtn label="+.5" onClick={() => onOffsetChange(round(offsetSec + 0.5))} />
            <OffsetBtn label="↺" onClick={() => onOffsetChange(0)} disabled={offsetSec === 0} />
          </div>
        )}
        <span style={{ opacity: 0.6 }}>{currentSectionType ?? '—'}</span>
        <span>{format(clock.currentTime)} / {format(clock.duration)}</span>
      </div>
    </div>
  );
}

function format(t: number): string {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function round(t: number): number {
  return Math.round(t * 100) / 100;
}

function OffsetBtn({
  label,
  onClick,
  disabled,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        minWidth: 24,
        height: 22,
        padding: '0 6px',
        background: 'transparent',
        border: '1px solid #f5efe355',
        borderRadius: 3,
        color: '#f5efe3',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.25 : 0.85,
        fontFamily: 'inherit',
        fontSize: 12,
        lineHeight: 1,
      }}
    >
      {label}
    </button>
  );
}

function moodTint(mood: string): string {
  switch (mood) {
    case 'still': return '#6b8ca8';
    case 'soft':  return '#dce4ea';
    case 'ache':  return '#3a1e24';
    case 'open':  return '#ffd27d';
    case 'defy':  return '#f2a65a';
    case 'fin':   return '#f5efe3';
    default:      return '#888';
  }
}
