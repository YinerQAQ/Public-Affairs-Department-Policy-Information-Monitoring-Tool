# -*- coding: utf-8 -*-
"""
国家级网站爬虫实现：

- MostSpider：国家科技管理信息系统
- MiitSpider：国家工信部官网
- NhcSpider ：国家卫健委官网
- NdrcSpider：国家发改委官网

注意：政府网站的实际 URL 结构会随着改版而变化。下面每个爬虫
中给出的列表页 URL 均为最常见、最合理的猜测；parse() 方法
对常见的 ul>li、table 结构都做了兼容处理，并对解析失败做了
保护，单个网站异常不会影响整体调度。
"""

import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseSpider


logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# 通用工具
# ----------------------------------------------------------------------
DATE_RE = re.compile(
    r'(\d{4}[-./年]\s*\d{1,2}[-./月]\s*\d{1,2}日?)'
)


def _extract_date(text: str) -> str:
    """从文本中提取常见格式的日期字符串"""
    if not text:
        return ''
    m = DATE_RE.search(text)
    if not m:
        return ''
    raw = m.group(1)
    # 统一转成 YYYY-MM-DD
    raw = raw.replace('年', '-').replace('月', '-').replace('日', '')
    raw = raw.replace('.', '-').replace('/', '-')
    parts = [p for p in raw.split('-') if p.strip()]
    if len(parts) >= 3:
        try:
            y, m_, d = parts[0], parts[1], parts[2]
            return f'{int(y):04d}-{int(m_):02d}-{int(d):02d}'
        except ValueError:
            return raw.strip()
    return raw.strip()


def _generic_parse_list(soup: BeautifulSoup, base_url: str,
                        link_keywords: Optional[List[str]] = None
                        ) -> List[dict]:
    """通用列表页解析：扫描 a 标签，结合周边文本提取标题/日期。

    适用于政府站点常见的 ul>li>a + 日期、或 table>tr>td>a + td(日期) 结构。

    :param soup: BeautifulSoup 对象
    :param base_url: 用于拼接相对链接的基础 URL
    :param link_keywords: 仅保留链接 href/文本中包含任一关键词的行（可选过滤）
    """
    articles: List[dict] = []
    seen_urls = set()

    # 优先扫描 li 与 tr，定位"标题 + 日期"的常见结构
    candidates = soup.find_all(['li', 'tr'])
    for node in candidates:
        a_tag = node.find('a')
        if not a_tag:
            continue
        href = a_tag.get('href', '').strip()
        title = a_tag.get('title', '').strip() or a_tag.get_text(strip=True)
        if not href or not title:
            continue
        # 过滤 javascript:、锚点
        if href.startswith('javascript') or href.startswith('#'):
            continue
        # 文本类型链接（粗略过滤掉非内容链接）
        if len(title) < 4:
            continue
        full_url = urljoin(base_url, href)
        if full_url in seen_urls:
            continue
        # 关键词过滤（如果调用方提供）
        if link_keywords:
            haystack = f'{href} {title}'
            if not any(k in haystack for k in link_keywords):
                # 不强制过滤，但记录命中情况；这里仍然保留
                pass

        # 从节点整体文本中提取日期
        node_text = node.get_text(' ', strip=True)
        publish_date = _extract_date(node_text)

        articles.append({
            'title': title,
            'url': full_url,
            'publish_date': publish_date,
            'summary': '',
        })
        seen_urls.add(full_url)

    # 如果上面的扫描结果太少，回退到所有 a 标签
    if len(articles) < 3:
        for a_tag in soup.find_all('a'):
            href = a_tag.get('href', '').strip()
            title = a_tag.get('title', '').strip() or a_tag.get_text(strip=True)
            if not href or not title or len(title) < 6:
                continue
            if href.startswith('javascript') or href.startswith('#'):
                continue
            full_url = urljoin(base_url, href)
            if full_url in seen_urls:
                continue
            articles.append({
                'title': title,
                'url': full_url,
                'publish_date': '',
                'summary': '',
            })
            seen_urls.add(full_url)

    return articles


# ----------------------------------------------------------------------
# MostSpider - 国家科技管理信息系统
# ----------------------------------------------------------------------
class MostSpider(BaseSpider):
    """国家科技管理信息系统（公开公示、项目申报）"""

    name = '国家科技管理信息系统'
    base_url = 'https://service.most.gov.cn'
    level = '国家'
    # 动态发现失败时使用的兜底列表页
    fallback_urls = [
        'https://service.most.gov.cn/2015tztg/tztg/index.html',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# MiitSpider - 国家工信部
# ----------------------------------------------------------------------
class MiitSpider(BaseSpider):
    """国家工信部（最新政策）"""

    name = '国家工信部官网'
    base_url = 'https://wap.miit.gov.cn/'
    level = '国家'
    fallback_urls = [
        'https://wap.miit.gov.cn/zwgk/zcwj/index.html',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# NhcSpider - 国家卫健委
# ----------------------------------------------------------------------
class NhcSpider(BaseSpider):
    """国家卫健委（政策解读）"""

    name = '国家卫健委官网'
    base_url = 'https://www.nhc.gov.cn/'
    level = '国家'
    fallback_urls = [
        'http://www.nhc.gov.cn/wjw/zcjd/zcjdlist.shtml',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# NdrcSpider - 国家发改委
# ----------------------------------------------------------------------
class NdrcSpider(BaseSpider):
    """国家发改委（通知公告）"""

    name = '国家发改委官网'
    base_url = 'https://www.ndrc.gov.cn/'
    level = '国家'
    fallback_urls = [
        'https://www.ndrc.gov.cn/xxgk/zcfb/tz/index.html',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# 汇总：方便外部统一调用
# ----------------------------------------------------------------------
NATIONAL_SPIDERS = [MostSpider, MiitSpider, NhcSpider, NdrcSpider]


def run_all_national() -> List[dict]:
    """依次运行 4 个国家级爬虫，单个失败不影响其他"""
    results = []
    for spider_cls in NATIONAL_SPIDERS:
        try:
            spider = spider_cls()
            results.append(spider.run())
        except Exception as exc:  # noqa: BLE001
            logger.exception('运行 %s 失败: %s', spider_cls.__name__, exc)
            results.append({
                'name': spider_cls.__name__,
                'total': 0,
                'inserted': 0,
                'status': 'failed',
                'error': str(exc),
            })
    return results
