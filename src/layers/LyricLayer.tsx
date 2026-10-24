import { AnimatePresence, motion } from 'motion/react';
import type { TimelineEntry } from '@/engine/types';
import { tokens } from '@/theme/tokens';

interface LyricLayerProps {
  lyric: TimelineEntry | null;
}

/**
 * Renders the currently-active lyric line with fade in/out.
 *
 * Keyed on `lyric.t` so Motion treats each line as a fresh element and
 * crossfades cleanly.
 */
export function LyricLayer({ lyric }: LyricLayerProps) {
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: tokens.layout.lyricSafeBottom,
        display: 'flex',
        justifyContent: 'center',
        pointerEvents: 'none',
        zIndex: 10,
      }}
    >
      {/*
        No `mode="wait"` — that would force the old line to fully exit before
        the new one mounts, doubling the perceived delay (fadeOut + fadeIn).
        Default "sync" lets them crossfade, so a new line lands at its own
        timestamp, not after the previous one's exit finishes.
      */}
      <AnimatePresence>
        {lyric && lyric.text.trim() !== '' && (
          <motion.div
            key={lyric.t}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{
              duration: tokens.motion.lyricFadeIn,
              ease: tokens.easing.lyricIn as unknown as number[],
            }}
            style={{
              fontFamily: tokens.typography.lyricMain.fontFamily,
              fontWeight: tokens.typography.lyricMain.weight,
              fontSize: tokens.typography.lyricMain.sizeClamp,
              lineHeight: tokens.typography.lyricMain.lineHeight,
              letterSpacing: tokens.typography.lyricMain.letterSpacing,
              color: tokens.color.paper,
              maxWidth: tokens.layout.lyricMaxWidth,
              textAlign: 'center',
              textShadow: '0 2px 18px rgba(0,0,0,0.45)',
            }}
          >
            {renderWithEmphasis(lyric.text, lyric.emphasis)}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function renderWithEmphasis(text: string, emphasis?: string[]) {
  if (!emphasis || emphasis.length === 0) return text;
  let rendered: (string | JSX.Element)[] = [text];
  emphasis.forEach((word, idx) => {
    rendered = rendered.flatMap((part) => {
      if (typeof part !== 'string') return [part];
      const segments = part.split(word);
      const result: (string | JSX.Element)[] = [];
      segments.forEach((seg, i) => {
        if (i > 0) {
          result.push(
            <span
              key={`em-${idx}-${i}`}
              style={{
                fontWeight: tokens.typography.lyricEmphasis.weight,
                letterSpacing: tokens.typography.lyricEmphasis.letterSpacing,
                color: tokens.color.sun,
              }}
            >
              {word}
            </span>,
          );
        }
        result.push(seg);
      });
      return result;
    });
  });
  return rendered;
}
