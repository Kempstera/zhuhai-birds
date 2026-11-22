/* 珠海观鸟图鉴 · 交互 */
/* 页面上同时存在两个播放器（封面那只 + 听声辨鸟小测）。
   谁开始播，就把另一个掐掉——否则两段鸟叫会叠在一起，听着像吵架。 */
window.__zhAudio = {
  cur: null,
  take: function (a) {
    if (this.cur && this.cur !== a) { try { this.cur.pause(); } catch (e) {} }
    this.cur = a;
  }
};

(function () {
  "use strict";

  /* ---------- 导航滚动态 ---------- */
  var nav = document.getElementById("nav");
  if (nav) {
    var onScroll = function () {
      nav.classList.toggle("solid", window.scrollY > 24);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  /* ---------- 滚动入场 ---------- */
  var reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && reveals.length) {
    var ro = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          ro.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.06 });
    reveals.forEach(function (el, i) {
      el.style.transitionDelay = Math.min(i % 6, 5) * 55 + "ms";
      ro.observe(el);
    });
  } else {
    reveals.forEach(function (el) { el.classList.add("in"); });
  }

  /* ---------- 名录筛选 ---------- */
  var grid = document.getElementById("grid");
  if (grid) {
    var items = Array.prototype.slice.call(grid.querySelectorAll(".bird-card"));
    var chips = Array.prototype.slice.call(document.querySelectorAll("#filters .chip"));
    var emptyEl = document.getElementById("empty");
    var input = document.getElementById("q");
    var curFilter = "all";
    var q = "";

    var apply = function () {
      var shown = 0;
      items.forEach(function (card) {
        var ok;
        if (curFilter === "all") ok = true;
        else ok = card.dataset.group === curFilter;

        if (ok && q) ok = (card.dataset.search || "").toLowerCase().indexOf(q) > -1;

        var li = card.parentElement;
        li.style.display = ok ? "" : "none";
        if (ok) shown++;
      });
      if (emptyEl) emptyEl.classList.toggle("show", shown === 0);
    };

    var setFilter = function (f) {
      curFilter = f;
      chips.forEach(function (c) { c.classList.toggle("on", c.dataset.f === f); });
      apply();
    };

    chips.forEach(function (c) {
      c.addEventListener("click", function () { setFilter(c.dataset.f); });
    });

    /* 首页类群卡跳过来时带 #songbird 这类锚点，进来就直接筛好 */
    var h0 = (location.hash || "").replace(/^#/, "");
    if (h0 && chips.some(function (c) { return c.dataset.f === h0; })) setFilter(h0);

    if (input) {
      var t;
      input.addEventListener("input", function () {
        clearTimeout(t);
        t = setTimeout(function () {
          q = input.value.trim().toLowerCase();
          apply();
        }, 120);
      });
      input.addEventListener("search", function () {
        q = input.value.trim().toLowerCase();
        apply();
      });
    }

    /* 类群卡片 → 筛选 */
    document.querySelectorAll("[data-jump]").forEach(function (el) {
      el.addEventListener("click", function () {
        setFilter(el.dataset.jump);
        if (input) { input.value = ""; q = ""; }
      });
    });
  }

  /* ---------- 本页导读 ---------- */
  var prose = document.getElementById("prose");
  var toc = document.getElementById("toc");
  if (prose && toc) {
    var hs = Array.prototype.slice.call(prose.querySelectorAll("h2"));
    if (hs.length) {
      var ul = document.createElement("ul");
      hs.forEach(function (h, i) {
        if (!h.id) h.id = "sec-" + i;
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = "#" + h.id;
        a.textContent = h.textContent.trim();
        li.appendChild(a);
        ul.appendChild(li);
      });
      toc.appendChild(ul);

      var links = Array.prototype.slice.call(ul.querySelectorAll("a"));
      if ("IntersectionObserver" in window) {
        var spy = new IntersectionObserver(function (entries) {
          entries.forEach(function (en) {
            if (!en.isIntersecting) return;
            var id = en.target.id;
            links.forEach(function (l) {
              l.classList.toggle("on", l.getAttribute("href") === "#" + id);
            });
          });
        }, { rootMargin: "-90px 0px -68% 0px", threshold: 0 });
        hs.forEach(function (h) { spy.observe(h); });
      }
    }
  }

  /* ---------- 鸟鸣播放器 ---------- */
  var cards = document.querySelectorAll(".audio-card");

  Array.prototype.forEach.call(cards, function (card) {
    var src = card.dataset.src;
    var wrap = card.querySelector(".wave-wrap");
    var canvas = card.querySelector("canvas");
    var btn = card.querySelector(".ac-btn");
    var curEl = card.querySelector(".t-cur");
    if (!src || !canvas || !wrap) return;

    var ctx = canvas.getContext("2d");
    var audio = new Audio();
    audio.preload = "none";
    audio.src = src;

    var peaks = null;
    var loading = false;
    var raf = 0;
    var css = getComputedStyle(document.documentElement);
    var cBase = (css.getPropertyValue("--line") || "#DCD4C2").trim();
    var cDone = (css.getPropertyValue("--clay") || "#A24E24").trim();
    var cGlow = (css.getPropertyValue("--clay-2") || "#C57A45").trim();

    function fmt(s) {
      if (!isFinite(s) || s < 0) s = 0;
      var m = Math.floor(s / 60);
      var r = Math.floor(s % 60);
      return m + ":" + (r < 10 ? "0" : "") + r;
    }

    function roundRect(c, x, y, w, h, r) {
      r = Math.min(r, w / 2, h / 2);
      c.beginPath();
      c.moveTo(x + r, y);
      c.arcTo(x + w, y, x + w, y + h, r);
      c.arcTo(x + w, y + h, x, y + h, r);
      c.arcTo(x, y + h, x, y, r);
      c.arcTo(x, y, x + w, y, r);
      c.closePath();
    }

    function sizeCanvas() {
      var rect = wrap.getBoundingClientRect();
      var w = Math.max(rect.width, 40);
      var h = Math.max(rect.height, 30);
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return { w: w, h: h };
    }

    function placeholder(n, w) {
      var arr = new Float32Array(n);
      for (var i = 0; i < n; i++) {
        var t = i / n;
        var env = Math.sin(Math.PI * Math.pow(t, 0.7)) * 0.55 + 0.18;
        var mod = 0.55 + 0.45 * Math.abs(Math.sin(t * 21 + 1.7) * Math.cos(t * 8.3));
        arr[i] = Math.min(1, env * mod);
      }
      return arr;
    }

    function draw() {
      var d = sizeCanvas();
      var w = d.w, h = d.h;
      ctx.clearRect(0, 0, w, h);
      if (!peaks) return;

      var n = peaks.length;
      var gap = w < 260 ? 1 : 1.6;
      var bw = Math.max(1.4, (w - gap * (n - 1)) / n);
      var mid = h / 2;
      var maxH = h - 8;
      var prog = audio.duration ? audio.currentTime / audio.duration : 0;

      for (var i = 0; i < n; i++) {
        var v = peaks[i];
        var bh = Math.max(3, v * maxH);
        var x = i * (bw + gap);
        var done = i / n <= prog;
        ctx.fillStyle = done ? cDone : cBase;
        roundRect(ctx, x, mid - bh / 2, bw, bh, bw / 2);
        ctx.fill();
      }

      /* 播放位置游标 */
      if (prog > 0 && prog < 1) {
        var px = Math.min(w - 1, prog * w);
        ctx.fillStyle = cGlow;
        ctx.fillRect(px - 0.5, 0, 1.2, h);
      }
    }

    async function loadWave() {
      if (peaks || loading) return;
      loading = true;
      try {
        var res = await fetch(src);
        var buf = await res.arrayBuffer();
        var AC = window.AudioContext || window.webkitAudioContext;
        var ac = new AC();
        var ab = await new Promise(function (resolve, reject) {
          var p = ac.decodeAudioData(buf, resolve, reject);
          if (p && p.then) p.then(resolve, reject);
        });
        var raw = ab.getChannelData(0);
        var d = sizeCanvas();
        var n = Math.round(Math.min(180, Math.max(60, d.w / 3.1)));
        var block = Math.floor(raw.length / n) || 1;
        var step = Math.max(1, Math.floor(block / 260));
        var arr = new Float32Array(n);
        var max = 0;
        for (var i = 0; i < n; i++) {
          var s = 0;
          var base = i * block;
          for (var j = 0; j < block; j += step) {
            var a = Math.abs(raw[base + j] || 0);
            if (a > s) s = a;
          }
          arr[i] = s;
          if (s > max) max = s;
        }
        for (var k = 0; k < n; k++) {
          arr[k] = Math.pow(arr[k] / (max || 1), 0.55);
        }
        peaks = arr;
        try { ac.close(); } catch (e) {}
      } catch (e) {
        peaks = placeholder(140);
      }
      loading = false;
      draw();
    }

    function tick() {
      draw();
      if (curEl) curEl.textContent = fmt(audio.currentTime);
      if (!audio.paused && !audio.ended) raf = requestAnimationFrame(tick);
    }

    btn.addEventListener("click", function () {
      if (audio.paused) {
        loadWave();
        audio.play().then(function () {
          card.classList.add("playing");
          cancelAnimationFrame(raf);
          raf = requestAnimationFrame(tick);
        }).catch(function () {});
      } else {
        audio.pause();
        card.classList.remove("playing");
        cancelAnimationFrame(raf);
        draw();
      }
    });

    audio.addEventListener("ended", function () {
      card.classList.remove("playing");
      cancelAnimationFrame(raf);
      draw();
      if (curEl) curEl.textContent = fmt(audio.duration || 0);
    });

    audio.addEventListener("loadedmetadata", draw);
    audio.addEventListener("timeupdate", function () {
      if (curEl) curEl.textContent = fmt(audio.currentTime);
    });

    wrap.addEventListener("click", function (e) {
      if (!audio.duration) return;
      var r = wrap.getBoundingClientRect();
      var ratio = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
      audio.currentTime = ratio * audio.duration;
      draw();
    });

    /* 进入视口后再加载波形 */
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            io.disconnect();
            setTimeout(loadWave, 260);
          }
        });
      }, { rootMargin: "160px" });
      io.observe(card);
    } else {
      loadWave();
    }

    var rt;
    window.addEventListener("resize", function () {
      clearTimeout(rt);
      rt = setTimeout(draw, 180);
    });
  });

  /* ---------- 图集放大 ---------- */
  var lb = document.getElementById("lightbox");
  if (lb) {
    var lbImg = lb.querySelector("img");
    var lbCap = lb.querySelector("figcaption");
    var lbClose = lb.querySelector(".lb-close");
    var lastFocus = null;

    function openLb(src, cap, alt) {
      lastFocus = document.activeElement;
      lbImg.src = src;
      lbImg.alt = alt || "";
      lbCap.textContent = cap || "";
      lb.hidden = false;
      lb.setAttribute("aria-hidden", "false");
      requestAnimationFrame(function () { lb.classList.add("in"); });
      document.body.style.overflow = "hidden";
      lbClose.focus();
    }

    function closeLb() {
      lb.classList.remove("in");
      lb.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
      setTimeout(function () {
        lb.hidden = true;
        lbImg.src = "";
      }, 300);
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    }

    document.querySelectorAll(".g-open").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openLb(
          btn.dataset.big,
          btn.dataset.cap,
          btn.querySelector("img") ? btn.querySelector("img").alt : ""
        );
      });
    });

    lbClose.addEventListener("click", closeLb);
    lb.addEventListener("click", function (e) {
      if (e.target === lb) closeLb();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !lb.hidden) closeLb();
    });
  }

  /* ---------- 首页封面：每天换一只鸟（连同它的鸣声） ----------
     静态页里渲染的是构建当天那一只，这里按「浏览器本地日期」再算一次：
     跨过零点、或者站点很久没重新构建，都会自动换成当天该出现的那只。
     池子里每种都只试听前十几秒（data-in/out），整段留给详情页。
     万一 play() 被自动播放策略拦下，就退回详情页的 #voice。 */
  var hlBtn = document.getElementById("heroListen");
  var heroImg = document.getElementById("heroImg");
  var heroTag = document.getElementById("heroTag");
  var heroCap = document.getElementById("heroCap");

  if (hlBtn || heroImg) {
    var hlTxt = hlBtn ? hlBtn.querySelector(".hl-t") : null;
    var hlLabel = hlBtn ? (hlBtn.dataset.label || "") : "";
    var hlTpl = hlBtn ? (hlBtn.dataset.playing || "%s") : "";
    var hlAudio = null;

    var heroState = {
      src: hlBtn ? hlBtn.dataset.src : "",
      name: hlBtn ? (hlBtn.dataset.name || "") : "",
      in: hlBtn ? (parseFloat(hlBtn.dataset.start || "0") || 0) : 0,
      out: hlBtn ? (parseFloat(hlBtn.dataset.end || "0") || 0) : 0,
      fallback: hlBtn ? (hlBtn.dataset.fallback || "") : ""
    };

    var hlSet = function (playing) {
      if (!hlBtn) return;
      hlBtn.classList.toggle("playing", playing);
      if (hlTxt) hlTxt.textContent = playing ? hlTpl.replace("%s", heroState.name) : hlLabel;
    };

    var heroApplyAudio = function (e) {
      heroState.src = e.audio;
      heroState.name = e.name;
      heroState.in = e.in || 0;
      heroState.out = e.out || 0;
      heroState.fallback = e.href;
      if (hlAudio) {
        try { hlAudio.pause(); } catch (err) {}
        hlAudio = null;      /* 换鸟就丢掉旧的播放器，下次点击重新建 */
      }
      hlSet(false);
    };

    if (hlBtn) {
      hlBtn.addEventListener("click", function () {
        if (!hlAudio) {
          hlAudio = new Audio();
          hlAudio.preload = "none";
          hlAudio.src = heroState.src;
          hlAudio.addEventListener("ended", function () {
            hlSet(false);
            if (heroState.in) hlAudio.currentTime = heroState.in;
          });
          hlAudio.addEventListener("pause", function () { hlSet(false); });
          hlAudio.addEventListener("loadedmetadata", function () {
            if (heroState.in && hlAudio.currentTime < heroState.in) {
              hlAudio.currentTime = heroState.in;
            }
          });
          /* 到窗口末尾就收声，别让试听按钮播满整段 */
          hlAudio.addEventListener("timeupdate", function () {
            if (heroState.out && hlAudio.currentTime >= heroState.out) {
              hlAudio.pause();
              hlAudio.currentTime = heroState.in;
            }
          });
        }
        if (!hlAudio.paused) {
          hlAudio.pause();
          return;
        }
        /* 上一轮播到窗口末尾自动停了，再点要从头来 */
        if (heroState.out && hlAudio.currentTime >= heroState.out - 0.15) {
          hlAudio.currentTime = heroState.in;
        }
        if (window.__zhAudio) window.__zhAudio.take(hlAudio);
        hlAudio.play().then(function () {
          hlSet(true);
        }).catch(function () {
          if (heroState.fallback) location.href = heroState.fallback;
        });
      });
    }

    /* 按本地日期挑当天那只。算法要和 build.py 完全一致，否则会闪一下再换。 */
    var heroPoolEl = document.getElementById("heroPool");
    var heroSwap = function (e) {
      if (heroImg) {
        var pre = new Image();
        pre.onload = function () {
          heroImg.src = e.img;
          heroImg.alt = e.name + " " + e.sci;
          if (e.w) heroImg.width = e.w;
          if (e.h) heroImg.height = e.h;
        };
        pre.src = e.img;
      }
      if (heroTag) {
        heroTag.href = e.href;
        var t = heroTag.querySelector(".ht-txt");
        if (t) t.textContent = e.name + " · " + e.sci;
      }
      if (heroCap) {
        var head = heroCap.getAttribute("data-head") || "";
        heroCap.textContent = head + " " + (e.credit || "Wikimedia Commons") +
                              " / " + (e.license || "—");
      }
      if (hlBtn) {
        hlBtn.dataset.fallback = e.href;
        hlBtn.dataset.src = e.audio;      /* 让 DOM 与实际状态一致，方便排查 */
        hlBtn.dataset.name = e.name;
      }
      heroApplyAudio(e);
    };

    if (heroPoolEl) {
      try {
        var pool = JSON.parse(heroPoolEl.textContent || "[]");
        var now = new Date();
        /* 调试用：?day=2026-03-01 可以预览某天的封面 */
        var m = /[?&]day=(\d{4})-(\d{2})-(\d{2})/.exec(location.search);
        if (m) now = new Date(+m[1], +m[2] - 1, +m[3]);

        var month = now.getMonth() + 1;
        var usable = pool.filter(function (e) {
          return !e.months || e.months.indexOf(month) > -1;
        });
        if (!usable.length) usable = pool;
        if (usable.length) {
          var midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
          var ord = Math.round(midnight.getTime() / 86400000) + 719163; /* 与 Python toordinal 对齐 */
          var idx = ord % usable.length;
          var builtDay = window.__heroDay || 0;
          if (ord !== builtDay) heroSwap(usable[idx]);
        }
      } catch (err) {}
    }
  }

  /* ---------- 我见过（只存本机 localStorage，不联网） ---------- */
  var SEEN_KEY = "zb_seen";

  function seenGet() {
    try {
      var a = JSON.parse(localStorage.getItem(SEEN_KEY));
      return Array.isArray(a) ? a : [];
    } catch (e) { return []; }
  }

  function seenSave(a) {
    try { localStorage.setItem(SEEN_KEY, JSON.stringify(a)); } catch (e) {}
  }

  function slugOf(href) {
    var m = /bird\/([^\/#?]+?)(?:\.html)?(?:[#?]|$)/.exec(href || "");
    return m ? m[1] : "";
  }

  var seen = seenGet();
  var seenBtn = document.querySelector(".seen-btn");

  if (seenBtn) {
    var curSlug = seenBtn.dataset.slug || "";
    if (curSlug && seen.indexOf(curSlug) > -1) seenBtn.classList.add("on");
    seenBtn.addEventListener("click", function () {
      var i = seen.indexOf(curSlug);
      if (i > -1) {
        seen.splice(i, 1);
        seenBtn.classList.remove("on");
      } else {
        seen.push(curSlug);
        seenBtn.classList.add("on");
      }
      seenSave(seen);
    });
  }

  /* 名录/首页的名片上，把已经见过的标出来 */
  if (seen.length) {
    Array.prototype.forEach.call(document.querySelectorAll(".bird-card"), function (card) {
      var s = slugOf(card.getAttribute("href"));
      if (!s || seen.indexOf(s) < 0) return;
      var box = card.querySelector(".bc-name");
      if (!box || box.querySelector(".seen-dot")) return;
      var dot = document.createElement("i");
      dot.className = "seen-dot";
      dot.textContent = "✓";
      dot.title = "已见过";
      box.appendChild(dot);
    });
  }
})();

/* ---------- 听声辨鸟 · 小测 ----------
   题目在构建时就排好了（build.py 的 build_quiz），这里只管交互。
   题目按月换一批，同一个月内每次打开都是这套题——不做随机，
   否则两个人聊起来会对不上号。 */
(function () {
  "use strict";

  var board = document.getElementById("quizBoard");
  var dataEl = document.getElementById("birdQuiz");
  if (!board || !dataEl) return;

  var Q;
  try { Q = JSON.parse(dataEl.textContent || "[]"); } catch (err) { return; }
  if (!Q || !Q.length) return;

  var elProg = document.getElementById("quizProg");
  var elFill = document.getElementById("quizFill");
  var elScore = document.getElementById("quizScore");
  var elPlay = document.getElementById("quizPlay");
  var elWave = document.getElementById("quizWave");
  var elAsk = document.getElementById("quizAsk");
  var elOpts = document.getElementById("quizOpts");
  var elFb = document.getElementById("quizFb");
  var elHint = document.getElementById("quizHint");

  /* 文案全部在 data-* 里，模板只负责排版，JS 不硬写中文 */
  var T = {
    prog: board.dataset.tProg || "%d / %d",
    ask: board.dataset.tAsk || "",
    play: board.dataset.tPlay || "Play",
    again: board.dataset.tAgain || "Play again",
    right: board.dataset.tRight || "",
    wrong: board.dataset.tWrong || "%s",
    hint: board.dataset.tHint || "%s",
    listen: board.dataset.tListen || "%s",
    next: board.dataset.tNext || "Next",
    result: board.dataset.tResult || "%d / %d",
    restart: board.dataset.tRestart || "Restart"
  };

  var PLAY_ICON = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">' +
    '<path d="M8 5.2c0-.8.9-1.3 1.6-.9l9.1 6c.7.5.7 1.5 0 1.9l-9.1 6c-.7.5-1.6 0-1.6-.9V5.2z"/></svg>';

  var ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return ESC[c]; });
  }
  /* 按顺序替换 %s / %d。值一律转义，模板本身是我们自己写的，允许带 <b>。 */
  function rich(tpl, args) {
    var n = 0;
    return String(tpl).replace(/%[sd]/g, function () {
      return n < args.length ? esc(args[n++]) : "";
    });
  }
  function plain(tpl, args) {
    var n = 0;
    return String(tpl).replace(/%[sd]/g, function () {
      return n < args.length ? String(args[n++]) : "";
    });
  }

  var au = null, curOn = null;
  var st = { i: 0, right: 0, answered: false, heard: false };

  function stopClip() {
    var a = au;
    au = null;
    if (a) { try { a.pause(); } catch (e) {} }
    if (curOn) { var f = curOn; curOn = null; f(false); }
  }

  function playClip(item, onState) {
    stopClip();
    var i0 = Number(item["in"]) || 0;
    var i1 = Number(item.out) || 0;
    var a = new Audio();
    a.preload = "auto";
    a.src = item.audio;
    au = a;
    curOn = onState;
    /* 页面上的另一个播放器（封面那只）要先停下来，不然两个声音叠在一起 */
    if (window.__zhAudio) window.__zhAudio.take(a);

    a.addEventListener("loadedmetadata", function () {
      if (i0 && a.currentTime < i0) a.currentTime = i0;
    });
    /* 到窗口末尾就收声，别整段播完——多数录音有十几二十秒 */
    a.addEventListener("timeupdate", function () {
      if (i1 && a.currentTime >= i1) a.pause();
    });
    a.addEventListener("ended", function () { onState(false); });
    a.addEventListener("pause", function () { onState(false); });

    var pr = a.play();
    if (pr && pr.then) {
      pr.then(function () { onState(true); st.heard = true; })
        .catch(function () { onState(false); });
    } else {
      onState(true);
      st.heard = true;
    }
  }

  function setMain(on) {
    elPlay.classList.toggle("playing", !!on);
    elWave.classList.toggle("on", !!on);
    if (st.heard) {
      elHint.textContent = on ? "" : T.again;
      elHint.classList.toggle("played", !on);
    }
  }

  function renderQuestion() {
    var q = Q[st.i];
    stopClip();
    st.answered = false;
    st.heard = false;

    elFb.hidden = true;
    elFb.innerHTML = "";
    elAsk.textContent = T.ask;
    elHint.textContent = T.play;
    elHint.classList.remove("played");
    elProg.textContent = plain(T.prog, [st.i + 1, Q.length]);
    elFill.style.width = (st.i / Q.length * 100) + "%";
    elScore.textContent = st.right ? "✓ " + st.right : "";

    elOpts.innerHTML = "";
    var keys = ["A", "B", "C", "D"];
    q.opts.forEach(function (o, idx) {
      var li = document.createElement("li");
      var b = document.createElement("button");
      b.type = "button";
      b.setAttribute("data-slug", o.slug);
      b.innerHTML = '<span class="qo-k">' + (keys[idx] || "") + '</span>' +
        '<span class="qo-t"><span class="qo-n"></span><span class="qo-sci"></span></span>';
      b.querySelector(".qo-n").textContent = o.name;
      b.querySelector(".qo-sci").textContent = o.sci || "";
      b.addEventListener("click", function () { pick(o, b, q); });
      li.appendChild(b);
      elOpts.appendChild(li);
    });
  }

  function pick(o, btn, q) {
    if (st.answered) return;
    st.answered = true;
    stopClip();

    var all = elOpts.querySelectorAll("button");
    Array.prototype.forEach.call(all, function (x) { x.disabled = true; });

    elFill.style.width = ((st.i + 1) / Q.length * 100) + "%";

    if (o.right) {
      st.right++;
      elScore.textContent = "✓ " + st.right;
      btn.classList.add("is-right");
      showRight(q);
      /* 答对了就往下走，不用再点一次。1.8 秒够看清答案。 */
      setTimeout(function () {
        if (st.answered && st.i < Q.length) goNext();
      }, 1800);
    } else {
      btn.classList.add("is-wrong");
      Array.prototype.forEach.call(all, function (x) {
        if (x.getAttribute("data-slug") === q.slug) x.classList.add("is-right");
        else if (x !== btn) x.classList.add("dim");
      });
      showWrong(q, o);
    }
  }

  function showRight(q) {
    var h = '<p class="fb-line">' + esc(T.right) + " · <b>" + esc(q.answer) + "</b></p>";
    if (q.tip) h += '<p class="fb-tip">' + esc(q.tip) + "</p>";
    h += '<div class="fb-acts"><button type="button" class="fb-btn primary" data-act="next">' +
      esc(T.next) + " <span aria-hidden=\"true\">→</span></button></div>";
    elFb.innerHTML = h;
    elFb.hidden = false;
  }

  function showWrong(q, o) {
    elScore.textContent = st.right ? "✓ " + st.right : "";
    var h = '<p class="fb-line">' + rich(T.wrong, [q.answer]) + "</p>";
    h += '<p class="fb-line">' + esc(plain(T.hint, [o.name])) + "</p>";
    if (q.tip) h += '<p class="fb-tip">' + esc(q.tip) + "</p>";
    h += '<div class="fb-acts">' +
      '<button type="button" class="fb-btn" data-act="cmp" data-slug="' + esc(o.slug) + '">' +
      PLAY_ICON + esc(plain(T.listen, [o.name])) + "</button>" +
      '<a class="fb-btn primary" href="' + esc(o.href) + '">' +
      esc(o.name) + ' <span aria-hidden="true">→</span></a>' +
      '<button type="button" class="fb-btn" data-act="next">' + esc(T.next) + "</button>" +
      "</div>";
    elFb.innerHTML = h;
    elFb.hidden = false;
    /* 自动放一遍「你选的那只」，对比才能真正发生；
       被浏览器拦下也没关系，下面的按钮可以手动放。 */
    setTimeout(function () {
      if (!st.answered) return;
      var cmp = elFb.querySelector('[data-act="cmp"]');
      if (cmp) playClip(o, function (on) { cmp.classList.toggle("playing", !!on); });
    }, 500);
  }

  function goNext() {
    if (st.i + 1 >= Q.length) { showResult(); return; }
    st.i++;
    renderQuestion();
  }

  function showResult() {
    stopClip();
    st.answered = false;
    elOpts.innerHTML = "";
    elAsk.textContent = "";
    elHint.textContent = "";
    elProg.textContent = "";
    elFill.style.width = "100%";
    elScore.textContent = "✓ " + st.right;
    elFb.innerHTML = '<p class="fb-line">' + esc(plain(T.result, [st.right, Q.length])) +
      '</p><div class="fb-acts"><button type="button" class="fb-btn primary" data-act="again">' +
      esc(T.restart) + "</button></div>";
    elFb.hidden = false;
  }

  elPlay.addEventListener("click", function () {
    if (st.answered || !Q[st.i] || !elOpts.children.length) return;
    var q = Q[st.i];
    if (elPlay.classList.contains("playing")) { stopClip(); return; }
    playClip(q, setMain);
  });

  elFb.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target.closest("[data-act]") : null;
    if (!t) return;
    var act = t.getAttribute("data-act");
    if (act === "cmp") {
      var q = Q[st.i];
      var o = null;
      for (var i = 0; i < q.opts.length; i++) {
        if (!q.opts[i].right) { o = q.opts[i]; break; }
      }
      /* 用按钮身上记的 slug 找回那一条，保证放的是访客真选中的那只 */
      var slug = null;
      var sel = elFb.querySelector("[data-act='cmp']");
      if (sel) slug = sel.getAttribute("data-slug");
      if (slug) {
        for (var j = 0; j < q.opts.length; j++) {
          if (q.opts[j].slug === slug) { o = q.opts[j]; break; }
        }
      }
      if (!o) return;
      if (t.classList.contains("playing")) { stopClip(); return; }
      playClip(o, function (on) { t.classList.toggle("playing", !!on); });
    } else if (act === "next") {
      goNext();
    } else if (act === "again") {
      st.i = 0; st.right = 0;
      renderQuestion();
    }
  });

  renderQuestion();
})();
