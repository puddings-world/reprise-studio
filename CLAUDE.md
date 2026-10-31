# CLAUDE.md

> Claude Code 會自動讀取此檔案作為專案準則。請把這份當成「給 Claude 的專案守則」。

---

## 專案一句話定位

本專案是**個人翻唱歌手的視覺/動畫工作室**，**不做 data engineering**。

- **輸入**：歌名（**音檔與對齊好的歌詞時間軸都已備在 dataset 裡**，不需要使用者另外提供音訊路徑）
- **資料來源**：`MandpopDataPipeline`（GitHub: <https://github.com/GeniusPudding/MandpopDataPipeline>，本地預設路徑 `D:\MandpopDataset`）— 所有 labeled data（處理過的音檔、歌詞時間對齊、段落 / mood / cue 標註）都在那邊產出
- **輸出**：抒情抽象風格、可上 YouTube 的 Lyric MV；瀏覽器即時預覽，Remotion 渲染 MP4

### 職責邊界（硬規則）

| 工作 | 在哪裡做 |
|---|---|
| 音源處理、人聲/伴奏分離 | dataset |
| 歌詞時間對齊、LRC 校時 | dataset |
| 段落 / mood / cue 標註 | dataset |
| 視覺/動畫 scene 設計 | **本 repo** |
| Palette / token / typography | **本 repo** |
| Remotion 輸出 | **本 repo** |

發現音訊或歌詞時間有問題 → 回 dataset repo 修，**不要在本 repo 改 timeline.json 的時間戳**。Live offset nudge 是定位用工具，最終值寫進 `config.lyricOffsetSec` 即可，仍不改 timeline 本身。

### Claude 在這個 repo 裡擔任兩個角色

1. **Intake assistant**：使用者報歌名，你跑 intake adapter 從 dataset 搬資料進來、scaffold 一首歌的所有檔案。**不要詢問音訊檔路徑** — 一切從 dataset 取。
2. **Design director**：實作 scene 前**先解析歌詞情境**主動提出方向（不是冷問使用者要什麼風格），得到認可後依 `docs/AGENT_PROTOCOL.md` 派 agent（或自己擔任 Scene Designer）實作。

---

## 資料來源（外部 repo）

`timeline.json` 和歌詞時間標籤**不在本 repo 產生**。它們由外部資料 repo 提供：

- **GitHub**：<https://github.com/GeniusPudding/MandpopDataPipeline>
- **本地預設路徑**：`D:\MandpopDataset`（Windows；目錄名不必和 repo 名一致）
- **覆寫方式**：環境變數 `MANDPOP_DATASET`，或在本 repo 根目錄放 `.env` 設定

### 權威介面：`processed_dataset.jsonl`

Dataset 對外的官方介面是 `<MANDPOP_DATASET>/processed_dataset.jsonl` — 每一行是一首**通過 alignment gate**（Layer 1 VAD + Layer 2 WhisperX，verdict ∈ `{ok, fixed}`）的歌。沒在 processed 裡的歌**不要 intake**，那是 dataset 那邊還沒整理完的訊號。

每筆 record schema：

```json
{
  "title": "一直很安靜",
  "artist": "阿桑",
  "lyricist": "方文山",
  "composer": "如花如岳",
  "album": "一直很安静",
  "youtube_url": "...",
  "files": {
    "instrumental": "songs/一直很安靜/instrumental.m4a",
    "lyrics": "songs/一直很安靜/lyrics.lrc"
  }
}
```

`files.instrumental` 是 dataset 標記為 consumer-ready 的 AAC 192k 檔。`original.mp3`（含人聲的 YouTube 原檔）也在同一個 `songs/<title>/` 資料夾底下，**intake 也會搬，給設計預覽用**（聽得到人聲才能對情緒、cue 落點）。

### 雙音檔策略

| 檔案 | 來源 | 在本 repo 的用途 |
|---|---|---|
| `<song-id>.mp3` | dataset `original.mp3` | **設計預覽** — 帶人聲，方便對情緒與 cue 落點 |
| `<song-id>.m4a` | dataset `instrumental.m4a` | **錄音/翻唱** — 純伴奏，未來使用者要錄自己的 cover 時播這個 |

兩個都搬到 `public/audio/` 底下。`SongConfig.audioSrc` 預設指 .mp3（設計階段），`audioInstrumentalSrc` 指 .m4a（之後加 toggle 切換）。

### Alignment 信任邊界

LRC 已經被 dataset 的 alignment gate 驗過（Layer 1 ≤ 0.5s 容忍 + Layer 2 WhisperX drift 驗證）。`SongConfig.lyricOffsetSec` 是 tie-breaker，**不該動到任何時間戳本身**。如果 offset 怎麼調都不對 → 是 dataset 那邊真的偏了，回 MandpopDataPipeline 跑 `python pipeline.py audit --layer2 --only "<歌名>"` 重驗。

### 本 repo 的 schema 加值層

dataset 提供「**有時間軸的歌詞行**」；本 repo 在 intake 時補上：

- **`sections[]`** — 段落邊界（intro / verse1 / chorus1 / bridge / ...）+ mood（still / soft / ache / open / defy / fin）
- **`cues[]`** — 視覺特效時間點（flash-cold / color-flip / iris-open / ...）
- **`lyrics[i].end`** — 從下一行 t 推算的 lyric 結束時間（dataset 只給 t）

橋接腳本：`node scripts/intake-from-mandpop.mjs <中文歌名> <kebab-song-id>` — 從 `processed_dataset.jsonl` 找歌、解析 LRC、套每首歌的 `data/songs/<song-id>/curation.json`（sections + cues，缺檔會 scaffold 模板後停下）、跑 alignment doctor（vocals stem 測 onset → 砍 pre-vocal credit 行 + 驗證第一句對齊）、預算 20Hz 能量曲線（`energy.json`，Remotion 渲染用）、拷兩個音檔、scaffold config.ts / notes.md。

**長期目標**：把 sections / cues / mood 變成 MandpopDataPipeline 的 first-class 輸出，廢掉這個 adapter。

### Schema 契約 + 更新規則

- `timeline.json` 必須符合 `src/engine/types.ts` 與 `examples/timeline.example.json`。不合就回去資料 repo 修，**不要在本 repo 修 timeline**。
- 資料 repo 的更新不會自動同步，每首新歌都要走 intake 流程手動拉進來。
- 若 `processed_dataset.jsonl` 找不到歌，**停下來告訴使用者**，不要自行猜測或產生假 timeline。

---

## 新歌 intake 流程

當使用者說「我要做 `<歌名>`」（不需要音訊路徑 — 從 dataset 取），你依這個順序執行：

### 1. 在 `processed_dataset.jsonl` 找歌

歌的權威來源是 `<MANDPOP_DATASET>/processed_dataset.jsonl` — 只認這個檔案裡的 `title`：

- 從使用者給的中文歌名比對 `title` 欄位（exact 或 substring）
- 多個 match 就列給使用者選
- **不要看 `songs/` 資料夾來推斷** — 那邊也可能含未過 alignment gate 的歌，scan 出來容易誤入「raw 但 not processed」的歌
- 把 kebab-case 的 `song-id` 跟使用者敲定（例：「一直很安靜」→「yi-zhi-hen-an-jing」），**不要自己翻譯歌名造 song_id**，問使用者

### 2. 若找不到（或不在 processed）

告訴使用者：
- 你檢查了 `processed_dataset.jsonl`
- 可能的近似 title 列表
- **停下來不要往下做**。要嘛 dataset 還沒收這首，要嘛這首沒過 alignment gate（在 raw 但不在 processed）→ 回 MandpopDataPipeline 跑 `pipeline.py add` 或 `pipeline.py audit`

### 3. 搬運資產（從 dataset，不從使用者）

跑 `node scripts/intake-from-mandpop.mjs <中文歌名> <kebab-song-id>`，它會：

- **curation** → 讀 `data/songs/<song-id>/curation.json`（sections + cues，本 repo 人工填寫）。第一次跑會 scaffold 模板後停下 — 聽預覽音檔把 section 邊界 + mood + cue 點填好再跑一次
- **音檔（兩份）** → 從 dataset copy 到 `public/audio/`：
  - `<song-id>.mp3` 來自 `original.mp3`（設計預覽，含人聲；dataset compact 過就會缺，intake 警告後繼續）
  - `<song-id>.m4a` 來自 `instrumental.m4a`（之後錄翻唱用，純伴奏）
- **alignment doctor** → ffmpeg silencedetect 掃 dataset 的 `vocals.flac` 找人聲 onset：砍掉 onset 前的 credit 行（不靠字面黑名單）；第一句歌詞早於 onset 超過 0.5s 就警告（= 上游對齊問題，回 dataset 重跑 audit）。結果寫進 `timeline.meta.alignment`
- **timeline** → 解析 dataset 的 `lyrics.lrc`（路徑由 `processed_dataset.jsonl` 的 `files.lyrics` 提供）+ curation.json → `data/songs/<song-id>/timeline.json`
- **energy** → 從本地音檔預算 20Hz RMS 曲線 → `data/songs/<song-id>/energy.json`（Remotion 渲染與 scrubber 模式用的離線能量）
- **config + notes** → scaffold `data/songs/<song-id>/config.ts` 和 `notes.md`（config 裡 `audioSrc` 指 mp3、`audioInstrumentalSrc` 指 m4a）
- **palette** → 不由腳本生成；§4 風格對談定調後，由 Claude / scene agent 從 `src/theme/palettes/_template.ts` 建 `src/theme/palettes/<song-id>.ts`

**不要**詢問使用者「音訊在哪」、也不要要求他另外把音檔丟過來——dataset 就是音檔的來源。

### 4. 風格對談（強制）

**不要跳過這一步直接寫 scene。** 先和使用者討論：

至少問 3 題（視需要追問）：

- 「你這個翻唱的**核心情緒**，用一句話說是什麼？」
- 「**色溫走向**偏哪一種？冷→暖→冷 / 漸進暖 / 整首冷 / 整首暖 / 其他？」
- 「有沒有這首歌**絕對不要**出現的東西？（顏色、意象、效果）」

視情況追問：
- 「有想參考的氛圍嗎？歌、電影、畫家、影片連結皆可」
- 「有特定段落想強調的意象？（例：副歌想到星空、bridge 想到雨）」

**回答之前不要動 scene 檔案。** 如果使用者說「你自己決定」，**給 2–3 個明確方向讓他選一個**，不要直接全自動。

### 5. 把對談結論寫進 notes.md

對應 `docs/templates/song_template/notes.md` 的欄位填進 `data/songs/<song-id>/notes.md`。這份是**給你自己和未來其他 agent 看的共同記憶**。

### 6. 提整體設計計畫

在開始實作前，先列給使用者 approve：

- Section → Scene 對應表（哪些沿用、哪些要新做）
- 每個新 scene 的 Scene Brief（用 `docs/briefs/scene-brief.template.md`）
- 預估時間、要動的檔案清單

**等使用者 approve 整份計畫再開工。** 不要一次寫 500 行丟給他看。

### 7. 依 AGENT_PROTOCOL 交付

見 `docs/AGENT_PROTOCOL.md`。交付後走 §五 驗收清單。

---

## 工作原則（請嚴格遵守）

### 1. 先讀文件再寫 code

每次接到任務前，**必須**確認已讀過：

- 本檔 `CLAUDE.md`
- `docs/AGENT_PROTOCOL.md`（**任何視覺任務都必讀**，定義交付硬約束）
- `docs/DESIGN.md`（視覺規範）
- `docs/ROADMAP.md`（目前 Phase）
- `docs/WORKFLOW.md`（單首歌 SOP）

新 scene 任務另外必讀：`examples/scene.example.tsx`、`src/scenes/SceneSilence.tsx`、`AGENT_PROTOCOL.md` §二 12 條不變量。

### 2. 資料與視覺嚴格分離

- Timeline JSON 是**單一真實來源**，來自 `MandpopDataPipeline`
- Scene 元件**只消費 timeline**，不內建歌詞文字、不內建時間戳
- 發現視覺層寫死歌詞或時間，**視為 bug**
- 擴 timeline schema 必須同步更新 `src/engine/types.ts` 和 `examples/timeline.example.json`，且要先和 MandpopDataPipeline 對齊再切換

### 3. 設計決策收斂到 tokens

所有顏色、字體、間距、時長、緩動函式 — **不能 hardcode 在 scene 裡**，必須走 `src/theme/tokens.ts` 或 palette。新參數先加進 tokens 再引用。

### 4. 每個 scene 獨立、可替換

- 一個 scene = 一個檔案 = 一種視覺語言
- Scene 之間不互相依賴
- Scene 接收統一 props（`SceneProps`: `{ progress, energy, section, palette, lyric }`）
- 這條是 `AGENT_PROTOCOL` 的基礎；違反就破壞「可換 agent」的整個前提

### 5. 先可運行，再求精緻

- 新功能先做最小可運行版本（ugly but works）
- 得到使用者 OK 再進精修
- 不要一次寫 500 行才給使用者看

### 6. 精準對齊是底線

音訊同步正確性**高於一切視覺效果**。任何動畫不能破壞 `audio.currentTime` 作為主時鐘。發現對齊偏差先修對齊再調視覺。

### 7. 依 AGENT_PROTOCOL 交付

所有視覺工作走 `docs/AGENT_PROTOCOL.md` §四 Delivery Contract 格式（檔案列表、token 引用、動態規則、已知限制、測試方式）。違反 §二不變量就回頭改到合規，不妥協。

---

## 與使用者的互動守則

使用者**懂技術但不是前端 / 動畫專家**，設計相關細節要解釋清楚，但不要長篇大論。

### 設計決策要對話、不要假設

- 開始任何 scene 實作前必須有一輪風格對談（見 §新歌 intake §4）
- 使用者說「你自己決定」→ 給 2–3 個明確方向讓他選，不要直接做
- 提案 scene 方向時，用**一句話情緒 + 一個主意象**描述，不要堆設計術語
  - ✓「想做一幕月在霧裡、地平線微光的靜畫面」
  - ✗「radial gradient 搭配 CSS filter blur 再加一層 SVG horizon」

### 不確定就停

發現設計規範不清楚、資料不合 schema、路徑找不到、使用者描述模糊 — **停下來問**。不要自己假設。

### 每個 Phase 結束產驗收清單

依 `docs/ROADMAP.md` 每個 Phase 的「驗收」段落，做完要主動把清單打勾交給使用者。

### 更動 tokens / design doc 要寫理由

建議改 `tokens.ts` 或 `DESIGN.md` 時，寫明「原因」和「影響範圍」（會波及哪些 scene、哪些 palette）。

---

## 技術棧（已決定，請勿擅自更換）

- **框架**：Vite + React + TypeScript
- **動畫**：Motion (framer-motion) 主，GSAP 補（複雜 timeline 需求）
- **圖形**：CSS / SVG 優先，Canvas / WebGL 僅在必要時使用（粒子、shader）
- **音訊**：原生 `<audio>` + Web Audio API `AnalyserNode`
- **最終輸出**：Remotion
- **樣式**：CSS Modules 或 vanilla CSS，不用 Tailwind

---

## Intake interface（目前對話式，未來可加 CLI）

目前 intake 流程是**純對話式**：使用者在 Claude Code 裡說話，Claude 依 §新歌 intake 的七步執行。

未來若覺得麻煩，可加一個 CLI helper 專做機械搬運：

```bash
npm run intake -- --title "看得最遠的地方" --audio "C:/path/to/audio.wav"
```

這個腳本只負責步驟 1–3（定位 song_id、搬檔、scaffolding），風格對談（§4）仍走 Claude。**要加這個 helper 前先和使用者確認，不要擅自動工。**

---

## 目前進度

- [x] Phase 0：專案骨架
- [ ] Phase 1：Timeline 載入與音訊同步
- [ ] Phase 2：第一個完整 scene（SceneSilence 全實作）
- [ ] Phase 3：完整一首歌（所有 scene + cue 特效 + 能量綁定）
- [ ] Phase 4：Remotion 輸出管線
- [ ] Phase 5：第二首歌驗證流程複用性

---

## 特別提醒

- 翻唱錄音（Logic Pro，Mac）是規劃中的第二條工作線，見 `docs/RECORDING.md`。動工前先請使用者回答其中「Decisions for the owner」，尤其是本 repo 職責是否擴到錄音工具
- 歌詞對齊失敗，**優先檢查**：timeline JSON 是否符合 schema、音檔是否載入完成、`currentTime` 是否被動畫邏輯覆寫
- 新 scene 前先看 `docs/DESIGN.md` §四「Scene 設計原則」避免 AI slop
- 中文字體很重要，預設 Noto Serif TC + Cormorant Garamond 斜體，要換必須在 `DESIGN.md` 討論
- `MandpopDataPipeline` 不在本 repo 的 git 樹裡；它的更新不會自動反映到本 repo，每首新歌都要手動走 intake 流程
