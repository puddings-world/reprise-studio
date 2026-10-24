# Scene Brief: SceneDustLight

> 必讀：`docs/AGENT_PROTOCOL.md`（agent 不讀 protocol 就拒收）。
> 必讀：`CLAUDE.md` 工作原則 §1-7、`docs/DESIGN.md` §四「Scene 設計原則」。

## 1. 定位

- **song_id**: `bu-neng-shuo-de-mi-mi`（周杰倫 — 不能說的秘密）
- **section(s)**: `pre_chorus` / `chorus1` / `bridge` / `chorus_last`
- **mood**: `ache`（pre_chorus / chorus1 / bridge），`open`（chorus_last）
- **palette reference**: `@/theme/palettes/bu-neng-shuo-de-mi-mi` (`buNengShuoDeMiMiPalette`)
  - `ache`: `primary = wound (#3a1e24)`, `accent = warm (#f2a65a)`
  - `open`: `primary = paper (#f5efe3)`, `accent = warm`

## 2. 情緒一句話

「廢棄琴房裡的一道斜光，光柱中漂浮著塵埃 — 時間像被慢動作拉長的一刻。」

歌詞參考（不要在 scene 渲染）：
- 「最美的不是下雨天，是曾與你躲過雨的屋簷」
- 「你說把愛漸漸放下會走更遠」
- 「或許命運的籤，只讓我們遇見」
- 「飄落後才發現，這幸福的碎片，要我怎麼撿」

## 3. 主視覺意象（最多三個）

1. **斜光柱**：從畫面左上到右下的對角光柱，寬度約畫面 25-35%（用 `clamp(180px, 28vw, 380px)`）。實作建議：絕對定位的細長矩形，`transform: rotate(-28deg)`，背景 `linear-gradient` 從 `transparent → color-mix(in srgb, var(--scene-accent) X%, transparent) → transparent`（中間最亮），`filter: blur(6-12px)`。光柱**本身不動**（不要 translate 它），但 alpha 可隨 energy 微微呼吸。
2. **漂浮塵埃**：在光柱範圍內可見的 12-18 個 1-2px 亮點 — absolutely-positioned `div`，每個獨立的 `@keyframes`（緩慢 `translate` 漂移 + 一點 opacity 起伏），週期 **5-9s**（必須 ≥ 3s 才符合 AGENT_PROTOCOL）。塵埃在光柱外（畫面其他地方）alpha 要趨近 0，產生「只在光柱中看得到」的錯覺 — 可以用一個 `mask` 或者直接設定 dust 的位置都集中在光柱座標範圍內、配 lower base alpha。
3. **遠景暈影**：背景是深沉的 sepia radial gradient（`color-mix` 從 `var(--scene-primary)` 派生），中心稍亮一圈、邊緣暗下去，再疊一層 vignette 收暗最外圈。

## 4. 動態規則（能量綁定）

- `beamAlpha = 0.5 + energy * 0.25`（光柱亮度）
- `dustVisibility = 0.6 + energy * 0.3`（高潮時塵埃更實）
- `dustDriftSpeedMul = 1 + energy * 0.4`（高潮時塵埃漂得稍快 — 改 animation-duration 或乘法）
- `brightness = 0.5 + energy * 0.2`

所有數值經 React `useMemo` 推到 CSS custom properties。**禁止寫死任何 hex / rgba**。

## 5. 進退場

- **Scene 進場**：fade in **1.6s**（這場戲是「回憶湧現」，慢慢來）
- **Scene 退場**：由 `BaseScene` 統一處理

## 6. 禁忌

- ❌ 不要出現琴鍵的具象（黑白條 / 鍵盤格）— 太字面了，用塵埃 + 光柱暗示鋼琴空間
- ❌ 不要使用 `cold` (鋼琴藍) — 整首歌不該有冷感
- ❌ 不要使用 `sun` (高飽和金黃) — 那是慶典的金，這裡是泛黃舊照的暖
- ❌ 不要快速閃爍 / 高頻動畫 — 時間感是慢的，連塵埃都緩慢
- ❌ 不要寫死 hex / rgba
- ❌ 不要在 scene 內讀歌詞
- ❌ 不要使用 `position: fixed` 或脫離 `BaseScene` 容器
- ❌ 動畫週期不得短於 3 秒

## 7. 交付物

- `src/scenes/SceneDustLight.tsx`
- `src/scenes/SceneDustLight.module.css`
- 在 `src/scenes/registry.ts` 加一行註冊（key 為字串 `'SceneDustLight'`）
- **不要**動 `data/songs/bu-neng-shuo-de-mi-mi/config.ts` — sceneMap 已設好

## 8. 參考

- `docs/DESIGN.md` §四
- `docs/AGENT_PROTOCOL.md` §二 12 條不變量
- 既有範本（**先讀**）：
  - `src/scenes/SceneSilence.tsx` + `.module.css`
  - `src/scenes/SceneNameless.tsx` + `.module.css`
- 同 song palette：`src/theme/palettes/bu-neng-shuo-de-mi-mi.ts`
- Tokens：`src/theme/tokens.ts`

---

## 備註區

- 用到的 tokens：
- 已知限制：
- prefers-reduced-motion 處理：
