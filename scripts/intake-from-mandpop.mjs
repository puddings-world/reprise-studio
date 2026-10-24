#!/usr/bin/env node
/**
 * One-shot adapter: MandpopDataset → reprise-studio data/songs/<id>/
 *
 * Authoritative source: `<MANDPOP_DATASET>/processed_dataset.jsonl`. Only
 * songs that passed the dataset's alignment gate (Layer 1 VAD + Layer 2
 * WhisperX, verdict ∈ {ok, fixed}) appear there. We refuse to intake a
 * song that isn't in processed — the alignment is the dataset's promise.
 *
 * Both audio tracks are pulled across:
 *   - original.mp3   → public/audio/<song-id>.mp3  (design preview, with vocals)
 *   - instrumental.m4a → public/audio/<song-id>.m4a (karaoke / cover-recording)
 *
 * Section boundaries and cue placement are NOT in the dataset — they are
 * visual-design metadata authored per song in
 * `data/songs/<song-id>/curation.json` (this script scaffolds a template if
 * missing). Long-term goal: move sections + cues into MandpopDataPipeline as
 * a first-class output, then this adapter can be retired.
 *
 * Alignment doctor: the dataset gate corrects a GLOBAL offset only (whole-LRC
 * shift verified by vocal-onset VAD + WhisperX drift stats). At intake we
 * re-derive the vocal onset from the vocals stem via ffmpeg silencedetect and
 *   1. drop LRC lines before the onset (kills credit lines regardless of
 *      wording — the prefix blacklist below is only a fallback), and
 *   2. report first-lyric-vs-onset delta, warning above the gate's 0.5s
 *      tolerance → that's a signal to re-audit in MandpopDataPipeline,
 *      NOT to hand-edit timeline.json here.
 *
 * Energy curve: a 20 Hz RMS curve is precomputed from the preview mp3 into
 * `data/songs/<song-id>/energy.json` so both the Remotion render (no live
 * AnalyserNode) and scrubber mode can use real, deterministic energy.
 *
 * Usage:
 *   node scripts/intake-from-mandpop.mjs <chinese-title> <song-id>
 *
 * Example:
 *   node scripts/intake-from-mandpop.mjs 一直很安靜 yi-zhi-hen-an-jing
 */

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..');
const DATASET_ROOT = process.env.MANDPOP_DATASET ?? 'D:\\MandpopDataset';

// Dataset alignment-gate tolerance (Layer 1). A first-lyric-vs-onset delta
// beyond this means the promoted LRC is suspect → re-audit upstream.
const GATE_TOLERANCE_SEC = 0.5;
// Lines earlier than (onset − margin) are considered pre-vocal credits.
const ONSET_CREDIT_MARGIN_SEC = 1.0;

// Fallback credit filter for lines that appear AFTER the vocal onset
// (e.g. trailing production credits). Pre-vocal credits are handled by the
// onset cut, which doesn't depend on wording.
const CREDIT_PREFIXES = ['作词', '作曲', '编曲', '原唱', '出品', '【', '制作', '吉他', '大提琴',
  '和声', '混音', '弦乐', '统筹', '监制', '企划', '出品人', '营销', 'OP：', 'SP：'];

// ---- Catalog (processed_dataset.jsonl) -----------------------------------

function loadProcessedCatalog() {
  const catalogPath = path.join(DATASET_ROOT, 'processed_dataset.jsonl');
  if (!fs.existsSync(catalogPath)) {
    console.error(`✗ processed_dataset.jsonl not found at ${catalogPath}`);
    console.error(`  Run \`python pipeline.py status\` in the dataset to confirm it exists.`);
    process.exit(1);
  }
  const lines = fs.readFileSync(catalogPath, 'utf8').split(/\r?\n/).filter(Boolean);
  return lines.map((l) => JSON.parse(l));
}

function findSong(catalog, chineseTitle) {
  const exact = catalog.find((r) => r.title === chineseTitle);
  if (exact) return exact;
  const partial = catalog.filter((r) => r.title.includes(chineseTitle) || chineseTitle.includes(r.title));
  if (partial.length === 1) return partial[0];
  if (partial.length > 1) {
    console.error(`✗ "${chineseTitle}" matches multiple processed songs:`);
    for (const r of partial) console.error(`    - ${r.title} (${r.artist})`);
    process.exit(1);
  }
  return null;
}

// ---- Curation (sections + cues, authored per song in this repo) ----------

const CURATION_TEMPLATE = (title) => `{
  "title": "${title}",
  "sections": [
    { "t": 0.0, "end": 0.0, "type": "intro", "mood": "still" }
  ],
  "cues": []
}
`;

function loadCuration(songId, title) {
  const curationPath = path.join(REPO_ROOT, 'data', 'songs', songId, 'curation.json');
  if (!fs.existsSync(curationPath)) {
    fs.mkdirSync(path.dirname(curationPath), { recursive: true });
    fs.writeFileSync(curationPath, CURATION_TEMPLATE(title));
    console.error(`✗ No curation file for "${title}".`);
    console.error(`  Scaffolded ${path.relative(REPO_ROOT, curationPath)} — fill in section`);
    console.error(`  boundaries (listen to the preview mp3) and cue points, then re-run.`);
    process.exit(1);
  }
  const curation = JSON.parse(fs.readFileSync(curationPath, 'utf8'));
  const ok =
    Array.isArray(curation.sections) &&
    curation.sections.length > 0 &&
    curation.sections.every((s) => typeof s.t === 'number' && typeof s.end === 'number' && s.end > s.t && s.type && s.mood);
  if (!ok) {
    console.error(`✗ ${path.relative(REPO_ROOT, curationPath)} is incomplete — every section needs t < end, type, mood.`);
    process.exit(1);
  }
  if (curation.title && curation.title !== title) {
    console.error(`✗ curation.json title "${curation.title}" ≠ requested song "${title}" — wrong song-id?`);
    process.exit(1);
  }
  return { sections: curation.sections, cues: curation.cues ?? [] };
}

// ---- ffmpeg (Remotion-bundled, no extra dependency) -----------------------

function resolveFfmpeg() {
  const scope = path.join(REPO_ROOT, 'node_modules', '@remotion');
  if (fs.existsSync(scope)) {
    for (const pkg of fs.readdirSync(scope)) {
      if (!pkg.startsWith('compositor-')) continue;
      for (const bin of ['ffmpeg.exe', 'ffmpeg']) {
        const p = path.join(scope, pkg, bin);
        if (fs.existsSync(p)) return p;
      }
    }
  }
  return 'ffmpeg'; // fall back to PATH
}

// ---- Alignment doctor ------------------------------------------------------

/**
 * Vocal onset from the separated vocals stem. The stem is silent until the
 * first sung note, so the end of the leading silence IS the onset. Returns
 * null when detection isn't possible (missing stem / ffmpeg failure).
 */
function detectVocalOnset(ffmpeg, vocalsPath) {
  if (!fs.existsSync(vocalsPath)) return null;
  const res = spawnSync(
    ffmpeg,
    ['-hide_banner', '-i', vocalsPath, '-af', 'silencedetect=noise=-35dB:d=0.5', '-f', 'null', '-'],
    { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 },
  );
  if (res.error || res.status !== 0) return null;
  const stderr = res.stderr ?? '';
  const starts = [...stderr.matchAll(/silence_start:\s*(-?[\d.]+)/g)].map((m) => Number(m[1]));
  const ends = [...stderr.matchAll(/silence_end:\s*([\d.]+)/g)].map((m) => Number(m[1]));
  // Leading silence present → onset is where it ends. Otherwise vocals start
  // at (or near) 0 — plausible for songs with an immediate vocal.
  if (starts.length > 0 && starts[0] <= 0.5 && ends.length > 0) return ends[0];
  return 0;
}

// ---- Energy curve ----------------------------------------------------------

const ENERGY_SAMPLE_RATE = 8000; // Hz, decode rate (mono)
const ENERGY_WINDOW = 400; // samples per RMS window → 20 Hz curve

/** Locate the `data` chunk inside a RIFF/WAVE buffer (chunk layout varies). */
function extractWavData(buf) {
  if (buf.length < 44 || buf.toString('ascii', 0, 4) !== 'RIFF' || buf.toString('ascii', 8, 12) !== 'WAVE') {
    return null;
  }
  let off = 12;
  while (off + 8 <= buf.length) {
    const id = buf.toString('ascii', off, off + 4);
    const size = buf.readUInt32LE(off + 4);
    if (id === 'data') {
      // ffmpeg streaming to a pipe writes size 0xffffffff; take the rest.
      const end = size === 0xffffffff ? buf.length : Math.min(buf.length, off + 8 + size);
      return buf.subarray(off + 8, end);
    }
    off += 8 + size + (size % 2);
  }
  return null;
}

function computeEnergyCurve(ffmpeg, audioPath) {
  // Remotion's bundled ffmpeg is a trimmed build without raw-PCM muxers
  // (`-f s16le` → "Requested output format 's16le' is not known"), so we
  // decode to WAV on stdout and skip to its data chunk ourselves.
  const res = spawnSync(
    ffmpeg,
    ['-hide_banner', '-v', 'error', '-i', audioPath, '-ac', '1', '-ar', String(ENERGY_SAMPLE_RATE), '-c:a', 'pcm_s16le', '-f', 'wav', '-'],
    { maxBuffer: 512 * 1024 * 1024 },
  );
  if (res.error || res.status !== 0 || !res.stdout || res.stdout.length === 0) return null;
  const pcm = extractWavData(res.stdout);
  if (!pcm) return null;
  const totalSamples = Math.floor(pcm.length / 2);
  const windows = Math.floor(totalSamples / ENERGY_WINDOW);
  const values = new Array(windows);
  let peak = 0;
  for (let w = 0; w < windows; w += 1) {
    let sum = 0;
    for (let i = 0; i < ENERGY_WINDOW; i += 1) {
      const s = pcm.readInt16LE((w * ENERGY_WINDOW + i) * 2) / 32768;
      sum += s * s;
    }
    const rms = Math.sqrt(sum / ENERGY_WINDOW);
    values[w] = rms;
    if (rms > peak) peak = rms;
  }
  if (peak === 0) return null;
  return {
    rate: ENERGY_SAMPLE_RATE / ENERGY_WINDOW,
    values: values.map((v) => Math.round((v / peak) * 1000) / 1000),
  };
}

// ---- LRC parsing ---------------------------------------------------------

function parseLrc(content) {
  const out = [];
  for (const raw of content.split(/\r?\n/)) {
    const m = raw.match(/^\[(\d+):(\d+)\.(\d+)\](.*)$/);
    if (!m) continue;
    const [, mm, ss, ms, text] = m;
    const t = Number(mm) * 60 + Number(ss) + Number(`0.${ms}`);
    const cleaned = text.trim();
    if (!cleaned) { out.push({ t, text: '', isMarker: true }); continue; }
    if (CREDIT_PREFIXES.some((p) => cleaned.startsWith(p))) continue;
    out.push({ t, text: cleaned, isMarker: false });
  }
  return out;
}

function buildLyricsArray(parsed, duration) {
  const lyrics = [];
  for (let i = 0; i < parsed.length; i += 1) {
    const cur = parsed[i];
    if (cur.isMarker) continue;
    let end = duration;
    for (let j = i + 1; j < parsed.length; j += 1) {
      end = parsed[j].t;
      break;
    }
    const span = end - cur.t;
    if (span > 6) end = cur.t + Math.min(span, 6);
    lyrics.push({ t: round2(cur.t), end: round2(end), text: cur.text });
  }
  return lyrics;
}

const round2 = (x) => Math.round(x * 100) / 100;

// ---- Main ----------------------------------------------------------------

const [chineseTitle, songId] = process.argv.slice(2);
if (!chineseTitle || !songId) {
  console.error('Usage: node scripts/intake-from-mandpop.mjs <chinese-title> <song-id>');
  process.exit(1);
}

const catalog = loadProcessedCatalog();
const record = findSong(catalog, chineseTitle);
if (!record) {
  console.error(`✗ "${chineseTitle}" is not in processed_dataset.jsonl.`);
  console.error(`  Either:`);
  console.error(`    - title doesn't match exactly — check spelling`);
  console.error(`    - song failed the dataset's alignment gate (still in raw, not promoted)`);
  console.error(`  Run \`python pipeline.py list --processed\` in the dataset to see what's available.`);
  process.exit(1);
}

console.log(`✓ found in processed: ${record.title} — ${record.artist}`);

const { sections, cues } = loadCuration(songId, record.title);

const songDir = path.join(DATASET_ROOT, 'songs', record.title);

// Metadata for duration / youtube_url (jsonl record is intentionally minimal).
const metadataPath = path.join(songDir, 'metadata.json');
const metadata = fs.existsSync(metadataPath)
  ? JSON.parse(fs.readFileSync(metadataPath, 'utf8'))
  : {};
const duration = metadata.duration_sec ?? 0;
if (!duration) {
  console.warn(`! metadata.json missing duration_sec — last-lyric end may be off`);
}

// LRC path comes from the catalog record (relative to dataset root).
const lrcPath = path.join(DATASET_ROOT, record.files.lyrics);
let parsedLrc = parseLrc(fs.readFileSync(lrcPath, 'utf8'));

// -- Alignment doctor --------------------------------------------------------
const ffmpeg = resolveFfmpeg();
const vocalOnset = detectVocalOnset(ffmpeg, path.join(songDir, 'vocals.flac'));
let alignment = { verdict: 'skipped' };
if (vocalOnset === null) {
  console.warn(`! vocals.flac missing or ffmpeg failed — alignment doctor skipped, credit filter falls back to prefixes only`);
} else {
  const cutoff = vocalOnset - ONSET_CREDIT_MARGIN_SEC;
  const dropped = parsedLrc.filter((l) => !l.isMarker && l.t < cutoff);
  parsedLrc = parsedLrc.filter((l) => l.isMarker || l.t >= cutoff);
  if (dropped.length > 0) {
    console.log(`✓ dropped ${dropped.length} pre-vocal line(s) before onset ${vocalOnset.toFixed(2)}s:`);
    for (const d of dropped) console.log(`    [${d.t.toFixed(2)}] ${d.text}`);
  }
  const firstLyric = parsedLrc.find((l) => !l.isMarker);
  if (firstLyric) {
    const delta = firstLyric.t - vocalOnset;
    // Asymmetric check: a lyric line EARLIER than any vocal sound is a real
    // misalignment. Vocals earlier than the first lyric line are normal —
    // hums / adlibs before the first written line (e.g. 一直很安靜 has vocal
    // activity from ~19.6s but its first lyric at 25.19s).
    const lyricTooEarly = delta < -GATE_TOLERANCE_SEC;
    alignment = {
      vocal_onset_sec: round2(vocalOnset),
      first_lyric_sec: round2(firstLyric.t),
      delta_sec: round2(delta),
      verdict: lyricTooEarly ? 'warn' : 'ok',
    };
    if (lyricTooEarly) {
      console.warn(`! alignment doctor: first lyric ${firstLyric.t.toFixed(2)}s precedes vocal onset ${vocalOnset.toFixed(2)}s by ${(-delta).toFixed(2)}s (> ${GATE_TOLERANCE_SEC}s gate tolerance).`);
      console.warn(`  Do NOT hand-edit timeline.json — re-audit upstream instead:`);
      console.warn(`    python pipeline.py audit --layer2 --only "${record.title}"`);
    } else if (delta > GATE_TOLERANCE_SEC) {
      console.log(`✓ alignment doctor: vocal activity from ${vocalOnset.toFixed(2)}s, first lyric ${firstLyric.t.toFixed(2)}s (pre-lyric hum/adlib — OK)`);
    } else {
      console.log(`✓ alignment doctor: onset ${vocalOnset.toFixed(2)}s vs first lyric ${firstLyric.t.toFixed(2)}s (Δ ${delta.toFixed(2)}s)`);
    }
  }
}

const lyrics = buildLyricsArray(parsedLrc, duration || sections[sections.length - 1].end);

// Compose timeline.json
const timeline = {
  meta: {
    song_id: songId,
    title: record.title,
    artist: record.artist,
    duration: round2(duration || sections[sections.length - 1].end),
    bpm: 0,
    key: '',
    created_at: new Date().toISOString().slice(0, 10),
    version: 1,
    source: {
      dataset: 'MandpopDataset',
      youtube_url: record.youtube_url,
      lyricist: record.lyricist,
      composer: record.composer,
      album: record.album,
    },
    alignment,
  },
  sections,
  lyrics,
  cues,
  beats: [],
};

// Output paths
const outDir = path.join(REPO_ROOT, 'data', 'songs', songId);
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, 'timeline.json'), JSON.stringify(timeline, null, 2) + '\n');
console.log(`✓ wrote ${path.relative(REPO_ROOT, path.join(outDir, 'timeline.json'))}`);

// ---- Copy both audio tracks ----------------------------------------------
// original.mp3 = design preview (vocals heard while iterating on visuals)
// instrumental.m4a = karaoke / cover-recording version (catalog-blessed)

const audioOutDir = path.join(REPO_ROOT, 'public', 'audio');
fs.mkdirSync(audioOutDir, { recursive: true });

function copyAudio(src, dest) {
  if (fs.existsSync(dest) && fs.statSync(dest).size === fs.statSync(src).size) {
    console.log(`· ${path.relative(REPO_ROOT, dest)} already up to date`);
    return;
  }
  fs.copyFileSync(src, dest);
  console.log(`✓ copied ${path.basename(src)} → ${path.relative(REPO_ROOT, dest)}`);
}

let audioSrcRel = null;
let audioInstrumentalSrcRel = null;

const originalSrc = path.join(songDir, 'original.mp3');
if (fs.existsSync(originalSrc)) {
  copyAudio(originalSrc, path.join(audioOutDir, `${songId}.mp3`));
  audioSrcRel = `/audio/${songId}.mp3`;
} else {
  console.warn(`! original.mp3 not found at ${originalSrc} — design preview will be missing vocals`);
}

const instrumentalSrc = path.join(DATASET_ROOT, record.files.instrumental);
if (fs.existsSync(instrumentalSrc)) {
  copyAudio(instrumentalSrc, path.join(audioOutDir, `${songId}.m4a`));
  audioInstrumentalSrcRel = `/audio/${songId}.m4a`;
} else {
  console.warn(`! instrumental.m4a not found at ${instrumentalSrc}`);
}

if (!audioSrcRel && !audioInstrumentalSrcRel) {
  console.error(`✗ no audio copied at all — aborting before scaffolding broken config`);
  process.exit(1);
}

// ---- Energy curve (from the same audio the preview plays) ------------------
// Use the LOCAL copy: it's literally the signal the preview plays, and it
// survives dataset-side reshuffles (e.g. original.mp3 removed upstream after
// a song was already intaken here).

const localMp3 = path.join(audioOutDir, `${songId}.mp3`);
const localM4a = path.join(audioOutDir, `${songId}.m4a`);
const energySource = fs.existsSync(localMp3) ? localMp3 : localM4a;
const energy = computeEnergyCurve(ffmpeg, energySource);
if (energy) {
  const energyOut = {
    source: path.basename(energySource),
    rate: energy.rate,
    values: energy.values,
  };
  fs.writeFileSync(path.join(outDir, 'energy.json'), JSON.stringify(energyOut) + '\n');
  console.log(`✓ wrote ${path.relative(REPO_ROOT, path.join(outDir, 'energy.json'))} (${energy.values.length} samples @ ${energy.rate}Hz)`);
} else {
  console.warn(`! energy extraction failed — Remotion renders will fall back to flat energy`);
}

// Scaffold config.ts (only if it doesn't already exist — don't clobber edits)
const configPath = path.join(outDir, 'config.ts');
if (!fs.existsSync(configPath)) {
  const configContent = `import type { SongConfig } from '@/engine/types';
import { templatePalette } from '@/theme/palettes/_template';

const config: SongConfig = {
  songId: '${songId}',
  audioSrc: '${audioSrcRel ?? audioInstrumentalSrcRel}',${audioInstrumentalSrcRel ? `
  audioInstrumentalSrc: '${audioInstrumentalSrcRel}',` : ''}
  timelineSrc: '/data/songs/${songId}/timeline.json',
  palette: templatePalette,
  sceneMap: {
${[...new Set(sections.map((s) => s.type))]
  .map((t) => `    ${(t + ':').padEnd(13)}'SceneSilence',`)
  .join('\n')}
  },
};

export default config;
`;
  fs.writeFileSync(configPath, configContent);
  console.log(`✓ wrote ${path.relative(REPO_ROOT, configPath)}`);
} else {
  console.log(`· config.ts exists, not overwriting`);
}

// Scaffold notes.md if missing
const notesPath = path.join(outDir, 'notes.md');
if (!fs.existsSync(notesPath)) {
  const notes = `# ${record.title} — 設計筆記

> Intake 自 MandpopDataset (\`${chineseTitle}\`)，等風格對談後填寫。

## YouTube 參考
${record.youtube_url}

## 一句話情緒
（待風格對談）

## 核心意象（3 個以內）
1.
2.
3.

## 色溫走向
${sections.map((s) => s.type).join(' → ')}

## Section → Scene 對應表
（先用 config.ts 預設，對談後調整）

## 特殊 cue 視覺決策

## 字體決策
沿用預設

## 禁忌清單

## 跨 scene 統一語彙

## 生產紀錄
- Intake 日：${new Date().toISOString().slice(0, 10)}
- 開工日：
- 交付日：
- 總工時：
`;
  fs.writeFileSync(notesPath, notes);
  console.log(`✓ wrote ${path.relative(REPO_ROOT, notesPath)}`);
}

console.log(`\nDone. Visit http://localhost:5173/?song=${songId}`);
