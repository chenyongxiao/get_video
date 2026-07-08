import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path

import httpx
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright

app = FastAPI(title="抖音视频下载器")

# 项目根目录
STATIC_DIR = Path(__file__).parent

# 配置
DOWNLOAD_DIR = Path(__file__).parent / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# 全局浏览器实例
_browser = None
_browser_lock = asyncio.Lock()


async def get_browser():
    """获取或创建浏览器实例"""
    global _browser
    async with _browser_lock:
        if _browser is None or not _browser.is_connected():
            p = await async_playwright().start()
            _browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
        return _browser


async def extract_video_info(douyin_url: str) -> dict:
    """
    通过 Playwright 打开抖音页面，从网络请求中提取视频真实地址
    """
    browser = await get_browser()
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
    )

    video_url = None
    video_info = {"title": "", "author": "", "duration": "", "cover": ""}

    def handle_response(response):
        nonlocal video_url
        url = response.url
        # 匹配抖音视频文件地址
        if "douyinvod.com" in url and "video/tos" in url and "mime_type=video_mp4" in url:
            video_url = url.split("?")[0] + "?" + url.split("?", 1)[1] if "?" in url else url

    context.on("response", handle_response)

    page = await context.new_page()

    try:
        # 设置超时
        await page.goto(douyin_url, timeout=30000, wait_until="domcontentloaded")

        # 等待页面加载
        await page.wait_for_timeout(5000)

        # 尝试获取视频标题
        try:
            title_el = await page.query_selector("h1")
            if title_el:
                video_info["title"] = await title_el.inner_text()
        except Exception:
            pass

        # 如果还没获取到视频URL，等待更多网络请求
        if not video_url:
            await page.wait_for_timeout(3000)

        # 尝试从页面中提取视频信息
        if not video_url:
            # 尝试从页面源码中提取
            html = await page.content()
            # 匹配 video 标签的 src
            match = re.search(r'<video[^>]*src=["\']([^"\']+)["\']', html)
            if match:
                video_url = match.group(1)

        if not video_url:
            # 尝试从 script 标签中提取
            scripts = await page.query_selector_all("script")
            for script in scripts:
                try:
                    content = await script.inner_text()
                    # 查找视频地址模式
                    patterns = [
                        r'https?://[^"\']*douyinvod[^"\']*video[^"\']*mp4[^"\']*',
                        r'"play_addr"[^}]*"url_list"\s*:\s*\["([^"]+)"',
                        r'"play_api"[^}]*"url_list"\s*:\s*\["([^"]+)"',
                    ]
                    for pattern in patterns:
                        matches = re.findall(pattern, content)
                        if matches:
                            video_url = matches[0].replace("\\u0026", "&")
                            # 提取标题
                            title_match = re.search(r'"desc"\s*:\s*"([^"]+)"', content)
                            if title_match:
                                video_info["title"] = title_match.group(1)
                            break
                    if video_url:
                        break
                except Exception:
                    continue

        if not video_url:
            raise HTTPException(status_code=404, detail="无法获取视频地址，请检查链接是否正确")

        # 清理URL
        video_url = video_url.replace("\\u0026", "&").replace("\\/", "/")

        # 获取视频标题（如果还没获取到）
        if not video_info.get("title"):
            try:
                title = await page.title()
                video_info["title"] = title.replace(" - 抖音", "").strip()
            except Exception:
                video_info["title"] = "抖音视频"

        return {
            "video_url": video_url,
            "title": video_info["title"][:100] if video_info["title"] else "抖音视频",
            "author": video_info.get("author", ""),
            "duration": video_info.get("duration", ""),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")
    finally:
        await page.close()
        await context.close()


async def download_video(video_url: str, filename: str) -> Path:
    """下载视频到本地"""
    filepath = DOWNLOAD_DIR / filename

    async with httpx.AsyncClient(
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.douyin.com/",
        },
        timeout=60,
    ) as client:
        response = await client.get(video_url)
        response.raise_for_status()

        with open(filepath, "wb") as f:
            f.write(response.content)

    return filepath


@app.get("/")
async def root():
    """返回前端页面"""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/parse")
async def parse_video(url: str = Query(..., description="抖音分享链接")):
    """解析抖音视频链接，获取视频信息"""
    # 验证链接格式
    if not url or ("douyin.com" not in url and "v.douyin.com" not in url):
        raise HTTPException(status_code=400, detail="请输入有效的抖音分享链接")

    # 如果是短链接，先解析
    if "v.douyin.com" in url:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                resp = await client.get(url, timeout=10)
                url = str(resp.url)
            except Exception:
                pass

    info = await extract_video_info(url)
    return JSONResponse(content=info)


@app.get("/api/download")
async def download_video_endpoint(
    url: str = Query(..., description="视频直链"),
    title: str = Query("抖音视频", description="视频标题"),
):
    """下载视频文件"""
    # 生成安全的文件名
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:50]
    timestamp = int(time.time())
    filename = f"{safe_title}_{timestamp}.mp4"
    if not filename:
        filename = f"douyin_video_{timestamp}.mp4"

    filepath = await download_video(url, filename)

    encoded_filename = quote(filename)
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="video/mp4",
        headers={
            "Content-Disposition": f"attachment; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}",
        },
    )


@app.get("/api/parse-and-download")
async def parse_and_download(url: str = Query(..., description="抖音分享链接")):
    """一键解析并下载视频"""
    # 验证链接
    if not url or ("douyin.com" not in url and "v.douyin.com" not in url):
        raise HTTPException(status_code=400, detail="请输入有效的抖音分享链接")

    # 解析视频
    info = await extract_video_info(url)

    # 下载视频
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", info["title"])[:50]
    timestamp = int(time.time())
    filename = f"{safe_title}_{timestamp}.mp4"

    filepath = await download_video(info["video_url"], filename)

    encoded_filename = quote(filename)
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="video/mp4",
        headers={
            "Content-Disposition": f"attachment; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
