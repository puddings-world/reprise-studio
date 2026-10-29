"""Self-contained HTML review pages (images inlined) for the character, storyboard, keyframes, edit and clips
stages.

The page's "Copy feedback" button produces the text `feedback.parse` reads, so the loop is:
generate -> review page -> paste feedback -> `videogen feedback` -> re-run the stage (only rejected shots).
"""
from __future__ import annotations

import base64
import html
import io
from pathlib import Path

from . import media
from .character import CHAR
from .draft import TODO
from .stages import Project

KIND_LABEL = {"perform": "演唱", "story": "故事", "image": "意象"}
INTRO = {
    "character": "每張是一個服裝 × 一個種子。點一張當主角（之後每個鏡頭都以它為準）。都不行就勾「全部重畫」並寫想改什麼。",
    "storyboard": "上方色條是整首歌的鏡頭節奏。逐鏡看歌詞、畫面與動態描述，標紅的是還沒寫的地方。想改的鏡頭在欄位裡寫備註。",
    "keyframes": "每個鏡頭點一張要用的圖（預設第一張）。都不行就勾「重做」並寫想改什麼。演唱鏡頭左邊是原影片那一格，動作照原影片走，這裡只選長相與光線。",
    "edit": "左邊是原圖、右邊是表情調整後。點要用的那張；調整後的不理想也可以勾「重做」寫備註。",
    "clips": "每段動畫取五格預覽（完整片段在 work/clips）。要重做就勾選並寫想改的動作或鏡頭運動。",
}


def _img(path: Path, width: int = 560) -> str:
    from PIL import Image
    if not path.exists():
        return ""
    im = Image.open(path).convert("RGB")
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _strip(path: Path) -> str:
    from PIL import Image
    frames = media.read_video(path, (480, 270))
    buf = io.BytesIO(); Image.fromarray(media.contact_strip(frames, 5, 240)).save(buf, "JPEG", quality=78)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _option(sid: str, value: str, src: str, label: str, selected: bool) -> str:
    return (f'<button type="button" class="pick" data-shot="{sid}" data-value="{value}" '
            f'aria-pressed="{str(selected).lower()}"><img src="{src}" alt="{sid} {label}" loading="lazy">'
            f'<span>{html.escape(label)}</span></button>')


def _todo(text: str) -> str:
    """Escaped text; anything still marked TODO is highlighted."""
    cls = ' class="todo"' if TODO in text else ""
    return f"<span{cls}>{html.escape(text)}</span>"


def _storyboard_rows(p: Project, only: list[str] | None) -> list[str]:
    rows = []
    entries = p.prompts.d.get("shots", {})
    for s in p.shots(only):
        sid = s["id"]
        if s["kind"] == "perform":
            plan = [("畫面", f"演唱（{s.get('framing', '?')}），動作依原影片")]
        else:
            e = entries.get(sid, {})
            plan = [("畫面", e.get("keyframe", "TODO")), ("動態", e.get("motion", "TODO"))]
        plan.append(("光線", s.get("light_prompt", "")))
        if s.get("note"):
            plan.append(("備註", s["note"]))
        lyric = html.escape("／".join(s.get("lyrics", [])) or "（間奏）")
        dl = "".join(f"<dt>{k}</dt><dd>{_todo(v)}</dd>" for k, v in plan)
        rows.append(f"""
<article class="shot {s['kind']}" id="{sid}">
  <div class="meta"><b>{sid}</b><span>{s['start']:.1f}–{s['end']:.1f}s</span>
    <i class="kind">{KIND_LABEL[s['kind']]}</i><span>{html.escape(s.get('section', ''))}</span></div>
  <div class="body">
    <p class="lyric">{lyric}</p>
    <dl class="plan">{dl}</dl>
    <div class="ctl"><span>轉場：{html.escape(s['transition_in'])}</span>
      <input type="text" class="note" id="note-{sid}" data-shot="{sid}" placeholder="這一鏡想怎麼改（選填）"></div>
  </div>
</article>""")
    return rows


def _timeline(p: Project) -> str:
    """The whole song as one bar: one segment per shot, coloured by kind, labelled by section."""
    segs, labels, prev = [], [], None
    for s in p.shots():
        span = s["end"] - s["start"]
        segs.append(f'<a href="#{s["id"]}" class="seg {s["kind"]}" style="flex-grow:{span:.2f}" '
                    f'title="{s["id"]} {s["start"]:.1f}s {KIND_LABEL[s["kind"]]}"></a>')
        sec = s.get("section", "")
        labels.append(f'<span style="flex-grow:{span:.2f}">{html.escape(sec) if sec != prev else ""}</span>')
        prev = sec
    legend = " ".join(f'<i class="seg {k}"></i>{v}' for k, v in KIND_LABEL.items())
    return (f'<div class="tl" aria-label="分鏡時間軸">{"".join(segs)}</div>'
            f'<div class="tl-labels">{"".join(labels)}</div><p class="legend">{legend}</p>')


def _character_rows(p: Project) -> list[str]:
    st = p.state.shot(CHAR)
    if not st["candidates"]:
        return []
    options = []
    for c in st["candidates"][-12:]:
        tag = Path(c).stem.removeprefix("char_")
        options.append(_option(CHAR, tag, _img(p.work / c, 360), tag, c == st["pick"]))
    return [f"""
<article class="shot" id="{CHAR}">
  <div class="meta"><b>角色</b><span>{len(st['candidates'])} 張</span></div>
  <div class="body">
    <div class="row grid">{''.join(options)}</div>
    <div class="ctl"><label><input type="checkbox" class="redo" id="redo-{CHAR}" data-shot="{CHAR}"> 全部重畫</label>
      <input type="text" class="note" id="note-{CHAR}" data-shot="{CHAR}" placeholder="想改什麼（選填）"></div>
  </div>
</article>"""]


def build(p: Project, stage: str, only: list[str] | None = None) -> Path:
    lead = ""
    if stage == "character":
        rows = _character_rows(p)
    elif stage == "storyboard":
        rows, lead = _storyboard_rows(p, only), _timeline(p)
    else:
        rows = _production_rows(p, stage, only)
    title = p.cfg.get("title", p.cfg.get("name", "MV"))
    page = (TEMPLATE.replace("{{TITLE}}", html.escape(title)).replace("{{STAGE}}", stage)
            .replace("{{INTRO}}", INTRO[stage]).replace("{{LEAD}}", lead)
            .replace("{{ROWS}}", "".join(rows) or "<p>這個階段沒有可審的鏡頭。</p>"))
    out = p.work / "review" / f"{stage}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def _production_rows(p: Project, stage: str, only: list[str] | None) -> list[str]:
    rows = []
    for s in p.shots(only):
        sid, st = s["id"], p.state.shot(s["id"])
        extra, options = "", []
        if stage == "keyframes":
            if not st["candidates"]:
                continue
            if s["kind"] == "perform":
                src = _img(p.work / "keys" / f"{sid}_source.png", 280)
                extra = f'<figure class="src"><img src="{src}" alt="{sid} 原影片"><figcaption>原影片</figcaption></figure>'
            for c in st["candidates"][-4:]:
                tag = c.rsplit("_", 1)[1].removesuffix(".png")
                options.append(_option(sid, tag, _img(p.work / c), tag, c == st["pick"]))
        elif stage == "edit":
            if not st["edit"]:
                continue
            options = [_option(sid, "orig", _img(p.work / st["pick"]), "原圖", not st["use_edit"]),
                       _option(sid, "edit", _img(p.work / st["edit"]), "調整後", st["use_edit"])]
        else:
            if not st["clip"]:
                continue
            extra = f'<img class="strip" src="{_strip(p.work / st["clip"])}" alt="{sid} 動畫預覽">'
        lyric = html.escape("／".join(s.get("lyrics", [])) or "（間奏）")
        rows.append(f"""
<article class="shot {s['kind']}" id="{sid}">
  <div class="meta"><b>{sid}</b><span>{s['start']:.1f}–{s['end']:.1f}s</span>
    <i class="kind">{KIND_LABEL[s['kind']]}</i><span class="sw l-{s.get('light', 'night')}"></span></div>
  <div class="body">
    <p class="lyric">{lyric}</p>
    <div class="row n{len(options) + (1 if extra and stage == 'keyframes' else 0)}">{extra}{''.join(options)}</div>
    <div class="ctl"><label><input type="checkbox" class="redo" id="redo-{sid}" data-shot="{sid}"> 重做</label>
      <input type="text" class="note" id="note-{sid}" data-shot="{sid}" placeholder="想改什麼（選填）"></div>
  </div>
</article>""")
    return rows


TEMPLATE = r"""<title>{{TITLE}} · {{STAGE}}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@1,500&family=Noto+Serif+TC:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: contact-sheet rows, one per shot in song order; the chosen frame gets a lamp-amber outline. Dark-first: night sea. */
:root {
  --bg: #0d1520; --panel: #142030; --line: #24354a; --fg: #e6ecf2; --muted: #8fa1b5; --accent: #e8b46a; --warn: #e07a6a;
  --night: #3b5f8f; --amber: #d99a4e; --dawn: #8fc3d9; --gold: #f0cc6e; --rose: #d9899a; --lamp: #c98a3a;
  --serif: "Noto Serif TC", "Songti TC", "PMingLiU", serif;
  --display: "Cormorant Garamond", "Noto Serif TC", Georgia, serif;
  --mono: "IBM Plex Mono", ui-monospace, Consolas, monospace;
  color-scheme: dark;
}
@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) {
  --bg: #f3f5f7; --panel: #ffffff; --line: #d5dde6; --fg: #17222e; --muted: #5a6b7d; --accent: #a8641c; --warn: #b8432f; color-scheme: light } }
:root[data-theme="light"] { --bg: #f3f5f7; --panel: #ffffff; --line: #d5dde6; --fg: #17222e; --muted: #5a6b7d; --accent: #a8641c; --warn: #b8432f; color-scheme: light }
body { background: var(--bg); color: var(--fg); font-family: var(--serif); line-height: 1.6; }
.wrap { max-width: 1180px; margin: 0 auto; padding-block: 32px 120px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
header { display: grid; gap: 10px; margin-bottom: 20px; }
.eyebrow { font: 500 12px/1 var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
h1 { margin: 0; font-weight: 600; font-size: clamp(26px, 4.5vw, 40px); text-wrap: balance; }
h1 em { font-family: var(--display); font-weight: 500; color: var(--accent); margin-left: .3em; font-size: .8em; }
.lede { max-width: 64ch; margin: 0; color: var(--muted); }
.shot { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 14px; padding: 16px 0; border-bottom: 1px dashed var(--line); }
.meta { display: grid; align-content: start; gap: 4px; font: 13px var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; }
.meta b { color: var(--fg); font-size: 16px; font-weight: 500; }
.kind { font-style: normal; font-size: 11px; letter-spacing: .08em; padding: 1px 6px; border-radius: 3px; border: 1px solid var(--line); justify-self: start; }
.image .kind { color: var(--accent); border-color: var(--accent); }
.story .kind { color: var(--dawn); border-color: var(--dawn); }
.sw { width: 12px; height: 12px; border-radius: 50%; }
.l-night { background: var(--night); } .l-amber { background: var(--amber); } .l-dawn { background: var(--dawn); }
.l-gold { background: var(--gold); } .l-rose { background: var(--rose); } .l-lamp { background: var(--lamp); }
.body { display: grid; gap: 8px; min-width: 0; }
.lyric { margin: 0; font-size: 17px; }
.row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.row.n3 { grid-template-columns: minmax(0, .55fr) repeat(2, minmax(0, 1fr)); }
.row.n1, .row.n0 { grid-template-columns: minmax(0, 1fr); }
figure { margin: 0; min-width: 0; }
figure img, .pick img, .strip { display: block; width: 100%; border-radius: 3px; max-width: 100%; }
figcaption { font: 12px var(--mono); color: var(--muted); }
.pick { position: relative; padding: 0; border: 3px solid transparent; border-radius: 6px; background: none; cursor: pointer; min-width: 0; }
.pick span { position: absolute; top: 6px; left: 6px; font: 500 12px var(--mono); background: var(--bg); color: var(--fg); padding: 0 6px; border-radius: 3px; opacity: .85; }
.pick[aria-pressed="true"] { border-color: var(--accent); }
.pick[aria-pressed="true"] span { background: var(--accent); color: var(--bg); opacity: 1; }
.pick:focus-visible { outline: 2px solid var(--fg); outline-offset: 2px; }
.shot.is-redo .pick, .shot.is-redo .strip { opacity: .35; }
.shot.is-redo .meta b { color: var(--warn); }
.ctl { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; font-size: 14px; color: var(--muted); }
.note { flex: 1 1 220px; min-width: 0; font: 14px var(--serif); padding: 4px 8px; border: 1px solid var(--line); border-radius: 4px; background: var(--panel); color: var(--fg); }
.bar { position: fixed; left: 0; right: 0; bottom: 0; background: var(--panel); border-top: 1px solid var(--line);
  padding-block: 10px calc(10px + env(safe-area-inset-bottom, 0px));
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.bar .in { max-width: 1180px; margin: 0 auto; display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; }
.bar .sum { font: 13px var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; }
.bar button { font: 600 15px var(--serif); padding: 6px 16px; border-radius: 4px; border: 0; background: var(--accent); color: var(--bg); cursor: pointer; }
.bar .ok { font-size: 13px; color: var(--accent); }
#out { width: 100%; font: 12px var(--mono); background: var(--bg); color: var(--fg); border: 1px solid var(--line); border-radius: 4px; }
.row.grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); }
.tl, .tl-labels { display: flex; gap: 2px; }
.tl { height: 22px; margin-top: 8px; }
.tl .seg { flex-basis: 0; border-radius: 2px; }
.tl-labels span { flex-basis: 0; min-width: 0; overflow: visible; white-space: nowrap; font: 11px var(--mono); color: var(--muted); }
.seg.perform { background: var(--night); } .seg.story { background: var(--dawn); } .seg.image { background: var(--accent); }
.legend { margin: 6px 0 0; font: 12px var(--mono); color: var(--muted); }
.legend .seg { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin: 0 4px 0 10px; }
.plan { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 2px 12px; margin: 0; font-size: 14px; }
.plan dt { color: var(--muted); }
.plan dd { margin: 0; overflow-wrap: anywhere; }
.todo { color: var(--warn); }
@media (max-width: 560px) { .row.n3 { grid-template-columns: repeat(2, minmax(0, 1fr)); } .row.n3 .src { grid-column: 1 / -1; max-width: 60%; } }
</style>
<div class="wrap" data-stage="{{STAGE}}">
<header>
  <div class="eyebrow">videogen · {{STAGE}}</div>
  <h1>{{TITLE}}<em>{{STAGE}}</em></h1>
  <p class="lede">{{INTRO}} 完成後按下方「複製回饋」，貼回對話。</p>
  {{LEAD}}
</header>
{{ROWS}}
</div>
<div class="bar"><div class="in">
  <span class="sum" id="sum"></span>
  <button type="button" id="copy">複製回饋</button>
  <span class="ok" id="ok" hidden>已複製，貼回對話即可</span>
  <textarea id="out" rows="4" hidden readonly></textarea>
</div></div>
<script>
const STAGE = document.querySelector(".wrap").dataset.stage;
const KEY = "videogen-" + document.title;
const rows = [...document.querySelectorAll(".shot")];
let state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
function initial(el) {
  const on = el.querySelector('.pick[aria-pressed="true"]');
  return { value: on ? on.dataset.value : null, redo: false, note: "", changed: false };
}
const get = el => state[el.id] || (state[el.id] = initial(el));
function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }
function render() {
  let redo = 0;
  for (const el of rows) {
    const s = get(el);
    el.querySelectorAll(".pick").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.value === s.value && !s.redo)));
    el.classList.toggle("is-redo", s.redo);
    const box = el.querySelector(".redo");  // the storyboard page takes notes only
    if (box) box.checked = s.redo;
    el.querySelector(".note").value = s.note;
    if (s.redo) redo++;
  }
  document.getElementById("sum").textContent = `${rows.length} 個鏡頭 · ${redo} 個要重做`;
}
document.addEventListener("click", e => {
  const b = e.target.closest(".pick"); if (!b) return;
  const s = get(document.getElementById(b.dataset.shot)); s.value = b.dataset.value; s.redo = false; s.changed = true; save(); render();
});
document.addEventListener("change", e => {
  if (e.target.classList.contains("redo")) { get(document.getElementById(e.target.dataset.shot)).redo = e.target.checked; save(); render(); }
});
document.addEventListener("input", e => {
  if (e.target.classList.contains("note")) { get(document.getElementById(e.target.dataset.shot)).note = e.target.value; save(); }
});
function feedback() {
  const lines = ["videogen-feedback stage=" + STAGE], picks = [], off = [];
  for (const el of rows) {
    const s = get(el);
    if (s.redo) { lines.push(`redo ${el.id}: ${s.note}`.trim()); continue; }
    if ((STAGE === "keyframes" || STAGE === "character") && s.value) picks.push(`${el.id}=${s.value}`);
    if (STAGE === "edit" && s.value === "orig") off.push(el.id);
    if (s.note) lines.push(`note ${el.id}: ${s.note}`);
  }
  if (picks.length) lines.splice(1, 0, "pick " + picks.join(" "));
  if (off.length) lines.splice(1, 0, "edit-off " + off.join(" "));
  return lines.join("\n");
}
document.getElementById("copy").addEventListener("click", () => {
  const text = feedback(), out = document.getElementById("out"), ok = document.getElementById("ok");
  out.value = text;
  navigator.clipboard.writeText(text).then(() => { ok.hidden = false; out.hidden = true; },
    () => { out.hidden = false; out.focus(); out.select(); });
});
render();
</script>
"""
