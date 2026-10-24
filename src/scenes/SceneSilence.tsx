import type { PaletteEntry, SceneProps } from '@/engine/types';
import { tokens } from '@/theme/tokens';
import { BaseScene } from './_BaseScene';

/**
 * SceneSilence — 寂靜
 *
 * Reference implementation. All future scene agents should copy this pattern:
 *
 *   1. Read palette + energy from props; never reach for global state.
 *   2. The pure visual lives in `SceneSilenceView`, which is driven entirely
 *      by props — `timeSec` for ambient motion, `energy` for breathing. No
 *      CSS `@keyframes` and no Motion transitions: both run on the browser's
 *      wall-clock and freeze under Remotion's frame-by-frame render. Deriving
 *      every moving value from `timeSec` keeps the scene deterministic in both
 *      the live preview and the MP4 export.
 *   3. Crossfade between scenes is BaseScene's job (live preview). The Remotion
 *      composition renders `SceneSilenceView` directly and supplies its own
 *      frame-based fade.
 *
 * Imagery (per docs/DESIGN.md): moon, still water, low horizon. Cold mood.
 */
export function SceneSilence({ energy, palette, timeSec }: SceneProps) {
  return (
    <BaseScene id="silence">
      <SceneSilenceView timeSec={timeSec ?? 0} energy={energy} palette={palette} />
    </BaseScene>
  );
}

interface SilenceViewProps {
  timeSec: number;
  energy: number;
  palette: PaletteEntry;
}

/**
 * Pure, frame-deterministic visual for 寂靜. Safe to mount under Remotion:
 * every animated value is a function of `timeSec` / `energy`, set inline.
 *
 * `color-mix(...)` strings are mathematical opacity operations on token-fed
 * colors, not magic colors — same rule the old CSS module followed.
 */
export function SceneSilenceView({ timeSec, energy, palette }: SilenceViewProps) {
  const brightness = 0.55 + energy * 0.2;
  const moonScale = 1 + energy * 0.04;

  // Fog drift: the old CSS was `drift 22s ease-in-out infinite alternate`,
  // i.e. a triangle wave with a 44s full period, smoothstep-eased, lerping
  // translate from (-2%, -1%) to (3%, 2%). Reproduced here from `timeSec`.
  const cycle = (timeSec / 22) % 2; // 0..2
  const tri = cycle <= 1 ? cycle : 2 - cycle; // 0..1..0
  const eased = tri * tri * (3 - 2 * tri); // smoothstep
  const fogX = -2 + eased * 5;
  const fogY = -1 + eased * 3;

  const { primary } = palette;
  const { ink, paper, mist, cold } = tokens.color;

  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', filter: `brightness(${brightness})` }}>
      {/* Layer 1: deep sky → ink */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          background: `radial-gradient(ellipse 70% 60% at 50% 65%, ${primary} 0%, ${ink} 75%)`,
        }}
      />
      {/* Layer 2: implied water surface */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: '60%',
          bottom: 0,
          background: `linear-gradient(180deg, transparent 0%, color-mix(in srgb, ${cold} 16%, transparent) 55%, color-mix(in srgb, ${ink} 55%, transparent) 100%)`,
        }}
      />
      {/* Layer 3: drifting fog */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: '-10%',
          filter: 'blur(34px)',
          transform: `translate(${fogX}%, ${fogY}%)`,
          background: `radial-gradient(45% 22% at 28% 42%, color-mix(in srgb, ${cold} 28%, transparent), transparent 60%), radial-gradient(55% 26% at 72% 68%, color-mix(in srgb, ${cold} 18%, transparent), transparent 60%)`,
        }}
      />
      {/* Layer 4: thin horizon line, mist-biased glow */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          left: '8%',
          right: '8%',
          top: '60%',
          height: 1,
          background: `linear-gradient(90deg, transparent 0%, color-mix(in srgb, ${mist} 60%, transparent) 50%, transparent 100%)`,
          boxShadow: `0 0 8px color-mix(in srgb, ${mist} 25%, transparent)`,
        }}
      />
      {/* Layer 5: moon — light biased upper-left, soft halo */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          left: '50%',
          top: '36%',
          width: 'clamp(140px, 16vw, 220px)',
          aspectRatio: '1',
          borderRadius: '50%',
          transform: `translate(-50%, -50%) scale(${moonScale})`,
          background: `radial-gradient(circle at 38% 35%, ${paper} 0%, color-mix(in srgb, ${mist} 80%, ${ink}) 70%, transparent 72%)`,
          boxShadow: `0 0 80px 8px color-mix(in srgb, ${mist} 18%, transparent), 0 0 200px 40px color-mix(in srgb, ${cold} 12%, transparent)`,
        }}
      />
      {/* Layer 6: vignette */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          opacity: tokens.layout.vignetteIntensity,
          background: `radial-gradient(ellipse at center, transparent 50%, ${ink} 100%)`,
        }}
      />
    </div>
  );
}
