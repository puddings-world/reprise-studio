# Scene Brief: SceneDefyLines

> 必讀：`docs/AGENT_PROTOCOL.md`（agent 不讀 protocol 就拒收）。
> 必讀：`CLAUDE.md` 工作原則 §1-7、`docs/DESIGN.md` §四「Scene 設計原則」。

## 1. 定位

- **song_id**: `jue-jiang`（五月天 — 倔強）
- **section(s)**: `pre_chorus` / `chorus1` / `chorus2` / `verse2` / `bridge` / `chorus_last`（這個 scene 撐起整首歌的「有人聲」段落）
- **mood**: `defy`（verse / pre_chorus / chorus1 / chorus2 / bridge），`open`（chorus_last 啦啦合唱段）
- **palette reference**: `@/theme/palettes/jue-jiang` (`jueJiangPalette`)
  - `defy`: `primary = ink (#0b0f14)`, `accent = sun (#ffd27d)`
  - `open`: `primary = sun`, `accent = warm (#f2a65a)`

## 2. 情緒一句話

「逆風衝刺的姿態 — 黑底中有幾道金光斜劃，像被風吹起的線條，邊緣有速度感的拖尾；副歌結尾整個畫面打開、共感釋放。」

歌詞參考（不要在 scene 渲染）：
- 「我和我最後的倔強，握緊雙手絕對不放」
- 「逆風的方向，更適合飛翔」
- 「我不怕千萬人阻擋，只怕自己投降」

## 3. 主視覺意象（最多三個）

1. **斜向速度線（4-7 條）**：從畫面右下到左上斜向（旋轉約 `-22deg` 到 `-32deg`）的細長矩形 — `linear-gradient` 細條，主色用 `var(--scene-accent)`（defy 時是 sun），邊緣 `filter: blur(4-8px)`。每條獨立 `transform: translate` 動畫，從畫面外（右下角外）向內衝過去後消失，週期 1.5-3s，stagger 起始時間 0-2s。**動畫週期不要短於 1.5s**（雖然 AGENT_PROTOCOL §二要求 ≥3s 是給 ambient 動畫的；速度線是 cue-driven 衝刺感，可以更短但仍要克制 — 用 stagger 而非高頻達到密度感）。
2. **遠處地平線光帶**：底部 22-28% 處一條水平的光暈 — `radial-gradient` 拉很扁的 ellipse，主色 `var(--scene-accent)`，alpha 隨 energy 漲。象徵衝向的方向、未來的光。
3. **稀疏粒子塵埃（可選）**：6-12 個 1-2px 的亮點，CSS `box-shadow` 或 absolutely-positioned `div`，每個獨立 `animation` 沿線條方向飄移。可以省略 — 但如果保留，**動畫週期 ≥ 3s**。

## 4. 動態規則（能量綁定）

- `lineCount`: section 切換時計算 = `floor(4 + sectionEnergy * 3)`（4-7），section 內**不變**。`sectionEnergy` 在這個 scene 內可用 `energy` 的瞬時值近似（沒有真實的 section-mean，先用 energy）— 注意：在 React 中要 useState + section key 變化時更新，不要每 frame 重算。
- `lineSpeedMul = 1 + energy * 0.8`（能量大時線條飆更快 — 影響 animation-duration 或 keyframe 的 translate 距離）
- `horizonAlpha = 0.3 + energy * 0.4`
- `brightness = 0.7 + energy * 0.25`

數值經 React `useMemo` 推到 CSS custom properties。**禁止寫死任何 hex / rgba**。

## 5. 進退場

- **Scene 進場**：快速 fade-in **0.4s**（這場戲是「衝出來」，不要慢慢 fade — 但仍透過 `BaseScene`，不要自己寫進場 keyframe）
  - 註：`BaseScene` 預設可能是更長的 fade。如果它接受 prop 控制 duration，傳 0.4；如果不行，**不要**在 scene 內疊一層自己的 fade，回報這個限制由我來改 `BaseScene`。
- **Scene 退場**：由 `BaseScene` 統一處理

## 6. 禁忌

- ❌ 不要出現具象人型 / 臉 / 手 — 用線條表達身體姿態，不要畫人
- ❌ 不要使用 `wound` / `blush` / `cold` — 這場戲不是傷感的，也不是冷的
- ❌ 線條不要過於密集或工業感（像螢光棒 / 跑馬燈 / 條碼）— 要有「手繪 / 即興」感（邊緣 blur、不對齊、stagger）
- ❌ 不要寫死 hex / rgba
- ❌ 不要在 scene 內讀歌詞
- ❌ 不要使用 `position: fixed` 或脫離 `BaseScene` 容器
- ❌ 動畫週期不得短於 1.5s（速度線專屬例外）；其他元素 ≥ 3s

## 7. 交付物

- `src/scenes/SceneDefyLines.tsx`
- `src/scenes/SceneDefyLines.module.css`
- 在 `src/scenes/registry.ts` 加一行註冊（key 為字串 `'SceneDefyLines'`）
- **不要**動 `data/songs/jue-jiang/config.ts` — sceneMap 已設好

## 8. 參考

- `docs/DESIGN.md` §四
- `docs/AGENT_PROTOCOL.md` §二 12 條不變量
- 既有範本（**先讀**）：
  - `src/scenes/SceneSilence.tsx` + `.module.css`
  - `src/scenes/SceneNameless.tsx` + `.module.css`（CSS vars + color-mix 的純 CSS 模式）
- 同 song palette：`src/theme/palettes/jue-jiang.ts`
- Tokens：`src/theme/tokens.ts`

---

## 備註區

- 用到的 tokens：
- 已知限制：
- prefers-reduced-motion 處理：
