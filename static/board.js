/* 留言板：Supabase Auth + 一张 bird_messages 表。
   没有配置 key 时整页降级成一句提示，不报错、不白屏。 */
(function () {
  var cfg = window.SB_CONFIG || {};
  var L = (document.documentElement.getAttribute("lang") || "zh").slice(0, 2) === "en" ? "en" : "zh";

  var $ = function (id) { return document.getElementById(id); };
  var elOff = $("bdOff"), elAuth = $("bdAuth"), elComposer = $("bdComposer");
  var elList = $("bdList"), elLoading = $("bdLoading"), elTotal = $("bdTotal");
  var elForm = $("bdForm"), elNickRow = $("nickRow"), elNick = $("bdNick");
  var elEmail = $("bdEmail"), elPw = $("bdPw"), elSubmit = $("bdSubmit");
  var elAuthMsg = $("bdAuthMsg"), elPostMsg = $("bdPostMsg");
  var elPost = $("bdPost"), elBody = $("bdBody"), elCount = $("bdCount");
  var elSend = $("bdSend"), elWho = $("bdWho"), elOut = $("bdOut");
  var elTabIn = $("tabIn"), elTabUp = $("tabUp");

  var mode = "in";
  var client = null;
  var user = null;

  /* ---------- 文案 ---------- */
  var T = {
    zh: {
      badCred: "邮箱或密码不对。",
      exists: "这个邮箱已经注册过了，直接登录吧。",
      shortPw: "密码至少 6 位。",
      badEmail: "邮箱格式看起来不对。",
      needNick: "给自己起个昵称吧。",
      mailSent: "注册成功，请到邮箱点确认链接，再回来登录。",
      posted: "已经贴出去了。",
      empty: "还没写内容。",
      rate: "十分钟内最多五条，歇一会儿。",
      net: "网络好像不太顺，再试一次。",
      del: "删除",
      delAsk: "确定删除这条留言？",
      justNow: "刚刚",
      mins: " 分钟前",
      hours: " 小时前",
      days: " 天前",
      emptyList: "还没有人留言，来做第一个。",
      anon: "观鸟人"
    },
    en: {
      badCred: "Wrong email or password.",
      exists: "That email is already registered — just sign in.",
      shortPw: "Password needs at least 6 characters.",
      badEmail: "That email doesn't look right.",
      needNick: "Pick a display name.",
      mailSent: "Check your inbox for the confirmation link, then sign in.",
      posted: "Posted.",
      empty: "Nothing written yet.",
      rate: "Five notes per ten minutes — take a breather.",
      net: "Network hiccup. Try again.",
      del: "Delete",
      delAsk: "Delete this note?",
      justNow: "just now",
      mins: " min ago",
      hours: " h ago",
      days: " d ago",
      emptyList: "No notes yet — be the first.",
      anon: "Birder"
    }
  }[L];

  var msg = function (node, text, isErr) {
    node.textContent = text || "";
    node.className = "bd-msg" + (isErr ? " err" : " ok");
  };

  /* ---------- 初始化 ---------- */
  if (!cfg.url || !cfg.anon || typeof supabase === "undefined") {
    elOff.hidden = false;
    elList.innerHTML = "";
    var lh = document.querySelector(".bd-list-head");
    if (lh) lh.hidden = true;          // 没接通就别留一个空标题
    if (elLoading) elLoading.hidden = true;
    return;
  }

  client = supabase.createClient(cfg.url, cfg.anon, {
    auth: { persistSession: true, autoRefreshToken: true }
  });

  /* ---------- 状态切换 ---------- */
  function setMode(m) {
    mode = m;
    elTabIn.classList.toggle("on", m === "in");
    elTabUp.classList.toggle("on", m === "up");
    elNickRow.hidden = m !== "up";
    elSubmit.textContent = m === "up" ? elSubmit.dataset.up : elSubmit.dataset.in;
    elPw.setAttribute("autocomplete", m === "up" ? "new-password" : "current-password");
    msg(elAuthMsg, "");
  }
  elTabIn.addEventListener("click", function () { setMode("in"); });
  elTabUp.addEventListener("click", function () { setMode("up"); });

  function paint() {
    var signed = !!user;
    elAuth.hidden = signed;
    elComposer.hidden = !signed;
    if (signed) {
      var nick = (user.user_metadata && user.user_metadata.nickname) || user.email.split("@")[0];
      elWho.textContent = nick;
    }
  }

  /* ---------- 认证 ---------- */
  function errText(e) {
    var m = (e && e.message) || "";
    if (/Invalid login credentials/i.test(m)) return T.badCred;
    if (/already registered|already exists/i.test(m)) return T.exists;
    if (/at least 6 characters/i.test(m)) return T.shortPw;
    if (/invalid format|Unable to validate email/i.test(m)) return T.badEmail;
    if (/rate_limited/i.test(m)) return T.rate;
    if (/Failed to fetch|NetworkError/i.test(m)) return T.net;
    return m || T.net;
  }

  elForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var email = elEmail.value.trim();
    var pw = elPw.value;
    var nick = elNick.value.trim();
    if (mode === "up" && !nick) { msg(elAuthMsg, T.needNick, true); elNick.focus(); return; }
    elSubmit.disabled = true;
    msg(elAuthMsg, L === "en" ? "Working…" : "处理中…");

    var run =
      mode === "in"
        ? client.auth.signInWithPassword({ email: email, password: pw })
        : client.auth.signUp({
            email: email,
            password: pw,
            options: { data: { nickname: nick } }
          });

    run.then(function (res) {
      elSubmit.disabled = false;
      if (res.error) { msg(elAuthMsg, errText(res.error), true); return; }
      if (mode === "up" && !res.data.session) {
        setMode("in");                 // 先切回登录态（会清空提示），再写提示
        msg(elAuthMsg, T.mailSent);
        elPw.value = "";
        return;
      }
      elPw.value = "";
      elNick.value = "";
      msg(elAuthMsg, "");
    }).catch(function (e) {
      elSubmit.disabled = false;
      msg(elAuthMsg, errText(e), true);
    });
  });

  elOut.addEventListener("click", function () {
    client.auth.signOut().then(function () {
      user = null; paint(); load();
    });
  });

  /* ---------- 留言 ---------- */
  elBody.addEventListener("input", function () {
    elCount.textContent = elBody.value.length;
  });

  elPost.addEventListener("submit", function (e) {
    e.preventDefault();
    var body = elBody.value.trim();
    if (!body) { msg(elPostMsg, T.empty, true); return; }
    elSend.disabled = true;
    msg(elPostMsg, L === "en" ? "Posting…" : "发布中…");

    client.from("bird_messages")
      .insert({
        user_id: user.id,
        body: body,
        author_name: (user.user_metadata && user.user_metadata.nickname) || T.anon
      })
      .then(function (res) {
        elSend.disabled = false;
        if (res.error) { msg(elPostMsg, errText(res.error), true); return; }
        elBody.value = "";
        elCount.textContent = "0";
        msg(elPostMsg, T.posted);
        load();
      })
      .catch(function (e) {
        elSend.disabled = false;
        msg(elPostMsg, errText(e), true);
      });
  });

  /* ---------- 列表 ---------- */
  function ago(iso) {
    var s = Math.max(1, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return T.justNow;
    if (s < 3600) return Math.floor(s / 60) + T.mins;
    if (s < 86400) return Math.floor(s / 3600) + T.hours;
    if (s < 86400 * 30) return Math.floor(s / 86400) + T.days;
    var d = new Date(iso);
    return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
  }

  function render(rows) {
    elList.innerHTML = "";
    if (!rows || !rows.length) {
      var p = document.createElement("p");
      p.className = "bd-empty";
      p.textContent = T.emptyList;
      elList.appendChild(p);
      elTotal.textContent = "";
      return;
    }
    elTotal.textContent = (L === "en" ? rows.length + " notes" : rows.length + " 条");
    rows.forEach(function (r) {
      var it = document.createElement("article");
      it.className = "bd-item";

      var head = document.createElement("div");
      head.className = "bd-head";
      var nm = document.createElement("b");
      nm.textContent = r.author_name || T.anon;
      var tm = document.createElement("time");
      tm.dateTime = r.created_at;
      tm.textContent = ago(r.created_at);
      head.appendChild(nm);
      head.appendChild(tm);

      if (user && r.user_id === user.id) {
        var del = document.createElement("button");
        del.type = "button";
        del.className = "bd-link bd-del";
        del.textContent = T.del;
        del.addEventListener("click", function () {
          if (!window.confirm(T.delAsk)) return;
          client.from("bird_messages").delete().eq("id", r.id).then(function () { load(); });
        });
        head.appendChild(del);
      }

      var body = document.createElement("p");
      body.className = "bd-text";
      body.textContent = r.body;

      it.appendChild(head);
      it.appendChild(body);
      elList.appendChild(it);
    });
  }

  function load() {
    if (!client) return;
    client
      .from("bird_messages")
      .select("id,user_id,author_name,body,created_at")
      .order("created_at", { ascending: false })
      .limit(100)
      .then(function (res) {
        if (res.error) {
          elList.innerHTML = "";
          var p = document.createElement("p");
          p.className = "bd-empty";
          p.textContent = errText(res.error);
          elList.appendChild(p);
          return;
        }
        render(res.data);
      });
  }

  /* ---------- 启动 ---------- */
  client.auth.getSession().then(function (res) {
    user = res.data.session ? res.data.session.user : null;
    paint();
    load();
  });

  client.auth.onAuthStateChange(function (_evt, session) {
    user = session ? session.user : null;
    paint();
  });
})();
