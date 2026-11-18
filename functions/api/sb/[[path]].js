// /api/sb/* —— 把 Supabase 的 REST / Auth 请求从本站域名中转过去。
//
// 为什么需要它：*.supabase.co 在中国大陆会被 TLS 层面重置（ClientHello 一发就被
// RST），游客打开 /board/ 时「登录」和「留言」都会静默失败。本站域名在 Cloudflare
// 上，国内可以正常访问，所以前端把 baseURL 写成 /api/sb，由这个函数转发到 Supabase。
//
// 转发是「透明」的：apikey / Authorization 原样带过去，权限仍然由 Postgres 的 RLS
// 决定，这里不做任何鉴权，也不缓存。

const UPSTREAM = "https://xivobmucjutdfoxmfjxu.supabase.co";

// 这些头由 Cloudflare 自己生成，转发上游会出错
const DROP = new Set([
  "host", "connection", "content-length", "accept-encoding", "cf-connecting-ip",
  "cf-ipcountry", "cf-ray", "cf-visitor", "cf-worker", "x-forwarded-proto",
  "x-forwarded-for", "x-real-ip", "cdn-loop", "origin", "referer",
]);

function pass(res) {
  const h = new Headers();
  for (const [k, v] of res.headers) {
    const lk = k.toLowerCase();
    if (lk === "content-encoding" || lk === "content-length" || lk === "transfer-encoding") continue;
    h.set(k, v);
  }
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers: h });
}

export async function onRequest({ request, params }) {
  const parts = params.path;
  const path = Array.isArray(parts) ? parts.join("/") : (parts || "");
  if (!path) return new Response("not found", { status: 404 });

  const url = new URL(request.url);
  const target = UPSTREAM + "/" + path + url.search;

  const headers = new Headers();
  for (const [k, v] of request.headers) {
    if (!DROP.has(k.toLowerCase())) headers.set(k, v);
  }

  const init = {
    method: request.method,
    headers,
    redirect: "manual",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  try {
    return pass(await fetch(target, init));
  } catch (e) {
    return new Response(JSON.stringify({ message: "upstream_unreachable" }), {
      status: 502,
      headers: { "content-type": "application/json" },
    });
  }
}
