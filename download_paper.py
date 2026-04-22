#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bulk paper and supplementary materials downloader.
Supports multiple PDF sources:
  - doi2pdf, scidownl, Sci-Hub direct, unpywall (OA)
  - Playwright browser automation (stealth mode)
  - arXiv direct download
  - OpenAlex API
  - CrossRef links
Supports supplementary materials: Datahugger + BeautifulSoup parsing.
Automatic deduplication, naming with {year}--{title}, and CSV report generation.

========== Installation ==========
Core dependencies:
  pip install requests pandas beautifulsoup4 doi2pdf scidownl unpywall datahugger pathvalidate

Optional (for enhanced downloading):
  # Playwright browser automation (recommended for bypassing anti-bot)
  pip install playwright
  playwright install chromium

  # For LLM-based browser control (future enhancement)
  pip install browser-use  # or other LLM browser tools

Usage:
  test_dois = ["10.1088/1367-2630/15/1/015025", ...]
  df_result = process_doi_list(test_dois, output_base_dir="my_papers")
"""

import os
import re
import time
import random
import requests
import pandas as pd
import argparse
import sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathvalidate import sanitize_filename
from typing import List, Dict, Optional, Tuple

# ========== Third-party imports (assumed installed) ==========
import doi2pdf
from scidownl import scihub_download
from unpywall import Unpywall
from unpywall.utils import UnpywallCredentials
import datahugger
from playwright.sync_api import sync_playwright
import pdfplumber

# PDF to Markdown conversion
try:
    from markitdown import MarkItDown
    HAS_MARKITDOWN = True
except ImportError:
    HAS_MARKITDOWN = False

try:
    from marker.convert import convert_single_pdf
    HAS_MARKER = True
except ImportError:
    HAS_MARKER = False

# Configure Unpywall with your email (replace with your actual email)
UnpywallCredentials("your_email@gmail.com")

# ========== Global configuration ==========
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Cache-Control': 'max-age=0',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'DNT': '1',
    'Connection': 'keep-alive',
}
REQUEST_DELAY = (2, 5)  # random delay range in seconds

# ========== Helper functions ==========
def pdf_to_markdown(pdf_path: str, md_path: str) -> bool:
    """
    Convert PDF to Markdown using MarkItDown or Marker.

    Args:
        pdf_path: Path to PDF file
        md_path: Path to output Markdown file

    Returns:
        True if conversion successful, False otherwise
    """
    try:
        if not os.path.exists(pdf_path):
            return False

        print(f"    📄 Converting PDF to Markdown: {os.path.basename(pdf_path)}")

        # Try MarkItDown first (usually faster and more reliable)
        if HAS_MARKITDOWN:
            try:
                md = MarkItDown()
                result = md.convert(pdf_path)

                if result and result.text_content:
                    with open(md_path, 'w', encoding='utf-8') as f:
                        # Add metadata header
                        header = f"""# {os.path.basename(pdf_path).replace('.pdf', '')}

**Source PDF**: {os.path.basename(pdf_path)}
**Converted**: {time.strftime('%Y-%m-%d %H:%M:%S')}

---

"""
                        f.write(header)
                        f.write(result.text_content)

                    print(f"    ✅ Converted using MarkItDown ({os.path.getsize(md_path)} bytes)")
                    return True
            except Exception as e:
                print(f"    ⚠️ MarkItDown conversion failed: {str(e)[:60]}")

        # Fallback to Marker if available
        if HAS_MARKER:
            try:
                result = convert_single_pdf(pdf_path)

                if result and result.get('text'):
                    with open(md_path, 'w', encoding='utf-8') as f:
                        header = f"""# {os.path.basename(pdf_path).replace('.pdf', '')}

**Source PDF**: {os.path.basename(pdf_path)}
**Converted**: {time.strftime('%Y-%m-%d %H:%M:%S')}

---

"""
                        f.write(header)
                        f.write(result['text'])

                    print(f"    ✅ Converted using Marker ({os.path.getsize(md_path)} bytes)")
                    return True
            except Exception as e:
                print(f"    ⚠️ Marker conversion failed: {str(e)[:60]}")

        # If neither library works
        print(f"    ❌ No PDF conversion tool available")
        return False

    except Exception as e:
        print(f"    ❌ PDF to Markdown conversion error: {e}")
        return False


def is_valid_pdf(file_path: str) -> bool:
    """Check if file is a valid PDF by checking magic number and other indicators."""
    try:
        if not os.path.exists(file_path):
            return False

        file_size = os.path.getsize(file_path)

        # PDF 文件通常至少 200 字节（最小有效 PDF）
        if file_size < 200:
            return False

        with open(file_path, 'rb') as f:
            # 检查 PDF 头部
            header = f.read(4)
            if header != b'%PDF':
                return False

            # 读取整个文件用于检查
            f.seek(0)
            content = f.read()

            # 检查 PDF 尾部标记
            if b'%%EOF' not in content and b'endobj' not in content:
                return False

        return True
    except Exception as e:
        print(f"    PDF validation error: {e}")
        return False

def is_valid_pdf_response(resp) -> bool:
    """Check if response content is likely a PDF, not HTML."""
    try:
        content = resp.content[:200]

        # 检查是否是 HTML（常见的失败指示符）
        html_indicators = [
            b'<html', b'<HTML', b'<!DOCTYPE', b'<head', b'<HEAD',
            b'<body', b'<BODY', b'<?xml', b'<title', b'<TITLE',
            b'Captcha', b'captcha', b'CAPTCHA', b'bot', b'Bot',
            b'challenge', b'Challenge', b'verify', b'Verify',
            b'access denied', b'Access Denied', b'403', b'404',
            b'redirect', b'Redirect', b'javascript', b'JavaScript'
        ]

        for indicator in html_indicators:
            if indicator in content:
                return False

        # 检查 PDF 魔法数字
        pdf_header = content[:4]
        return pdf_header == b'%PDF'
    except Exception:
        return False

def download_pdf_from_url(pdf_url: str, output_path: str, source_name: str = "unknown", use_playwright: bool = True) -> bool:
    """
    Universal PDF download function with HTTP and Playwright fallback.

    Strategy:
    1. Try direct HTTP download (fast)
    2. If fails or protected (403), try Playwright with browser session

    Args:
        pdf_url: URL to the PDF file
        output_path: Where to save the PDF
        source_name: Name of download source (for logging)
        use_playwright: Whether to try Playwright fallback (default: True)

    Returns:
        True if successfully downloaded, False otherwise
    """

    # Step 1: Try direct HTTP download (fast path)
    try:
        print(f"      Trying direct HTTP download...")
        pdf_resp = requests.get(pdf_url, headers=HEADERS, timeout=30)

        if pdf_resp.status_code == 200 and is_valid_pdf_response(pdf_resp):
            with open(output_path, 'wb') as f:
                f.write(pdf_resp.content)

            if is_valid_pdf(output_path):
                print(f"    {source_name} result: True (direct HTTP)")
                return True
            else:
                os.remove(output_path)
                print(f"      PDF validation failed after HTTP")

    except Exception as e:
        print(f"      Direct HTTP failed: {str(e)[:50]}")

    # Step 2: Try Playwright for protected URLs (if enabled and not already downloaded)
    if use_playwright and not os.path.exists(output_path):
        print(f"      Trying Playwright for protected URL...")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
                )

                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = context.new_page()

                try:
                    # Load PDF URL to establish session and get cookies
                    print(f"      Loading {pdf_url[:60]}...")
                    response = page.goto(pdf_url, wait_until='domcontentloaded', timeout=20000)

                    if response and response.status in [200, 304]:
                        page.wait_for_timeout(2000)

                        # Get cookies from browser session
                        cookies = context.cookies()
                        cookie_dict = {c['name']: c['value'] for c in cookies}

                        # Retry download with browser cookies
                        print(f"      Retrying with browser session...")
                        pdf_resp = requests.get(
                            pdf_url,
                            headers=HEADERS,
                            cookies=cookie_dict,
                            timeout=30
                        )

                        if pdf_resp.status_code == 200 and is_valid_pdf_response(pdf_resp):
                            with open(output_path, 'wb') as f:
                                f.write(pdf_resp.content)

                            if is_valid_pdf(output_path):
                                print(f"    {source_name} result: True (Playwright session)")
                                browser.close()
                                return True
                            else:
                                os.remove(output_path)
                                print(f"      PDF validation failed after Playwright")

                except Exception as e:
                    print(f"      Playwright error: {str(e)[:50]}")

                finally:
                    browser.close()

        except Exception as e:
            print(f"      Playwright fallback failed: {str(e)[:50]}")

    # Both methods failed
    if os.path.exists(output_path):
        os.remove(output_path)

    return False


    """Remove/replace illegal characters for cross-platform safety."""
    illegal_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(illegal_chars, '_', filename)
    sanitized = sanitized.strip('. ')
    if not sanitized:
        sanitized = "unnamed"
    return sanitize_filename(sanitized)

def get_metadata_from_unpywall(doi: str) -> Optional[Dict]:
    """Fetch metadata (title, year, OA PDF URL) using unpywall."""
    try:
        df = Unpywall.doi(dois=[doi])
        if df is not None and not df.empty:
            row = df.iloc[0]
            title = row.get('title', '')
            year = row.get('year', '')
            oa_pdf_url = None
            oa_status = row.get('is_oa', False)
            if 'best_oa_location' in row:
                best = row['best_oa_location']
                if isinstance(best, dict):
                    oa_pdf_url = best.get('url_for_pdf')
            return {
                'title': str(title) if title else '',
                'year': str(year) if pd.notna(year) else '',
                'oa_pdf_url': oa_pdf_url,
                'is_oa': oa_status
            }
    except Exception as e:
        print(f"  unpywall metadata fetch failed: {e}")
    return None

def get_metadata_from_crossref(doi: str) -> Optional[Dict]:
    """Fallback: fetch title and year via Crossref API."""
    try:
        url = f"https://api.crossref.org/works/{doi}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            title = data['message']['title'][0] if data['message'].get('title') else ''
            year = data['message'].get('issued', {}).get('date-parts', [[None]])[0][0]
            return {'title': title, 'year': str(year) if year else ''}
    except Exception as e:
        print(f"  Crossref metadata fetch failed: {e}")
    return None

def get_paper_metadata(doi: str) -> Tuple[str, str]:
    """Get paper title and year, preferring unpywall then Crossref."""
    meta = get_metadata_from_unpywall(doi)
    if not meta or not meta['title']:
        meta = get_metadata_from_crossref(doi)
    if not meta or not meta['title']:
        # Fallback: construct placeholder from DOI
        return f"Paper_{doi.replace('/', '_')}", "unknown"
    return meta['title'], meta['year']

def check_paper_already_exists(output_dir: str, year: str, title: str, doi: str) -> Optional[str]:
    """
    Check if a paper is already downloaded.
    If PDF exists but Markdown doesn't, generate it automatically.
    Returns the file path if found, None otherwise.

    Checks for files matching pattern: {year}--{sanitized_title}*.pdf
    """
    if not year or not title:
        return None

    try:
        base_filename = f"{year}--{sanitize_filename_custom(title)}"
        pdf_path = None

        # Check if exact file exists
        exact_path = os.path.join(output_dir, f"{base_filename}.pdf")
        if os.path.exists(exact_path) and is_valid_pdf(exact_path):
            pdf_path = exact_path
        else:
            # Check for numbered variants (_1, _2, etc.)
            for filename in os.listdir(output_dir):
                if filename.startswith(base_filename) and filename.endswith('.pdf'):
                    full_path = os.path.join(output_dir, filename)
                    if is_valid_pdf(full_path):
                        pdf_path = full_path
                        break

        # If PDF found, check and generate Markdown if needed
        if pdf_path:
            # Generate corresponding markdown path
            pdf_base = os.path.splitext(pdf_path)[0]
            md_path = f"{pdf_base}.md"

            # If Markdown doesn't exist, try to generate it
            if not os.path.exists(md_path):
                print(f"    📝 Markdown not found, generating from PDF...")
                success = pdf_to_markdown(pdf_path, md_path)
                if success:
                    print(f"       ✅ Markdown generated: {os.path.basename(md_path)}")
                else:
                    print(f"       ⚠️ Markdown generation skipped (no tool available)")
                    # Continue anyway - PDF is still valid

            return pdf_path

    except Exception as e:
        print(f"    Error checking for existing file: {e}")

    return None


def get_pdf_output_path(output_dir: str, year: str, title: str, doi: str) -> str:
    """Generate PDF file path, avoiding duplicates."""
    filename = f"{year}--{sanitize_filename_custom(title)}.pdf"
    path = os.path.join(output_dir, filename)
    if os.path.exists(path):
        return path
    base, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(path):
        new_name = f"{base}_{counter}{ext}"
        path = os.path.join(output_dir, new_name)
        counter += 1
    return path

# ========== PDF download functions with print of return values ==========
def download_via_doi2pdf(doi: str, output_path: str) -> bool:
    try:
        doi2pdf.doi2pdf(doi, output=output_path)
        success = os.path.exists(output_path) and is_valid_pdf(output_path)
        if success:
            print(f"    doi2pdf result: True")
        else:
            # 如果不是有效 PDF，删除文件
            if os.path.exists(output_path):
                os.remove(output_path)
            print(f"    doi2pdf result: False (invalid PDF or HTML)")
        return success
    except Exception as e:
        print(f"    doi2pdf exception: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False

def download_via_scidownl(doi: str, output_path: str) -> bool:
    try:
        # scidownl's scihub_download function: returns (success, path) or similar
        result = scihub_download(doi, output_path)
        # Assuming result is a tuple (bool, message/path) or just boolean
        if isinstance(result, tuple):
            success = result[0] if len(result) > 0 else False
        else:
            success = bool(result)
        print(f"    scidownl result: {success}")
        return success and os.path.exists(output_path)
    except Exception as e:
        print(f"    scidownl exception: {e}")
        return False

def download_via_unpywall(doi: str, output_path: str) -> bool:
    try:
        import subprocess
        result = subprocess.run(
            ['unpywall', 'fetch', doi, '--out', output_path],
            capture_output=True, text=True, timeout=60
        )
        success = (result.returncode == 0 and os.path.exists(output_path) and is_valid_pdf(output_path))
        if success:
            print(f"    unpywall result: True")
        else:
            # 验证失败，删除文件
            if os.path.exists(output_path):
                os.remove(output_path)
            print(f"    unpywall result: False (invalid PDF or download failed)")
        return success
    except Exception as e:
        print(f"    unpywall exception: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False

def download_via_scihub_direct(doi: str, output_path: str) -> bool:
    """Try Sci-Hub with enhanced PDF extraction and validation."""
    scihub_urls = [
        "https://sci-hub.ru",
        "https://sci-hub.st",
        "http://sci-hub.ru",
        "http://sci-hub.st",
    ]

    for base_url in scihub_urls:
        try:
            url = f"{base_url}/{doi}"
            resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)

            if resp.status_code == 200:
                # Check if response is HTML (need to extract PDF link)
                if resp.headers.get('content-type', '').startswith('text/html'):
                    print(f"    scihub_direct ({base_url}): Received HTML, extracting PDF link...")
                    soup = BeautifulSoup(resp.text, 'html.parser')

                    # Try to find PDF link in various ways
                    pdf_urls = []

                    # Method 1: Look for iframe with PDF
                    for iframe in soup.find_all('iframe'):
                        src = iframe.get('src', '')
                        if src:
                            pdf_urls.append(urljoin(url, src))

                    # Method 2: Look for embed tag
                    for embed in soup.find_all('embed'):
                        src = embed.get('src', '')
                        if src and 'pdf' in src.lower():
                            pdf_urls.append(urljoin(url, src))

                    # Method 3: Look for direct PDF links in HTML
                    for link in soup.find_all('a', href=True):
                        href = link.get('href', '')
                        if 'pdf' in href.lower() or href.endswith('.pdf'):
                            pdf_urls.append(urljoin(url, href))

                    # Method 4: Look for data attributes
                    for elem in soup.find_all(['div', 'span']):
                        for attr in elem.attrs:
                            if isinstance(elem.attrs[attr], str):
                                if '.pdf' in elem.attrs[attr]:
                                    pdf_urls.append(urljoin(url, elem.attrs[attr]))

                    # Try to download from extracted URLs
                    for pdf_url in pdf_urls:
                        try:
                            print(f"      Trying extracted URL: {pdf_url[:80]}...")
                            pdf_resp = requests.get(pdf_url, headers=HEADERS, timeout=30)
                            if pdf_resp.status_code == 200 and is_valid_pdf_response(pdf_resp):
                                with open(output_path, 'wb') as f:
                                    f.write(pdf_resp.content)
                                if is_valid_pdf(output_path):
                                    print(f"    scihub_direct ({base_url}) result: True")
                                    return True
                                else:
                                    # 验证失败，删除文件
                                    os.remove(output_path)
                        except Exception as e:
                            print(f"      Failed: {str(e)[:50]}")
                            if os.path.exists(output_path):
                                os.remove(output_path)
                            continue
                else:
                    # Binary content, likely PDF
                    if is_valid_pdf_response(pdf_resp):
                        with open(output_path, 'wb') as f:
                            f.write(pdf_resp.content)
                        if is_valid_pdf(output_path):
                            print(f"    scihub_direct ({base_url}) result: True")
                            return True
                        else:
                            # 验证失败，删除文件
                            os.remove(output_path)
        except Exception as e:
            print(f"    scihub_direct ({base_url}) exception: {str(e)[:80]}")
            continue

    print(f"    scihub_direct result: False (all domains failed or returned HTML)")
    return False


def download_via_playwright_enhanced(doi: str, output_path: str) -> bool:
    """
    增强版本的Playwright下载器，处理高级机器人检测（如APS）。
    针对需要Cloudflare验证和额外反爬虫检测的网站。
    """
    try:
        url = f"https://doi.org/{doi}"
        print(f"    playwright_enhanced: Accessing {url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                ]
            )

            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York',
            )

            page = context.new_page()

            # 隐藏所有自动化检测标记
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                window.chrome = { runtime: {} };
            """)

            try:
                # 添加随机延迟模拟真实用户
                import random
                random_delay = random.uniform(1.0, 3.0)
                print(f"      Adding delay: {random_delay:.1f}s")
                page.wait_for_timeout(int(random_delay * 1000))

                # 访问页面，使用 'domcontentloaded' 避免超时
                print(f"      Navigating to {url}...")
                response = page.goto(url, wait_until='domcontentloaded', timeout=20000)
                print(f"      Response: {response.status if response else 'None'}")

                # 等待额外内容加载
                page.wait_for_timeout(3000)

                # 处理重定向后的最终URL
                print(f"      Final URL: {page.url}")

                # 检查是否需要处理iframe
                iframes = page.query_selector_all('iframe')
                print(f"      Found {len(iframes)} iframe(s)")

                # 获取页面内容
                content = page.content()

                # 查找PDF下载链接
                pdf_links = []
                pdf_selectors = [
                    'a[href*=".pdf"]',
                    'a[href*="pdf"]',
                    'a[data-article-pdf]',
                    'button[aria-label*="PDF"]',
                    'a[aria-label*="PDF"]',
                    '[role="button"][aria-label*="view"][aria-label*="PDF"]',
                ]

                for selector in pdf_selectors:
                    try:
                        elements = page.query_selector_all(selector)
                        for elem in elements:
                            href = elem.get_attribute('href')
                            if href and not href.startswith('javascript:'):
                                pdf_links.append(href)
                                print(f"      Found PDF link: {href[:80]}")
                    except:
                        continue

                # 尝试下载找到的PDF
                for pdf_url in pdf_links:
                    try:
                        print(f"      Downloading from: {pdf_url[:80]}")
                        # 使用browser的download feature如果是绝对链接
                        if pdf_url.startswith('http'):
                            pdf_resp = requests.get(pdf_url, headers=HEADERS, timeout=30)
                        else:
                            full_url = urljoin(page.url, pdf_url)
                            pdf_resp = requests.get(full_url, headers=HEADERS, timeout=30)

                        if pdf_resp.status_code == 200 and is_valid_pdf_response(pdf_resp):
                            with open(output_path, 'wb') as f:
                                f.write(pdf_resp.content)
                            if is_valid_pdf(output_path):
                                print(f"    playwright_enhanced result: True")
                                browser.close()
                                return True
                            else:
                                os.remove(output_path)
                    except Exception as e:
                        print(f"      Download error: {str(e)[:50]}")
                        continue

                browser.close()

            except Exception as e:
                print(f"    playwright_enhanced page error: {str(e)[:80]}")
                browser.close()
                return False

    except Exception as e:
        print(f"    playwright_enhanced exception: {str(e)[:80]}")

    if os.path.exists(output_path):
        os.remove(output_path)
    print(f"    playwright_enhanced result: False")
    return False


def download_via_playwright_doi_page(doi: str, output_path: str) -> bool:
    """
    使用 Playwright 访问 DOI 页面，查找 PDF 下载链接和补充文件。
    这是最优先尝试的方法，因为可以直接从出版商页面获取。
    """
    try:
        url = f"https://doi.org/{doi}"
        print(f"    playwright_doi_page: Accessing {url}")

        with sync_playwright() as p:
            # 使用隐身模式浏览器
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            )

            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
            )

            # 添加初始化脚本隐藏自动化标记
            page = context.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        { name: 'Chrome PDF Plugin' },
                        { name: 'Chrome PDF Viewer' },
                    ],
                });
            """)

            try:
                # 访问 DOI 页面，等待内容加载
                page.goto(url, wait_until='networkidle', timeout=30000)

                # 等待任何动态内容加载
                page.wait_for_timeout(3000)

                # 处理 iframe（许多出版商在 iframe 中加载内容）
                print(f"      Checking for iframes...")
                iframes = page.query_selector_all('iframe')
                print(f"      Found {len(iframes)} iframe(s)")

                # 等待 iframe 内容加载
                for i, iframe in enumerate(iframes):
                    try:
                        frame = iframe.content_frame()
                        if frame:
                            print(f"      Waiting for iframe {i} to load...")
                            frame.wait_for_load_state('networkidle')
                    except Exception as e:
                        print(f"      iframe {i} error: {str(e)[:40]}")

                # 获取页面 HTML
                content = page.content()

                # 1. 查找 PDF 下载链接
                pdf_links = []

                # 常见的 PDF 链接选择器和属性
                pdf_selectors = [
                    'a[href*=".pdf"]',
                    'a[href*="pdf"]',
                    'a[data-article-pdf]',
                    'a[title*="PDF"]',
                    'button[aria-label*="PDF"]',
                    '[class*="pdf-link"]',
                    '[class*="download-pdf"]',
                    'a[aria-label*="PDF"]',
                    '[role="button"][aria-label*="PDF"]',
                ]

                for selector in pdf_selectors:
                    try:
                        elements = page.query_selector_all(selector)
                        for elem in elements:
                            href = elem.get_attribute('href')
                            data_url = elem.get_attribute('data-url')
                            aria_label = elem.get_attribute('aria-label')

                            if href:
                                full_url = page.evaluate(
                                    f'() => new URL("{href}", "{page.url}").href'
                                )
                                pdf_links.append(full_url)
                            elif data_url:
                                pdf_links.append(data_url)

                            print(f"      Found PDF link: {href or data_url or aria_label}")
                    except Exception as e:
                        print(f"      Selector error {selector}: {str(e)[:50]}")
                        continue

                # 2. 尝试下载找到的 PDF 链接
                for pdf_url in pdf_links:
                    try:
                        print(f"      Trying to download from: {pdf_url[:80]}")
                        pdf_resp = requests.get(pdf_url, headers=HEADERS, timeout=30)

                        if pdf_resp.status_code == 200 and is_valid_pdf_response(pdf_resp):
                            with open(output_path, 'wb') as f:
                                f.write(pdf_resp.content)

                            if is_valid_pdf(output_path):
                                print(f"    playwright_doi_page result: True")
                                browser.close()
                                return True
                            else:
                                os.remove(output_path)
                    except Exception as e:
                        print(f"      Download failed: {str(e)[:50]}")
                        continue

                # 3. 智能处理交互式元素（点击验证、加载指示器等）
                print(f"      Checking for interactive elements (verify, challenge, etc)...")
                try:
                    # 查找并处理可能的验证或"查看PDF"按钮
                    interactive_selectors = [
                        'button:has-text("Verify")',
                        'button:has-text("verify")',
                        'button:has-text("I\'m not a robot")',
                        'button:has-text("Continue")',
                        'button:has-text("View PDF")',
                        'button:has-text("Download PDF")',
                        'button:has-text("Get PDF")',
                        'a:has-text("Download PDF")',
                        '[class*="verify"]',
                        '[class*="download-btn"]',
                        '[aria-label*="Download"]',
                        '[aria-label*="View PDF"]',
                    ]

                    for selector in interactive_selectors:
                        try:
                            elem = page.query_selector(selector)
                            if elem and elem.is_visible():
                                print(f"      Found interactive element: {selector}")
                                # 确保元素在视口内
                                elem.scroll_into_view_if_needed()
                                page.wait_for_timeout(500)
                                # 点击元素
                                elem.click()
                                print(f"      Clicked: {selector}")
                                # 等待新内容加载
                                page.wait_for_timeout(3000)
                                break
                        except Exception:
                            continue
                except Exception as e:
                    print(f"      Interactive element handling error: {str(e)[:50]}")

                # 4. 如果没有找到 PDF 链接，尝试访问页面上的常见 PDF 按钮
                try:
                    # 尝试点击下载按钮
                    download_button_selectors = [
                        'button:has-text("Download")',
                        'button:has-text("PDF")',
                        '[class*="download"]',
                        'a[title*="Download"]',
                        'button[aria-label*="Download"]',
                    ]

                    for selector in download_button_selectors:
                        try:
                            button = page.query_selector(selector)
                            if button and button.is_visible():
                                print(f"      Found download button: {selector}")
                                # 点击按钮触发下载
                                button.click()
                                page.wait_for_timeout(2000)
                        except Exception:
                            continue
                except Exception as e:
                    print(f"      Button click error: {str(e)[:50]}")

                browser.close()

            except Exception as e:
                print(f"    playwright_doi_page page error: {str(e)[:80]}")
                browser.close()
                return False

    except Exception as e:
        print(f"    playwright_doi_page exception: {str(e)[:80]}")

    if os.path.exists(output_path):
        os.remove(output_path)
    print(f"    playwright_doi_page result: False")
    return False


def extract_text_from_pdf(pdf_path: str, max_pages: Optional[int] = None) -> Optional[str]:
    """
    从PDF提取纯文本。

    Args:
        pdf_path: PDF文件路径
        max_pages: 最多提取多少页（None表示全部）

    Returns:
        提取的文本，如果失败返回None
    """
    try:
        if not os.path.exists(pdf_path):
            return None

        text_content = []
        page_count = 0

        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                if max_pages and page_idx >= max_pages:
                    break

                text = page.extract_text()
                if text:
                    text_content.append(f"--- Page {page_idx + 1} ---\n{text}")
                    page_count += 1

        return "\n\n".join(text_content) if text_content else None

    except Exception as e:
        print(f"    PDF text extraction error: {e}")
        return None


def extract_supplementary_from_pdf_text(text: str) -> Dict[str, any]:
    """
    从PDF文本中搜索supplementary相关信息。

    Returns:
        包含supplementary信息的字典
    """
    supplementary_keywords = [
        'supplementary', 'supporting information', 'additional data',
        'extended data', 'appendix', 'supplemental', 'additional files',
        'supporting material', 'supplemental material', 'online resource',
        'electronic supplementary'
    ]

    result = {
        'has_supplementary': False,
        'keywords_found': [],
        'context_snippets': []
    }

    # 将文本转为小写用于搜索
    text_lower = text.lower()

    for keyword in supplementary_keywords:
        if keyword in text_lower:
            result['has_supplementary'] = True
            result['keywords_found'].append(keyword)

            # 提取关键词周围的上下文（前后各100字符）
            idx = text_lower.find(keyword)
            start = max(0, idx - 100)
            end = min(len(text), idx + len(keyword) + 100)
            context = text[start:end].replace('\n', ' ')
            result['context_snippets'].append(context)

    return result


def save_pdf_as_markdown(pdf_path: str, md_path: str, max_pages: Optional[int] = None) -> bool:
    """
    将PDF文本保存为Markdown文件。

    Args:
        pdf_path: PDF文件路径
        md_path: 输出Markdown文件路径
        max_pages: 最多保存多少页

    Returns:
        是否成功保存
    """
    try:
        text = extract_text_from_pdf(pdf_path, max_pages)
        if not text:
            return False

        # 添加元数据头部
        md_content = f"""# PDF Content

**Source:** {os.path.basename(pdf_path)}
**Extracted:** {time.strftime('%Y-%m-%d %H:%M:%S')}

---

{text}
"""

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        return True

    except Exception as e:
        print(f"    Markdown save error: {e}")
        return False


def extract_supplementary_from_pdf(pdf_path: str, doi: str) -> Tuple[bool, List[str]]:
    """
    从已下载的PDF文件中检查supplementary信息。

    Args:
        pdf_path: PDF文件路径
        doi: DOI（用于fallback）

    Returns:
        (是否找到supplementary, supplementary相关信息列表)
    """
    try:
        # 步骤1: 提取PDF文本
        print(f"    📄 Extracting text from PDF: {os.path.basename(pdf_path)}")
        text = extract_text_from_pdf(pdf_path, max_pages=5)  # 只查看前5页加快速度

        if not text:
            return False, []

        # 步骤2: 在文本中搜索supplementary关键词
        supp_info = extract_supplementary_from_pdf_text(text)

        if supp_info['has_supplementary']:
            print(f"    ✅ Found supplementary markers in PDF text:")
            for keyword in supp_info['keywords_found']:
                print(f"       - '{keyword}'")

            return True, supp_info['context_snippets']

        return False, []

    except Exception as e:
        print(f"    PDF supplementary extraction error: {e}")
        return False, []


def extract_supplementary_with_playwright(doi: str) -> List[str]:
    """
    使用 Playwright 访问 DOI 页面，查找补充文件链接。
    """
    supp_links = []

    try:
        url = f"https://doi.org/{doi}"
        print(f"  Extracting supplementary with Playwright from: {url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                ]
            )

            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            page = context.new_page()

            try:
                page.goto(url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)

                # 查找补充文件链接
                supp_keywords = [
                    'supplementary', 'supporting', 'additional', 'supplemental',
                    'esm', 'extended data', 'appendix', 'material'
                ]

                # 查找所有链接
                all_links = page.query_selector_all('a[href]')

                for link in all_links:
                    href = link.get_attribute('href')
                    text = link.inner_text().lower()

                    if href and any(kw in text for kw in supp_keywords):
                        full_url = page.evaluate(
                            f'() => new URL("{href}", "{page.url}").href'
                        )
                        supp_links.append(full_url)
                        print(f"    Found supplementary: {text[:50]}")

                browser.close()

            except Exception as e:
                print(f"  Playwright supplementary extraction error: {str(e)[:80]}")
                browser.close()

    except Exception as e:
        print(f"  Playwright supplementary exception: {str(e)[:80]}")

    return supp_links

    """Check if response content is likely a PDF, not HTML."""
    try:
        content = resp.content[:200]

        # 检查是否是 HTML（常见的失败指示符）
        html_indicators = [
            b'<html', b'<HTML', b'<!DOCTYPE', b'<head', b'<HEAD',
            b'<body', b'<BODY', b'<?xml', b'<title', b'<TITLE',
            b'Captcha', b'captcha', b'CAPTCHA', b'bot', b'Bot',
            b'challenge', b'Challenge', b'verify', b'Verify',
            b'access denied', b'Access Denied', b'403', b'404',
            b'redirect', b'Redirect', b'javascript', b'JavaScript'
        ]

        for indicator in html_indicators:
            if indicator in content:
                return False

        # 检查 PDF 魔法数字
        pdf_header = content[:4]
        return pdf_header == b'%PDF'
    except Exception:
        return False

def download_via_arxiv(doi: str, output_path: str) -> bool:
    """Try to download from arXiv if this is a preprint."""
    try:
        # Check if DOI is from arXiv (10.48550/arXiv.*)
        if "48550" not in doi and "arxiv" not in doi.lower():
            return False

        # Extract arXiv ID from DOI (format: 10.48550/arXiv.XXXX.XXXXX)
        match = re.search(r'(\d+\.\d+)', doi)
        if not match:
            return False

        arxiv_id = doi.split('/')[-1]  # Get the arXiv ID part
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        resp = requests.get(pdf_url, headers=HEADERS, timeout=30)
        if resp.status_code == 200 and is_valid_pdf_response(resp):
            with open(output_path, 'wb') as f:
                f.write(resp.content)
            if is_valid_pdf(output_path):
                print(f"    arXiv result: True")
                return True
            else:
                # 验证失败，删除文件
                os.remove(output_path)
    except Exception as e:
        print(f"    arXiv exception: {e}")

    if os.path.exists(output_path):
        os.remove(output_path)
    print(f"    arXiv result: False")
    return False

def download_via_crossref_links(doi: str, output_path: str) -> bool:
    """Fetch PDF link from CrossRef API and download it using universal downloader."""
    try:
        url = f"https://api.crossref.org/works/{doi}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return False

        data = resp.json()
        links = data.get('message', {}).get('link', [])

        for link_item in links:
            if link_item.get('content-type') == 'application/pdf':
                pdf_url = link_item.get('URL')
                if pdf_url:
                    # Use universal PDF downloader with Playwright fallback
                    return download_pdf_from_url(
                        pdf_url=pdf_url,
                        output_path=output_path,
                        source_name="crossref_links",
                        use_playwright=True
                    )

    except Exception as e:
        print(f"    crossref_links exception: {e}")

    if os.path.exists(output_path):
        os.remove(output_path)
    print(f"    crossref_links result: False")
    return False

def download_via_openalex(doi: str, output_path: str) -> bool:
    """Try to fetch OA PDF from OpenAlex API using universal downloader with Playwright fallback."""
    try:
        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        print(f"    openalex: Querying API...")

        # 为OpenAlex使用特殊headers，避免gzip压缩问题
        api_headers = HEADERS.copy()
        api_headers['Accept-Encoding'] = 'identity'  # 禁用gzip

        resp = requests.get(url, headers=api_headers, timeout=15)

        if resp.status_code != 200:
            print(f"    openalex: API error {resp.status_code}")
            return False

        # 安全地解析JSON
        try:
            data = resp.json()
        except Exception as json_err:
            print(f"    openalex: JSON parse error: {json_err}")
            return False

        oa_url = data.get('open_access', {}).get('oa_url')

        if not oa_url:
            print(f"    openalex: No OA URL found")
            return False

        print(f"      Found OA URL: {oa_url[:80]}")

        # Use universal PDF downloader with HTTP + Playwright fallback
        return download_pdf_from_url(
            pdf_url=oa_url,
            output_path=output_path,
            source_name="openalex",
            use_playwright=True
        )

    except Exception as e:
        print(f"    openalex exception: {e}")

    if os.path.exists(output_path):
        os.remove(output_path)
    print(f"    openalex result: False")
    return False

def download_via_playwright_stealth(doi: str, output_path: str) -> bool:
    """Use Playwright with stealth mode to extract real PDF from HTML wrapper."""
    try:
        with sync_playwright() as p:
            # Launch browser with stealth options
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ]
            )

            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
            )

            # 隐藏自动化检测标记
            page = context.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            context.set_extra_http_headers(HEADERS)

            # Try Sci-Hub domains
            scihub_urls = [
                "https://sci-hub.ru",
                "https://sci-hub.st",
                "http://sci-hub.ru",
                "http://sci-hub.st",
            ]

            for base_url in scihub_urls:
                try:
                    url = f"{base_url}/{doi}"
                    print(f"    playwright: Navigating to {url}")
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")

                    # Wait a bit for JavaScript to load
                    page.wait_for_timeout(2000)

                    # Method 1: Look for PDF in iframe
                    try:
                        iframe = page.query_selector("embed[type='application/pdf']")
                        if iframe:
                            pdf_src = iframe.get_attribute("src")
                            if pdf_src:
                                full_url = urljoin(url, pdf_src)
                                print(f"      Found embed src: {full_url[:80]}")
                                pdf_resp = requests.get(full_url, headers=HEADERS, timeout=30)
                                if pdf_resp.status_code == 200 and is_valid_pdf_response(pdf_resp):
                                    with open(output_path, 'wb') as f:
                                        f.write(pdf_resp.content)
                                    browser.close()
                                    print(f"    playwright ({base_url}) result: True")
                                    return True
                    except Exception as e:
                        print(f"      embed method failed: {str(e)[:50]}")

                    # Method 2: Look for iframe with PDF
                    try:
                        frames = page.query_selector_all("iframe")
                        for frame in frames:
                            src = frame.get_attribute("src")
                            if src and ('pdf' in src.lower() or '.pdf' in src):
                                full_url = urljoin(url, src)
                                print(f"      Found iframe src: {full_url[:80]}")
                                pdf_resp = requests.get(full_url, headers=HEADERS, timeout=30)
                                if pdf_resp.status_code == 200 and is_valid_pdf_response(pdf_resp):
                                    with open(output_path, 'wb') as f:
                                        f.write(pdf_resp.content)
                                    browser.close()
                                    print(f"    playwright ({base_url}) result: True")
                                    return True
                    except Exception as e:
                        print(f"      iframe method failed: {str(e)[:50]}")

                    # Method 3: Look for download button or link
                    try:
                        download_button = page.query_selector("a[href*='.pdf'], button[onclick*='pdf'], a.download")
                        if download_button:
                            href = download_button.get_attribute("href")
                            if href:
                                full_url = urljoin(url, href)
                                print(f"      Found download link: {full_url[:80]}")
                                pdf_resp = requests.get(full_url, headers=HEADERS, timeout=30)
                                if pdf_resp.status_code == 200 and is_valid_pdf_response(pdf_resp):
                                    with open(output_path, 'wb') as f:
                                        f.write(pdf_resp.content)
                                    browser.close()
                                    print(f"    playwright ({base_url}) result: True")
                                    return True
                    except Exception as e:
                        print(f"      download button method failed: {str(e)[:50]}")

                    # Method 4: Get page content and extract PDF URLs
                    try:
                        page_content = page.content()
                        soup = BeautifulSoup(page_content, 'html.parser')

                        for link in soup.find_all('a', href=True):
                            href = link.get('href', '')
                            if 'pdf' in href.lower():
                                full_url = urljoin(url, href)
                                print(f"      Found HTML link: {full_url[:80]}")
                                pdf_resp = requests.get(full_url, headers=HEADERS, timeout=30)
                                if pdf_resp.status_code == 200 and is_valid_pdf_response(pdf_resp):
                                    with open(output_path, 'wb') as f:
                                        f.write(pdf_resp.content)
                                    browser.close()
                                    print(f"    playwright ({base_url}) result: True")
                                    return True
                    except Exception as e:
                        print(f"      HTML parsing method failed: {str(e)[:50]}")

                except Exception as e:
                    print(f"    playwright ({base_url}) attempt failed: {str(e)[:80]}")
                    continue

            browser.close()
            print(f"    playwright result: False (all methods exhausted)")
            return False

    except Exception as e:
        print(f"    playwright exception: {str(e)[:100]}")
    return False

def download_pdf(doi: str, output_dir: str, title: str, year: str) -> Tuple[str, str]:
    """
    Try multiple sources to download PDF.
    Returns (status_string, final_file_path)
    """
    # First check if paper is already downloaded
    existing_file = check_paper_already_exists(output_dir, year, title, doi)
    if existing_file:
        file_size_mb = os.path.getsize(existing_file) / (1024 * 1024)
        return f"✅ Already downloaded ({file_size_mb:.1f}MB)", existing_file

    target_path = get_pdf_output_path(output_dir, year, title, doi)
    if os.path.exists(target_path):
        return "Already exists (skipped)", target_path

    temp_name = f"{doi.replace('/', '_')}.pdf"
    temp_path = os.path.join(output_dir, temp_name)

    download_funcs = [
        ("playwright_doi_page", download_via_playwright_doi_page),  # 新增：最优先尝试
        ("doi2pdf", download_via_doi2pdf),
        ("openalex", download_via_openalex),
        ("crossref_links", download_via_crossref_links),
        ("unpywall", download_via_unpywall),
        ("arxiv", download_via_arxiv),
        ("scidownl", download_via_scidownl),
        ("scihub_direct", download_via_scihub_direct),
        ("playwright_stealth", download_via_playwright_stealth),
    ]

    success = False
    method = ""
    for name, func in download_funcs:
        print(f"    Trying {name}...")
        if func(doi, temp_path):
            success = True
            method = name
            break
        time.sleep(random.uniform(0.5, 1.5))

    if success and os.path.exists(temp_path):
        os.rename(temp_path, target_path)
        file_size_mb = os.path.getsize(target_path) / (1024 * 1024)
        return f"✅ Downloaded ({method}, {file_size_mb:.1f}MB)", target_path
    else:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return "❌ Failed (all sources unavailable)", None

# ========== Supplementary materials download ==========
def find_supplementary_links_with_bs(doi: str) -> List[str]:
    """Parse paper HTML using BeautifulSoup to find supplementary material links (improved)."""
    url = f"https://doi.org/{doi}"
    try:
        # 重试机制：最多尝试 3 次
        for attempt in range(3):
            try:
                # 添加 Referer 头，防止被某些出版社拒绝
                headers = HEADERS.copy()
                headers['Referer'] = 'https://www.google.com/'

                print(f"    Attempting BeautifulSoup (attempt {attempt + 1}/3)...")
                resp = requests.get(url, headers=headers, timeout=15)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, 'html.parser')
                links = []
                keywords = ['supplementary', 'supporting information', 'additional file', 'supplemental', 'esm', 'extended data']

                # Find <a> tags containing keywords in text or href
                for a in soup.find_all('a', href=True):
                    text = a.get_text().lower()
                    href = a.get('href', '').lower()

                    # Only include links that point to actual files (PDF, ZIP, etc.)
                    if any(k in text or k in href for k in keywords):
                        # Filter out obvious non-file links
                        if any(ext in href for ext in ['.pdf', '.zip', '.xlsx', '.xls', '.docx', '.txt', '.xlsx']):
                            full_url = urljoin(url, a['href'])
                            links.append(full_url)
                        # Also include Springer/Nature ESM links even without extensions (they might redirect)
                        elif 'static-content.springer.com' in href or 'esm' in href or 'media/objects' in href.lower():
                            full_url = urljoin(url, a['href'])
                            links.append(full_url)

                # Remove duplicates
                links = list(set(links))

                if links:
                    print(f"    Found {len(links)} supplementary links")

                # Validate links by checking headers (without downloading)
                valid_links = []
                for link in links:
                    try:
                        head_resp = requests.head(link, headers=headers, timeout=10, allow_redirects=True)
                        # Only keep links that return 200 OK and have reasonable size
                        if head_resp.status_code == 200:
                            content_type = head_resp.headers.get('content-type', '').lower()
                            content_length = int(head_resp.headers.get('content-length', 0))

                            # Accept PDF, archive files, or any content with reasonable size
                            if (content_type.startswith('application/pdf') or
                                content_type.startswith('application/zip') or
                                content_type.startswith('application/x-rar') or
                                content_type.startswith('application/vnd') or
                                content_type.startswith('text/') or
                                (content_length > 1000 and content_length < 1000000000)):  # 1KB to 1GB
                                valid_links.append(link)
                                print(f"      ✓ Valid supplementary link: {link[:80]}")
                    except Exception as e:
                        print(f"      ✗ Validation failed for {link[:60]}: {str(e)[:40]}")
                        continue

                return valid_links

            except requests.exceptions.RequestException as e:
                if resp.status_code == 403:
                    print(f"    403 Forbidden - server rejected request (attempt {attempt + 1}/3)")
                    if attempt < 2:
                        # 等待后重试
                        time.sleep(random.uniform(2, 5))
                        continue
                    else:
                        print(f"    ❌ After {attempt + 1} attempts, server still returns 403")
                        print(f"    💡 建议: 这个论文可能需要使用 Playwright 浏览器来访问")
                        return []
                else:
                    raise

        return []

    except Exception as e:
        print(f"  BeautifulSoup parsing failed: {e}")
        print(f"  💡 建议: 如果是 403 错误，请使用 Playwright 浏览器访问此论文页面")
        return []

def download_supplementary_via_datahugger(doi: str, output_dir: str) -> bool:
    """Use Datahugger to download datasets/supplementary (if they have independent DOI)."""
    try:
        datahugger.get(doi, output_dir)
        # Check if any new file appeared in the directory
        return len(os.listdir(output_dir)) > 0
    except Exception as e:
        print(f"  Datahugger download failed: {e}")
        return False

def download_single_supplementary(url: str, output_path: str) -> bool:
    """Download a single supplementary file with validation and Playwright fallback."""
    try:
        # Try direct HTTP download first
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True, allow_redirects=True)

        # Check response code
        if resp.status_code != 200:
            print(f"    Initial HTTP failed {resp.status_code}, trying Playwright...")
            # Try Playwright for protected supplements
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
                    )

                    context = browser.new_context(
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    )
                    page = context.new_page()

                    try:
                        page.goto(url, wait_until='domcontentloaded', timeout=20000)
                        page.wait_for_timeout(2000)

                        # Get cookies and retry
                        cookies = context.cookies()
                        cookie_dict = {c['name']: c['value'] for c in cookies}

                        resp = requests.get(
                            url,
                            headers=HEADERS,
                            cookies=cookie_dict,
                            timeout=30,
                            stream=True,
                            allow_redirects=True
                        )

                        if resp.status_code != 200:
                            print(f"    Playwright session also failed ({resp.status_code}): {url[:60]}")
                            browser.close()
                            return False

                    except Exception as e:
                        print(f"    Playwright error: {str(e)[:50]}")
                        browser.close()
                        return False

                    finally:
                        browser.close()

            except Exception as e:
                print(f"    Playwright fallback error: {str(e)[:50]}")
                return False

        content_type = resp.headers.get('content-type', '').lower()
        content_length = int(resp.headers.get('content-length', 0))

        # Reject HTML responses (likely error pages)
        if content_type.startswith('text/html'):
            print(f"    Rejected (HTML page): {url[:60]}")
            return False

        # Reject very small files (likely error messages)
        if content_length > 0 and content_length < 100:
            print(f"    Rejected (too small {content_length}B): {url[:60]}")
            return False

        # Download the file
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Verify file was created and has content
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
            print(f"    Downloaded but invalid: {url[:60]}")
            if os.path.exists(output_path):
                os.remove(output_path)
            return False

        print(f"    ✓ Downloaded ({os.path.getsize(output_path)} bytes): {url[:60]}")
        return True

    except Exception as e:
        print(f"    Download exception: {str(e)[:50]}")
        return False

def download_supplementary_materials(doi: str, output_dir: str, title: str, year: str, pdf_path: Optional[str] = None) -> Tuple[str, List[str]]:
    """
    Download supplementary materials with improved strategy.

    Priority:
    1. Search PDF text (fast, local)
    2. Datahugger (public platform)
    3. BeautifulSoup (web scraping)
    4. Playwright (last resort, slow)

    Returns (status_string, list_of_downloaded_file_paths)
    """
    downloaded_files = []
    status = "No supplementary materials found"

    # 0. Check PDF text first (NEW - fastest and most reliable)
    if pdf_path and os.path.exists(pdf_path):
        print("  💡 Checking PDF content for supplementary information...")
        has_supp, context = extract_supplementary_from_pdf(pdf_path, doi)
        if has_supp:
            print(f"    ✅ PDF mentions supplementary materials")
            # We found indicators, but we still need to find the actual links
            # Continue with other methods to find downloadable links

    # 1. Try Datahugger (public platform)
    print("  Trying Datahugger for supplementary...")
    datahugger_dir = output_dir
    if download_supplementary_via_datahugger(doi, datahugger_dir):
        items = os.listdir(datahugger_dir)
        for item in items:
            full_path = os.path.join(datahugger_dir, item)
            if os.path.isfile(full_path) and item.endswith(('.pdf', '.zip', '.xlsx', '.xls')):
                downloaded_files.append(full_path)
        if downloaded_files:
            status = f"Success (Datahugger, {len(downloaded_files)} files)"
            return status, downloaded_files

    # 2. Use BeautifulSoup (web scraping, public access)
    print("  Trying BeautifulSoup to find supplementary links...")
    supp_links = find_supplementary_links_with_bs(doi)
    if supp_links:
        base_name = f"{year}--{sanitize_filename_custom(title)}--supplementary"
        for idx, link in enumerate(supp_links, start=1):
            # Infer extension
            ext = '.pdf'
            if '.' in link.split('/')[-1]:
                ext = '.' + link.split('/')[-1].split('.')[-1]
                if len(ext) > 5:
                    ext = '.pdf'
            if idx == 1 and len(supp_links) == 1:
                filename = f"{base_name}{ext}"
            else:
                filename = f"{base_name}_{idx}{ext}"
            filepath = os.path.join(output_dir, filename)
            if os.path.exists(filepath):
                downloaded_files.append(filepath)
                continue
            if download_single_supplementary(link, filepath):
                downloaded_files.append(filepath)
        if downloaded_files:
            status = f"Success (BeautifulSoup, {len(downloaded_files)} files)"
            return status, downloaded_files
        else:
            status = "Links found but download failed"

    # 3. Try Playwright as last resort (slow, but handles JavaScript)
    print("  Trying Playwright (last resort) to find supplementary links...")
    try:
        playwright_links = extract_supplementary_with_playwright(doi)
        if playwright_links:
            base_name = f"{year}--{sanitize_filename_custom(title)}--supplementary"
            for idx, link in enumerate(playwright_links, start=1):
                ext = '.pdf'
                if '.' in link.split('/')[-1]:
                    ext = '.' + link.split('/')[-1].split('.')[-1]
                    if len(ext) > 5:
                        ext = '.pdf'
                if idx == 1 and len(playwright_links) == 1:
                    filename = f"{base_name}{ext}"
                else:
                    filename = f"{base_name}_{idx}{ext}"
                filepath = os.path.join(output_dir, filename)
                if os.path.exists(filepath):
                    downloaded_files.append(filepath)
                    continue
                if download_single_supplementary(link, filepath):
                    downloaded_files.append(filepath)
            if downloaded_files:
                status = f"Success (Playwright, {len(downloaded_files)} files)"
                return status, downloaded_files
    except Exception as e:
        print(f"  Playwright supplementary extraction failed: {str(e)[:80]}")

    return status, downloaded_files


# ========== Main processing ==========
def process_doi_list(doi_list: List[str], output_base_dir: str = "downloaded_papers") -> pd.DataFrame:
    """
    Process a list of DOIs: download PDFs and supplementary materials.
    Returns a DataFrame with results.
    """
    os.makedirs(output_base_dir, exist_ok=True)

    # Pre-scan: Check which papers are already downloaded
    print("\n" + "=" * 70)
    print("📋 Pre-scan: Checking for already downloaded papers...")
    print("=" * 70)
    already_downloaded = []
    need_download = []

    for doi in doi_list:
        title, year = get_paper_metadata(doi)
        existing_file = check_paper_already_exists(output_base_dir, year, title, doi)
        if existing_file:
            file_size = os.path.getsize(existing_file) / (1024 * 1024)
            already_downloaded.append((doi, title, year, existing_file, file_size))
            print(f"  ✅ {doi}: {title[:50]}... ({file_size:.1f}MB)")
        else:
            need_download.append(doi)
            print(f"  📥 {doi}: {title[:50]}... (need download)")
        # Small delay to avoid rate limiting
        time.sleep(0.2)

    print("\n" + "=" * 70)
    if already_downloaded:
        print(f"📊 Summary: {len(already_downloaded)} papers already downloaded, {len(need_download)} need downloading")
    else:
        print(f"📊 Summary: All {len(need_download)} papers need downloading")
    print("=" * 70 + "\n")

    results = []

    # Process papers
    for idx, doi in enumerate(doi_list):
        print(f"\n[{idx+1}/{len(doi_list)}] Processing DOI: {doi}")

        # 1. Get metadata
        title, year = get_paper_metadata(doi)
        print(f"  Title: {title[:80]}...")
        print(f"  Year: {year}")

        # 2. Download PDF
        pdf_status, pdf_path = download_pdf(doi, output_base_dir, title, year)
        print(f"  PDF status: {pdf_status}")

        # Calculate file size if PDF was downloaded
        file_size_mb = 0.0
        md_path = None

        if pdf_path and os.path.exists(pdf_path):
            file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)

            # Generate Markdown from PDF
            pdf_base = os.path.splitext(pdf_path)[0]
            md_path = f"{pdf_base}.md"

            if not os.path.exists(md_path):
                print(f"  📝 Generating Markdown from PDF...")
                if pdf_to_markdown(pdf_path, md_path):
                    print(f"     ✅ Markdown saved: {os.path.basename(md_path)}")
                    md_size = os.path.getsize(md_path) / (1024 * 1024)
                    print(f"     📊 Markdown size: {md_size:.2f}MB")
                else:
                    print(f"     ⚠️ Markdown generation skipped")
                    md_path = None
            else:
                print(f"  📝 Markdown already exists: {os.path.basename(md_path)}")


        # 3. Download supplementary materials (pass pdf_path for text analysis)
        supp_status, supp_files = download_supplementary_materials(doi, output_base_dir, title, year, pdf_path)
        print(f"  Supplementary status: {supp_status}")

        results.append({
            "DOI": doi,
            "Title": title,
            "Year": year,
            "PDF_Status": pdf_status,
            "PDF_Path": pdf_path if pdf_path else "",
            "File_Size_MB": file_size_mb,
            "Markdown_Path": md_path if md_path else "",
            "Supplementary_Status": supp_status,
            "Supplementary_Files": "; ".join(supp_files) if supp_files else ""
        })

        # Random delay to be polite
        delay = random.uniform(*REQUEST_DELAY)
        time.sleep(delay)

    # Save report
    df = pd.DataFrame(results)
    report_path = os.path.join(output_base_dir, "download_report.csv")
    df.to_csv(report_path, index=False, encoding='utf-8-sig')
    print(f"\n✅ Processing completed! Report saved to: {report_path}")
    return df

# ========== Example usage ==========
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="论文批量下载工具 - 支持多种下载源",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：
  # 使用 doi_list.txt 文件下载
  python download_paper.py

  # 指定自定义 DOI 列表文件
  python download_paper.py --file my_dois.txt

  # 直接指定 DOI
  python download_paper.py --doi 10.1038/nphys2439 10.1103/PhysRevLett.92.185001

  # 指定输出目录
  python download_paper.py --output papers_2024

  # 结合使用
  python download_paper.py --file my_dois.txt --output downloaded_papers
        """
    )

    parser.add_argument(
        "--file",
        type=str,
        default="doi_list.txt",
        help="DOI 列表文件路径（默认：doi_list.txt）"
    )

    parser.add_argument(
        "--doi",
        nargs="+",
        help="直接指定 DOI（空格分隔），不读取文件"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="downloaded_papers",
        help="输出目录（默认：downloaded_papers）"
    )

    args = parser.parse_args()

    # 获取 DOI 列表
    dois = []

    if args.doi:
        # 直接指定 DOI
        dois = args.doi
        print(f"📝 使用命令行指定的 {len(dois)} 个 DOI")
    else:
        # 从文件读取
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if line and not line.startswith('#'):
                        dois.append(line)
            print(f"📖 从 {args.file} 读取 {len(dois)} 个 DOI")
        except FileNotFoundError:
            print(f"❌ 错误：文件 {args.file} 不存在")
            print(f"📝 请创建 {args.file} 文件，每行一个 DOI")
            sys.exit(1)
        except Exception as e:
            print(f"❌ 读取文件出错：{e}")
            sys.exit(1)

    if not dois:
        print("❌ 错误：没有找到任何 DOI")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🚀 开始批量下载论文")
    print("=" * 60)
    print(f"待下载论文数：{len(dois)}")
    print(f"输出目录：{args.output}")
    print("=" * 60 + "\n")

    df_result = process_doi_list(dois, output_base_dir=args.output)
    print("\n" + "=" * 60)
    print("📊 下载统计")
    print("=" * 60)
    print(df_result.to_string())
    print("\n✅ 所有操作完成！")