// Raster -> vector tracer used to build the Bayan logo SVGs.
// field: Float32Array (0..1 coverage), W,H. Returns closed loops of points (field px units).
function marchingLoops(field, W, H, T = 0.5, minLen = 40) {
  const v = (i, j) => (i < 0 || j < 0 || i >= W || j >= H) ? 0 : field[j * W + i];
  const pts = new Map(), adj = new Map();
  const key = (t, i, j) => ((j + 2) * (W + 4) + (i + 2)) * 2 + t;
  const link = (a, b) => { if (!adj.has(a)) adj.set(a, []); if (!adj.has(b)) adj.set(b, []); adj.get(a).push(b); adj.get(b).push(a); };
  for (let j = -1; j < H; j++) for (let i = -1; i < W; i++) {
    const a = v(i, j), b = v(i + 1, j), c = v(i + 1, j + 1), d = v(i, j + 1);
    const idx = (a >= T ? 8 : 0) | (b >= T ? 4 : 0) | (c >= T ? 2 : 0) | (d >= T ? 1 : 0);
    if (idx === 0 || idx === 15) continue;
    const top = key(0, i, j), right = key(1, i + 1, j), bot = key(0, i, j + 1), left = key(1, i, j);
    const it = (p, q) => (T - p) / (q - p), sp = (k, p) => { if (!pts.has(k)) pts.set(k, p); };
    if ((a >= T) !== (b >= T)) sp(top, [i + it(a, b), j]);
    if ((b >= T) !== (c >= T)) sp(right, [i + 1, j + it(b, c)]);
    if ((d >= T) !== (c >= T)) sp(bot, [i + it(d, c), j + 1]);
    if ((a >= T) !== (d >= T)) sp(left, [i, j + it(a, d)]);
    const m = (a + b + c + d) / 4;
    switch (idx) {
      case 1: case 14: link(left, bot); break; case 2: case 13: link(bot, right); break;
      case 3: case 12: link(left, right); break; case 4: case 11: link(top, right); break;
      case 6: case 9: link(top, bot); break; case 7: case 8: link(left, top); break;
      case 5: if (m >= T) { link(left, top); link(bot, right); } else { link(left, bot); link(top, right); } break;
      case 10: if (m >= T) { link(left, bot); link(top, right); } else { link(left, top); link(bot, right); } break;
    }
  }
  const seen = new Set(), loops = [];
  for (const s of adj.keys()) {
    if (seen.has(s)) continue; const loop = []; let prev = null, cur = s;
    while (cur != null && !seen.has(cur)) { seen.add(cur); loop.push(pts.get(cur)); const n = adj.get(cur); const nx = n[0] !== prev ? n[0] : n[1]; prev = cur; cur = nx; }
    if (loop.length > minLen) loops.push(loop);
  }
  return loops;
}
function gaussBlur(f, W, H, passes = 2) {
  const K = [1, 4, 6, 4, 1];
  const pass = (src, horiz) => { const o = new Float32Array(W * H); for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) { let s = 0, w = 0; for (let k = -2; k <= 2; k++) { const ii = horiz ? i + k : i, jj = horiz ? j : j + k; if (ii < 0 || jj < 0 || ii >= W || jj >= H) continue; s += src[jj * W + ii] * K[k + 2]; w += K[k + 2]; } o[j * W + i] = s / w; } return o; };
  for (let n = 0; n < passes; n++) { f = pass(f, true); f = pass(f, false); }
  return f;
}
// resample loop at uniform arc length
function resample(loop, step) {
  const out = []; let acc = 0; out.push(loop[0]);
  for (let i = 1; i <= loop.length; i++) {
    let a = loop[i - 1], b = loop[i % loop.length]; let seg = Math.hypot(b[0] - a[0], b[1] - a[1]);
    while (acc + seg >= step) { const t = (step - acc) / seg; const p = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]; out.push(p); a = p; seg = Math.hypot(b[0] - a[0], b[1] - a[1]); acc = 0; }
    acc += seg;
  }
  if (Math.hypot(out[0][0] - out[out.length - 1][0], out[0][1] - out[out.length - 1][1]) < step * 0.5) out.pop();
  return out;
}
const V = { sub: (a, b) => [a[0] - b[0], a[1] - b[1]], add: (a, b) => [a[0] + b[0], a[1] + b[1]], mul: (a, s) => [a[0] * s, a[1] * s], dot: (a, b) => a[0] * b[0] + a[1] * b[1], len: a => Math.hypot(a[0], a[1]), norm: a => { const l = Math.hypot(a[0], a[1]) || 1; return [a[0] / l, a[1] / l]; } };
function bez(b, t) { const m = 1 - t; return [m * m * m * b[0][0] + 3 * m * m * t * b[1][0] + 3 * m * t * t * b[2][0] + t * t * t * b[3][0], m * m * m * b[0][1] + 3 * m * m * t * b[1][1] + 3 * m * t * t * b[2][1] + t * t * t * b[3][1]]; }
function bezD(b, t) { const m = 1 - t; return [3 * m * m * (b[1][0] - b[0][0]) + 6 * m * t * (b[2][0] - b[1][0]) + 3 * t * t * (b[3][0] - b[2][0]), 3 * m * m * (b[1][1] - b[0][1]) + 6 * m * t * (b[2][1] - b[1][1]) + 3 * t * t * (b[3][1] - b[2][1])]; }
function bezDD(b, t) { const m = 1 - t; return [6 * m * (b[2][0] - 2 * b[1][0] + b[0][0]) + 6 * t * (b[3][0] - 2 * b[2][0] + b[1][0]), 6 * m * (b[2][1] - 2 * b[1][1] + b[0][1]) + 6 * t * (b[3][1] - 2 * b[2][1] + b[1][1])]; }
function chordParam(P) { const u = [0]; for (let i = 1; i < P.length; i++) u.push(u[i - 1] + V.len(V.sub(P[i], P[i - 1]))); const L = u[u.length - 1] || 1; return u.map(x => x / L); }
function genBez(P, u, t1, t2) {
  const p0 = P[0], p3 = P[P.length - 1]; let C = [[0, 0], [0, 0]], X = [0, 0];
  for (let i = 0; i < P.length; i++) { const t = u[i], m = 1 - t; const A1 = V.mul(t1, 3 * m * m * t), A2 = V.mul(t2, 3 * m * t * t);
    C[0][0] += V.dot(A1, A1); C[0][1] += V.dot(A1, A2); C[1][1] += V.dot(A2, A2);
    const tmp = V.sub(P[i], bez([p0, p0, p3, p3], t)); X[0] += V.dot(A1, tmp); X[1] += V.dot(A2, tmp); }
  C[1][0] = C[0][1]; const det = C[0][0] * C[1][1] - C[1][0] * C[0][1];
  let a1 = det ? (X[0] * C[1][1] - X[1] * C[0][1]) / det : 0, a2 = det ? (C[0][0] * X[1] - C[1][0] * X[0]) / det : 0;
  const segL = V.len(V.sub(p3, p0)), eps = 1e-6 * segL;
  if (a1 < eps || a2 < eps || a1 > segL * 2 || a2 > segL * 2) { a1 = a2 = segL / 3; }
  return [p0, V.add(p0, V.mul(t1, a1)), V.add(p3, V.mul(t2, a2)), p3];
}
function maxErr(P, b, u) { let m = 0, s = Math.floor(P.length / 2); for (let i = 1; i < P.length - 1; i++) { const d = V.sub(bez(b, u[i]), P[i]); const e = V.dot(d, d); if (e > m) { m = e; s = i; } } return [m, s]; }
function reparam(b, P, u) { return u.map((t, i) => { const d = V.sub(bez(b, t), P[i]), d1 = bezD(b, t), d2 = bezDD(b, t); const num = V.dot(d, d1), den = V.dot(d1, d1) + V.dot(d, d2); if (!den) return t; const n = t - num / den; return Math.min(1, Math.max(0, n)); }); }
function fitCubic(P, t1, t2, err, out) {
  if (P.length === 2) { const d = V.len(V.sub(P[1], P[0])) / 3; out.push([P[0], V.add(P[0], V.mul(t1, d)), V.add(P[1], V.mul(t2, d)), P[1]]); return; }
  let u = chordParam(P), b = genBez(P, u, t1, t2), [e, s] = maxErr(P, b, u);
  if (e < err) { out.push(b); return; }
  if (e < err * 16) { for (let k = 0; k < 20; k++) { const u2 = reparam(b, P, u); b = genBez(P, u2, t1, t2); [e, s] = maxErr(P, b, u2); if (e < err) { out.push(b); return; } u = u2; } }
  s = Math.max(1, Math.min(P.length - 2, s));
  const tc = V.norm(V.sub(P[s - 1], P[s + 1]));
  fitCubic(P.slice(0, s + 1), t1, tc, err, out); fitCubic(P.slice(s), V.mul(tc, -1), t2, err, out);
}
// corners: indices where turning angle (over window k) is sharp; returns sorted list
function findCorners(P, k = 4, thresh = 140) {
  const n = P.length, ang = new Float32Array(n);
  for (let i = 0; i < n; i++) { const a = V.sub(P[(i - k + n) % n], P[i]), b = V.sub(P[(i + k) % n], P[i]); ang[i] = Math.acos(Math.max(-1, Math.min(1, V.dot(V.norm(a), V.norm(b))))) * 180 / Math.PI; }
  const c = []; for (let i = 0; i < n; i++) { if (ang[i] >= thresh) continue; let min = true; for (let d = -k; d <= k; d++) if (d && ang[(i + d + n) % n] < ang[i]) { min = false; break; } if (min) c.push(i); }
  return c;
}
function tangentAt(P, i, dir, k = 3) { const n = P.length; let s = [0, 0]; for (let d = 1; d <= k; d++) s = V.add(s, V.sub(P[(i + dir * d + n * 4) % n], P[i])); return V.norm(s); }
function fitLoop(P, err, cornerOpts = {}) {
  const n = P.length; let C = findCorners(P, cornerOpts.k || 4, cornerOpts.thresh || 140);
  const segs = [];
  if (!C.length) { // smooth loop: split at 0 and n/2
    const h = Math.floor(n / 2); const t0 = V.norm(V.sub(P[1], P[n - 1])), th = V.norm(V.sub(P[h + 1], P[h - 1]));
    fitCubic(P.slice(0, h + 1), t0, V.mul(th, -1), err, segs); fitCubic(P.slice(h).concat([P[0]]), th, V.mul(t0, -1), err, segs); return segs;
  }
  for (let ci = 0; ci < C.length; ci++) {
    const a = C[ci], b = C[(ci + 1) % C.length]; const pts = []; let i = a; while (true) { pts.push(P[i]); if (i === b && pts.length > 1) break; i = (i + 1) % n; if (pts.length > n + 1) break; }
    if (pts.length < 2) continue;
    const m = pts.length; const t1 = tangentAt(pts, 0, 1, Math.min(3, m - 1)), t2 = tangentAt(pts, m - 1, -1, Math.min(3, m - 1));
    // use local, non-wrapping tangents
    const lt = V.norm(V.sub(pts[Math.min(m - 1, 3)], pts[0])), rt = V.norm(V.sub(pts[Math.max(0, m - 4)], pts[m - 1]));
    fitCubic(pts, lt, rt, err, segs);
  }
  return segs;
}
function segsToD(segs, f = n => (+n.toFixed(2)).toString()) {
  if (!segs.length) return ''; let d = `M${f(segs[0][0][0])} ${f(segs[0][0][1])}`;
  for (const s of segs) d += `C${f(s[1][0])} ${f(s[1][1])} ${f(s[2][0])} ${f(s[2][1])} ${f(s[3][0])} ${f(s[3][1])}`;
  return d + 'Z';
}
return { marchingLoops, gaussBlur, resample, fitLoop, segsToD, findCorners };
