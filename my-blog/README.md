# 我的博客（零运维静态站）

写完 Markdown，`git push`，GitHub Actions 自动构建并发布到 GitHub Pages。
没有服务器、没有数据库、没有 npm 依赖，构建器只有一个 `build.py`（仅用 Python 标准库）。

## 目录结构

```
my-blog/
├── build.py                  # 生成器：Markdown -> 静态 HTML
├── build.cmd                 # Windows 本地构建/预览封装
├── site.json                 # 站点配置（标题、作者、域名、导航）
├── posts/                    # 文章，文件名 YYYY-MM-DD-slug.md
├── pages/about.md            # 「关于」页
├── static/                   # 原样拷贝到站点根目录（style.css / app.js / 图片）
├── public/                   # 构建产物（已被 .gitignore 忽略）
└── .github/workflows/deploy.yml   # 推送即部署
```

## 本地写作与预览

```powershell
cd my-blog
.\build.cmd --serve      # Windows：自动找 Python，构建并打开 http://127.0.0.1:8000
python build.py --serve  # macOS / Linux，或已把 python 加进 PATH 时
```

`build.cmd` 只是包了一层「找一个能用的 Python 3 再调用 build.py」：
本机 `python` 若被微软应用商店的占位符劫持（报 `Python was not found`），它会自动回退到可用的解释器。
不想用封装脚本时，直接 `python build.py` 即可，只需 Python 3.11+，无第三方依赖。

其它命令：

| 命令 | 作用 |
| --- | --- |
| `build.cmd` / `python build.py` | 只构建到 `public/` |
| `--clean` | 先清空 `public/` 再构建 |
| `--drafts` | 连 `draft: true` 的文章一起构建 |
| `--new "文章标题"` | 在 `posts/` 新建一篇带 front matter 的草稿 |
| `--serve --port 8080` | 指定端口预览 |

> 必须用 `--serve` 或任意本地 HTTP 服务器打开（`python -m http.server -d public 8000`）。
> 直接双击 `public/index.html` 用 `file://` 打开时，搜索功能会被浏览器拦截、相对链接也会失效。

## 写一篇文章

文件名要求：`YYYY-MM-DD-英文或中文slug.md`，日期和 slug 都能从文件名推断。

```markdown
---
title: 文章标题
date: 2025-03-01 10:30
tags: 技术, 随笔
summary: 一句话摘要，会显示在列表和搜索结果里；不写就自动取第一段。
draft: true
---

正文从这里开始……
```

front matter 字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `title` | 建议 | 不写则用文件名里的 slug |
| `date` | 建议 | 不写则用文件名前缀的日期，再不行用文件修改时间 |
| `tags` | 否 | 逗号分隔，自动生成标签页 |
| `summary` | 否 | 列表摘要、搜索摘要、RSS 描述 |
| `draft` | 否 | `true` 时不参与构建，除非加 `--drafts` |
| `slug` | 否 | 覆盖 URL 里的文件名 |

正文里可以放图片：把文件丢进 `static/images/`，然后写 `![说明](/images/photo.jpg)`。

## 站点配置 `site.json`

```json
{
  "title": "我的博客",
  "author": "站长",
  "description": "记录学习、折腾与思考。",
  "url": "https://example.com",
  "base_path": "",
  "lang": "zh-CN",
  "nav": [{ "name": "首页", "path": "index.html" }]
}
```

- `url`：上线后填上真实域名，用于 RSS、sitemap、canonical 链接。
- `base_path`：部署在子路径时才需要，例如 `https://用户名.github.io/blog/` 就填 `"/blog"`；用「用户名.github.io」仓库或自定义域名时留空。

## 部署到 GitHub Pages（推荐）

1. 在 GitHub 新建仓库，把本项目内容推上去（分支名必须是 `main`，或同步改 `deploy.yml` 里的 `branches`）：

   ```powershell
   git init
   git add .
   git commit -m "init blog"
   git branch -M main
   git remote add origin https://github.com/你的用户名/仓库名.git
   git push -u origin main
   ```

2. 仓库 **Settings → Pages → Build and deployment → Source** 选 **GitHub Actions**。
3. 回到 **Actions** 标签，等 `Deploy blog` 跑完，站点地址会显示在部署摘要里。
4. 访问 `https://你的用户名.github.io/仓库名/`。这时记得把 `site.json` 的 `base_path` 设为 `"/仓库名"`，再推一次。

仓库名如果是 `用户名.github.io`，站点直接挂在根路径，`base_path` 留空。

### 绑自定义域名

1. `public/` 里放一个 `CNAME` 文件（内容就是域名，比如 `blog.example.com`）——把它放到 `static/CNAME`，构建时会自动拷过去。
2. 域名商处加 CNAME 记录指向 `你的用户名.github.io`。
3. Settings → Pages → Custom domain 填域名，勾选 Enforce HTTPS（证书自动签发）。
4. `site.json` 的 `url` 填 `https://blog.example.com`，`base_path` 改回 `""`。

> 中国大陆访问 `*.github.io` 可能不稳定；要面向国内读者，建议加 CDN 或改用备案过的国内托管。

## 备选托管（同样零运维）

- **Netlify**：连仓库即可，`netlify.toml` 已经写好；免费额度够个人博客用。
- **Vercel**：连仓库即可，`vercel.json` 已经写好。
- 两者都能自动 HTTPS、绑定自定义域名、每次推送生成预览。

## 生成的文件

| 文件 | 说明 |
| --- | --- |
| `index.html` | 首页文章列表 |
| `posts/<slug>.html` | 文章页（含目录、上一篇/下一篇） |
| `archive.html` | 按年份归档 |
| `tags/index.html`、`tags/<tag>.html` | 标签云与标签页 |
| `search.html` + `search.json` | 纯前端全文搜索（无需服务） |
| `feed.xml` | RSS 订阅 |
| `sitemap.xml` | 站点地图（填了 `url` 才生成） |
| `404.html` | GitHub Pages / Netlify 自动使用的 404 页 |

## 支持的 Markdown 语法

标题、段落（行末两空格强制换行）、有序/无序/嵌套列表、任务列表、引用（可嵌套）、
表格（支持 `:---:` 对齐）、围栏代码块（` ```python `）、行内 `code`、
`**粗体**`、`*斜体*`、`***粗斜体***`、`~~删除线~~`、`==高亮==`、
链接与图片、`<https://...>` 自动链接、原始 HTML 直通、水平线。

不支持的：脚注、数学公式、目录自动编号、HTML 之外的扩展语法。需要的话在 `build.py` 里加，几十行的事。

## 换主题 / 改样式

所有样式在 `static/style.css`，配色集中在文件顶部的 CSS 变量里，
深浅色由 `html[data-theme="dark"]` 覆盖。改完重新构建即可。

## 常见问题

**构建报 `UnicodeDecodeError`？**
文章要存成 UTF-8。Windows 上用 VS Code 右下角切到 `UTF-8` 再保存。

**中文文件名/URL 能行吗？**
能，生成的链接是 UTF-8 百分号编码。想让 URL 更干净，就在 front matter 里加 `slug: my-post`。

**能加评论吗？**
可以接 giscus（GitHub Discussions，免费、无广告），在 `build.py` 的 `build_post()` 里插一段 `<script>` 就行。默认没加，是为了保持零第三方依赖。