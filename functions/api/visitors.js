// GET /api/visitors?days=30&limit=3000 —— 访客明细行（站长专用，需要 Bearer 口令）
//
// 与 /api/stats 的区别：这里返回的是**逐条记录**，让 /visits/ 页面像 musicradio 那样
// 在浏览器里现算 KPI、趋势、时段、洞察与明细表 —— 切时间范围、搜索、排序都不用再打接口。
//
// 返回的字段里有原始 IP、城市、地区、运营商 —— 这个接口要 Bearer 口令，只给站长用；
// 页面本身 noindex，不进导航与 sitemap。vid 仍是「ip+UA+盐+当日」的哈希前 8 字节。
import { ensureSchema, readCfg, safeEqual, json } from "../_lib.js";

export async function onRequestGet({ request, env }) {
  const auth = request.headers.get("authorization") || "";
  const token = auth.replace(/^Bearer\s+/i, "").trim();
  if (!token) return json({ ok: false, error: "unauthorized" }, 401);

  // 顺手跑一次建表 + 补列（幂等，CI 里只跑一次），否则老库没有 ip/city 列会 SELECT 失败
  let expected = env.ADMIN_TOKEN || "";
  try {
    await ensureSchema(env.DB);
    if (!expected) expected = await readCfg(env.DB, "admin_token");
  } catch (e) {
    return json({ ok: false, error: "db_not_ready", detail: String(e) }, 503);
  }
  if (!expected) return json({ ok: false, error: "not_initialized" }, 503);
  if (!safeEqual(token, expected)) return json({ ok: false, error: "unauthorized" }, 401);

  const url = new URL(request.url);
  const days = Math.min(3650, Math.max(1, parseInt(url.searchParams.get("days") || "3650", 10) || 3650));
  const limit = Math.min(5000, Math.max(100, parseInt(url.searchParams.get("limit") || "3000", 10) || 3000));

  const from = new Date(Date.now() + 8 * 3600e3 - (days - 1) * 864e5).toISOString().slice(0, 10);

  let rows, total;
  try {
    const [r1, r2] = await env.DB.batch([
      env.DB.prepare(
        `SELECT ts, d, h, path, ref, country, lang, dev, br, vid,
                ip, city, region, asn, org, colo
           FROM hit WHERE d >= ? ORDER BY ts DESC LIMIT ?`
      ).bind(from, limit),
      env.DB.prepare("SELECT COUNT(*) n FROM hit WHERE d >= ?").bind(from),
    ]);
    rows = r1.results || [];
    total = (r2.results && r2.results[0] ? r2.results[0].n : 0) || 0;
  } catch (e) {
    return json({ ok: false, error: "query_failed", detail: String(e) }, 503);
  }

  const body = JSON.stringify({
    ok: true,
    generatedAt: new Date().toISOString(),
    tz: "Asia/Shanghai",
    range: { days, from },
    total,
    truncated: total > rows.length,
    rows: rows.map((r) => ({
      t: r.ts,        // 毫秒时间戳
      d: r.d,         // 北京时间日期
      h: r.h,         // 北京时间小时
      p: r.path,
      r: r.ref,
      c: r.country,
      l: r.lang,
      dv: r.dev,
      br: r.br,
      v: r.vid,       // 当日指纹（哈希前 16 位）
      ip: r.ip || "",
      ci: r.city || "",
      rg: r.region || "",
      asn: r.asn || "",
      og: r.org || "",
      co: r.colo || "",
    })),
  });

  return new Response(body, {
    headers: {
      "content-type": "application/json; charset=utf-8",
      // 站长数据不进任何缓存
      "cache-control": "no-store, max-age=0",
      "x-content-type-options": "nosniff",
    },
  });
}
