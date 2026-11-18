/* 珠海观鸟图鉴 · 交互 */
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
})();
