"""使用 Playwright 渲染 docs/ 下所有 Markdown 中的 Mermaid 代码块为 PNG 图片。

输出目录: docs/images/
依赖: 项目 python/ 嵌入式环境内已安装 playwright 与 bundled chromium

运行方式（项目根目录下）：
    set PLAYWRIGHT_BROWSERS_PATH=0
    python\\python.exe docs\\generate_png.py
"""
import os
import re
import sys
import json

# 让脚本可独立运行，无论 cwd 在哪
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 强制使用 bundled 浏览器
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

from playwright.sync_api import sync_playwright  # noqa: E402

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
PNG_DIR = os.path.join(DOCS_DIR, "images")
os.makedirs(PNG_DIR, exist_ok=True)

# Mermaid CDN（如内网无法访问可改为本地文件路径）
MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"


def extract_mermaid_blocks(md_file):
    """从 markdown 文件提取 mermaid 代码块。"""
    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = r"```mermaid\s*\n(.*?)```"
    return re.findall(pattern, content, re.DOTALL)


def build_html(mermaid_code: str) -> str:
    """构造一个仅包含 mermaid 图的最小 HTML 页面。"""
    safe_code = json.dumps(mermaid_code)  # 安全转义，作为 JS 字符串注入
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>mermaid render</title>
<style>
  body {{
    margin: 0;
    padding: 24px;
    background: #ffffff;
    font-family: "Microsoft YaHei", "PingFang SC", -apple-system, sans-serif;
  }}
  #target {{ display: inline-block; }}
  #target svg {{ max-width: none !important; }}
</style>
<script src="{MERMAID_CDN}"></script>
</head>
<body>
<div id="target"></div>
<script>
  const code = {safe_code};
  window.__rendered__ = false;
  document.addEventListener('DOMContentLoaded', async () => {{
    try {{
      mermaid.initialize({{
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'loose',
        flowchart: {{ htmlLabels: true, curve: 'basis' }}
      }});
      const {{ svg }} = await mermaid.render('rendered', code);
      document.getElementById('target').innerHTML = svg;
      window.__rendered__ = true;
    }} catch (e) {{
      document.body.innerHTML = '<pre style="color:red">' + e.message + '</pre>';
      window.__rendered__ = 'error';
    }}
  }});
</script>
</body>
</html>"""


def render_one(page, mermaid_code: str, output_path: str) -> bool:
    """渲染单个 mermaid 图为 PNG，成功返回 True。"""
    html = build_html(mermaid_code)
    page.set_content(html, wait_until="load")
    # 等待 mermaid 渲染完成
    try:
        page.wait_for_function(
            "window.__rendered__ === true || window.__rendered__ === 'error'",
            timeout=30000,
        )
    except Exception as e:
        print(f"  [超时] {e}")
        return False

    status = page.evaluate("window.__rendered__")
    if status != True:  # noqa: E712
        msg = page.evaluate("document.body.innerText")
        print(f"  [渲染失败] {msg[:200]}")
        return False

    # 读取 SVG 实际尺寸，设置 viewport 和容器尺寸，确保截图可见
    size = page.evaluate(
        """() => {
            const svg = document.querySelector('#target svg');
            if (!svg) return null;
            const bb = svg.getBBox();
            // 给 svg 设定显式宽高，避免 inline-block 0尺寸问题
            const w = Math.ceil(bb.width + bb.x + 40);
            const h = Math.ceil(bb.height + bb.y + 40);
            svg.setAttribute('width', w);
            svg.setAttribute('height', h);
            svg.style.maxWidth = 'none';
            return { w: w + 48, h: h + 48 };
        }"""
    )
    if not size:
        debug_html = page.evaluate("document.body.innerHTML.substring(0, 500)")
        print(f"  [找不到 SVG] body: {debug_html}")
        return False

    w = max(int(size["w"]), 600)
    h = max(int(size["h"]), 400)
    # 上限保护，避免极端尺寸导致截图失败
    w = min(w, 6000)
    h = min(h, 8000)
    page.set_viewport_size({"width": w, "height": h})
    page.wait_for_timeout(200)

    page.screenshot(path=output_path, full_page=True, omit_background=False)
    return True


def main():
    md_files = sorted(
        f for f in os.listdir(DOCS_DIR)
        if f.endswith(".md") and not f.startswith("_")
    )
    if not md_files:
        print("docs/ 下未找到任何 .md 文件")
        return

    print(f"待处理 Markdown 文件: {md_files}")
    print(f"PNG 输出目录: {PNG_DIR}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2,  # 2倍清晰度
        )

        total, ok = 0, 0
        for md_file in md_files:
            blocks = extract_mermaid_blocks(os.path.join(DOCS_DIR, md_file))
            if not blocks:
                continue
            stem = os.path.splitext(md_file)[0]
            print(f"=== {md_file} 共 {len(blocks)} 个图 ===")
            for i, block in enumerate(blocks, 1):
                total += 1
                png_name = f"{stem}_{i}.png" if len(blocks) > 1 else f"{stem}.png"
                out_path = os.path.join(PNG_DIR, png_name)
                print(f"  [{i}/{len(blocks)}] 渲染 -> {png_name}")
                # 每次新建 page，避免全局状态污染
                page = context.new_page()
                try:
                    if render_one(page, block, out_path):
                        ok += 1
                        print(f"        OK  {os.path.getsize(out_path)//1024} KB")
                    else:
                        print(f"        FAIL")
                finally:
                    page.close()

        browser.close()
    print(f"\n完成: {ok}/{total} 张 PNG 已生成于 {PNG_DIR}")


if __name__ == "__main__":
    main()
