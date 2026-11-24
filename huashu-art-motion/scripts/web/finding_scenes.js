(() => {
  const book = 'NotoSerifSC';
  const body = 'PuHui-Medium';
  const numbers = 'RobotoCondensed';
  const clamp = U.clamp;
  const formats = new Intl.NumberFormat('zh-CN', {maximumFractionDigits: 4});

  function rect(c, x, y, w, h, fill) {
    c.fillStyle = fill; c.fillRect(x, y, w, h);
  }

  function line(c, a, b, color, width = 1) {
    c.beginPath(); c.moveTo(...a); c.lineTo(...b);
    c.strokeStyle = color; c.lineWidth = width; c.stroke();
  }

  function dot(c, x, y, radius, color) {
    c.fillStyle = color; c.beginPath(); c.arc(x, y, radius, 0, 2 * Math.PI); c.fill();
  }

  function words(c, text, x, y, width, size, color, opts = {}) {
    const {family = body, lines = 1, right = false} = opts;
    const result = TY.fit(c, String(text || ''), width, size, family, {maxLines: lines, min: 0.42});
    c.font = `${result.size}px "${family}", ${family === book ? 'serif' : 'sans-serif'}`;
    c.textBaseline = 'top';
    c.textAlign = right ? 'right' : 'left';
    c.fillStyle = color;
    result.lines.forEach((row, i) => c.fillText(row, x, y + i * result.size * 1.25, width));
  }

  const ease = t => 1 - (1 - clamp(t)) ** 3;
  const slide = t => (1 - ease(t * 2)) * 28;

  function artboard(c) {
    const {W, H} = window.STAGE;
    const w = W >= H ? 1280 : 760;
    const h = H / W * w;
    c.scale(W / w, W / w);
    return {w, h, tall: H > W, pad: Math.round(w * .058)};
  }

  function fitTrend(c, box, series, p, palette) {
    const ys = series.map(row => row.value);
    const lo = Math.min(...ys), hi = Math.max(...ys);
    const pad = Math.max((hi - lo) * .1, hi === lo ? Math.max(Math.abs(lo) * .1, 1) : 0);
    const y = CH.lin(lo - pad, hi + pad, box.y + box.h, box.y);
    const positions = ys.map((value, i) => [
      box.x + (box.w - 48) * i / (ys.length - 1), y(value),
    ]);
    for (let i = 0; i < 4; i++) {
      const level = box.y + box.h * i / 3;
      line(c, [box.x, level], [box.x + box.w - 43, level], palette.grid);
      const mark = hi + pad - (hi - lo + 2 * pad) * i / 3;
      words(c, formats.format(mark), box.x + box.w, level - 8, 40, 14,
        palette.sub, {family: numbers, right: true});
    }
    const head = CH.line(c, positions, p, {col: palette.accent, lw: 4.5, head: false});
    positions.forEach(([x, cy], i) => {
      if (p + 1e-7 < i / (positions.length - 1)) return;
      dot(c, x, cy, 4.75, palette.accent);
      if (i === 0 || i === series.length - 1) {
        const isLast = i !== 0;
        const labelX = isLast ? x + 5 : x;
        const labelWidth = box.w * .38;
        const valY = cy - 27 < box.y ? cy + 9 : cy - 28;
        words(c, formats.format(series[i].value), labelX, valY, labelWidth, 22, palette.ink, {family: numbers, right: isLast});
        words(c, series[i].label, labelX, box.y + box.h + 10, labelWidth, 17, palette.sub, {right: isLast});
      }
    });
    if (head && p < 1) dot(c, ...head, 5.25, palette.accent);
  }

  function fitBars(c, box, series, t, palette, horizontal) {
    const ys = [0, ...series.map(row => row.value)];
    const lo = Math.min(...ys), hi = Math.max(...ys);
    const span = hi - lo || 1;
    const min = lo < 0 ? lo - span * .11 : 0;
    const max = hi > 0 ? hi + span * .14 : span * .14;
    const count = series.length;
    if (horizontal) {
      const plotX = box.x + box.w * .29, plotW = box.w * .60;
      const x = CH.lin(min, max, plotX, plotX + plotW);
      const row = box.h / count;
      line(c, [x(0), box.y], [x(0), box.y + box.h], palette.grid, 1.5);
      series.forEach((s, i) => {
        const p = ease((t - .25 - i * .11) / .56);
        const cy = box.y + i * row + row * .5;
        const end = x(s.value * p);
        words(c, s.label, box.x, cy - 9, box.w * .25, Math.min(20, row * .48), palette.sub);
        if (!p) return;
        rect(c, Math.min(x(0), end), cy - 5, Math.abs(end - x(0)), 10, palette.accent);
        words(c, formats.format(s.value), box.x + box.w, cy - 10, box.w * .12, Math.min(21, row * .52),
          palette.ink, {family: numbers, right: true});
      });
      return;
    }
    const y = CH.lin(min, max, box.y + box.h, box.y);
    const slot = box.w / count;
    line(c, [box.x, y(0)], [box.x + box.w, y(0)], palette.grid, 1.6);
    series.forEach((s, i) => {
      const p = ease((t - .25 - i * .12) / .7);
      const center = box.x + (i + .5) * slot;
      const end = y(s.value * p), width = Math.min(64, slot * .50);
      words(c, s.label, center - slot * .43, box.y + box.h + 12 + (i % 2) * (count > 7 ? 15 : 0), slot * .86,
        17, palette.sub);
      if (!p) return;
      rect(c, center - width / 2, Math.min(y(0), end), width, Math.abs(end - y(0)), palette.accent);
      const labelY = s.value >= 0 ? end - 22 : end + 4;
      words(c, formats.format(s.value), center - slot * .43, Math.min(box.y + box.h - 18, labelY),
        slot * .86, 19, palette.ink, {family: numbers});
    });
  }

  function chart(c, data, box, t, style, horizontal = false) {
    if (data.chart === 'line') fitTrend(c, box, data.series, ease((t - .22) / 1.9), style);
    else fitBars(c, box, data.series, t, style, horizontal);
  }

  function footer(c, data, page, color) {
    const {w, h, pad} = page;
    words(c, data.source, pad, h - pad * .57, w - 2 * pad, 17, color);
  }

  function archive(c, data, t, page) {
    const {w, h, tall, pad} = page;
    const p = {ink:'#2b231e', sub:'#68574c', accent:'#ad2e24', grid:'#d0bda6'};
    rect(c, 0, 0, w, h, '#d9c8b3');
    const band = tall ? w : w * .31;
    rect(c, 0, 0, band, tall ? h * .23 : h, '#30251f');
    const tx = tall ? pad : band + 36, ty = tall ? h * .31 : pad * .78;
    const tw = w - tx - pad, th = tall ? h * .58 : h - ty - pad * .90;
    rect(c, tx + 8, ty + 9 + slide(t), tw, th, '#b6a28a');
    rect(c, tx, ty + slide(t), tw, th, '#f6ecd6');
    rect(c, tx - 4, ty + slide(t), 9, th, '#9c3828');
    words(c, data.kind === 'chart' ? data.unit : '文档摘录', pad, pad * .74, band - pad * 1.4, 24, '#ead4ae');
    words(c, data.title, pad, pad * 1.48, band - pad * 1.4, 56, '#fff3dc', {family: book, lines: 3});
    const reveal = ease((t - .23) / .73);
    c.save(); c.globalAlpha = reveal; c.translate(0, slide(t));
    if (data.kind === 'chart') {
      chart(c, data, {x:tx + 34, y:ty + th * .22, w:tw - 68, h:th * .61}, t, p, true);
    } else {
      words(c, '“', tx + 36, ty + th * .12, 120, 94, p.accent, {family: book});
      words(c, data.text, tx + 40, ty + th * .36, tw - 80, 53, p.ink, {family: book, lines: 4});
    }
    c.restore();
    const sourceX = tall ? pad : tx;
    words(c, data.source, sourceX, h - pad * .57, w - sourceX - pad, 17, p.ink);
  }

  function chalk(c, data, t, page) {
    const {w,h,tall,pad} = page;
    const p = {ink:'#f3e8cb',sub:'#c2ccb4',accent:'#f1cb6c',grid:'#58695d'};
    rect(c,0,0,w,h,'#203e32');
    for (let x=pad; x<w-pad; x+=31) line(c,[x,pad],[x,h-pad],'#285143',.75);
    for (let y=pad; y<h-pad; y+=31) line(c,[pad,y],[w-pad,y],'#285143',.75);
    words(c,data.title,pad,pad * .68,w-pad*2,63,p.ink,{family:'LXGWWenKai-500',lines:2});
    line(c,[pad,h*.25],[pad + (w-pad*2)*ease(t*2.7),h*.25-2],p.accent,2);
    if (data.kind === 'chart') {
      words(c,data.unit,pad,h*.275,w-pad*2,23,p.sub);
      chart(c,data,{x:pad+9,y:h*.38,w:w-2*pad-18,h:h*.44},t,p);
    } else {
      const phrases = data.beats || [];
      const quoteY = phrases.length ? h * .65 : h * .40;
      for (const [i, part] of phrases.entries()) {
        const step = (w-pad*2)/phrases.length;
        const x = pad + i*step, y=h*.36, reveal=ease((t-.26-i*.23)*2);
        c.save(); c.globalAlpha = reveal;
        rect(c,x,y,step*.81,tall?86:72,'#325747');
        words(c,part,x+12,y+15,step*.81-24,31,p.ink,{family:'LXGWWenKai-500',lines:2});
        if (i+1<phrases.length) {
          const start=x+step*.83, end=x+step*.96;
          line(c,[start,y+36],[end,y+36],p.accent,2);
          line(c,[end-6,y+31],[end,y+36],p.accent,2);
          line(c,[end-6,y+41],[end,y+36],p.accent,2);
        }
        c.restore();
      }
      c.save(); c.globalAlpha=ease((t-.3)/.72);
      words(c,data.text,pad + 12,quoteY,w-2*pad-24,phrases.length ? 35 : 56,p.ink,{family:'LXGWWenKai-500',lines:4});
      c.restore();
    }
    footer(c,data,page,p.sub);
  }

  function keynote(c, data, t, page) {
    const {w,h,tall,pad} = page;
    const p = {ink:'#ecf5fe',sub:'#afc2d6',accent:'#71d9fc',grid:'#374d64'};
    rect(c,0,0,w,h,'#101c2d');
    rect(c,pad,pad*.8,6,34,p.accent);
    words(c,data.title,pad+24,pad*.76,w-pad*2-24,53,p.ink,{lines:2});
    const right = tall ? pad : w*.43;
    const panelWidth = w-right-pad;
    const graphTop = tall ? h*.48 : h*.29;
    if (data.kind === 'chart') {
      const focus = data.series.at(-1);
      const numY = tall ? h*.205 : h*.36;
      words(c,data.unit,pad,numY - 44,(tall ? w - pad : right) - pad-16,23,p.sub);
      c.save(); c.globalAlpha = ease((t-.22)/.62); c.translate(0,slide(t));
      words(c,formats.format(focus.value),pad,numY,(tall ? w-pad : right)-pad-16,tall?100:120,p.accent,{family:numbers});
      words(c,focus.label,pad,numY+(tall?114:145), (tall ? w - pad : right) - pad-16,24,p.ink);
      c.restore();
      rect(c,right-16,graphTop-28,panelWidth+18,h*.80-graphTop+70,'#192b43');
      chart(c,data,{x:right,y:graphTop,w:panelWidth-12,h:h*.76-graphTop},t,p);
    } else {
      const y=h*.33+slide(t);
      c.save(); c.globalAlpha = ease((t-.10)/.62);
      line(c,[pad,y],[w-pad,y],p.accent,2.1);
      words(c,data.text,pad,y+42,w-pad*2,tall?54:68,p.ink,{lines:4});
      c.restore();
    }
    footer(c,data,page,p.sub);
  }

  const artists = {archive, chalk, keynote};
  window.makeFindingScene = function (style, data) {
    return {draw(c, time) {
      c.save();
      try { artists[style](c, data, Math.max(0,time), artboard(c)); }
      finally { c.restore(); }
    }};
  };
})();
