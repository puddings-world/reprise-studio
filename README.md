# Reprise Studio

**個人翻唱歌手的視覺/動畫工作室。**

輸入是一首歌的 **song_id**（音檔與對齊好的歌詞時間軸早就在 dataset 裡備齊了），輸出是抒情抽象風格、可上 YouTube 的 Lyric MV — 瀏覽器即時預覽，Remotion 出 MP4。

職責邊界（這條請當作硬規則）：

- **Dataset (`MandpopDataPipeline`，本地 `D:\MandpopDataset`)**：負責所有 labeled data — 音源處理、人聲/伴奏分離、歌詞時間對齊、段落 / cue 標註。**本 repo 不碰這些。**
- **本 repo (`reprise-studio`)**：拿到對齊資料後，**純做視覺與動畫設計**。不處理音訊、不校對歌詞、不調時間戳。

對齊歌詞、剪音檔、跑語音分離、改 LRC 時間 — 全部回 dataset repo 修。在這邊只做「畫面怎麼漂亮」。

---

## 為什麼做這個

一般 AI 生成的 MV 看起來「可以但就這樣」。這個專案要反著做：

- **風格收斂到設計系統**：色、字、動畫都在 `docs/DESIGN.md` 裡寫死，不是每次隨興發揮
- **資料與視覺嚴格分離**：換歌不換 code，換畫面不動資料
- **可換的 agent 設計協定**：任何畫面都可以由不同 agent 獨立設計、隨時替換，見 `docs/AGENT_PROTOCOL.md`
- **最終可輸出 MP4**：Remotion 走標準流程，不靠瀏覽器錄影

---

## Quick start

需求：Node 18+。

```bash
npm install
npm run dev
```

Remotion（Phase 4 之後用）：

```bash
npm run remotion:studio
npm run remotion:render
```

翻唱動畫 MV（`tools/videogen`，Python，GPU 階段可在任何機器上跑）：

```bash
bash tools/videogen/scripts/setup.sh        # Windows: powershell -ExecutionPolicy Bypass -File tools/videogen/scripts/setup.ps1
videogen --project data/videogen/alaska doctor
```

---

## 翻唱動畫 MV（videogen）

第二條產線：把**自己的翻唱演出影片**依歌詞分鏡做成動畫 MV。流程是半自動的：每一階段先生成候選、出一頁審閱頁，你選圖或寫意見退件，只有被退的鏡頭會重做。

| # | 階段 | 怎麼做 | 你要決定的 |
|---|---|---|---|
| 0 | 開專案 | `videogen init --title 歌名 --video 演出.mp4` | |
| 1 | 角色設定 | `videogen character`：每種服裝 × 幾個種子各畫一張 | 選一個主角 |
| 2 | 依歌詞設計分鏡 | `videogen storyboard --lyrics 歌詞.lrc` 自動切鏡、標段落；每鏡的畫面、動態、光線由 Claude 和你一起寫（標 TODO 的欄位） | `review storyboard` 審分鏡表 |
| 3 | 關鍵幀 | `videogen keyframes` | 每鏡選圖或退件 |
| 4 | 表情調整（可選） | `videogen edit` | 原圖或調整後 |
| 5 | 動畫 | `videogen clips`：演唱鏡頭由原影片動作驅動（Wan-Animate-2），故事 / 意象鏡頭用圖生影片（Wan2.2-TI2V-5B） | 每段可退件 |
| 6 | 剪接 | `videogen assemble`：轉場、繁中歌詞、原音軌 | 看成品 |
| 7 | 封面 | `videogen cover` + `cover-title` | 選一張 |

- **不綁硬體**：依當下可用顯存自動選擇放置策略；`--host` 可把 GPU 階段送到別台機器跑，結果同步回本機，斷線可用 `attach` 接回。
- **換歌只換資料**：每首歌的資料在 `data/videogen/<song>/`，素材與產出不進 git。
- **第一首成品**：阿拉斯加海灣，3:43、43 個鏡頭，約 4 GPU 小時。

完整流程、技術路線（選用模型與理由、實測速度、試過放棄的做法、已知限制、下一步）、指令與疑難排解，見 [`tools/videogen/README.md`](tools/videogen/README.md)。工具鏈見 [`docs/toolchain.md`](docs/toolchain.md)。

---

## 翻唱錄音（規劃中）

另一半工作：用 dataset 的伴奏在 Mac 的 Logic Pro 錄翻唱，再把混音、人聲 stem 和演出影片帶回本 repo 給兩條視覺產線用。
目前只有規劃，尚未實作。分期（R0 Mac 環境、R1 錄音 kit、R2 Logic 範本、R3 演出影片、R4 匯回與對齊）、待決事項和「在 Mac 上從哪開始」見 [`docs/RECORDING.md`](docs/RECORDING.md)。

---

## 資料集契約（Dataset Contract）

Dataset (`MandpopDataPipeline`) 是 labeled data 的**唯一產地**：

- GitHub: <https://github.com/GeniusPudding/MandpopDataPipeline>
- 本地預設：`D:\MandpopDataset`（可用環境變數 `MANDPOP_DATASET` 覆寫）

### 權威介面：`processed_dataset.jsonl`

Dataset 對外的 catalog 是 `<MANDPOP_DATASET>/processed_dataset.jsonl` — 每一行是一首通過 **alignment gate**（Layer 1 VAD + Layer 2 WhisperX，verdict ∈ `{ok, fixed}`）的歌。本 repo 只認這個檔案裡的歌；沒在裡面的歌請先回 dataset repo 跑 `python pipeline.py add` / `audit`。

每筆 record 提供：

| 欄位 | 內容 |
|---|---|
| `title` / `artist` / `lyricist` / `composer` / `album` | 中繼資料 |
| `youtube_url` | 來源 |
| `files.instrumental` | `songs/<title>/instrumental.m4a`（AAC 192k，consumer-ready） |
| `files.lyrics` | `songs/<title>/lyrics.lrc`（alignment-verified） |

dataset 的 `songs/<title>/` 資料夾額外有 `original.mp3`（含人聲的 YouTube 原檔）— intake 也會搬過來給設計階段預覽用。注意：dataset 跑過 `pipeline.py compact` 後 `original.mp3` 會被刪除（可從 youtube_url 重抓）；intake 遇到缺檔會警告並繼續，已搬過的本地拷貝不受影響。

### 雙音檔策略

| 本 repo 檔名 | 來源 | 用途 |
|---|---|---|
| `public/audio/<song-id>.mp3` | dataset `original.mp3` | **設計預覽** — 帶人聲，方便對情緒與 cue 落點 |
| `public/audio/<song-id>.m4a` | dataset `instrumental.m4a` | **錄音/翻唱** — 純伴奏，使用者要錄自己的 cover 時播這個 |

`SongConfig.audioSrc` 預設指 mp3、`audioInstrumentalSrc` 指 m4a。前端 toggle 切換預計後續加。

### 本 repo 在 timeline 上補的東西

Dataset 給「**有時間軸的歌詞行**」；本 repo 補：

- **`sections[]`** — 段落邊界（intro / verse1 / chorus1 / bridge / ...）+ mood
- **`cues[]`** — 視覺特效時間點（flash-cold / color-flip / iris-open / ...）
- **`lyrics[i].end`** — 每句結束時間（dataset 只給開始時間）

sections / cues 是視覺設計決策，人工填在每首歌自己的 `data/songs/<song-id>/curation.json`（intake 找不到會自動 scaffold 模板並停下）。長期目標：搬進 dataset 變成 first-class 輸出（提案見 dataset repo 的 `PROPOSAL_ALIGNMENT_EXPORT.md`）。

Intake 同時做兩件品質工作：

- **Alignment doctor** — 用 ffmpeg `silencedetect` 掃 dataset 的 `vocals.flac` 找人聲 onset：(1) 砍掉 onset 之前的 credit 行（不依賴字面，比字首黑名單可靠）；(2) 第一句歌詞若**早於** onset 超過 0.5s 就警告（這代表上游對齊有問題，回 dataset 重跑 audit，不要改 timeline）。結果記在 `timeline.meta.alignment`。
- **能量曲線** — 從本地音檔預算 20Hz RMS 存成 `data/songs/<song-id>/energy.json`，給 Remotion 渲染（無法用即時 AnalyserNode）和 scrubber 模式用。

Schema 權威定義在 `src/engine/types.ts` 與 `examples/timeline.example.json`。

### 必備資產（per 歌）

```
data/songs/<song-id>/
├── curation.json    # 本 repo 寫：section 邊界 + mood + cue 點（intake 的輸入）
├── timeline.json    # intake 從 dataset 產出，入 git
├── energy.json      # intake 預算的 20Hz RMS 能量曲線，入 git
├── config.ts        # 本 repo 寫：section → scene 對應、palette、雙音檔路徑
└── notes.md         # 本 repo 寫：設計意圖、風格決策

public/audio/
├── <song-id>.mp3    # original.mp3：設計預覽含人聲（gitignored）
└── <song-id>.m4a    # instrumental.m4a：純伴奏給錄翻唱用（gitignored）
```

### Timeline JSON 規範

| 欄位 | 型別 | 說明 |
|---|---|---|
| `meta` | `TimelineMeta` | song_id / title / duration / bpm 等 |
| `sections[]` | `Section[]` | `{ t, end, type, mood }`，type 和 mood 是列舉 |
| `lyrics[]` | `TimelineEntry[]` | `{ t, end, text, emphasis? }`，時間單位秒 |
| `cues[]` | `Cue[]` | `{ t, type, label? }`，type 限定七種特效 |
| `beats?` | `number[]` | 選填；需要 beat-sync 才填 |

所有時間單位**秒（float，精度 10ms）**。允許的 `section.type` / `section.mood` / `cue.type` 列舉值請見 `src/engine/types.ts`。

> 資料 repo 若要擴充 schema：請先在本 repo 發 PR 同步 `types.ts` 和 `examples/timeline.example.json`，否則會被視為不合法的 timeline。

---

## 目錄結構

```
reprise-studio/
├── CLAUDE.md                       # Claude Code 專案守則（自動讀取）
├── README.md                       # 本檔
├── package.json
│
├── docs/
│   ├── AGENT_PROTOCOL.md           # ⭐ 如何操作 agent 做畫面（新）
│   ├── DESIGN.md                   # 視覺規範（scene / palette / typography / cue）
│   ├── ROADMAP.md                  # Phase 規劃與驗收
│   ├── WORKFLOW.md                 # 單首歌完整 SOP
│   ├── briefs/                     # Agent brief 模板
│   │   ├── scene-brief.template.md
│   │   └── palette-brief.template.md
│   └── templates/song_template/    # 新歌資料夾模板
│
├── examples/
│   ├── timeline.example.json       # Dataset 契約範例
│   └── scene.example.tsx           # Scene 寫法範例
│
├── src/
│   ├── main.tsx / App.tsx          # 入口
│   ├── theme/                      # tokens + palettes（設計系統）
│   ├── engine/                     # 換歌不動：時鐘、timeline、router、types
│   ├── scenes/                     # 一幕一檔（可被任何 agent 獨立替換）
│   ├── layers/                     # 跨 scene 疊加層（歌詞、grain、cue flash）
│   ├── remotion/                   # MP4 輸出
│   └── utils/                      # 載入、插值、音訊輔助
│
├── data/songs/<song-id>/           # 每首歌一個資料夾（timeline + config + notes）
├── data/videogen/<song>/           # 翻唱動畫 MV 專案（分鏡、提示詞、主機設定）
├── tools/videogen/                 # 翻唱動畫 MV 產線（Python）
├── public/audio/                   # 前端播放用音檔
└── out/                            # Remotion 輸出（.gitignore）
```

---

## 怎麼做一首新歌

前提：歌已經在 dataset 裡，包含對齊好的音檔 + 歌詞時間。如果還沒，請先去 `MandpopDataPipeline` 跑流水線。

1. **Intake**（一鍵從 dataset 搬進來）：

   ```bash
   node scripts/intake-from-mandpop.mjs <中文歌名> <kebab-song-id>
   ```

   第一次跑會 scaffold `data/songs/<song-id>/curation.json` 模板然後停下 —
   聽預覽音檔填好 section 邊界（+ mood）和 cue 點再跑一次。第二次會：
   跑 alignment doctor、產出 `timeline.json` / `energy.json` / `config.ts` /
   `notes.md`，並把音檔 copy 到 `public/audio/`。
2. 挑/調 palette：`src/theme/palettes/<song-id>.ts`
3. 風格對談 → 寫進 `notes.md`（見 `CLAUDE.md` §新歌 intake §4）
4. 依 `docs/AGENT_PROTOCOL.md` 為每個 section 寫 Scene Brief，派 agent 實作
5. 審收（AGENT_PROTOCOL §五 的驗收清單）
6. 細修 → Remotion 輸出 MP4

每一步的詳細 SOP 見 `docs/WORKFLOW.md`。

---

## Agent 操作協定（重點）

因為這個專案的核心假設是「畫面會持續迭代 / 探索 / 替換」，
我們把「怎麼叫 agent 做事」寫成了正式 protocol：`docs/AGENT_PROTOCOL.md`。

重點：

- **Scene 是單檔單位**，可以被任何 agent 獨立接手、替換、A/B 測試
- **標準 brief 模板**在 `docs/briefs/`，貼給 agent 就能開工
- **12 條不變量**（AGENT_PROTOCOL §二）是硬底線，違反即退回
- **驗收清單**（§五）把「符合美學」變成可檢查的項目，而不是玄學

並行探索多方向、切換 agent 供應商（Claude / Codex / 其他）、換設計師——都走同一個 protocol。

---

## 目前進度

依 `docs/ROADMAP.md`：

- [x] **Phase 0**：專案骨架、engine types、SceneSilence placeholder
- [ ] **Phase 1**：Timeline 載入與歌詞同步
- [ ] **Phase 2**：第一個完整 scene（SceneSilence 全實作）
- [ ] **Phase 3**：完整一首歌（所有 scenes + cue 特效 + 能量綁定）
- [ ] **Phase 4**：Remotion MP4 輸出
- [ ] **Phase 5**：第二首歌驗證流程複用性

---

## 技術棧（已決定，請勿擅自更換）

Vite + React 18 + TypeScript + Motion (framer-motion) + GSAP + Remotion + CSS Modules。
原生 `<audio>` + Web Audio AnalyserNode 做音訊分析。
詳見 `docs/ROADMAP.md`。
