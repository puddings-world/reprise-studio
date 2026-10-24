# Scene Brief: SceneSteamTable

> 必讀：`docs/AGENT_PROTOCOL.md`（agent 不讀 protocol 就拒收）。
> 必讀：`CLAUDE.md` 工作原則 §1-7、`docs/DESIGN.md` §四「Scene 設計原則」。

## 1. 定位

- **song_id**: `yi-hun-yi-su`（毛不易 — 一葷一素）
- **section(s)**: `chorus1` / `chorus2` / `chorus_last`
- **mood**: `ache`（但這首歌的 ache 是月光 + 蒸氣 + 思念，**不是** wound / 血色）
- **palette reference**: `@/theme/palettes/yi-hun-yi-su` (`yiHunYiSuPalette`)
  - chorus 走 `ache` palette entry：`primary = sun (#ffd27d)`, `accent = paper (#f5efe3)`

## 2. 情緒一句話

「半夜對著空椅子說話，蒸氣從一鍋飯緩緩上升，像來訪的影子，又像捨不得散去的記憶。」

歌詞參考（不要在 scene 裡渲染這些文字，由 `LyricLayer` 負責；只是給你抓情緒）：
- 「月兒明 風兒輕，可是你在敲打我的窗欞」
- 「其實我過的還可以」
- 「一定是你來時太小心，怕我再想起你」

## 3. 主視覺意象（最多三個）

1. **餐桌剪影帶**：畫面下方 22-30% 處的一條深色水平剪影帶。象徵木桌邊緣 — 不畫桌腳、不畫盤子、不畫食物。CSS `linear-gradient` 或單一深色 box，邊緣有 1-2px 羽化。剪影色從 `var(--scene-ink)` 取，alpha 約 0.7-0.85。
2. **蒸氣柱（2-3 道）**：從餐桌剪影上緣升起的細長垂直蒸氣 — CSS `filter: blur(18-28px)`，配 `linear-gradient(180deg, transparent → accent 半透明 → transparent)` 的細條 (寬度 clamp 30-60px)，alpha 隨高度衰減到 0。每道有獨立的緩慢動畫：`translateY` 從桌面慢慢往上飄、`translateX` 用 sine 微擺。週期 6-10s，stagger 起始時間不要同步。
3. **暖光暈**：偏右上的一盞 radial-gradient ellipse 光源（例如 `left: 65-75%`、`top: 18-32%`），向桌面方向照下。色彩用 `color-mix(in srgb, var(--scene-primary) X%, transparent)`，飽和度低、邊緣非常柔。象徵一盞夜燈、廚房未關的燈。

## 4. 動態規則（能量綁定）

- `brightness = 0.5 + energy * 0.2`（chorus 比 verse 暖，但不要過亮 — 這是記憶不是慶典）
- `steamAlpha = 0.4 + energy * 0.2`（高潮時蒸氣更實，但 cap 在 0.6）
- `steamRiseSpeedMul = 1 + energy * 0.3`（能量大時蒸氣稍微加速）
- `lampGlow = 0.6 + energy * 0.15`（暖光跟著呼吸）

所有上面四個數值經 React `useMemo` 推到 CSS custom properties（如 `--scene-steam-alpha`、`--scene-lamp-glow`），CSS module 用 `color-mix()` / `calc()` 從這些 vars 推導實際顏色與動畫參數。**禁止寫死任何 hex / rgba**。

## 5. 進退場

- **Scene 進場**：fade in **1.2s**（透過 `BaseScene` 提供的默認 fade，scene 自己不要寫進場 keyframe）
- **Scene 退場**：由 `BaseScene` 統一處理，scene 不寫 exit 動畫

## 6. 禁忌

- ❌ 不要出現任何具象「人形 / 臉 / 手 / 食物 / 餐具」— 這場戲的力量在於「沒有人」
- ❌ 不要使用 `wound` (酒紅色) 或 `blush` — 整首歌不該有「身體傷痕 / 紅暈」的暗示
- ❌ 不要快速閃爍 / 強對比 / 高頻動畫 — 蒸氣的時間感是慢的
- ❌ 不要寫死任何 hex / rgba / px-only color（除非從 token 推導）
- ❌ 不要在 scene 內讀歌詞文字（歌詞 = LyricLayer 的職責）
- ❌ 不要使用 `position: fixed` 或脫離 `BaseScene` 的容器
- ❌ 動畫週期不得短於 3 秒（除了能量驅動的 brightness/alpha 漸變，可以即時）

## 7. 交付物

- `src/scenes/SceneSteamTable.tsx`
- `src/scenes/SceneSteamTable.module.css`
- 在 `src/scenes/registry.ts` 加一行註冊（key 為字串 `'SceneSteamTable'`）
- **不要**動 `data/songs/yi-hun-yi-su/config.ts` — 我已經設好 `sceneMap` 指向 `'SceneSteamTable'`

## 8. 參考

- `docs/DESIGN.md` §四「Scene 設計原則」
- `docs/AGENT_PROTOCOL.md` §二 12 條不變量
- 既有範本（**先讀完再開工**）：
  - `src/scenes/SceneSilence.tsx` + `.module.css`
  - `src/scenes/SceneNameless.tsx` + `.module.css`（這個更接近你要做的 — vars + color-mix 的純 CSS 模式）
- 同 song 的 palette：`src/theme/palettes/yi-hun-yi-su.ts`
- Tokens：`src/theme/tokens.ts`（你需要的暖色都在 color.warm / color.sun / color.paper）

---

## 備註區（給 agent 自由筆記，回報時用 — Delivery Contract §四）

- 用到的 tokens：
- 已知限制：
- prefers-reduced-motion 處理：
