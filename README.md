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

中英双语，**中文为默认**；`/en/` 为英文版，右上角按钮可互相切换。

```
index.html          首页：Hero、生态类群、物种名录（可筛选/搜索）、观鸟地点、野外守则
bird/<slug>.html    65 个物种详情页
guide.html          观鸟指南：为什么是珠海、四季日历、装备、如何听鸟、记录与分享
404.html            自定义错误页
en/                 英文版，目录结构与上面完全镜像
robots.txt          搜索引擎规则
sitemap.xml         站点地图（中英成对 + xhtml:link 互指）
```

## 目录说明

```
data/species.json          物种内容（中文名、学名、特征、习性、鸣声描述、观察点等）
data/species_en.json       每个物种的英文正文（tagline / summary / features / behavior / voice / tip）
data/i18n/ui.json          界面文案（导航、按钮、小标题、页脚…），zh / en 两份
data/i18n/vocab.json       枚举词表（生境、观察点、特征键、科名、居留型、保护级别、IUCN）
data/assets.json           素材元数据（封面图 / 录音 / 图集三项的文件名、作者、许可、原始页）
data/gallery_override.json 人工挑选清单（修正自动检索结果，指定图版或照片）
data/plate_exclude.json    图版黑名单（海报、地图、报纸版面等不适合入册的扫描件）
scripts/                   素材采集与整理脚本（见下表）
templates/                 Jinja2 页面模板
static/                    样式与脚本（style.css / app.js）
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

`build.py` 对 `LANGS = ("zh", "en")` 循环两遍，中文写进 `dist/`，英文写进 `dist/en/`。
同一个模板靠 `make_view()` 产出的视图字典渲染，所以模板里没有 `if 中文 else 英文` 的分支。

- 界面文案 → `data/i18n/ui.json`（`T.nav.species`、`T.d.voice_h` 之类）
- 词表（科名、生境、居留型、保护级别、特征键）→ `data/i18n/vocab.json`
- 物种正文 → `data/species_en.json`；缺某条时构建会打印「待翻译」清单，并自动退回
  「特征键英文 + 中文正文」，不会崩
- 页面里 `<html lang>`、`hreflang`、`canonical`、sitemap 的成对 `<url>` 都由构建生成

**两个 root 不要混。** 英文详情页在 `/en/bird/x.html`：

| 变量 | 值 | 用途 |
| --- | --- | --- |
| `root` | `../../` | 指向站点根：`static/`、`assets/` |
| `pr` | `../` | 指向**本语言**根：`index.html`、`guide.html`、`bird/` |

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
