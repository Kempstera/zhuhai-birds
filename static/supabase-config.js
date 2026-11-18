/* ------------------------------------------------------------------
 * Supabase 连接配置（前端公开信息，不是密码）
 *
 * url  = 项目地址    anon = 公开的 anon public key
 * anon key 本来就是给浏览器用的，谁能读谁能写由 RLS 决定（见 supabase/schema.sql）
 * 千万不要把 service_role key 放在这里
 * ------------------------------------------------------------------ */
window.SB_CONFIG = {
  url: "https://birds.signupeverywhere.cc/api/sb",
  anon: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inhpdm9ibXVjanV0ZGZveG1manh1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTAxNDk1MzMsImV4cCI6MjEwNTcyNTUzM30.F9HBb17S9RarsLKOlCJp3S3fJ2c374KP10x_DvmTZRA"
};
