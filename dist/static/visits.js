/* 访客看板 /visits —— 站长专用。
   一次取回明细（最多 3000 条），KPI、趋势、时段、洞察、排行、明细表全部在浏览器里现算，
   所以切时间范围、搜索、排序都不用再打接口。表里没有 IP，指纹是哈希截断，按日去重。 */
(function () {
  "use strict";

  var gate = document.getElementById("vdGate");
  var body = document.getElementById("vdBody");
  if (!gate || !body) return;

  var KEY_STORE = "birds_visits_key";
  var RANGE_STORE = "birds_visits_days";
  var MAX_ROWS = 3000;

  var state = {
    key: "",
    days: 30,
    rows: [],
    total: 0,
    truncated: false,
    generatedAt: "",
    page: 1,
    size: 50,
    q: "",
    sort: "time",
    dir: -1,
  };

  var $ = function (id) { return document.getElementById(id); };
  var nf = new Intl.NumberFormat("zh-CN");
  var fmt = function (n) { return nf.format(n || 0); };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var pad = function (n) { return n < 10 ? "0" + n : "" + n; };
  var pct = function (a, b) { return b ? Math.round((a / b) * 100) : 0; };
  var sum = function (a) { return a.reduce(function (x, y) { return x + y; }, 0); };

  /* ---------- 时间 ---------- */
  function bjDay(ms) { return new Date(ms + 8 * 3600e3).toISOString().slice(0, 10); }
  function fmtTime(ms) {
    var t = new Date(ms + 8 * 3600e3);
    if (isNaN(t)) return "—";
    return pad(t.getUTCMonth() + 1) + "-" + pad(t.getUTCDate()) + " " +
      pad(t.getUTCHours()) + ":" + pad(t.getUTCMinutes());
  }
  function fmtDayShort(d) { return d.slice(5).replace("-", "/"); }
  var WEEK = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

  /* ---------- 国家 ---------- */
  var region = null;
  try { region = new Intl.DisplayNames(["zh-CN"], { type: "region" }); } catch (e) { region = null; }
  function ccName(code) {
    if (!code || code === "??") return "未知";
    try { return (region && region.of(code)) || code; } catch (e) { return code; }
  }
  function flag(cc) {
    if (!cc || cc.length !== 2) return "🌐";
    try {
      return String.fromCodePoint.apply(null, cc.toUpperCase().split("").map(function (c) {
        return 0x1f1e6 - 65 + c.charCodeAt(0);
      }));
    } catch (e) { return "🌐"; }
  }

  /* ---------- 归类 ---------- */
  var BIRDS = window.VD_BIRDS || {};

  function sideOf(p) {
    if (p.indexOf("/zh") === 0) return "中文版 /zh/";
    if (p.indexOf("/en") === 0) return "旧英文 /en/";
    return "英文版（根目录）";
  }
  function kindOf(p) {
    var q = p.replace(/^\/(zh|en)(?=\/|$)/, "") || "/";
    if (q === "/" || q === "/index.html") return "首页";
    if (q.indexOf("/bird/") === 0) return "物种详情";
    if (q.indexOf("/guide") === 0) return "观鸟指南";
    if (q.indexOf("/board") === 0) return "留言板";
    if (q.indexOf("/visits") === 0) return "统计页";
    if (q.indexOf("/admin") === 0) return "后台";
    return "其他";
  }
  function slugOf(p) {
    var m = p.replace(/^\/(zh|en)(?=\/|$)/, "").match(/^\/bird\/([^\/.]+)/);
    return m ? m[1] : null;
  }
  function birdName(slug) { return BIRDS[slug] || slug; }
  function devName(d) {
    return { mobile: "📱 手机", tablet: "📲 平板", desktop: "🖥 电脑", unknown: "❔ 未知" }[d] || "❔ 未知";
  }
  function prettyRef(r) {
    if (!r) return "直接打开 / 微信内点开";
    return r;
  }

  /* ---------- 计数 ---------- */
  function countBy(rows, fn) {
    var m = {};
    rows.forEach(function (r) {
      var k = fn(r);
      if (k === null || k === undefined || k === "") return;
      m[k] = (m[k] || 0) + 1;
    });
    return Object.keys(m).map(function (k) { return { k: k, c: m[k] }; })
      .sort(function (a, b) { return b.c - a.c; });
  }

  function inRange() {
    if (!state.days) return state.rows;
    var cut = bjDay(Date.now() - (state.days - 1) * 864e5);
    return state.rows.filter(function (r) { return r.d >= cut; });
  }

  /* ---------- 分析 ---------- */
  function analyze(rows) {
    var today = bjDay(Date.now());
    var yesterday = bjDay(Date.now() - 864e5);
    var nowSql = 0;

    var uniq = {};
    rows.forEach(function (r) {
      uniq[r.d + "|" + (r.v || "anon")] = 1;
      nowSql += 1;
    });
    var visitors = Object.keys(uniq).length;
    var views = rows.length;

    /* 今天/昨天始终按全部已载入的数据算，否则切到「今天」时昨天会显示 0 */
    var all = state.rows.length ? state.rows : rows;
    var tToday = all.filter(function (r) { return r.d === today; }).length;
    var tYest = all.filter(function (r) { return r.d === yesterday; }).length;

    /* 每日序列：最多画 90 根柱子 */
    var byDay = {};
    rows.forEach(function (r) {
      if (!byDay[r.d]) byDay[r.d] = { pv: 0, set: {} };
      byDay[r.d].pv++;
      byDay[r.d].set[r.v || "anon"] = 1;
    });
    var span;
    if (state.days) {
      span = Math.min(state.days, 90);
    } else if (rows.length) {
      var first = rows.reduce(function (m, r) { return r.d < m ? r.d : m; }, rows[0].d);
      var diff = Math.round((Date.parse(today) - Date.parse(first)) / 864e5) + 1;
      span = Math.min(90, Math.max(1, diff));
    } else {
      span = 30;
    }
    var series = [];
    for (var i = span - 1; i >= 0; i--) {
      var d = bjDay(Date.now() - i * 864e5);
      var hit = byDay[d];
      series.push({ d: d, pv: hit ? hit.pv : 0, uv: hit ? Object.keys(hit.set).length : 0 });
    }

    /* 时段 */
    var hourly = new Array(24).fill(0);
    rows.forEach(function (r) { if (r.h >= 0 && r.h < 24) hourly[r.h]++; });

    /* 星期 */
    var week = new Array(7).fill(0);
    rows.forEach(function (r) {
      var t = new Date(r.d + "T00:00:00+08:00");
      if (!isNaN(t)) week[t.getDay()]++;
    });

    /* 访问深度：同一天同一指纹看了几页 */
    var depthMap = {};
    rows.forEach(function (r) {
      var k = r.d + "|" + (r.v || "anon");
      depthMap[k] = (depthMap[k] || 0) + 1;
    });
    var depths = Object.keys(depthMap).map(function (k) { return depthMap[k]; });
    var depthBars = [
      { k: "只看了 1 页", c: depths.filter(function (n) { return n === 1; }).length },
      { k: "2–3 页", c: depths.filter(function (n) { return n >= 2 && n <= 3; }).length },
      { k: "4–6 页", c: depths.filter(function (n) { return n >= 4 && n <= 6; }).length },
      { k: "7 页以上", c: depths.filter(function (n) { return n >= 7; }).length },
    ];

    /* 物种热度 */
    var birds = countBy(rows, function (r) { return slugOf(r.p); });

    var mobile = rows.filter(function (r) { return r.dv === "mobile"; }).length;
    var desktop = rows.filter(function (r) { return r.dv === "desktop"; }).length;
    var zh = rows.filter(function (r) { return (r.l || "").toLowerCase().indexOf("zh") === 0; }).length;
    var en = rows.filter(function (r) { return (r.l || "").toLowerCase().indexOf("en") === 0; }).length;

    return {
      views: views, visitors: visitors,
      perPerson: visitors ? views / visitors : 0,
      today: tToday, yesterday: tYest,
      series: series, hourly: hourly, week: week,
      depthBars: depthBars, depths: depths,
      birds: birds, mobile: mobile, desktop: desktop, zh: zh, en: en,
      devices: countBy(rows, function (r) { return devName(r.dv); }),
      browsers: countBy(rows, function (r) { return r.br || "未知"; }),
      langs: countBy(rows, function (r) { return r.l || "未知"; }),
      kinds: countBy(rows, function (r) { return kindOf(r.p); }),
      sides: countBy(rows, function (r) { return sideOf(r.p); }),
      sources: countBy(rows, function (r) { return prettyRef(r.r); }),
      pages: countBy(rows, function (r) { return r.p || "/"; }),
      countries: countBy(rows, function (r) { return r.c ? flag(r.c) + " " + ccName(r.c) : "未知"; }),
      singles: depths.filter(function (n) { return n === 1; }).length,
    };
  }

  /* ---------- 渲染：KPI ---------- */
  function renderKpis(a) {
    var delta = a.yesterday ? Math.round(((a.today - a.yesterday) / a.yesterday) * 100) : null;
    var items = [
      { v: fmt(a.visitors), u: "位", l: "访客（按日去重）", n: "跨日不可关联，隔天再来会再计一次" },
      { v: fmt(a.views), u: "次", l: "页面浏览", n: "日均 " + (a.series.length ? (a.views / Math.max(1, a.series.filter(function (s) { return s.pv; }).length)).toFixed(1) : "0") + " 次" },
      { v: a.perPerson.toFixed(1), u: "页", l: "人均页数", n: "只看 1 页的占 " + pct(a.singles, a.visitors) + "%" },
      { v: fmt(a.today), u: "次", l: "今天", n: "昨日 " + a.yesterday + " 次" + (delta === null ? "" : "（" + (delta > 0 ? "+" : "") + delta + "%）"), cls: delta > 0 ? "up" : delta < 0 ? "down" : "" },
      { v: pct(a.mobile, a.views) + "%", u: "", l: "手机访问", n: "桌面 " + a.desktop + " 次" },
      { v: pct(a.zh, a.views) + "%", u: "", l: "中文界面", n: "英文 " + a.en + " 次" },
    ];
    $("vdKpis").innerHTML = items.map(function (it) {
      return '<div class="vd__kpi"><b>' + esc(it.v) + (it.u ? "<small>" + it.u + "</small>" : "") + "</b>" +
        "<span>" + it.l + "</span>" +
        (it.n ? '<i class="' + (it.cls || "") + '">' + esc(it.n) + "</i>" : "") + "</div>";
    }).join("");
  }

  /* ---------- 渲染：趋势 ---------- */
  function renderTrend(a) {
    var host = $("vdTrend");
    var pts = a.series;
    if (!pts.length || !a.views) { host.innerHTML = '<p class="vd__empty">这个时间段还没有数据</p>'; return; }
    var firstIdx = 0;
    for (var k = 0; k < pts.length; k++) { if (pts[k].pv) { firstIdx = k; break; } }
    pts = pts.slice(firstIdx);
    var W = 640, H = 200, P = 30, B = 26;
    var maxV = Math.max.apply(null, pts.map(function (p) { return p.pv; })) || 1;
    var bw = (W - P * 2) / pts.length;
    var barW = Math.max(2, Math.min(18, bw * 0.52));
    var y = function (v) { return H - B - (v / maxV) * (H - B - 14); };

    var bars = pts.map(function (p, i) {
      var x = P + i * bw + (bw - barW) / 2;
      var h = Math.max(p.pv ? 1.5 : 0, (H - B) - y(p.pv));
      if (!p.pv) return "";
      return '<rect x="' + x.toFixed(1) + '" y="' + ((H - B) - h).toFixed(1) + '" width="' + barW.toFixed(1) +
        '" height="' + h.toFixed(1) + '" rx="1.5" fill="var(--forest)" opacity="0.18"><title>' +
        esc(fmtDayShort(p.d) + "：" + p.pv + " 次浏览 / " + p.uv + " 位访客") + "</title></rect>";
    }).join("");

    var line = pts.map(function (p, i) {
      var x = P + i * bw + bw / 2;
      return (i ? "L" : "M") + x.toFixed(1) + " " + y(p.uv).toFixed(1);
    }).join(" ");

    var dots = pts.map(function (p, i) {
      if (!p.uv) return "";
      var x = P + i * bw + bw / 2;
      return '<circle cx="' + x.toFixed(1) + '" cy="' + y(p.uv).toFixed(1) + '" r="2.5" fill="var(--clay)"><title>' +
        esc(fmtDayShort(p.d) + "：" + p.uv + " 位访客") + "</title></circle>";
    }).join("");

    var every = Math.ceil(pts.length / 7);
    var labels = pts.map(function (p, i) {
      if (i % every) return "";
      var x = P + i * bw + bw / 2;
      return '<text x="' + x.toFixed(1) + '" y="' + (H - 7) + '" font-size="9.5" fill="var(--ink-3)" text-anchor="middle">' +
        esc(fmtDayShort(p.d)) + "</text>";
    }).join("");

    host.innerHTML = '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="访问趋势">' +
      '<line x1="' + P + '" y1="' + (H - B) + '" x2="' + (W - P) + '" y2="' + (H - B) + '" stroke="var(--line)" stroke-width="1"/>' +
      bars +
      '<path d="' + line + '" fill="none" stroke="var(--clay)" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" opacity="0.85"/>' +
      dots + labels +
      '<text x="' + P + '" y="11" font-size="9.5" fill="var(--ink-3)">峰值 ' + maxV + " 次/天</text>" +
      "</svg>";
  }

  /* ---------- 渲染：时段 ---------- */
  function renderHours(a) {
    var host = $("vdHours");
    var arr = a.hourly;
    var W = 380, H = 200, P = 10, B = 24;
    var maxV = Math.max.apply(null, arr) || 1;
    var bw = (W - P * 2) / 24;
    var bars = arr.map(function (v, h) {
      var barH = v ? Math.max(1.5, (v / maxV) * (H - B - 20)) : 0;
      if (!v) return "";
      var hot = v >= maxV * 0.72;
      return '<rect x="' + (P + h * bw + 1).toFixed(1) + '" y="' + (H - B - barH).toFixed(1) +
        '" width="' + (bw - 2).toFixed(1) + '" height="' + barH.toFixed(1) + '" rx="1.5" fill="' +
        (hot ? "var(--clay)" : "var(--forest)") + '" opacity="' + (hot ? 0.8 : 0.22) + '"><title>' +
        h + ":00 — " + v + " 次</title></rect>";
    }).join("");
    var labels = [0, 6, 12, 18, 23].map(function (h) {
      return '<text x="' + (P + h * bw + bw / 2).toFixed(1) + '" y="' + (H - 7) +
        '" font-size="9.5" fill="var(--ink-3)" text-anchor="middle">' + h + "</text>";
    }).join("");
    host.innerHTML = '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="时段分布">' +
      '<line x1="' + P + '" y1="' + (H - B) + '" x2="' + (W - P) + '" y2="' + (H - B) + '" stroke="var(--line)" stroke-width="1"/>' +
      bars + labels + "</svg>";
  }

  /* ---------- 渲染：自动分析 ---------- */
  function renderInsights(a) {
    var out = [];
    var rows = a.views;

    /* 1 今天 vs 昨天 */
    if (a.today || a.yesterday) {
      var d = a.yesterday ? Math.round(((a.today - a.yesterday) / a.yesterday) * 100) : 0;
      out.push({
        ico: d >= 0 ? "📈" : "📉",
        cls: d > 40 ? "good" : d < -30 ? "warn" : "",
        b: "今天 " + a.today + " 次浏览，昨天 " + a.yesterday + " 次",
        p: (a.today < a.yesterday ? "今天还没过完，" : "") + (d === 0
          ? "两天基本持平。" + (a.today < 3 ? "样本还小，单日波动不必过度解读。" : "")
          : "相比昨天" + (d > 0 ? "增长" : "回落") + " " + Math.abs(d) + "%。") + " " +
            (d > 60 && a.today >= a.yesterday ? "这种量级的跳变通常来自一次转发（朋友圈或群里），可以看看同时段的国家与来源是不是突然多了同一处。" : ""),
      });
    }

    /* 2 高峰时段 */
    var peak = a.hourly.indexOf(Math.max.apply(null, a.hourly));
    if (rows >= 5) {
      out.push({
        ico: "🕘",
        b: "访问高峰在 " + peak + ":00 – " + (peak + 1) + ":00（占 " + pct(a.hourly[peak], rows) + "%）",
        p: "看鸟的人多半是白天出门、晚上查资料。想把新物种推出去，挑这个时段发，被看到的概率最高。" +
          (peak >= 22 || peak <= 5 ? "凌晨也有量，多半是手机没锁屏或后台刷新，不必当成真实读者。" : ""),
      });
    }

    /* 3 移动端 */
    if (rows >= 3) {
      var ms = pct(a.mobile, rows);
      out.push({
        ico: "📱",
        cls: ms > 80 ? "warn" : "",
        b: "手机访问占 " + ms + "%（桌面 " + a.desktop + " 次）",
        p: ms > 80
          ? "这是「一个在野外用手机翻的图鉴」，不是「也支持手机」的桌面站。字号、图集滑动、录音按钮都该按单手操作来定。"
          : "桌面与手机都有相当比例：桌面大概是行前做功课，手机是在现场核对。两边都得站得住。",
      });
    }

    /* 4 语言 */
    if (rows >= 5) {
      var zs = pct(a.zh, rows);
      out.push({
        ico: "🌏",
        cls: zs < 20 ? "good" : "",
        b: "中文界面占 " + zs + "%，英文 " + pct(a.en, rows) + "%",
        p: zs < 20
          ? "默认改成英文之后，英文读者已经占多数 —— 这条曲线是判断「英文版有没有真的被用上」最直接的证据。"
          : "绝大多数人还在用中文界面。默认语言虽是英文，但中文入口（右上角切换）得足够显眼，不然熟客会以为走错了站。",
      });
    }

    /* 5 来源 */
    if (a.sources.length) {
      var top = a.sources[0];
      var direct = /直接打开/.test(top.k);
      out.push({
        ico: "🔗",
        b: "主要来源：" + top.k + "（" + pct(top.c, rows) + "%）",
        p: direct
          ? "「直接打开」占大头在微信里很常见：朋友圈、群聊、聊天窗口的链接都不带 referrer。真实传播路径要看国家与页面的分布来反推。"
          : "外部引荐在起作用，说明链接是被放到别处再点进来的，值得盯住那个来源接下来还带来多少。",
      });
    }

    /* 6 页面结构 */
    if (rows >= 10) {
      var home = 0, sp = 0;
      a.kinds.forEach(function (x) {
        if (x.k === "首页") home = x.c;
        if (x.k === "物种详情") sp = x.c;
      });
      out.push({
        ico: "🧭",
        b: "首页 " + pct(home, rows) + "%，物种详情页 " + pct(sp, rows) + "%",
        p: sp > home
          ? "详情页多于首页：多数人是被搜索结果或分享直接送到某个物种上的。那一页的「同一科还有谁」和「在哪里能看到」就是留住他们的关键。"
          : "首页占多数：大家在名录里挑鸟看。名录的筛选与排序，比单页排版更影响他们能看到多少种。",
      });
    }

    /* 7 深度 */
    if (a.visitors >= 5) {
      var sp1 = pct(a.singles, a.visitors);
      out.push({
        ico: "⏱",
        cls: sp1 > 60 ? "warn" : "good",
        b: "人均 " + a.perPerson.toFixed(1) + " 页，" + sp1 + "% 的人当天只看了一页",
        p: sp1 > 60
          ? "只看一页就走，多半是「查完这只鸟就关」。可以在详情页底部把同科近亲和「四季日历」往前放一点，给一个继续看的理由。"
          : "多数人会连看几页，说明名录与详情之间的串联是通的，可以放心继续加物种。",
      });
    }

    /* 8 地域 */
    if (a.countries.length >= 2) {
      var top3 = a.countries.slice(0, 3);
      var share3 = pct(sum(top3.map(function (x) { return x.c; })), rows);
      out.push({
        ico: "📍",
        b: "访客集中在 " + top3.map(function (x) { return x.k; }).join("、") + "（合计 " + share3 + "%）",
        p: share3 > 80
          ? "地域非常集中：目前更像「熟人与本地观鸟圈」的流量。想扩大，得靠能被二次转发的钩子 —— 比如某个季节的候鸟清单。"
          : "分布比较散，海外也有人在看，说明英文版与搜索引擎都在起作用。",
      });
    }

    $("vdInsights").innerHTML = out.map(function (x) {
      return '<div class="vd__insight ' + (x.cls ? "vd__insight--" + x.cls : "") + '">' +
        '<span class="ico" aria-hidden="true">' + x.ico + "</span>" +
        "<div><b>" + esc(x.b) + "</b><p>" + esc(x.p) + "</p></div></div>";
    }).join("");
  }

  /* ---------- 渲染：条状榜 ---------- */
  function bars(id, arr, limit, labelFn) {
    var host = $(id);
    if (!host) return;
    if (!arr || !arr.length) { host.innerHTML = '<li class="vd__empty">暂无数据</li>'; return; }
    var list = arr.slice(0, limit || 8);
    var max = Math.max.apply(null, list.map(function (x) { return x.c; })) || 1;
    host.innerHTML = list.map(function (x) {
      var name = labelFn ? labelFn(x) : x.k;
      return '<li><span class="n" title="' + esc(name) + '">' + esc(name) + "</span>" +
        '<span class="c">' + x.c + "</span>" +
        '<span class="b"><i style="width:' + Math.max((x.c / max) * 100, 3).toFixed(1) + '%"></i></span></li>';
    }).join("");
  }

  function pageName(p) {
    var s = String(p || "/").replace(/\/index\.html$/, "/").replace(/\.html$/, "");
    return s || "/";
  }

  /* ---------- 渲染：明细表 ---------- */
  function filtered() {
    var q = state.q.trim().toLowerCase();
    var rows = inRange();
    if (q) {
      rows = rows.filter(function (r) {
        return [r.p, r.r, r.c, r.dv, r.br, r.l, r.v].filter(Boolean).join(" ").toLowerCase().indexOf(q) >= 0;
      });
    }
    var dir = state.dir;
    return rows.slice().sort(function (a, b) {
      return (a.t - b.t) * dir;
    });
  }

  function renderTable() {
    var rows = filtered();
    var size = state.size;
    var pages = Math.max(1, Math.ceil(rows.length / size));
    if (state.page > pages) state.page = pages;
    var slice = rows.slice((state.page - 1) * size, state.page * size);

    $("vdCount").textContent = "共 " + rows.length + " 条" +
      (rows.length !== inRange().length ? "（已筛选）" : "");

    var head = '<div class="vd__row vd__row--head">' +
      '<span data-sort="time">时间 ' + (state.dir < 0 ? "↓" : "↑") + "</span>" +
      "<span>地区</span><span>设备 / 浏览器</span><span>来源</span>" +
      "<span>落地页</span><span>语言</span><span>指纹</span></div>";

    if (!slice.length) {
      $("vdTable").innerHTML = head + '<div class="vd__row"><span style="grid-column:1/-1">没有匹配的记录</span></div>';
    } else {
      $("vdTable").innerHTML = head + slice.map(function (r) {
        var where = [r.c ? flag(r.c) : "🌐", ccName(r.c)].join(" ");
        return '<div class="vd__row">' +
          '<span class="t">' + esc(fmtTime(r.t)) + "</span>" +
          '<span class="g">' + esc(where) + "</span>" +
          '<span class="s">' + esc(devName(r.dv).replace(/^\S+\s/, "") + " · " + (r.br || "—")) + "</span>" +
          '<span class="s">' + esc(prettyRef(r.r)) + "</span>" +
          '<span class="p" title="' + esc(r.p) + '">' + esc(pageName(r.p)) + "</span>" +
          '<span class="s">' + esc((r.l || "—").replace(/-.*$/, "")) + "</span>" +
          '<span class="n2">' + esc(r.v || "—") + "</span>" +
          "</div>";
      }).join("");
    }

    $("vdPager").innerHTML =
      '<button type="button" id="vdPrev"' + (state.page <= 1 ? " disabled" : "") + ">上一页</button>" +
      "<span>第 " + state.page + " / " + pages + " 页 · 每页 " + size + " 条</span>" +
      '<button type="button" id="vdNext"' + (state.page >= pages ? " disabled" : "") + ">下一页</button>";

    var prev = $("vdPrev"), next = $("vdNext");
    if (prev) prev.onclick = function () { state.page--; renderTable(); };
    if (next) next.onclick = function () { state.page++; renderTable(); };
  }

  /* ---------- 总渲染 ---------- */
  function render() {
    var rows = inRange();
    var a = analyze(rows);
    renderKpis(a);
    renderTrend(a);
    renderHours(a);
    renderInsights(a);

    bars("vdDevice", a.devices, 4);
    bars("vdBrowser", a.browsers, 6);
    bars("vdLang", a.langs, 6);
    bars("vdKind", a.kinds, 6);
    bars("vdSource", a.sources, 7);
    bars("vdPage", a.pages, 8, function (x) { return pageName(x.k); });
    bars("vdCountry", a.countries, 7);
    bars("vdSide", a.sides, 3);
    bars("vdWeekday", countBy(rows, function (r) {
      var t = new Date(r.d + "T00:00:00+08:00");
      return isNaN(t) ? null : WEEK[t.getDay()];
    }), 7);
    bars("vdDepth", a.depthBars, 4);
    bars("vdBird", a.birds, 8, function (x) { return birdName(x.k); });

    var span = state.days ? (state.days === 1 ? "今天" : "最近 " + state.days + " 天") : "全部时间";
    $("vdMeta").textContent = span + " · " + rows.length + " 条浏览 · " + a.visitors + " 位访客（按日去重）· 共载入 " +
      state.rows.length + " 条 · 更新于 " + fmtTime(Date.parse(state.generatedAt) || Date.now());

    $("vdBanner").hidden = !state.truncated;
    if (state.truncated) {
      $("vdBanner").textContent = "服务端共有 " + state.total + " 条记录，这里只载入了最近 " +
        state.rows.length + " 条。更早的数据仍可用「导出 CSV」按范围取，或把 /api/visitors 的 limit 调大。";
    }

    renderTable();
  }

  /* ---------- 取数 ---------- */
  function msg(text, ok) {
    var m = $("vdMsg");
    m.textContent = text || "";
    m.classList.toggle("ok", !!ok);
  }

  function load(key, keepRange) {
    state.key = key;
    if (!keepRange) state.page = 1;
    msg("正在加载…", true);
    fetch("/api/visitors?days=3650&limit=" + MAX_ROWS, {
      headers: { authorization: "Bearer " + key },
      cache: "no-store",
    })
      .then(function (r) { return r.json().then(function (j) { return { status: r.status, body: j }; }); })
      .then(function (res) {
        var j = res.body || {};
        if (res.status === 401) {
          msg("口令不对。");
          try { sessionStorage.removeItem(KEY_STORE); } catch (e) {}
          gate.hidden = false; body.hidden = true;
          return;
        }
        if (j.error === "not_initialized") { msg("后台还没设口令：去 D1 的 cfg 表插入 admin_token。"); return; }
        if (j.error === "db_not_ready") { msg("数据表还没建好，稍后再试。"); return; }
        if (!j.rows) { msg("加载失败，稍后再试。"); return; }

        try { sessionStorage.setItem(KEY_STORE, key); } catch (e) {}
        // 给 beacon.js 一个标记：站长本人在这台机器上的浏览不再计入统计
        try { localStorage.setItem("zb_admin_token", "1"); } catch (e) {}
        gate.hidden = true; body.hidden = false;
        msg("");

        state.rows = j.rows;
        state.total = j.total || j.rows.length;
        state.truncated = !!j.truncated;
        state.generatedAt = j.generatedAt || "";
        render();
      })
      .catch(function () { msg("网络错误，稍后再试。"); });
  }

  /* ---------- 事件 ---------- */
  $("vdForm").addEventListener("submit", function (e) {
    e.preventDefault();
    var v = ($("vdKey").value || "").trim();
    if (!v) { msg("请先输入口令。"); return; }
    load(v);
  });

  $("vdRefresh").addEventListener("click", function () { if (state.key) load(state.key, true); });

  $("vdExit").addEventListener("click", function () {
    try { sessionStorage.removeItem(KEY_STORE); } catch (e) {}
    try { localStorage.removeItem("zb_admin_token"); } catch (e) {}
    state.rows = []; state.key = "";
    body.hidden = true; gate.hidden = false;
    $("vdKey").value = ""; msg("");
  });

  Array.prototype.forEach.call(document.querySelectorAll("#vdRange button"), function (b) {
    b.addEventListener("click", function () {
      Array.prototype.forEach.call(document.querySelectorAll("#vdRange button"), function (x) {
        x.classList.remove("is-on");
      });
      b.classList.add("is-on");
      state.days = Number(b.getAttribute("data-days")) || 0;
      state.page = 1;
      try { localStorage.setItem(RANGE_STORE, String(state.days)); } catch (e) {}
      render();
    });
  });

  $("vdQ").addEventListener("input", function (e) {
    state.q = e.target.value || "";
    state.page = 1;
    renderTable();
  });
  $("vdSize").addEventListener("change", function (e) {
    state.size = Number(e.target.value) || 50;
    state.page = 1;
    renderTable();
  });
  $("vdTable").addEventListener("click", function (e) {
    var t = e.target.closest("[data-sort]");
    if (!t) return;
    state.dir = -state.dir;
    renderTable();
  });

  $("vdCsv").addEventListener("click", function () {
    var rows = filtered();
    var cols = ["t", "d", "h", "p", "r", "c", "dv", "br", "l", "v"];
    var head = "时间,日期,小时,页面,来源,国家,设备,浏览器,语言,指纹";
    var body2 = rows.map(function (r) {
      return cols.map(function (c) {
        var v = c === "t" ? fmtTime(r.t) : r[c];
        v = v == null ? "" : String(v);
        return '"' + v.replace(/"/g, '""') + '"';
      }).join(",");
    }).join("\n");
    var blob = new Blob(["\ufeff" + head + "\n" + body2], { type: "text/csv;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "birds-visits-" + bjDay(Date.now()) + ".csv";
    a.click();
    URL.revokeObjectURL(a.href);
  });

  /* ---------- 记住上次的范围 / 自动登录 ---------- */
  try {
    var raw = localStorage.getItem(RANGE_STORE);
    if (raw !== null && raw !== "") {
      var d = Number(raw);
      if (d === 0 || [1, 7, 30, 90].indexOf(d) >= 0) {
        state.days = d;
        Array.prototype.forEach.call(document.querySelectorAll("#vdRange button"), function (x) {
          x.classList.toggle("is-on", Number(x.getAttribute("data-days")) === d);
        });
      }
    }
  } catch (e) {}

  try {
    var saved = sessionStorage.getItem(KEY_STORE);
    if (saved) load(saved);
  } catch (e) {}
})();
