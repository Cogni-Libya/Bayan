// v3 contour smoother for the Bayan logo: removes trace wobble, keeps corners, refits cubic Béziers.
// smoothPath(d, opts) -> d. Contours matched by skip(bbox) are passed through untouched (e.g. Latin outlines).
function parseD(d) {
  const toks = d.match(/[MLCZmlcz]|-?\d*\.?\d+(?:e-?\d+)?/g); const subs = []; let cur = null, i = 0, cmd = '', pen = [0, 0];
  const num = () => parseFloat(toks[i++]);
  while (i < toks.length) {
    if (/[MLCZ]/i.test(toks[i])) cmd = toks[i++];
    if (cmd === 'M') { pen = [num(), num()]; cur = { start: pen, segs: [] }; subs.push(cur); cmd = 'L'; }
    else if (cmd === 'L') { const p = [num(), num()]; cur.segs.push([pen, p]); pen = p; }
    else if (cmd === 'C') { const a = [num(), num()], b = [num(), num()], p = [num(), num()]; cur.segs.push([pen, a, b, p]); pen = p; }
    else if (cmd === 'Z' || cmd === 'z') { pen = cur.start; cmd = ''; }
    else throw new Error('unsupported ' + cmd);
  }
  return subs;
}
const bez = (s, t) => { if (s.length === 2) return [s[0][0] + (s[1][0] - s[0][0]) * t, s[0][1] + (s[1][1] - s[0][1]) * t]; const u = 1 - t; return [0, 1].map(k => u * u * u * s[0][k] + 3 * u * u * t * s[1][k] + 3 * u * t * t * s[2][k] + t * t * t * s[3][k]); };
function polyOf(sub) { const pts = []; for (const s of sub.segs) for (let j = 0; j < 24; j++) pts.push(bez(s, j / 24)); return pts; }
function resample(pts, h) {
  const n = pts.length, out = []; let acc = 0; out.push(pts[0]);
  for (let i = 0; i < n; i++) { const a = pts[i], b = pts[(i + 1) % n]; let L = Math.hypot(b[0] - a[0], b[1] - a[1]), t0 = 0;
    while (acc + L * (1 - t0) >= h) { const t = t0 + (h - acc) / L; out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]); t0 = t; acc = 0; }
    acc += L * (1 - t0); }
  if (out.length > 2 && Math.hypot(out[out.length - 1][0] - out[0][0], out[out.length - 1][1] - out[0][1]) < h * 0.5) out.pop();
  return out;
}
function corners(p, k, deg) {
  const n = p.length, ang = new Float32Array(n);
  for (let i = 0; i < n; i++) { const a = p[(i - k + n) % n], b = p[i], c = p[(i + k) % n];
    const v1 = [b[0] - a[0], b[1] - a[1]], v2 = [c[0] - b[0], c[1] - b[1]];
    ang[i] = Math.abs(Math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1[0] * v2[0] + v1[1] * v2[1])) * 180 / Math.PI; }
  const cs = []; for (let i = 0; i < n; i++) { if (ang[i] < deg) continue; let m = true; for (let j = -k; j <= k; j++) if (j && ang[(i + j + n) % n] > ang[i]) m = false; if (m) cs.push(i); }
  return cs;
}
function taubin(p, pinned, iters, lam = 0.5, mu = -0.53) {
  const n = p.length; let a = p.map(q => q.slice());
  for (let it = 0; it < iters; it++) for (const f of [lam, mu]) { const b = a.map(q => q.slice());
    for (let i = 0; i < n; i++) { if (pinned[i]) continue; const l = a[(i - 1 + n) % n], r = a[(i + 1) % n];
      b[i][0] = a[i][0] + f * ((l[0] + r[0]) / 2 - a[i][0]); b[i][1] = a[i][1] + f * ((l[1] + r[1]) / 2 - a[i][1]); }
    a = b; }
  return a;
}
// Schneider curve fitting
const sub = (a, b) => [a[0] - b[0], a[1] - b[1]], add = (a, b) => [a[0] + b[0], a[1] + b[1]], mul = (a, s) => [a[0] * s, a[1] * s], dot = (a, b) => a[0] * b[0] + a[1] * b[1];
const norm = a => { const l = Math.hypot(a[0], a[1]) || 1; return [a[0] / l, a[1] / l]; };
function fitCubic(P, t1, t2, err, out) {
  if (P.length === 2) { const d = Math.hypot(...sub(P[1], P[0])) / 3; out.push([P[0], add(P[0], mul(t1, d)), add(P[1], mul(t2, d)), P[1]]); return; }
  let u = chord(P), b = gen(P, u, t1, t2), [e, si] = maxErr(P, b, u);
  if (e < err) { out.push(b); return; }
  if (e < err * 16) for (let k = 0; k < 20; k++) { u = u.map((x, i) => newton(b, P[i], x)); b = gen(P, u, t1, t2); [e, si] = maxErr(P, b, u); if (e < err) { out.push(b); return; } }
  const tc = norm(sub(P[si - 1], P[si + 1]));
  fitCubic(P.slice(0, si + 1), t1, tc, err, out); fitCubic(P.slice(si), mul(tc, -1), t2, err, out);
}
function chord(P) { const u = [0]; for (let i = 1; i < P.length; i++) u.push(u[i - 1] + Math.hypot(...sub(P[i], P[i - 1]))); return u.map(x => x / u[u.length - 1]); }
function gen(P, u, t1, t2) {
  const f = P[0], l = P[P.length - 1]; let C = [[0, 0], [0, 0]], X = [0, 0];
  u.forEach((t, i) => { const A1 = mul(t1, 3 * t * (1 - t) ** 2), A2 = mul(t2, 3 * t * t * (1 - t));
    C[0][0] += dot(A1, A1); C[0][1] += dot(A1, A2); C[1][1] += dot(A2, A2);
    const tmp = sub(P[i], bez([f, f, l, l], t)); X[0] += dot(A1, tmp); X[1] += dot(A2, tmp); });
  C[1][0] = C[0][1]; const det = C[0][0] * C[1][1] - C[0][1] * C[1][0];
  let a1 = det ? (X[0] * C[1][1] - X[1] * C[0][1]) / det : 0, a2 = det ? (C[0][0] * X[1] - C[1][0] * X[0]) / det : 0;
  const seg = Math.hypot(...sub(l, f)); if (a1 < seg * 1e-3 || a2 < seg * 1e-3) a1 = a2 = seg / 3;
  return [f, add(f, mul(t1, a1)), add(l, mul(t2, a2)), l];
}
function maxErr(P, b, u) { let m = 0, si = Math.floor(P.length / 2); for (let i = 1; i < P.length - 1; i++) { const d = sub(bez(b, u[i]), P[i]), e = dot(d, d); if (e > m) { m = e; si = i; } } return [m, si]; }
function newton(b, p, t) {
  const d = sub(bez(b, t), p), q1 = [0, 1, 2].map(i => mul(sub(b[i + 1], b[i]), 3)), q2 = [0, 1].map(i => mul(sub(q1[i + 1], q1[i]), 2));
  const b1 = [0, 1].map(k => (1 - t) ** 2 * q1[0][k] + 2 * (1 - t) * t * q1[1][k] + t * t * q1[2][k]), b2 = [0, 1].map(k => (1 - t) * q2[0][k] + t * q2[1][k]);
  const den = dot(b1, b1) + dot(d, b2); return den ? Math.min(1, Math.max(0, t - dot(d, b1) / den)) : t;
}
const f2 = v => (Math.round(v * 100) / 100).toString();
function bbox(pts) { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); } return { x0, y0, x1, y1, w: x1 - x0, h: y1 - y0 }; }
function area(p) { let a = 0; for (let i = 0; i < p.length; i++) { const q = p[(i + 1) % p.length]; a += p[i][0] * q[1] - q[0] * p[i][1]; } return a / 2; }
function ellipseD(cx, cy, rx, ry, ccw) { const k = 0.5523; const s = ccw ? -1 : 1;
  const P = [[cx + rx, cy], [cx, cy + s * ry], [cx - rx, cy], [cx, cy - s * ry]];
  let d = `M${f2(P[0][0])} ${f2(P[0][1])}`;
  for (let i = 0; i < 4; i++) { const a = P[i], b = P[(i + 1) % 4]; const ta = i % 2 === 0 ? [0, s * ry * k] : [-(a[0] - cx) / rx * rx * k, 0]; const tb = i % 2 === 0 ? [(b[0] - cx) === 0 ? (cx - a[0]) / rx * rx * k : 0, 0] : [0, 0];
    // explicit quarter arcs
    const c1 = i === 0 ? [cx + rx, cy + s * ry * k] : i === 1 ? [cx - rx * k, cy + s * ry] : i === 2 ? [cx - rx, cy - s * ry * k] : [cx + rx * k, cy - s * ry];
    const c2 = i === 0 ? [cx + rx * k, cy + s * ry] : i === 1 ? [cx - rx, cy + s * ry * k] : i === 2 ? [cx - rx * k, cy - s * ry] : [cx + rx, cy - s * ry * k];
    d += `C${f2(c1[0])} ${f2(c1[1])} ${f2(c2[0])} ${f2(c2[1])} ${f2(b[0])} ${f2(b[1])}`; }
  return d + 'Z';
}
function smoothContour(pts, o) {
  const h = o.h ?? 0.4; let p = resample(pts, h);
  const cs = corners(p, o.k ?? 5, o.deg ?? 55); const pin = new Uint8Array(p.length); cs.forEach(i => pin[i] = 1);
  p = taubin(p, pin, o.iters ?? 60);
  const breaks = cs.length ? cs : [0]; const out = [];
  for (let bi = 0; bi < breaks.length; bi++) {
    const s = breaks[bi], e = breaks[(bi + 1) % breaks.length]; const run = []; let i = s;
    do { run.push(p[i]); i = (i + 1) % p.length; } while (i !== e); run.push(p[e]);
    if (run.length < 3) { out.push([run[0], run[0], run[run.length - 1], run[run.length - 1]]); continue; }
    const m = Math.min(4, run.length - 1);
    const t1 = norm(sub(run[m], run[0])), t2 = norm(sub(run[run.length - 1 - m], run[run.length - 1]));
    if (!cs.length) { // closed smooth loop: tangent from neighbours
      const n = p.length, tt = norm(sub(p[m], p[n - m])); fitCubic(run, tt, mul(tt, -1), o.err ?? 0.02, out);
    } else fitCubic(run, t1, t2, o.err ?? 0.02, out);
  }
  let d = `M${f2(out[0][0][0])} ${f2(out[0][0][1])}`;
  for (const c of out) d += `C${f2(c[1][0])} ${f2(c[1][1])} ${f2(c[2][0])} ${f2(c[2][1])} ${f2(c[3][0])} ${f2(c[3][1])}`;
  return { d: d + 'Z', n: out.length, corners: cs.length };
}
function smoothPath(d, o = {}) {
  const subs = parseD(d); const items = subs.map(s => { const pts = polyOf(s); return { pts, bb: bbox(pts), a: area(pts) }; });
  // dots: small, compact contours -> true ellipses, unified size per row
  const isDot = it => !(o.skip && o.skip(it.bb)) && it.bb.w < (o.dotMax ?? 16) && it.bb.h < (o.dotMax ?? 16) && it.bb.w / it.bb.h > 0.6 && it.bb.w / it.bb.h < 1.6;
  const dots = items.filter(isDot);
  if (dots.length) { const rx = dots.reduce((s, it) => s + it.bb.w, 0) / dots.length / 2, ry = dots.reduce((s, it) => s + it.bb.h, 0) / dots.length / 2;
    const cyAvg = dots.reduce((s, it) => s + (it.bb.y0 + it.bb.y1) / 2, 0) / dots.length;
    dots.forEach(it => it.dot = { cx: (it.bb.x0 + it.bb.x1) / 2, cy: cyAvg, rx, ry }); }
  let nodes = 0;
  const ds = items.map((it, i) => {
    if (o.skip && o.skip(it.bb)) { const s = subs[i]; let dd = `M${f2(s.start[0])} ${f2(s.start[1])}`; for (const g of s.segs) dd += g.length === 2 ? `L${f2(g[1][0])} ${f2(g[1][1])}` : `C${g.slice(1).map(q => f2(q[0]) + ' ' + f2(q[1])).join(' ')}`; nodes += s.segs.length; return dd + 'Z'; }
    if (it.dot) { nodes += 4; return ellipseD(it.dot.cx, it.dot.cy, it.dot.rx, it.dot.ry, it.a < 0); }
    const r = smoothContour(it.pts, o); nodes += r.n; return r.d;
  });
  return { d: ds.join(''), nodes, contours: items.length, dots: dots.length };
}
if (typeof module !== 'undefined') module.exports = { smoothPath, parseD };
