// POST /api/hit —— 记录一次页面浏览
// 不写 cookie、不存原始 IP；只落一行聚合所需的字段。
import { ensureSchema, bj, normPath, deviceOf, browserOf, hostOf, visitorId, readCfg, json } from "../_lib.js";

const BOT =
  /bot|crawl|spider|slurp|bingpreview|facebookexternalhit|embedly|quora link preview|pinterest|vkshare|w3c_validator|monitor|uptime|pingdom|curl|wget|python-requests|python-urllib|go-http|okhttp|java\/|headless|phantom|scrapy|semrush|ahrefs|mj12|dotbot|petalbot|bytespider|yisou|yandex|baidu|sogou|exabot|ia_archiver|archive\.org/i;

let ready = false;

export async function onRequestPost({ request, env }) {
  try {
    // 同源校验：只接受本站页面发来的信标
    const origin = request.headers.get("origin");
    if (origin) {
      const oh = hostOf(origin);
      const uh = hostOf(request.url);
      if (oh && uh && oh !== uh) return new Response(null, { status: 403 });
    }

    const ua = request.headers.get("user-agent") || "";
    if (!ua || BOT.test(ua)) return new Response(null, { status: 204 });
    // 尊重「请勿追踪」
    if (request.headers.get("dnt") === "1" || request.headers.get("sec-gpc") === "1")
      return new Response(null, { status: 204 });

    const text = await request.text();
    if (text.length > 800) return new Response(null, { status: 204 });
    let body = {};
    try {
      body = JSON.parse(text || "{}");
    } catch {
      return new Response(null, { status: 204 });
    }

    const now = Date.now();
    const { d, h } = bj(now);
    const path = normPath(body.path);
    if (path.startsWith("/admin") || path.startsWith("/api")) return new Response(null, { status: 204 });

    // 站内跳转不算来源
    const siteHost = hostOf(request.url);
    let ref = hostOf(body.ref);
    if (ref === siteHost || ref.endsWith("." + siteHost)) ref = "";
    if (ref.length > 80) ref = ref.slice(0, 80);

    const country = (request.headers.get("cf-ipcountry") || "").slice(0, 2).toUpperCase();
    const lang = (body.lang || "").slice(0, 8);
    const ip = request.headers.get("cf-connecting-ip") || "";
    const dev = deviceOf(ua);
    const br = browserOf(ua);

    if (!ready) {
      await ensureSchema(env.DB);
      ready = true;
    }
    const salt = (await readCfg(env.DB, "salt")) || "zhuhai-birds";
    const vid = await visitorId(ip, ua, salt, d);

    await env.DB.prepare(
      "INSERT INTO hit (ts,d,h,path,ref,country,lang,dev,br,vid) VALUES (?,?,?,?,?,?,?,?,?,?)"
    )
      .bind(now, d, h, path, ref, country, lang, dev, br, vid)
      .run();

    // 偶尔清理两年前的数据，避免库无限增长
    if (Math.random() < 0.02) {
      await env.DB.prepare("DELETE FROM hit WHERE ts < ?").bind(now - 730 * 864e5).run();
    }
    return new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
  } catch {
    // 统计失败绝不影响页面
    return new Response(null, { status: 204 });
  }
}

export async function onRequestGet() {
  return json({ ok: false, error: "POST only" }, 405);
}
