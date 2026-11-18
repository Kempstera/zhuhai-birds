/* 站长看板：口令存本机，数据来自 /api/stats */
(function () {
  var KEY = "zb_admin_token";
  var CACHE = "zb_cache";
  var state = { days: 7, data: null, token: "" };

  /* 上次拿到的数据快照：回到这一页时先画出来，不必等接口 */
  function readCache(days) {
    try {
      var c = JSON.parse(sessionStorage.getItem(CACHE) || "null");
      if (c && c.d === days && Date.now() - c.t < 10 * 60 * 1000) return c.j;
    } catch (e) {}
    return null;
  }
  function writeCache(days, j) {
    try { sessionStorage.setItem(CACHE, JSON.stringify({ d: days, t: Date.now(), j: j })); } catch (e) {}
  }

  var gate = document.getElementById("gate");
  var dash = document.getElementById("dash");
  var form = document.getElementById("gateform");
  var pw = document.getElementById("pw");
  var msg = document.getElementById("msg");
  var gobtn = document.getElementById("gobtn");

  var el = function (id) { return document.getElementById(id); };
  var esc = function (s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var nf = function (n) { return (n || 0).toLocaleString("zh-CN"); };

  /* ---------- 口令 ---------- */
  function unlock(token) {
    state.token = token;
    localStorage.setItem(KEY, token);
    gate.hidden = true;
    dash.hidden = false;
    load(state.days);
  }
  function lock() {
    localStorage.removeItem(KEY);
    state.token = "";
    dash.hidden = true;
    gate.hidden = false;
    pw.value = "";
    msg.textContent = "";
    pw.focus();
  }
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var t = pw.value.trim();
    if (!t) return;
    gobtn.disabled = true;
    msg.className = "adm-msg";
    msg.textContent = "校验中…";
    fetch("/api/stats?days=7", { headers: { authorization: "Bearer " + t } })
      .then(function (r) { return r.json().then(function (j) { return { s: r.status, j: j }; }); })
      .then(function (res) {
        gobtn.disabled = false;
        if (res.s === 200 && res.j.ok) { unlock(t); return; }
        msg.className = "adm-msg err";
        if (res.j && res.j.error === "not_initialized") msg.textContent = "后台还没初始化口令，先看部署说明。";
        else msg.textContent = "口令不对。";
        pw.select();
      })
      .catch(function () {
        gobtn.disabled = false;
        msg.className = "adm-msg err";
        msg.textContent = "连不上统计接口。";
      });
  });

  /* ---------- 数据 ---------- */
  function load(days) {
    state.days = days;
    var cached = readCache(days);
    if (cached) render(cached);
    if (!cached) el("stamp").textContent = "读取中…";
    fetch("/api/stats?days=" + days, { headers: { authorization: "Bearer " + state.token } })
      .then(function (r) {
        if (r.status === 401) { lock(); throw new Error("401"); }
        return r.json();
      })
      .then(function (j) {
        if (!j.ok) { el("stamp").textContent = "读取失败：" + (j.error || "未知错误"); return; }
        state.data = j;
        writeCache(days, j);
        render(j);
      })
      .catch(function (e) {
        if (e.message !== "401") el("stamp").textContent = "读取失败，请重试。";
      });
  }

  /* ---------- 渲染 ---------- */
  function render(d) {
    var at = new Date(d.generatedAt);
    el("stamp").textContent =
      "统计区间 " + d.range.from + " 至 " + d.range.to + "（北京时间） · 更新于 " +
      at.toLocaleString("zh-CN", { hour12: false }) +
      (d.allTime.since ? " · 建站以来累计 " + nf(d.allTime.pv) + " 次浏览，覆盖 " + nf(d.allTime.days) + " 天" : "");

    /* KPI */
    var kpi = [
      ["浏览量", nf(d.totals.pv), "PV"],
      ["独立访客", nf(d.totals.uv), "UV · 按日去重后相加"],
      ["日均浏览", d.totals.avg, "次 / 天"],
      ["今日", nf(d.today.pv), "浏览 " + nf(d.today.uv) + " 人"],
    ];
    el("kpis").innerHTML = kpi
      .map(function (k) {
        return '<div class="adm-kpi"><span class="n">' + esc(k[1]) + '</span><span class="l">' + esc(k[0]) +
          '</span><span class="s">' + esc(k[2]) + "</span></div>";
      })
      .join("");

    /* 趋势 */
    var max = 1;
    d.series.forEach(function (s) { if (s.pv > max) max = s.pv; });
    var bars = d.series
      .map(function (s) {
        var hp = Math.max(s.pv ? 2 : 0, Math.round((s.pv / max) * 100));
        var hu = Math.max(s.uv ? 1 : 0, Math.round((s.uv / max) * 100));
        return (
          '<div class="adm-day" title="' + s.d + "：浏览 " + s.pv + " / 访客 " + s.uv + '">' +
          '<div class="adm-pair"><i class="pv" style="height:' + hp + '%"></i><i class="uv" style="height:' + hu + '%"></i></div>' +
          '<span class="x">' + (d.range.days <= 14 ? s.d.slice(5) : s.d.slice(8)) + "</span></div>"
        );
      })
      .join("");
    var cls = d.series.length > 31 ? " dense" : d.series.length <= 14 ? " few" : "";
    el("chart").innerHTML = d.series.length
      ? '<div class="adm-bars' + cls + '">' + bars + "</div>"
      : '<p class="adm-empty">这个区间还没有记录。</p>';
    var peak = el("peak");
    if (peak) peak.textContent = "峰值 " + max + " 次 / 天";

    /* 列表 */
    rows("paths", d.paths.map(function (r) {
      return { k: r.p, v: r.c, note: r.u + " 人" };
    }));
    rows("refs", d.refs.map(function (r) { return { k: r.k, v: r.c }; }));
    rows("countries", d.countries.map(function (r) { return { k: cc(r.k), v: r.c }; }));
    rows("devices", d.devices.map(function (r) { return { k: devName(r.k), v: r.c }; }));
    rows("langs", d.langs.map(function (r) { return { k: langName(r.k), v: r.c }; }));
    rows("browsers", d.browsers.map(function (r) { return { k: r.k, v: r.c }; }));

    /* 时段 */
    var hmax = 1;
    d.hourly.forEach(function (v) { if (v > hmax) hmax = v; });
    el("hours").innerHTML = d.hourly
      .map(function (v, h) {
        var hp = Math.max(v ? 3 : 0, Math.round((v / hmax) * 100));
        return '<div class="adm-h" title="' + h + ':00 — ' + v + ' 次"><i style="height:' + hp + '%"></i>' +
          (h % 3 === 0 ? '<span>' + h + "</span>" : "<span></span>") + "</div>";
      })
      .join("");
  }

  function rows(id, list) {
    if (!list || !list.length) { el(id).innerHTML = '<p class="adm-empty">暂无数据</p>'; return; }
    var max = 1;
    list.forEach(function (r) { if (r.v > max) max = r.v; });
    el(id).innerHTML = list
      .map(function (r) {
        var w = Math.max(2, Math.round((r.v / max) * 100));
        return (
          '<div class="adm-row"><span class="k" title="' + esc(r.k) + '">' + esc(r.k) + "</span>" +
          '<span class="bar"><i style="width:' + w + '%"></i></span>' +
          '<span class="v">' + nf(r.v) + "</span>" +
          (r.note ? '<span class="note">' + esc(r.note) + "</span>" : "") + "</div>"
        );
      })
      .join("");
  }

  function cc(code) {
    if (!code || code === "??") return "未知";
    var m = { CN: "中国", HK: "中国香港", MO: "中国澳门", TW: "中国台湾", US: "美国", JP: "日本",
      SG: "新加坡", GB: "英国", DE: "德国", FR: "法国", CA: "加拿大", AU: "澳大利亚",
      KR: "韩国", MY: "马来西亚", TH: "泰国", VN: "越南", IN: "印度", RU: "俄罗斯", NL: "荷兰" };
    return m[code] || code;
  }
  function devName(k) {
    return { mobile: "手机", desktop: "桌面", tablet: "平板", unknown: "未知" }[k] || k;
  }
  function langName(k) {
    if (!k) return "未知";
    if (k.indexOf("zh") === 0) return "中文";
    if (k.indexOf("en") === 0) return "English";
    return k;
  }

  /* ---------- 交互 ---------- */
  el("seg").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-d]");
    if (!b) return;
    [].forEach.call(this.querySelectorAll("button"), function (x) { x.classList.toggle("on", x === b); });
    load(parseInt(b.dataset.d, 10));
  });
  el("refresh").addEventListener("click", function () { load(state.days); });
  el("lock").addEventListener("click", lock);

  /* 自动进入 */
  var saved = localStorage.getItem(KEY);
  if (saved) {
    state.token = saved;
    var c0 = readCache(state.days);
    if (c0) { gate.hidden = true; dash.hidden = false; render(c0); }
    fetch("/api/stats?days=7", { headers: { authorization: "Bearer " + saved } })
      .then(function (r) {
        if (r.status === 401) { lock(); return; }
        gate.hidden = true;
        dash.hidden = false;
        load(state.days);
      })
      .catch(function () { gate.hidden = false; pw.focus(); });
  } else {
    pw.focus();
  }
})();
