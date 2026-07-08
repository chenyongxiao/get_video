# 视频下载器

一个基于 FastAPI + Playwright 的视频下载工具，支持通过分享链接解析并下载无水印视频。

## 功能特性

- 粘贴分享链接，自动解析视频地址
- 一键下载无水印视频到本地
- 下载历史记录管理
- 手机端适配的响应式界面
- 一键解析并下载（`/api/parse-and-download`）

## 环境要求

- Python 3.9+
- 操作系统：Windows / macOS / Linux
- 网络环境：可正常访问

## 快速开始

### 1. 克隆项目

```bash
git clone <项目地址>
cd get_video
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 安装 Playwright 浏览器

```bash
playwright install chromium
```

### 4. 启动服务

```bash
python main.py
```

服务默认运行在 `http://localhost:8000`

### 5. 使用

1. 打开浏览器访问 `http://localhost:8000`
2. 在输入框中粘贴分享链接（如 `https://v.douyin.com/xxxxx/`）
3. 点击「解析并下载」按钮
4. 等待解析完成，视频将自动下载到本地

## API 接口

### POST /api/parse

解析视频链接，获取视频信息。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 分享链接 |

**返回示例：**

```json
{
  "video_url": "https://...douyinvod.com/...",
  "title": "视频标题",
  "author": "作者名",
  "duration": ""
}
```

### GET /api/download

下载视频文件。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 视频直链（从 parse 接口获取） |
| `title` | string | 否 | 视频标题，用于文件名 |

### GET /api/parse-and-download

一键解析并下载视频（直接返回视频文件）。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 分享链接 |

## 项目结构

```
get_video/
├── main.py              # 后端服务主程序
├── index.html           # 前端页面（CSS/JS内联）
├── requirements.txt     # Python 依赖
├── README.md            # 本文档
├── downloads/           # 视频下载目录（自动创建）
└── server.log           # 服务运行日志
```

## 注意事项

- 首次启动需要下载 Playwright 浏览器（约 200MB）
- 解析速度取决于网络状况和页面加载速度
- 下载的视频文件保存在 `downloads/` 目录
- 请遵守平台的使用条款和相关法律法规
