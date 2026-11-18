/* 匿名访问计数：不写 cookie、不取原始 IP、不含任何个人标识。
   站长若在浏览器里开启了「请勿追踪」，这里就什么都不发。 */
(function () {
  try {
    if (navigator.doNotTrack === "1" || window.doNotTrack === "1" || navigator.globalPrivacyControl) return;
    // 站长本人登录过后台就不计入自己的浏览
    try { if (localStorage.getItem("zb_admin_token")) return; } catch (e) {}
    var p = location.pathname;
    if (p.indexOf("/admin") === 0 || p.indexOf("/api") === 0) return;
    var body = JSON.stringify({
      path: p,
      ref: document.referrer || "",
      lang: document.documentElement.getAttribute("lang") || "",
    });
    var url = "/api/hit";
    if (navigator.sendBeacon) {
      navigator.sendBeacon(url, new Blob([body], { type: "application/json" }));
    } else {
      fetch(url, {
        method: "POST",
        body: body,
        headers: { "content-type": "application/json" },
        keepalive: true,
        mode: "same-origin",
      }).catch(function () {});
    }
  } catch (e) {}
})();
