# 珠海观鸟图鉴 · Field Guide to the Birds of Zhuhai

一份面向华南（珠三角 / 珠海）的常见鸟类科普图鉴网站。收录 **65 种**本地有机会遇见的鸟类（按遇见率从极常见到罕见排序），
每种包含辨识特征、习性、野外鸣声录音、珠海具体观察地点与相似种对照，以及
**一张科学绘图（博物画）+ 两张野外摄影**组成的图集。

纯静态站点，无框架、无外部字体依赖，构建产物可直接托管。

## 线上地址

- 生产环境：https://birds.signupeverywhere.cc
- Pages 默认域名：https://zhuhai-birds.pages.dev
- 源码仓库：https://github.com/Kempstera/zhuhai-birds

---

## 站点结构

中英双语，**英文为默认**（`/` 根目录放英文，方便境外转发与搜索收录）；`/zh/` 为中文版，右上角按钮可互相切换。旧的 `/en/...` 地址由 `dist/_redirects` 301 到根目录同名路径，不会失效。

```
index.html          首页：Hero、生态类群、物种名录（可筛选/搜索）、观鸟地点、野外守则
bird/<slug>.html    65 个物种详情页
guide.html          观鸟指南：为什么是珠海、四季日历、装备、如何听鸟、记录与分享
board/index.html    留言板（Supabase 注册 / 登录 / 留言，配置好才进导航）
visits/index.html   访客看板（站长专用，口令进入；noindex，不进导航与 sitemap）
404.html            自定义错误页
zh/                 中文版，除访客看板外与上面完全镜像
robots.txt          搜索引擎规则
sitemap.xml         站点地图（中英成对 + xhtml:link 互指，x-default 指英文）
```

## 目录说明

```
functions/                 Cloudflare Pages Functions（访问统计 + Supabase 同域中转）
functions/api/visitors.js  访客明细接口（Bearer 口令，前端现算全部图表）
wrangler.toml              Pages 项目配置 + D1 绑定
data/species.json          物种内容（中文名、学名、特征、习性、鸣声描述、观察点等）
data/species_en.json       每个物种的英文正文（tagline / summary / features / behavior / voice / tip）
data/i18n/ui.json          界面文案（导航、按钮、小标题、页脚…），zh / en 两份
data/i18n/vocab.json       枚举词表（生境、观察点、特征键、科名、居留型、保护级别、IUCN）
data/assets.json           素材元数据（封面图 / 录音 / 图集三项的文件名、作者、许可、原始页）
data/gallery_override.json 人工挑选清单（修正自动检索结果，指定图版或照片）
data/plate_exclude.json    图版黑名单（海报、地图、报纸版面等不适合入册的扫描件）
scripts/                   素材采集与整理脚本（见下表）
templates/                 Jinja2 页面模板
static/                    样式与脚本（style.css / app.js / beacon.js / board.js / visits.js）
static/vendor/             本地内嵌的第三方库（supabase.js，避免 CDN 被墙或版本漂移）
static/supabase-config.js  留言板的 Supabase 地址与 anon key（空则整块功能隐藏）
supabase/schema.sql        留言板建表 / RLS / 触发器，贴进 Supabase SQL Editor 执行一次
assets/img/                鸟类图片 webp，每张两档尺寸（1600px / 900px）
assets/audio/              鸟鸣录音 mp3（单声道 32kHz，约 55 秒内）
dist/                      构建产物（部署这个目录）
build.py                   静态站点生成器
```

### 图集素材

每个物种页都有一组 **3 张图**：

| 位置 | 内容 | 文件命名 |
| --- | --- | --- |
| 第 1 张 | 科学绘图 / 博物画（Gould、Keulemans、Hardwicke、Iconographia Zoologica、BHL 等） | `<slug>-plate-{1600,900}.webp` |
| 第 2、3 张 | 野外摄影 | `<slug>-ph{1,2}-{1600,900}.webp` |

封面大图另记为 `<slug>-hero-*.webp`。图集条目在 `data/assets.json` 的 `gallery` 数组里，
每项形如：

```json
{
  "card": "chi-lu-ph1-900.webp",
  "big":  "chi-lu-ph1-1600.webp",
  "w": 1600, "h": 1067,
  "kind": "photo",
  "title": "Ardeola bacchus (52).jpg",
  "credit": "author", "license": "CC BY-SA 4.0", "page": "https://commons.wikimedia.org/...",
  "note": "（可选）同属对照说明"
}
```

`kind` 取 `plate`（绘图）或 `photo`（摄影），构建时绘图一律排在最前。
少数物种（池鹭、黑脸琵鹭、黑领椋鸟）没有开放授权的本种历史图版，
改用同属近缘种绘图，并在 `note` 字段里写明「同属对照」以免误认。

### 两套裁切（容易搞错的地方）

首页卡片和详情页大图是**两种完全不同的画面比例**，因此各有一个裁切字段：

| 字段 | 作用位置 | 画面比例 | 默认值 |
| --- | --- | --- | --- |
| `img.cardpos` | 首页物种名录卡片 `.bc-media` | 4 / 2.9 ≈ 1.38 : 1 | 浏览器默认（居中 50%） |
| `img.pos` | 详情页顶部大图 `.detail-hero` | 2.29 : 1（视口矮时会到 3.37 : 1） | `center 18%` |

两者都写 CSS 的 `object-position`，形如 `"center 10%"`。
**百分比越小取景越靠上**——鸟头贴顶或出框时要把数值调小。
只为个别物种加覆盖值，不要全局改动，否则会连带改掉本来正常的构图。

### 汉语拼音

`data/species.json` 每个物种的 `py` 字段存带声调拼音（音节用空格分隔）。
`build.py` 的 `ruby()` 会把它逐音节对齐到每个汉字头顶：

```html
<ruby class="rb">白<rt>bái</rt></ruby><ruby class="rb">头<rt>tóu</rt></ruby>…
```

前提是**汉字数 == 音节数**（65 个名称目前全部满足）；对不上时函数会自动退回
「汉字 + 并排拼音」的老写法，不会错位。新增物种后可用这段自查：

```bash
python3 -c "import json,re;sp=json.load(open('data/species.json'));
[print(s['zh'],len(re.findall(r'[\u4e00-\u9fff]',s['zh'])),len(s['py'].split())) for s in sp if len(re.findall(r'[\u4e00-\u9fff]',s['zh']))!=len(s['py'].split())]"
```

### 双语机制

`build.py` 对 `LANGS = ("zh", "en")` 循环两遍，**英文写进 `dist/`（默认语言），中文写进 `dist/zh/`**。
同一个模板靠 `make_view()` 产出的视图字典渲染，所以模板里没有 `if 中文 else 英文` 的分支。

- 界面文案 → `data/i18n/ui.json`（`T.nav.species`、`T.d.voice_h` 之类）
- 词表（科名、生境、居留型、保护级别、特征键）→ `data/i18n/vocab.json`
- 物种正文 → `data/species_en.json`；缺某条时构建会打印「待翻译」清单，并自动退回
  「特征键英文 + 中文正文」，不会崩
- 页面里 `<html lang>`、`hreflang`、`canonical`、sitemap 的成对 `<url>` 都由构建生成

**两个 root 不要混。** 英文首页在 `/`、详情页在 `/bird/x.html`；中文首页在 `/zh/`、详情页在 `/zh/bird/x.html`：

| 变量 | 首页层级 | 详情页层级 | 用途 |
| --- | --- | --- | --- |
| `root` | `""`（中：`../`） | `../`（中：`../../`） | 指向**站点根**：`static/`、`assets/` |
| `pr` | `""` | `../` | 指向**本语言根**：`index.html`、`guide.html`、`bird/` |

`root` 是「距站点根几层」的资源前缀，`pr` 是「距本语言根几层」的页面前缀。两种语言的 `pr` 完全一样
（各自语言的首页、404 都在本语言根目录里），只有 `root` 因为中文多一层 `/zh/` 而不同。
用 `root` 写页面链接会把英文页的导航带到中文首页去——这是最容易踩的坑。

### scripts

| 脚本 | 作用 |
| --- | --- |
| `fetch_assets.py` | 采集封面高清图与野外录音，转 webp / mp3 |
| `fetch_gallery.py` | 采集图集素材：2 张摄影 + 1 张科学绘图 |
| `pick_plates.py` | 对候选图版重新打分挑选（全局去重、排除海报/地图/报纸） |
| `trim_plates.py` | 自动裁掉古版画扫描件四周的纸边 |
| `repair_gallery.py` | 修复图版与照片的文件名冲突 |
| `probe_photos.py` | 抓候选照片并渲染成对照表，供人工挑选 |
| `probe_audio.py` / `patch_audio.py` / `fix_audio.py` | 录音补齐与修补 |

## 访客看板 /visits（站长专用）

站内自建，不依赖第三方统计服务：**没有 cookie、不存 IP、不接追踪脚本**。

- 入口：<https://birds.signupeverywhere.cc/visits/>（页脚右下角那个很淡的「统计」；不进导航、不进 sitemap、`noindex`）
- 打开先要口令。口令只存在 Cloudflare D1 的 `cfg` 表（`admin_token`），页面本身不含任何口令，
  校验在服务端做；浏览器只在 `sessionStorage` 里记一次，关标签页即失效
- 输对之后是**一屏看板**：6 个 KPI（访客／浏览／人均页数／今天对昨天／手机占比／中文界面占比）、
  访问趋势（柱＝浏览、线＝访客）、时段分布（北京时间 24 小时）、七八条自动分析、
  11 个排行榜（设备／浏览器／语言／页面类型／来源／落地页／国家／中英文地址／星期／访问深度／热门物种），
  以及带搜索、排序、分页、CSV 导出的逐条明细
- 时间范围可切 今天／7 天／30 天／90 天／全部，**切换不再打接口**：页面一次取回明细，全部在浏览器里现算

```
functions/api/hit.js       收信标 → 写一行记录（爬虫/脚本 UA 直接丢，DNT 不发）
functions/api/visitors.js  读明细行，需要 Bearer 口令，口令不对一律 401，响应 no-store
functions/_lib.js          建表语句与共用小工具（以 _ 开头，不会被注册成路由）
```

数据在 D1 表 `hit`（`ts / d / h / path / ref / country / lang / dev / br / vid`），
`d` 与 `h` 是**北京时间**的日期与小时。

- 访客指纹 = `sha256(IP + UA + 盐 + 日期)` 取前 16 位：**当日唯一、跨日不可关联、不可逆推**。
  代价是「访客数」只能按日去重后相加 —— 同一个人隔天再来会再计一次，看板上已注明
- 国家来自 `CF-IPCountry`，只到国家一级
- 站长本人登录后台后，自己的浏览不再计入（`beacon.js` 检测本机口令）
- 两年以上的记录在写入时按 2% 概率顺手清掉
- 旧的 `/admin/` 与 `/zh/visits/` 都 301 到 `/visits/`

### 改口令

```bash
NEW=$(python3 -c "import secrets;print('wren-'+secrets.token_urlsafe(12).replace('_','')[:14])")
node ~/.npm/_npx/*/node_modules/wrangler/bin/wrangler.js d1 execute zhuhai-birds-stats \
  --remote --command "INSERT INTO cfg(k,v) VALUES('admin_token','$NEW') \
  ON CONFLICT(k) DO UPDATE SET v=excluded.v"
```

改完在后台点「退出」再重新进入。注意：口令只存在 D1 里，**不要写进仓库**。

## 留言板（Supabase）

`/board/` 与 `/en/board/`：访客用邮箱注册 / 登录，然后写一条留言。数据存在你自己的
Supabase 项目里，不经过任何第三方服务。

- 页面：`templates/board.html`，前端逻辑：`static/board.js`（Supabase JS SDK v2，本地内嵌，不走 CDN）
- 表结构、权限、触发器：`supabase/schema.sql`
- 连接地址：`static/supabase-config.js` 里的 `url` 与 `anon`
- 当前项目：`xivobmucjutdfoxmfjxu`（`Geoffrey's Project`，us-east-2），表 `public.bird_messages`

### 为什么 url 写的是本站域名

```js
url: "https://birds.signupeverywhere.cc/api/sb"   // 不是 https://xxx.supabase.co
```

`*.supabase.co` 在中国大陆会被 TLS 层直接重置（ClientHello 发出去就 RST），游客在手机
上根本连不上，登录和留言都会静默失败。本站域名在 Cloudflare 上、国内可访问，所以
`functions/api/sb/[[path]].js` 把 `/api/sb/**` 原样转发到 Supabase：`apikey` 与
`Authorization` 一起带过去，权限仍由 Postgres 的 RLS 决定，这一层不做任何鉴权、不缓存。

实测：本机直连 `*.supabase.co` 100% 失败，经本站中转登录 200、发帖 201、列表可读、删除 204。

### 三步接通（已完成，换项目时照做）

1. 在 <https://supabase.com/dashboard> 建一个项目（区域选 Singapore 或 Tokyo，离华南近）
2. 打开 **SQL Editor**，把 `supabase/schema.sql` 整段粘进去执行一次（幂等，可重复跑）
3. **Settings → API** 里复制 `Project URL` 与 `anon public`，填进 `static/supabase-config.js`，
   然后 `python3 build.py` 重新生成

两项都填好之后，导航栏和页脚才会出现「留言」入口；没填时页面只显示一句「还没接通」。
`anon` 是**公开**密钥，放进前端没问题，安全由数据库的 RLS 保证。`service_role` 密钥
**绝对不能**出现在这里。

### 三条设计取舍

| 做法 | 原因 |
| --- | --- |
| 昵称由触发器从 `auth.users.raw_user_meta_data` 覆写 | 客户端传什么名字都不算数，避免冒用 |
| 同一用户 10 分钟内最多 5 条（触发器里 `raise exception 'rate_limited'`） | 防手抖和刷屏，不引入额外服务 |
| 只有 `select` 开放给匿名，`insert / delete` 仅限本人 | 留言公开可读，但改删只能动自己那条 |

### 邮箱确认：当前是关闭的

这个项目的 *Authentication → Providers → Email → Confirm email* 是**关**的，注册完直接登录，
也就不需要配置 SMTP（Supabase 自带的邮件服务每小时只能发几封，做公开站点不够用）。

如果哪天打开了它：前端已经处理——注册拿不到 session 时提示「请到邮箱点确认链接」，
同时要把 *Authentication → URL Configuration* 的 `Site URL` 填成
`https://birds.signupeverywhere.cc`，否则邮件里的链接会指向 `localhost:3000`。


## 本地构建与预览

```bash
python3 -m pip install jinja2
python3 build.py                    # 输出到 dist/
python3 -m http.server 8877 --directory dist
# 打开 http://127.0.0.1:8877
```

## 部署

### 方式一：GitHub + Cloudflare Pages（推荐，push 自动部署）

1. 在 GitHub 新建仓库并推送本目录（`dist/` 一并提交）。
2. Cloudflare Dashboard → Workers & Pages → Create → Pages → Connect to Git。
3. 构建设置：
   - Framework preset：`None`
   - Build command：**留空**
   - Build output directory：`dist`
4. 部署完成后，进入 Custom domains，绑定 `birds.signupeverywhere.cc`。
5. 在域名 DNS 处按 Cloudflare 提示添加 CNAME（若域名已托管在 Cloudflare，会自动配置）。

### 方式二：Wrangler 直接上传

```bash
npx wrangler pages deploy dist --project-name zhuhai-birds
```

**必须在仓库根目录执行**：命令会顺带打包根目录下的 `functions/` 与 `wrangler.toml`
里的 D1 绑定；换到别的目录跑，静态页面照样能传上去，但 `/api/hit` 和 `/api/stats`
会变成 404，统计就静默失效了（页面本身不受影响）。部署输出里出现
`Uploading Functions bundle` 才算带上了函数。

方式一的 Git 集成同样能用，前提是构建设置把 `functions/` 目录一起带上（默认会）。

### 更新内容

修改 `data/species.json` → 运行 `python3 build.py` → 提交并推送。

## 素材来源与许可

- **图片**：Wikimedia Commons，各自遵循 CC BY / CC BY-SA / CC0 / Public Domain 等许可。
  每个物种页侧栏均标注作者与许可类型，并提供原始文件链接。
- **录音**：Wikimedia Commons（多为 Xeno-canto 转载）与 iNaturalist 的开放许可野外录音，
  同样在播放器下方标注作者、许可与来源页。

如需商用，请逐条核对各素材的许可条款；CC BY-NC 类素材不可用于商业用途。

## 内容准确性说明

- 保护级别依据《国家重点保护野生动物名录》（2021 年版）。
- 濒危等级依据 IUCN 红色名录。
- 居留型与遇见率以珠海—珠三角的普遍观察经验为准，会因年份、天气、潮位而有差异。
- 本站在物种选择上偏向「初学者一周内有机会遇到」的种类，并非珠海鸟类全名录
  （全市记录逾 300 种）。

## 免责与倡议

本站为非营利的科普项目。观察野生鸟类请保持距离、不使用回放引诱、不投喂、不进入保护区核心区。
中国境内所有野生鸟类均受《中华人民共和国野生动物保护法》保护。
