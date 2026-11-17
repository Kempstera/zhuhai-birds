# 珠海观鸟图鉴 · Field Guide to the Birds of Zhuhai

一份面向华南（珠三角 / 珠海）的常见鸟类科普图鉴网站。收录 **33 种**本地相对容易遇见的鸟类，
每种包含辨识特征、习性、野外鸣声录音、珠海具体观察地点与相似种对照。

纯静态站点，无框架、无外部字体依赖，构建产物可直接托管。

## 线上地址

- 生产环境：https://birds.signupeverywhere.cc
- Pages 默认域名：https://zhuhai-birds.pages.dev
- 源码仓库：https://github.com/Kempstera/zhuhai-birds

---

## 站点结构

```
index.html          首页：Hero、生态类群、物种名录（可筛选/搜索）、观鸟地点、野外守则
bird/<slug>.html    33 个物种详情页
guide.html          观鸟指南：为什么是珠海、四季日历、装备、如何听鸟、记录与分享
404.html            自定义错误页
robots.txt          搜索引擎规则
sitemap.xml         站点地图
```

## 目录说明

```
data/species.json   物种内容数据（中文名、学名、特征、习性、鸣声描述、观察点等）
data/assets.json    素材元数据（图片/录音的文件名、作者、许可、原始链接）
scripts/            素材采集脚本（维基共享资源 + iNaturalist）
templates/          Jinja2 页面模板
static/             样式与脚本（style.css / app.js）
assets/img/         鸟类图片，每种两张 webp（1600px / 900px）
assets/audio/       鸟鸣录音，mp3（单声道 32kHz，约 55 秒内）
dist/               构建产物（部署这个目录）
build.py            静态站点生成器
```

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
