// 参数化片段运行时：一份 spec（JSON）→ 一段时长严格等于 spec.duration 的动画。给口播视频管线当「动画段」用。
// 契约见 references/09-视频动画语法.md「片段契约」。和 engine.js 的区别：没有段落表/转场，一个语法一个 draw(c, t, ctx)，画布尺寸从 spec 读（竖屏也行）。
//
// spec.finish（可选）：成片质感层，预设 soft / film / punch / clean 或对象，见 lib/finish.js；alpha 模式忽略。
// spec = { grammar, duration, fps=30, width=1920, height=1080, safe?: {top,bottom,left,right（px，留给字幕/平台 UI）, fill?（让开的边涂这个色）}, theme?, alpha?, data?, cues: [{at, kind, text?, sub?, data?, image?, frames?, fps?, dur?}] }
// spec.theme：全片共用的色板（lib/palettes.js）——名字（paper poster ink navy bauhaus snow wood chalk）、{name, 要覆盖的键}、或完整 6 键 {bg, surface, ink, sub, accent, accent2}。
//   解析成 ctx.pal（完整 6 键＋name），各语法按它上色；名字写错 / 缺键 → 启动失败。不写 → ctx.pal = null，各语法用自己的默认配色。
//   语法可以声明 legacyTheme(theme) → true：这个 theme 是它自己的旧写法（t3 的 'light' / 'dark' / 旧主题对象），不当色板解析，语法照旧读 ctx.theme。
// 素材路径（构建时用 spec_assets.py 核存在并改写）：cue.image、cue.frames（帧序列：目录或路径数组）、data.image。
// 任何一张加载失败 → 启动失败、拒绝渲染（不出空白帧）。语法里取素材：ctx.still(q) = 这条 cue 的静态图（有 frames 时是第一帧），ctx.frame(q, t) = t 时刻该画的那一帧。
// 语法文件 clips/<grammar>.js 注册 CLIPS[grammar] = { init?(ctx), draw(c, t, ctx), safe?: true（按 ctx.safe / ctx.box 排版了才写，否则 spec.safe 会告警） }。
// 对齐约定（CLIP.lt）：cue 的「揭开那一帧」= at 所在的那一帧——元素在 t = at 这一帧第一次可见，动画内部时间从 at − 1 帧起算。
(() => {
window.CLIPS = {};
const C = window.CLIP = {};

// ---------- 给语法文件用的小工具 ----------
// 片内时间：cue 在 at 这一帧第一次可见
C.lt = (t, at, fps) => t - at + 1 / fps;
// 进度：从 at 起 dur 秒走完 0→1（at 这一帧已经 >0）
C.p = (t, at, dur, fps) => U.clamp(C.lt(t, at, fps) / dur);
// 等比放进框里（contain，不裁）：返回 {x, y, w, h}
C.fit = (iw, ih, bx, by, bw, bh) => { const s = Math.min(bw / iw, bh / ih); const w = iw * s, h = ih * s; return { x: bx + (bw - w) / 2, y: by + (bh - h) / 2, w, h, s }; };
// 归一化矩形 [x,y,w,h]（0..1，相对图片）→ 画面矩形
C.sub = (r, box) => ({ x: box.x + r[0] * box.w, y: box.y + r[1] * box.h, w: r[2] * box.w, h: r[3] * box.h });
C.text = (cue, ...fallback) => (cue && (cue.text ?? cue.data?.text)) ?? fallback.find(v => v != null) ?? '';

window.createMotionClip = async function (spec, G, canvas) {
  const c = canvas.getContext('2d');
  const { width: W, height: H, fps: FPS } = spec;
  const fail = message => { throw new Error(message); };
  if (!G || typeof G.draw !== 'function') fail(`语法未注册：${spec.grammar}`);
  // 主题色板：在加载素材之前核，写错就别白等图片
  let pal = null;
  if (!(G.legacyTheme && G.legacyTheme(spec.theme))) { try { pal = PAL.resolve(spec.theme); } catch (e) { return fail(e.message); } }
  // 成片质感层（spec.finish）：写错预设名就别白等图片
  let fin = null; try { fin = FINISH.resolve(spec.finish); } catch (e) { return fail(e.message); }
  // 图片
  const IMG = {}, urls = new Set();
  for (const q of (spec.cues || [])) {
    if (q.image) urls.add(q.image);
    if (q.frames != null) { if (!Array.isArray(q.frames) || !q.frames.length) return fail(`cue ${q.kind} at=${q.at} 的 frames 要是非空的路径数组（render.py 会把目录展开成数组；预览模式只认数组）`); q.frames.forEach(f => urls.add(f)); }
  }
  if (spec.data && spec.data.image) urls.add(spec.data.image);
  try { await Promise.all([...urls].map(u => new Promise((res, rej) => { const im = new Image(); im.onload = () => { IMG[u] = im; res(); }; im.onerror = () => rej(u); im.src = window.MOTION_ASSETS[u] || u; }))); }
  catch (u) { return fail('图片加载失败：' + u); }
  const cues0 = (spec.cues || []).map((q, i) => ({ ...q, i, at: +q.at || 0 })).sort((a, b) => a.at - b.at || a.i - b.i);
  for (const q of cues0) if (q.at > spec.duration + 1e-9) console.warn(`cue ${q.kind} at=${q.at} 超出片段时长 ${spec.duration}s，看不到，已丢掉（不占版面）`);
  const cues = cues0.filter(q => q.at <= spec.duration + 1e-9);   // 看不到的 cue 不进语法：否则照样占排版位置、进度轨照样数它
  // number 的说明字段各语法以前各认各的（t2/t3 认 text，y5 认 sub），写错了不报错只是没字。统一：text 与 sub 互为别名，data.text 也算
  for (const q of cues) if (q.kind === 'number') { const cap = q.text ?? q.sub ?? (q.data && q.data.text); if (cap != null) { q.text = cap; q.sub = cap; } }
  const safe = { top: 0, bottom: 0, left: 0, right: 0, ...(spec.safe || {}) };   // 让开的边（px）：管线烧录字幕、平台 UI 压在这里，带字的语法不往里排
  const box = { x: safe.left, y: safe.top, w: W - safe.left - safe.right, h: H - safe.top - safe.bottom };   // 让开之后的内容框，语法排版用它（ctx.box）
  const ctx = { spec, data: spec.data || {}, theme: spec.theme || {}, pal, cues, W, H, FPS, u: Math.min(W, H) / 1080, portrait: H > W, alpha: !!spec.alpha, IMG, dur: spec.duration, safe, box,
    of: (...kinds) => cues.filter(q => kinds.includes(q.kind)), lt: (t, at) => C.lt(t, at, FPS), p: (t, at, d) => C.p(t, at, d, FPS),
    // 素材：still = 定版式用的那张（image，或 frames 的第一帧）；frame = t 时刻画哪一帧（frames 从 at 起按 q.fps（默认 30）播，播完停在最后一帧，q.loop 循环）
    still: q => q && (q.image ? IMG[q.image] : q.frames ? IMG[q.frames[0]] : null),
    frame: (q, t) => !q ? null : q.frames ? MD.frameAt(q.frames.map(f => IMG[f]), t - q.at, q.fps || 30, !!q.loop) : q.image ? IMG[q.image] : null };
  if (G.fonts) { const txt = cues.map(q => [q.text, q.sub, q.data && q.data.text].filter(Boolean).join('')).join('') + JSON.stringify(spec.data || {});
    for (const fam of G.fonts) { const miss = U.missingGlyphs(fam, [...txt].filter(ch => ch.codePointAt(0) >= 0x2E80).join(''));   /* 只查汉字与全角符号：拉丁/希腊/数学符号各语法另有字体 */ if (miss.length) console.warn(`字体「${fam}」缺字：${miss.join('')}（会回退系统字体；常用字已在 GB2312 子集里，生僻字用 scripts/font_subset.py --text 补）`); } }
  if (spec.safe && (safe.top || safe.bottom || safe.left || safe.right) && !G.safe)
    console.warn(`语法 ${spec.grammar} 还没接 safe（语法对象里没有 safe: true），spec.safe 被忽略：字幕带可能压在字上`);
  if (G.init) G.init(ctx);
  // safe.fill：让开的边涂成这个颜色（竖屏片把图表做成和相邻 contain 素材同一块「卡片」，外面是片子的底色）；透明模式下不涂
  const band = (safe.fill && !spec.alpha) ? (cc => { cc.fillStyle = safe.fill; const { top: t0, bottom: b0, left: l0, right: r0 } = safe;
    if (t0) cc.fillRect(0, 0, W, t0); if (b0) cc.fillRect(0, H - b0, W, b0); if (l0) cc.fillRect(0, 0, l0, H); if (r0) cc.fillRect(W - r0, 0, r0, H); }) : null;
  return t => {
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.clearRect(0, 0, W, H);
    c.save();
    try { G.draw(c, t, ctx); } finally { c.restore(); }
    if (fin && !spec.alpha) FINISH.apply(c, t, fin, W, H, FPS);
    if (band) band(c);
  };
};
})();
