-- ===========================================================
-- 珠海观鸟图鉴 · 留言板
-- 在 Supabase Dashboard → SQL Editor 里整段粘贴执行一次即可。
-- 幂等：重复执行不会报错，也不会清掉已有留言。
-- ===========================================================

-- 1) 表 --------------------------------------------------------
create table if not exists public.bird_messages (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  author_name text not null,
  body        text not null,
  created_at  timestamptz not null default now(),
  constraint bird_messages_body_len check (char_length(body) between 1 and 800)
);

create index if not exists bird_messages_created_idx
  on public.bird_messages (created_at desc);

-- 2) 权限 ------------------------------------------------------
-- 线上默认只让登录用户写入，匿名只读。
revoke all on public.bird_messages from anon, authenticated;
grant select on public.bird_messages to anon, authenticated;
grant insert, delete on public.bird_messages to authenticated;

-- 3) 行级安全 --------------------------------------------------
alter table public.bird_messages enable row level security;

drop policy if exists "bird_msg_read" on public.bird_messages;
create policy "bird_msg_read"
  on public.bird_messages for select
  to anon, authenticated
  using (true);

drop policy if exists "bird_msg_insert_own" on public.bird_messages;
create policy "bird_msg_insert_own"
  on public.bird_messages for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "bird_msg_delete_own" on public.bird_messages;
create policy "bird_msg_delete_own"
  on public.bird_messages for delete
  to authenticated
  using (auth.uid() = user_id);

-- 4) 写入前后处理 ----------------------------------------------
-- 昵称以注册时填的 user metadata 为准，客户端传什么都不算数，
-- 免得有人冒用别人的名字留言。
create or replace function public.bird_msg_before_insert()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  nick text;
  recent int;
begin
  if new.user_id is null then
    raise exception 'missing user';
  end if;

  select coalesce(nullif(btrim(u.raw_user_meta_data ->> 'nickname'), ''), '观鸟人')
    into nick
    from auth.users u
   where u.id = new.user_id;

  new.author_name := left(coalesce(nick, '观鸟人'), 40);
  new.body        := btrim(new.body);

  if char_length(new.body) < 1 then
    raise exception 'empty_body';
  end if;

  -- 同一个人 10 分钟内最多 5 条，挡一下手抖和刷屏
  select count(*) into recent
    from public.bird_messages m
   where m.user_id = new.user_id
     and m.created_at > now() - interval '10 minutes';

  if recent >= 5 then
    raise exception 'rate_limited' using hint = '十分钟内最多五条';
  end if;

  return new;
end;
$$;

drop trigger if exists bird_msg_before_insert on public.bird_messages;
create trigger bird_msg_before_insert
  before insert on public.bird_messages
  for each row execute function public.bird_msg_before_insert();
