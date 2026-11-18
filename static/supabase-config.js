/* ------------------------------------------------------------------
 * Supabase 连接配置（前端公开信息，不是密码）
 *
 * 1. 打开 https://supabase.com/dashboard ，进入你的项目
 * 2. 左侧 Settings → API
 * 3. 把 "Project URL" 填到下面的 url
 * 4. 把 "Project API keys" 里的 anon / public 填到下面的 anon
 *
 * anon key 本来就是给浏览器用的公开密钥，放在这里不会泄露任何东西；
 * 谁能读、谁能写，全部由数据库的 RLS 策略决定（见 supabase/schema.sql）。
 * 千万不要把 service_role key 放到这个文件里。
 *
 * 两项都填好之后重新 build，导航栏和页脚才会出现「留言」入口。
 * ------------------------------------------------------------------ */
window.SB_CONFIG = {
  url: "",
  anon: ""
};
