/* 公开的访问统计页：只画聚合数字，不碰任何个体数据。
   数据来自 /api/visits（边缘缓存 5 分钟），接口本身不接受参数、不落 cookie。 */
(function () {
  var root = document.getElementById("vsRoot");
  if (!root) return;
  var D = root.dataset;
  var L = D.lang === "en" ? "en" : "zh";

  var $ = function (id) { return document.getElementById(id); };
  var nf = new Intl.NumberFormat(L === "en" ? "en-US" : "zh-CN");

  function fmt(n) { return nf.format(n || 0); }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function mmdd(d) {
    var p = String(d).split("-");
    return p.length === 3 ? p[1] + "/" + p[2] : String(d);
  }

  /* 国家代码 → 本地语言的国家名；取不到就退回代码 */
  var region = null;
  try {
    region = new Intl.DisplayNames([L === "en" ? "en" : "zh-CN"], { type: "region" });
  } catch (e) { region = null; }

  function ccName(code) {
    if (!code || code === "??") return "—";
    try {
      return (region && region.of(code)) || code;
    } catch (e) {
      return code;
    }
  }

  function langName(k) {
    var s = String(k || "").toLowerCase();
    if (s.indexOf("zh") === 0) return L === "en" ? "Chinese" : "中文";
    if (s.indexOf("en") === 0) return "English";
    return k || "—";
  }

  function devName(k) {
    var map = {
      desktop: D.dDesktop, mobile: D.dMobile, tablet: D.dTablet, unknown: D.dUnknown,
    };
    return map[k] || k || "—";
  }

  function pathName(p) {
    var s = String(p || "/");
    if (s === "/" || s === "") return "/";
    return s.replace(/index\.html$/, "").replace(/\.html$/, "");
  }

  function rankList(box, rows, labelOf) {
    box.innerHTML = "";
    if (!rows || !rows.length) {
      box.appendChild(el("p", "vs-empty", D.empty));
      return;
    }
    var top = rows.reduce(function (m, r) { return Math.max(m, r.c || 0); }, 1);
    rows.forEach(function (r) {
      var row = el("div", "vs-row");
      var label = el("span", "vs-label", labelOf(r));
      if (r.title) label.title = r.title;
      var bar = el("i", "vs-bar");
      bar.style.width = Math.max(2, Math.round(((r.c || 0) / top) * 100)) + "%";
      row.appendChild(label);
      row.appendChild(bar);
      row.appendChild(el("b", "vs-n", fmt(r.c)));
      box.appendChild(row);
    });
  }

  function drawBars(series) {
    var box = $("vsBars");
    box.innerHTML = "";
    if (!series || !series.length) {
      box.appendChild(el("p", "vs-empty", D.empty));
      return;
    }
    var top = series.reduce(function (m, r) { return Math.max(m, r.pv || 0); }, 1);
    series.forEach(function (r) {
      var day = el("div", "vs-day");
      var stack = el("div", "vs-stack");
      var pv = el("i", "vs-pv");
      var uv = el("i", "vs-uv");
      pv.style.height = Math.max(2, Math.round(((r.pv || 0) / top) * 100)) + "%";
      uv.style.height = Math.max(1, Math.round(((r.uv || 0) / top) * 100)) + "%";
      stack.appendChild(pv);
      stack.appendChild(uv);
      day.appendChild(stack);
      day.appendChild(el("span", "vs-x", mmdd(r.d)));
      day.title = r.d + " · " + fmt(r.pv) + " / " + fmt(r.uv);
      box.appendChild(day);
    });
  }

  fetch("/api/visits", { credentials: "omit" })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (!d || !d.ok) throw new Error("bad");
      $("vsAll").textContent = fmt(d.allTime.pv);
      $("vsUv").textContent = fmt(d.month.uv);
      $("vsToday").textContent = fmt(d.today.pv);
      $("vsWeek").textContent = fmt(d.week.pv);

      if (d.allTime.since) {
        $("vsSince").textContent = (L === "en" ? "since " : "自 ") + d.allTime.since + (L === "en" ? "" : " 起");
      }

      drawBars(d.series);

      rankList($("vsPaths"), (d.paths || []).map(function (r) {
        return { c: r.c, title: r.p, label: pathName(r.p) };
      }), function (r) { return r.label; });

      rankList($("vsRefs"), (d.refs || []).map(function (r) {
        return { c: r.c, label: r.k || D.direct };
      }), function (r) { return r.label; });

      rankList($("vsGeo"), (d.countries || []).map(function (r) {
        return { c: r.c, title: r.k, label: ccName(r.k) };
      }), function (r) { return r.label; });

      rankList($("vsDev"), (d.devices || []).map(function (r) {
        return { c: r.c, label: devName(r.k) };
      }), function (r) { return r.label; });

      rankList($("vsLang"), (d.langs || []).map(function (r) {
        return { c: r.c, label: langName(r.k) };
      }), function (r) { return r.label; });

      var when = new Date(d.generatedAt);
      var stamp = when.toLocaleDateString(L === "en" ? "en-GB" : "zh-CN",
        { year: "numeric", month: "2-digit", day: "2-digit" }) + " " +
        when.toLocaleTimeString(L === "en" ? "en-GB" : "zh-CN",
        { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Shanghai" });
      $("vsUpdated").textContent = (D.updated || "%s").replace("%s", stamp);
    })
    .catch(function () {
      ["vsBars", "vsPaths", "vsRefs", "vsGeo", "vsDev", "vsLang"].forEach(function (id) {
        var box = $(id);
        if (!box) return;
        box.innerHTML = "";
        box.appendChild(el("p", "vs-empty", D.fail));
      });
    });
})();
