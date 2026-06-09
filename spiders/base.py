# -*- coding: utf-8 -*-
"""
爬虫基类模块（Playwright 版）

由于政府网站普遍存在 WAF 防护、JS 渲染、Cookie 校验等反爬措施，
单纯的 requests 方案无法稳定取到内容。本模块改用 Playwright 无头浏览器
作为底层抓取通道，模拟真实浏览器访问；上层 parse() 仍接收一个具有
.text / .url 属性的 Response-like 对象，从而保持现有解析逻辑不变。

提供的能力：
- 浏览器懒加载 + 整个爬虫生命周期复用
- 随机 UA / Locale / Viewport，降低指纹
- 动态发现导航链接（在 Page 对象上直接查找）
- 关键词匹配 + 文章入库 + 爬取日志
"""

import logging
import random
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import config
from database import get_db


logger = logging.getLogger(__name__)


class SimpleResponse:
    """模拟 requests.Response 的简单对象，兼容现有 parse() 实现。

    parse() 通常只用到 .text / .url / .status_code / .content / .encoding，
    本类提供这些属性即可。
    """

    def __init__(self, status_code: int, text: str, url: str):
        self.status_code = status_code
        self.text = text or ''
        self.url = url or ''
        try:
            self.content = (text or '').encode('utf-8', errors='ignore')
        except Exception:  # noqa: BLE001
            self.content = b''
        self.encoding = 'utf-8'
        self.apparent_encoding = 'utf-8'


class BaseSpider:
    """爬虫基类，所有具体网站的爬虫均应继承本类并实现 parse() 方法。"""

    # 子类需覆盖
    name: str = ''
    base_url: str = ''
    level: str = ''
    # 子类可覆盖：要爬取的列表页 URL（默认为 base_url，旧逻辑兼容）
    list_url: str = ''
    # 子类可覆盖：动态发现失败时的兜底列表页 URL 集合
    fallback_urls: List[str] = []

    # 常见浏览器 User-Agent 列表（用于浏览器上下文 user_agent 字段）
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) '
        'Gecko/20100101 Firefox/125.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
        '(KHTML, like Gecko) Version/17.4 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    ]

    # 默认页面加载超时（毫秒）
    PAGE_TIMEOUT_MS = 30000
    # 页面加载完成后额外等待时间（毫秒），等动态内容渲染
    # 增大到 5 秒以给国产 WAF（瑞数/安恒等）的 JS 挑战留出验证时间
    EXTRA_WAIT_MS = 5000

    # 页面加载完成后额外等待时间（毫秒），给 WAF JS 挑战留出计算时间
    WAF_CHALLENGE_WAIT_MS = 10000

    def __init__(self):
        self._start_time: Optional[str] = None
        self._playwright = None
        self._browser = None
        self._current_ua: Optional[str] = None
        # 关键词缓存（一次爬取生命周期内只读一次数据库），
        # None 表示尚未加载，加载后即使为空也不会重复查询。
        self._keywords_cache: Optional[List[str]] = None
        # 可选的日期范围过滤 (YYYY-MM-DD)，由调用方赋值
        self.date_from: Optional[str] = None
        self.date_to: Optional[str] = None

    # ------------------------------------------------------------------
    # 浏览器生命周期
    # ------------------------------------------------------------------
    def _get_random_ua(self) -> str:
        ua = random.choice(self.USER_AGENTS)
        self._current_ua = ua
        return ua

    def _get_browser(self):
        """获取浏览器实例（懒加载，整个爬虫生命周期复用）"""
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
                channel='chrome',  # 使用系统安装的 Chrome，获取真实 TLS 指纹
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--disable-dev-shm-usage',
                    '--disable-browser-side-navigation',
                    '--disable-gpu',
                    '--lang=zh-CN',
                ],
            )
        return self._browser

    def _new_context(self):
        """创建一个新的浏览器上下文（独立 cookies / storage）"""
        return self._create_stealth_context()

    def _create_stealth_context(self):
        """创建带反检测配置的浏览器上下文。

        注意：不注入任何 JS 脚本来修改 navigator 属性！
        瑞数等国产 WAF 的 JS 挑战会检测属性描述符是否被篡改，
        任何 Object.defineProperty 覆盖都会导致指纹异常从而生成无效 token。
        反而依赖 --disable-blink-features=AutomationControlled 启动参数
        在浏览器层面关闭 webdriver 标记即可。
        """
        browser = self._get_browser()
        context = browser.new_context(
            user_agent=self._get_random_ua(),
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            color_scheme='light',
            ignore_https_errors=True,
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;'
                          'q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", '
                             '"Not-A.Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
            },
        )
        return context

    def close(self) -> None:
        """关闭浏览器并释放资源"""
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning('[%s] 关闭浏览器异常: %s', self.name, exc)
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception as exc:  # noqa: BLE001
            logger.warning('[%s] 停止 playwright 异常: %s', self.name, exc)
        self._browser = None
        self._playwright = None

    # ------------------------------------------------------------------
    # 网络请求（基于 Playwright）
    # ------------------------------------------------------------------
    def delay(self, base_min: float = 1.0, base_max: float = 2.5) -> None:
        """随机等待，降低被反爬概率（即使用浏览器也保留合理间隔）"""
        import time as _time
        _time.sleep(random.uniform(base_min, base_max))

    def fetch(self, url: str, referer: Optional[str] = None,
              wait_for: str = 'networkidle') -> Optional[SimpleResponse]:
        """使用 Playwright 获取页面内容（带反检测）。

        :param url: 目标 URL
        :param referer: Referer 来源页（可选）
        :param wait_for: 等待策略，'networkidle' / 'load' / 'domcontentloaded'，
            或一个 CSS 选择器（出现该选择器后视为加载完成）
        :return: SimpleResponse 或 None
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        context = self._create_stealth_context()
        page = context.new_page()
        try:
            if referer:
                try:
                    page.set_extra_http_headers({'Referer': referer})
                except Exception:  # noqa: BLE001
                    pass

            wait_until = 'networkidle'
            css_selector = None
            if wait_for in ('networkidle', 'load', 'domcontentloaded'):
                wait_until = wait_for
            else:
                # 视为 CSS 选择器：先按 domcontentloaded 加载，再等选择器
                wait_until = 'domcontentloaded'
                css_selector = wait_for

            response = page.goto(url, timeout=self.PAGE_TIMEOUT_MS,
                                 wait_until=wait_until)

            if css_selector:
                try:
                    page.wait_for_selector(css_selector,
                                           timeout=self.PAGE_TIMEOUT_MS)
                except PlaywrightTimeout:
                    logger.warning('[%s] 等待选择器 %s 超时',
                                   self.name, css_selector)

            status = response.status if response is not None else 200

            # WAF JS 挑战处理：等待脚本计算并自动跳转
            if status == 412 or len(page.content()) < 500:
                logger.info('[%s] WAF JS 挑战(status=%s)，等待自动跳转...',
                            self.name, status)
                try:
                    page.wait_for_load_state(
                        'networkidle', timeout=self.WAF_CHALLENGE_WAIT_MS)
                except PlaywrightTimeout:
                    pass

            # 额外稳定等待
            page.wait_for_timeout(self.EXTRA_WAIT_MS)

            html = page.content()
            final_url = page.url

            return SimpleResponse(200 if len(html) >= 500 else status,
                                  html, final_url)

        except PlaywrightTimeout:
            logger.warning('[%s] 页面加载超时: %s', self.name, url)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning('[%s] 访问失败: %s - %s', self.name, url, exc)
            return None
        finally:
            try:
                context.close()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # 解析与关键词匹配
    # ------------------------------------------------------------------
    def parse(self, response) -> List[dict]:
        """子类实现：解析列表页，返回文章字典列表

        每个 dict 至少包含：title, url, publish_date, summary
        """
        raise NotImplementedError('子类必须实现 parse() 方法')

    def _load_keywords(self) -> List[str]:
        """加载关键词列表（数据库优先，回退 config.KEYWORDS）。

        结果会缓存到 self._keywords_cache，避免在批量匹配时反复查库。
        """
        if self._keywords_cache is not None:
            return self._keywords_cache

        keywords: List[str] = []
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='keywords'"
            )
            if cursor.fetchone():
                cursor.execute(
                    'SELECT keyword FROM keywords '
                    'WHERE keyword IS NOT NULL AND keyword != ""'
                )
                rows = cursor.fetchall()
                for row in rows:
                    kw = row[0] if not isinstance(row, dict) else row.get('keyword')
                    if kw and kw not in keywords:
                        keywords.append(kw)
            conn.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning('[%s] 从数据库读取关键词失败，回退到 config.KEYWORDS: %s',
                           self.name, exc)
            keywords = []

        if not keywords:
            for words in (config.KEYWORDS or {}).values():
                for w in (words or []):
                    if w and w not in keywords:
                        keywords.append(w)

        # 过滤空字符串
        keywords = [k for k in keywords if k and str(k).strip()]
        self._keywords_cache = keywords
        logger.info('[%s] 已加载关键词 %d 个', self.name, len(keywords))
        return keywords

    def match_keywords(self, title: str, summary: str = '') -> List[str]:
        """匹配关键词，返回命中的关键词列表（不区分大小写）。

        按用户要求，匹配仅基于文章标题；summary 参数保留是为了兼容旧调用方，
        实际不参与判定。
        """
        title = (title or '').strip()
        if not title:
            return []
        title_lower = title.lower()
        all_keywords = self._load_keywords()
        matched: List[str] = []
        for kw in all_keywords:
            if not kw:
                continue
            if kw.lower() in title_lower and kw not in matched:
                matched.append(kw)
        return matched

    # ------------------------------------------------------------------
    # 动态导航发现
    # ------------------------------------------------------------------
    def find_nav_links_on_page(self, page, button_names) -> List[dict]:
        """在已加载的 Playwright Page 上查找匹配按钮名称的导航链接。

        :param page: Playwright Page 对象（已 goto 主页）
        :param button_names: List[str]，按钮名称列表
        :return: List[dict]，每个 dict 形如 {'name': '匹配到的按钮名', 'url': '完整URL'}
        """
        links: List[dict] = []
        if not button_names:
            return links

        names = []
        for b in button_names:
            s = (b or '').strip()
            if s and s not in names:
                names.append(s)
        if not names:
            return links

        seen_urls = set()
        for btn in names:
            try:
                # has-text 用 in 方式匹配文本，'通知' 能命中 '通知公告'
                locators = page.locator(f'a:has-text("{btn}")')
                count = locators.count()
            except Exception as exc:  # noqa: BLE001
                logger.warning('[%s] 定位按钮 %s 失败: %s',
                               self.name, btn, exc)
                continue
            for i in range(count):
                try:
                    href = locators.nth(i).get_attribute('href')
                except Exception:  # noqa: BLE001
                    href = None
                if not href:
                    continue
                href = href.strip()
                if (not href
                        or href.startswith('javascript')
                        or href.startswith('#')):
                    continue
                full_url = urljoin(page.url, href)
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                links.append({'name': btn, 'url': full_url})
        return links

    def find_nav_links(self, response, button_names) -> List[dict]:
        """从 HTML 文本中查找匹配按钮名称的导航链接（兼容旧调用方）。"""
        if response is None or not button_names:
            return []
        names = []
        for b in button_names:
            s = (b or '').strip()
            if s and s not in names:
                names.append(s)
        if not names:
            return []

        try:
            soup = BeautifulSoup(response.text, 'lxml')
        except Exception:  # noqa: BLE001
            soup = BeautifulSoup(response.text, 'html.parser')

        base_for_join = getattr(response, 'url', None) or self.base_url
        results: List[dict] = []
        seen_urls = set()
        for a_tag in soup.find_all('a'):
            text = a_tag.get_text(strip=True)
            if not text:
                continue
            href = (a_tag.get('href') or '').strip()
            if not href or href.startswith('javascript') or href.startswith('#'):
                continue
            matched_name = None
            for btn in names:
                if btn in text:
                    matched_name = btn
                    break
            if not matched_name:
                continue
            full_url = urljoin(base_for_join, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            results.append({'name': matched_name, 'url': full_url})
        return results

    def get_website_config(self) -> dict:
        """读取当前爬虫对应网站的配置（数据库优先 -> config.WEBSITES）"""
        if not self.name:
            return {}

        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='websites'"
            )
            if cursor.fetchone():
                cursor.execute(
                    'SELECT * FROM websites WHERE name = ? LIMIT 1',
                    (self.name,),
                )
                row = cursor.fetchone()
                conn.close()
                if row:
                    d = dict(row)
                    raw_btns = d.get('buttons') or ''
                    d['buttons'] = [
                        b.strip()
                        for b in str(raw_btns).replace('，', ',').split(',')
                        if b.strip()
                    ]
                    return d
            else:
                conn.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning('[%s] 读取数据库网站配置失败: %s', self.name, exc)

        for site in getattr(config, 'WEBSITES', []) or []:
            if site.get('name') == self.name:
                d = dict(site)
                btns = d.get('buttons', [])
                if isinstance(btns, str):
                    d['buttons'] = [
                        b.strip()
                        for b in btns.replace('，', ',').split(',')
                        if b.strip()
                    ]
                else:
                    d['buttons'] = list(btns or [])
                return d
        return {}

    # ------------------------------------------------------------------
    # 主流程（基于 Playwright）
    # ------------------------------------------------------------------
    def _in_date_range(self, publish_date: str) -> bool:
        """判断 publish_date 是否在 self.date_from / self.date_to 范围内。

        没有设置任何范围时返回 True；文章未提供日期时为避免误杀保留。"""
        if not (self.date_from or self.date_to):
            return True
        date_str = (publish_date or '').strip()
        if not date_str:
            return True
        # 只取前 10 位作为 YYYY-MM-DD 比较
        date_str = date_str[:10]
        if self.date_from and date_str < self.date_from:
            return False
        if self.date_to and date_str > self.date_to:
            return False
        return True

    def _normalize_articles(self, raw_articles: List[dict]) -> List[dict]:
        """对 parse() 返回的原始结果做去重 + 关键词过滤 + 字段补齐。

        严格过滤：只有标题命中至少一个关键词的文章才会被保留并最终入库。
        """
        results: List[dict] = []
        seen_urls = set()
        total_raw = 0
        dropped_no_kw = 0
        dropped_date = 0
        for art in raw_articles or []:
            total_raw += 1
            title = (art.get('title') or '').strip()
            url = (art.get('url') or '').strip()
            if not title or not url:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            matched = self.match_keywords(title)
            if not matched:
                # 关键词未命中：直接丢弃，不入库
                dropped_no_kw += 1
                continue

            summary = (art.get('summary') or '').strip()
            publish_date = (art.get('publish_date') or '').strip()

            # 日期范围过滤
            if not self._in_date_range(publish_date):
                dropped_date += 1
                continue

            results.append({
                'title': title,
                'url': url,
                'source_name': self.name,
                'source_url': self.base_url,
                'publish_date': publish_date,
                'summary': summary,
                'matched_keywords': matched,
                'level': self.level,
            })
        logger.info(
            '[%s] 关键词过滤: 原始 %d 篇 -> 命中 %d 篇，无关键词丢弃 %d 篇，日期越界丢弃 %d 篇',
            self.name, total_raw, len(results), dropped_no_kw, dropped_date,
        )
        return results

    def _goto_and_parse(self, page, url: str) -> List[dict]:
        """在已有 Page 上访问 URL 并调用 parse()，自动处理 WAF JS 挑战。"""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        try:
            response = page.goto(url, timeout=self.PAGE_TIMEOUT_MS,
                                 wait_until='domcontentloaded')
            status = response.status if response is not None else 200

            # WAF JS 挑战处理：412 表示需要等待 JS 计算 token 并自动跳转
            if status == 412 or len(page.content()) < 500:
                logger.info('[%s] WAF JS 挑战页(status=%s)，等待自动跳转...',
                            self.name, status)
                try:
                    # 等待 JS 挑战脚本加载并执行完毕，页面会自动重新请求
                    page.wait_for_load_state('networkidle',
                                            timeout=self.WAF_CHALLENGE_WAIT_MS)
                except PlaywrightTimeout:
                    pass  # 超时也继续尝试解析

            # 额外稳定等待
            page.wait_for_timeout(self.EXTRA_WAIT_MS)
            html = page.content()

            resp = SimpleResponse(200 if len(html) >= 500 else status, html, page.url)
            return self.parse(resp) or []
        except PlaywrightTimeout:
            logger.warning('[%s] 访问超时: %s', self.name, url)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning('[%s] 访问/解析异常 %s: %s', self.name, url, exc)
            return []

    def _crawl_fallback_urls(self, context) -> List[dict]:
        """使用 fallback URLs 在给定 context 内逐个抓取。"""
        articles: List[dict] = []
        urls = list(self.fallback_urls or [])
        if not urls:
            fb = self.list_url or self.base_url
            if fb:
                urls = [fb]
        if not urls:
            return articles

        page = context.new_page()
        try:
            for url in urls:
                logger.info('[%s] Fallback 抓取: %s', self.name, url)
                articles.extend(self._goto_and_parse(page, url))
                self.delay()
        finally:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass
        return articles

    def crawl(self) -> List[dict]:
        """使用 Playwright 的完整爬取流程：

        1. 访问主页 -> 等待加载
        2. 在主页上按 buttons 配置查找导航链接
        3. 找到则逐个进入栏目页解析；未找到 / 主页失败 -> fallback URLs
        4. 关键词匹配 + 去重 + 字段补齐
        """
        all_articles: List[dict] = []
        cfg = self.get_website_config() or {}
        buttons = cfg.get('buttons') or []

        context = self._create_stealth_context()
        page = context.new_page()
        try:
            # 1. 访问主页
            home_ok = False
            if self.base_url:
                logger.info('[%s] 访问主页: %s', self.name, self.base_url)
                try:
                    response = page.goto(self.base_url,
                                         timeout=self.PAGE_TIMEOUT_MS,
                                         wait_until='domcontentloaded')
                    status = response.status if response else 0

                    # WAF JS 挑战处理：等待脚本计算并自动跳转
                    if status == 412 or len(page.content()) < 500:
                        logger.info('[%s] WAF JS 挑战(status=%s)，等待自动跳转...',
                                    self.name, status)
                        try:
                            page.wait_for_load_state(
                                'networkidle',
                                timeout=self.WAF_CHALLENGE_WAIT_MS)
                        except Exception:  # noqa: BLE001
                            pass

                    page.wait_for_timeout(self.EXTRA_WAIT_MS)
                    html_len = len(page.content())
                    if html_len >= 500:
                        home_ok = True
                    else:
                        logger.warning('[%s] 主页访问失败: status=%s, len=%d',
                                       self.name, status, html_len)
                except Exception as exc:  # noqa: BLE001
                    logger.warning('[%s] 主页访问异常: %s', self.name, exc)

            # 2. 主页上动态发现导航链接
            nav_links: List[dict] = []
            if home_ok and buttons:
                try:
                    nav_links = self.find_nav_links_on_page(page, buttons)
                except Exception as exc:  # noqa: BLE001
                    logger.warning('[%s] 解析导航链接异常: %s', self.name, exc)
                logger.info('[%s] 动态发现 %d 个栏目链接',
                            self.name, len(nav_links))

            # 3. 逐个进入栏目页
            if nav_links:
                for link in nav_links:
                    link_url = (link or {}).get('url')
                    if not link_url:
                        continue
                    logger.info('[%s] 进入栏目: %s -> %s',
                                self.name, link.get('name'), link_url)
                    all_articles.extend(self._goto_and_parse(page, link_url))
                    self.delay()
            else:
                # 4. 没找到 / 主页失败 -> fallback
                all_articles = self._crawl_fallback_urls(context)

            # 若导航链接全部失败但还没走过 fallback，再 fallback 一次
            if not all_articles and nav_links:
                logger.info('[%s] 栏目页未取到内容，回退到 fallback URLs',
                            self.name)
                all_articles = self._crawl_fallback_urls(context)

        except Exception as exc:  # noqa: BLE001
            logger.exception('[%s] 爬取异常: %s', self.name, exc)
            if not all_articles:
                try:
                    all_articles = self._crawl_fallback_urls(context)
                except Exception:  # noqa: BLE001
                    pass
        finally:
            try:
                context.close()
            except Exception:  # noqa: BLE001
                pass

        # 5. 标准化
        results = self._normalize_articles(all_articles)
        logger.info('[%s] 解析得到 %d 篇文章', self.name, len(results))
        return results

    # ------------------------------------------------------------------
    # 数据落库 / 日志
    # ------------------------------------------------------------------
    def save_results(self, articles: List[dict]) -> int:
        """将文章批量写入数据库，跳过已存在的 URL，返回新增条数。

        判重策略：
        - 同 URL 已存在 -> 跳过
        - 同 标题 + 来源网站 + 发布日期 已存在 -> 跳过（避免同一篇文章因
          不同页面或 URL 带参重复入库）
        """
        # 二次防护：确保只保存匹配了关键词的文章
        articles = [a for a in (articles or []) if a.get('matched_keywords')]
        if not articles:
            return 0
        conn = get_db()
        cursor = conn.cursor()
        inserted = 0
        crawl_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            for art in articles:
                # 1) URL 去重
                cursor.execute(
                    'SELECT 1 FROM articles WHERE url = ? LIMIT 1',
                    (art['url'],),
                )
                if cursor.fetchone():
                    continue
                # 2) 标题 + 来源 + 发布日期 去重
                title_for_dup = (art.get('title') or '').strip()
                source_for_dup = (art.get('source_name') or self.name or '').strip()
                pub_for_dup = (art.get('publish_date') or '').strip()
                if title_for_dup and source_for_dup:
                    if pub_for_dup:
                        cursor.execute(
                            'SELECT 1 FROM articles WHERE title = ? AND source_name = ? '
                            'AND publish_date = ? LIMIT 1',
                            (title_for_dup, source_for_dup, pub_for_dup),
                        )
                    else:
                        cursor.execute(
                            'SELECT 1 FROM articles WHERE title = ? AND source_name = ? LIMIT 1',
                            (title_for_dup, source_for_dup),
                        )
                    if cursor.fetchone():
                        continue
                matched_kw = art.get('matched_keywords') or []
                if isinstance(matched_kw, list):
                    matched_kw_str = ','.join(matched_kw)
                else:
                    matched_kw_str = str(matched_kw)
                cursor.execute(
                    '''INSERT INTO articles
                       (title, url, source_name, source_url, publish_date,
                        summary, matched_keywords, crawl_time, level)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        art.get('title', ''),
                        art.get('url', ''),
                        art.get('source_name', self.name),
                        art.get('source_url', self.base_url),
                        art.get('publish_date', ''),
                        art.get('summary', ''),
                        matched_kw_str,
                        crawl_time,
                        art.get('level', self.level),
                    ),
                )
                inserted += 1
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            logger.exception('[%s] 保存文章失败: %s', self.name, exc)
        finally:
            conn.close()
        logger.info('[%s] 新增入库 %d 篇', self.name, inserted)
        return inserted

    def log_crawl(self, status: str, article_count: int,
                  error_msg: Optional[str] = None) -> None:
        """记录一次爬取的日志到 crawl_logs 表"""
        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        start_time = self._start_time or end_time
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO crawl_logs
                   (website_name, start_time, end_time, status,
                    article_count, error_message)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (self.name, start_time, end_time, status,
                 article_count, error_msg),
            )
            conn.commit()
            conn.close()
        except Exception as exc:  # noqa: BLE001
            logger.exception('[%s] 写入日志失败: %s', self.name, exc)

    def run(self) -> dict:
        """完整运行流程：crawl -> save_results -> log_crawl，最后释放浏览器"""
        self._start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        result = {
            'name': self.name,
            'total': 0,
            'inserted': 0,
            'status': 'success',
            'error': None,
        }
        try:
            articles = self.crawl()
            result['total'] = len(articles)
            inserted = self.save_results(articles)
            result['inserted'] = inserted
            self.log_crawl('success', inserted)
        except Exception as exc:  # noqa: BLE001
            err = f'{type(exc).__name__}: {exc}'
            logger.exception('[%s] 运行失败: %s', self.name, err)
            result['status'] = 'failed'
            result['error'] = err
            self.log_crawl('failed', 0, error_msg=err)
        finally:
            self.close()
        return result
