// GET /api/visits —— 公开的站点访问统计（只有聚合数字，没有个体痕迹）
// 与 /api/stats 的区别：不需要口令，因此只给「能公开展示」的维度：
// 总量、按天曲线、热门页面、来源站点、国家、设备、语言。
// 不返回原始 IP（本来就没存）、不返回访客指纹、不返回逐条记录。
import { ensureSchema, bj, json } from "../_lib.js";

const dayStr = (ms) => bj(ms).d;

export async function onRequestGet({ env }) {
  try {
    await ensureSchema(env.DB);
  } catch (e) {
    return json({ ok: false, error: "db_not_ready" }, 503);
  }

  const days = 30;
  const today = dayStr(Date.now());
  const from = dayStr(Date.now() - (days - 1) * 864e5);
  const P = (sql, ...args) => env.DB.prepare(sql).bind(...args);

  let R;
  try {
    R = await env.DB.batch([
      /* 0 */ P("SELECT COUNT(*) pv, COUNT(DISTINCT vid) uv FROM hit WHERE d >= ?", from),
      /* 1 */ P("SELECT d, COUNT(*) pv, COUNT(DISTINCT vid) uv FROM hit WHERE d >= ? GROUP BY d ORDER BY d", from),
      /* 2 */ P(`SELECT CASE WHEN path IN ('/en','/en/') THEN '/'
                 WHEN path LIKE '/en/%' THEN substr(path, 4) ELSE path END p,
                 COUNT(*) c FROM hit WHERE d >= ? GROUP BY p ORDER BY c DESC LIMIT 8`, from),
      /* 3 */ P("SELECT CASE WHEN ref = '' THEN '' ELSE ref END k, COUNT(*) c FROM hit WHERE d >= ? GROUP BY k ORDER BY c DESC LIMIT 7", from),
      /* 4 */ P("SELECT CASE WHEN country = '' THEN '??' ELSE country END k, COUNT(*) c FROM hit WHERE d >= ? GROUP BY k ORDER BY c DESC LIMIT 8", from),
      /* 5 */ P("SELECT dev k, COUNT(*) c FROM hit WHERE d >= ? GROUP BY k ORDER BY c DESC", from),
      /* 6 */ P("SELECT lang k, COUNT(*) c FROM hit WHERE d >= ? GROUP BY k ORDER BY c DESC", from),
      /* 7 */ P("SELECT COUNT(*) pv FROM hit"),
      /* 8 */ P("SELECT MIN(d) s, MAX(d) e FROM hit"),
      /* 9 */ P("SELECT COUNT(*) n FROM (SELECT 1 FROM hit GROUP BY d)"),
      /* 10 */ P("SELECT COUNT(*) pv, COUNT(DISTINCT vid) uv FROM hit WHERE d = ?", today),
      /* 11 */ P("SELECT COUNT(*) pv, COUNT(DISTINCT vid) uv FROM hit WHERE d >= ?",
        dayStr(Date.now() - 6 * 864e5)),
    ]);
  } catch (e) {
    return json({ ok: false, error: "query_failed" }, 503);
  }

  const rows = (i) => R[i]?.results || [];
  const one = (i) => rows(i)[0] || {};

  const map = new Map(rows(1).map((r) => [r.d, r]));
  const series = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = dayStr(Date.now() - i * 864e5);
    const r = map.get(d);
    series.push({ d, pv: r ? r.pv : 0, uv: r ? r.uv : 0 });
  }

  const body = JSON.stringify({
    ok: true,
    generatedAt: new Date().toISOString(),
    tz: "Asia/Shanghai",
    range: { days, from, to: today },
    month: { pv: one(0).pv || 0, uv: one(0).uv || 0 },
    today: { pv: one(10).pv || 0, uv: one(10).uv || 0 },
    week: { pv: one(11).pv || 0, uv: one(11).uv || 0 },
    allTime: { pv: one(7).pv || 0, days: one(9).n || 0, since: one(8).s || null },
    series,
    paths: rows(2),
    refs: rows(3),
    countries: rows(4),
    devices: rows(5),
    langs: rows(6),
  });

  return new Response(body, {
    headers: {
      "content-type": "application/json; charset=utf-8",
      // 边缘缓存 5 分钟：访客再多也只打一次库
      "cache-control": "public, max-age=60, s-maxage=300",
      "x-content-type-options": "nosniff",
    },
  });
}
