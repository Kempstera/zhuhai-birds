// 共用小工具（Pages Functions 里以 _ 开头的文件不会被当成路由）

export const SCHEMA_STATEMENTS = [
  `CREATE TABLE IF NOT EXISTS hit (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      INTEGER NOT NULL,
    d       TEXT    NOT NULL,   -- 北京时间日期 YYYY-MM-DD
    h       INTEGER NOT NULL,   -- 北京时间小时 0-23
    path    TEXT    NOT NULL,
    ref     TEXT    NOT NULL DEFAULT '',
    country TEXT    NOT NULL DEFAULT '',
    lang    TEXT    NOT NULL DEFAULT '',
    dev     TEXT    NOT NULL DEFAULT '',
    br      TEXT    NOT NULL DEFAULT '',
    vid     TEXT    NOT NULL DEFAULT '',  -- 当日访客指纹（哈希后截断，不可逆）
    ip      TEXT    NOT NULL DEFAULT '',  -- 访客 IP（只在口令保护的看板里显示）
    city    TEXT    NOT NULL DEFAULT '',  -- CF-IPCity，中文城市名
    region  TEXT    NOT NULL DEFAULT '',  -- CF-IPRegion，省 / 州
    asn     TEXT    NOT NULL DEFAULT '',  -- 运营商 AS 号
    org     TEXT    NOT NULL DEFAULT '',  -- 运营商名称
    colo    TEXT    NOT NULL DEFAULT ''   -- Cloudflare 边缘节点
  )`,
  `CREATE INDEX IF NOT EXISTS idx_hit_ts   ON hit(ts)`,
  `CREATE INDEX IF NOT EXISTS idx_hit_d    ON hit(d)`,
  `CREATE INDEX IF NOT EXISTS idx_hit_path ON hit(path)`,
  `CREATE TABLE IF NOT EXISTS cfg (k TEXT PRIMARY KEY, v TEXT NOT NULL)`,
];

/* 老库补列：字段名、类型。SQLite 没有 ADD COLUMN IF NOT EXISTS，只能先查再加。 */
const EXTRA_COLS = [
  ["ip", "TEXT NOT NULL DEFAULT ''"],
  ["city", "TEXT NOT NULL DEFAULT ''"],
  ["region", "TEXT NOT NULL DEFAULT ''"],
  ["asn", "TEXT NOT NULL DEFAULT ''"],
  ["org", "TEXT NOT NULL DEFAULT ''"],
  ["colo", "TEXT NOT NULL DEFAULT ''"],
];

let schemaReady = false;

/** 建表 + 补列（幂等）。注意：不能用 db.exec() 跑多行 DDL —— 它按行切分会报 incomplete input。 */
export async function ensureSchema(db) {
  if (schemaReady) return;
  await db.batch(SCHEMA_STATEMENTS.map((sql) => db.prepare(sql)));
  // 迁移：早期建的表没有 ip/city 这些列，补上（已有则跳过）
  try {
    const info = await db.prepare("PRAGMA table_info(hit)").all();
    const have = new Set((info.results || []).map((r) => r.name));
    for (const [col, type] of EXTRA_COLS) {
      if (have.has(col)) continue;
      try {
        await db.prepare(`ALTER TABLE hit ADD COLUMN ${col} ${type}`).run();
      } catch (e) {
        /* 并发补列时可能撞车，忽略 */
      }
    }
  } catch (e) {
    /* 迁移失败不影响写入，后面的 INSERT 会自己报错 */
  }
  schemaReady = true;
}

/** 北京时间日期与小时 */
export function bj(ms) {
  const t = new Date(ms + 8 * 3600 * 1000);
  return { d: t.toISOString().slice(0, 10), h: t.getUTCHours() };
}

/** 把路径规整成便于聚合的形式 */
export function normPath(p) {
  if (!p || typeof p !== "string") return "/";
  let s = p.split("?")[0].split("#")[0];
  if (!s.startsWith("/")) s = "/" + s;
  s = s.replace(/\/index\.html$/, "/");
  if (s.length > 120) s = s.slice(0, 120);
  return s || "/";
}

export function deviceOf(ua) {
  if (!ua) return "unknown";
  if (/iPad|Tablet|PlayBook|Silk|(Android(?!.*Mobile))/i.test(ua)) return "tablet";
  if (/Mobi|iPhone|iPod|Android.*Mobile|Windows Phone/i.test(ua)) return "mobile";
  return "desktop";
}

export function browserOf(ua) {
  if (!ua) return "unknown";
  if (/Edg\//i.test(ua)) return "Edge";
  if (/OPR\/|Opera/i.test(ua)) return "Opera";
  if (/Firefox\//i.test(ua)) return "Firefox";
  if (/CriOS/i.test(ua)) return "Chrome";
  if (/Chrome\//i.test(ua)) return "Chrome";
  if (/Safari\//i.test(ua)) return "Safari";
  if (/curl|wget|python|Go-http|node-fetch/i.test(ua)) return "script";
  return "other";
}

export function hostOf(url) {
  if (!url) return "";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

/** 当日访客指纹：ip + UA + 盐 + 日期 → 16 位十六进制，不可逆推 */
export async function visitorId(ip, ua, salt, day) {
  const bytes = new TextEncoder().encode(`${ip}|${ua}|${salt}|${day}`);
  const buf = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(buf)]
    .slice(0, 8)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** 从 D1 cfg 表读一个值 */
export async function readCfg(db, key) {
  const row = await db.prepare("SELECT v FROM cfg WHERE k = ?").bind(key).first();
  return row ? row.v : "";
}

/** 常量时间比较，避免时序侧信道 */
export function safeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
