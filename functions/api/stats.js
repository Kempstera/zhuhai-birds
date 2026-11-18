// GET /api/stats?days=7 —— 站长看板数据（需要 Bearer token）
import { ensureSchema, bj, readCfg, safeEqual, json } from "../_lib.js";

const dayStr = (ms) => bj(ms).d;

export async function onRequestGet({ request, env }) {
  const auth = request.headers.get("authorization") || "";
  const token = auth.replace(/^Bearer\s+/i, "").trim();
  if (!token) return json({ ok: false, error: "unauthorized" }, 401);

  let expected = env.ADMIN_TOKEN || "";
  if (!expected) {
    try {
      await ensureSchema(env.DB);
      expected = await readCfg(env.DB, "admin_token");
    } catch (e) {
      return json({ ok: false, error: "db_not_ready", detail: String(e) }, 503);
    }
  }
  if (!expected) return json({ ok: false, error: "not_initialized" }, 503);
  if (!safeEqual(token, expected)) return json({ ok: false, error: "unauthorized" }, 401);

  const url = new URL(request.url);
  const days = Math.min(365, Math.max(1, parseInt(url.searchParams.get("days") || "7", 10) || 7));
  const today = dayStr(Date.now());
  const from = dayStr(Date.now() - (days - 1) * 864e5);
  const P = (sql, ...args) => env.DB.prepare(sql).bind(...args);

  const R = await env.DB.batch([
    /* 0 */ P("SELECT COUNT(*) pv, COUNT(DISTINCT vid) uv FROM hit WHERE d >= ?", from),
    /* 1 */ P("SELECT d, COUNT(*) pv, COUNT(DISTINCT vid) uv FROM hit WHERE d >= ? GROUP BY d ORDER BY d", from),
    /* 2 */ P("SELECT path p, COUNT(*) c, COUNT(DISTINCT vid) u FROM hit WHERE d >= ? GROUP BY path ORDER BY c DESC LIMIT 15", from),
    /* 3 */ P("SELECT CASE WHEN ref = '' THEN '(direct)' ELSE ref END k, COUNT(*) c FROM hit WHERE d >= ? GROUP BY k ORDER BY c DESC LIMIT 12", from),
    /* 4 */ P("SELECT CASE WHEN country = '' THEN '??' ELSE country END k, COUNT(*) c FROM hit WHERE d >= ? GROUP BY k ORDER BY c DESC LIMIT 12", from),
    /* 5 */ P("SELECT dev k, COUNT(*) c FROM hit WHERE d >= ? GROUP BY k ORDER BY c DESC", from),
    /* 6 */ P("SELECT br k, COUNT(*) c FROM hit WHERE d >= ? GROUP BY br ORDER BY c DESC LIMIT 8", from),
    /* 7 */ P("SELECT lang k, COUNT(*) c FROM hit WHERE d >= ? GROUP BY k ORDER BY c DESC", from),
    /* 8 */ P("SELECT COUNT(*) pv FROM hit"),
    /* 9 */ P("SELECT MIN(d) s, MAX(d) e FROM hit"),
    /* 10 */ P("SELECT h, COUNT(*) c FROM hit WHERE d = ? GROUP BY h ORDER BY h", today),
    /* 11 */ P("SELECT COUNT(*) pv, COUNT(DISTINCT vid) uv FROM hit WHERE d = ?", today),
    /* 12 */ P("SELECT COUNT(*) n FROM (SELECT 1 FROM hit GROUP BY d)", ),
  ]);

  const rows = (i) => R[i]?.results || [];
  const one = (i) => rows(i)[0] || {};

  const map = new Map(rows(1).map((r) => [r.d, r]));
  const series = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = dayStr(Date.now() - i * 864e5);
    const r = map.get(d);
    series.push({ d, pv: r ? r.pv : 0, uv: r ? r.uv : 0 });
  }

  const hourly = Array.from({ length: 24 }, (_, h) => {
    const r = rows(10).find((x) => x.h === h);
    return r ? r.c : 0;
  });

  const t = one(0);
  return json({
    ok: true,
    generatedAt: new Date().toISOString(),
    range: { days, from, to: today, tz: "Asia/Shanghai" },
    totals: {
      pv: t.pv || 0,
      uv: t.uv || 0,
      avg: Math.round(((t.pv || 0) / days) * 10) / 10,
    },
    today: { pv: one(11).pv || 0, uv: one(11).uv || 0 },
    allTime: { pv: one(8).pv || 0, days: one(12).n || 0, since: one(9).s || null, until: one(9).e || null },
    series,
    hourly,
    paths: rows(2),
    refs: rows(3),
    countries: rows(4),
    devices: rows(5),
    browsers: rows(6),
    langs: rows(7),
  });
}
