# -*- coding: utf-8 -*-
"""
高新通系统爬虫实现：

- GaoXinTongSpider：高新通（政策日历 → 事项列表）

实现说明：
高新通（https://www.cdhtqyfw.cn/）是基于 Vue 的 SPA，使用 hash 路由。
政策列表入口为 ``https://www.cdhtqyfw.cn/#/zct``，列表项渲染为
``.pcbc-r-list-item``。每条事项包含：
- 状态徽标 ``.p-name-txt-status`` (e.g. "申报中"、"待申报")
- 标题文本 ``.p-name-txt``
- 申报时间 ``.delay-box-time`` (e.g. "2024年09月25日 ~ 2026年09月25日")
- 标签 ``.p-info-tags-item``

由于事项详情通过 JS 路由跳转生成 ``#/policyCalendarDetail?pkid=<UUID>``，
直接从 DOM 上拿不到 href。这里采用启发式方案：
1. 优先使用 ``.pcbc-r-list-item`` 自身的 ``data-id`` / ``data-pkid`` 等属性；
2. 退化为对 (item index, title) 拼出稳定的合成 URL，保证去重。
"""

import logging
import re
import urllib.parse
from typing import List

from .base import BaseSpider


logger = logging.getLogger(__name__)


class GaoXinTongSpider(BaseSpider):
    """高新通（政策通 / 政策日历）爬虫，基于 Playwright 抓取 SPA 渲染结果。"""

    name = '高新通'
    base_url = 'https://www.cdhtqyfw.cn/'
    level = '市'
    # 政策通 hash 路由（SPA）
    list_url = 'https://www.cdhtqyfw.cn/#/zct'
    fallback_urls = [
        'https://www.cdhtqyfw.cn/#/zct',
    ]

    # 等待事项列表渲染的最大耗时（毫秒）
    LIST_RENDER_WAIT_MS = 12000

    def parse(self, response) -> List[dict]:  # noqa: D401
        """parse 仅作为接口存在；实际抓取已在 crawl 中完成。"""
        return []

    def crawl(self) -> List[dict]:
        """直接使用 Playwright 渲染 SPA 并抓取 .pcbc-r-list-item。"""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        articles: List[dict] = []
        context = self._create_stealth_context()
        page = context.new_page()
        try:
            logger.info('[%s] 访问政策通: %s', self.name, self.list_url)
            try:
                page.goto(self.list_url, timeout=self.PAGE_TIMEOUT_MS,
                          wait_until='domcontentloaded')
            except PlaywrightTimeout:
                logger.warning('[%s] 页面加载超时', self.name)

            # 等待列表项出现
            try:
                page.wait_for_selector(
                    '.pcbc-r-list-item', timeout=self.LIST_RENDER_WAIT_MS)
            except PlaywrightTimeout:
                logger.warning('[%s] 等待 .pcbc-r-list-item 超时', self.name)
            # 额外等渲染稳定
            try:
                page.wait_for_load_state('networkidle', timeout=8000)
            except PlaywrightTimeout:
                pass
            page.wait_for_timeout(2000)

            # 提取所有事项卡片
            raw_items = page.evaluate(r'''() => {
                const out = [];
                const items = document.querySelectorAll('.pcbc-r-list-item');
                for (let i = 0; i < items.length; i++) {
                    const it = items[i];
                    const status = (it.querySelector('.p-name-txt-status')?.innerText || '').trim();
                    // 标题：去掉状态前缀
                    let title = (it.querySelector('.p-name-txt')?.innerText || '').trim();
                    if (status && title.startsWith(status)) {
                        title = title.slice(status.length).trim();
                    }
                    const dateText = (it.querySelector('.delay-box-time')?.innerText || '').trim();
                    const tags = Array.from(it.querySelectorAll('.p-info-tags-item'))
                        .map(t => (t.innerText || '').trim()).filter(Boolean);
                    // 尝试读取卡片 data-* 属性作为唯一标识
                    let pkid = '';
                    for (const a of it.attributes) {
                        if (a.name.startsWith('data-') && a.value && a.value.length > 6) {
                            pkid = a.value;
                            break;
                        }
                    }
                    out.push({
                        index: i,
                        status: status,
                        title: title,
                        dateText: dateText,
                        tags: tags,
                        pkid: pkid,
                    });
                }
                return out;
            }''')

            logger.info('[%s] DOM 提取到 %d 个事项', self.name, len(raw_items))

            articles = self._normalize_raw_items(raw_items)

        except Exception as exc:  # noqa: BLE001
            logger.exception('[%s] 抓取异常: %s', self.name, exc)
        finally:
            try:
                context.close()
            except Exception:  # noqa: BLE001
                pass

        # 关键词匹配 + 去重 + 字段补齐
        results = self._normalize_articles(articles)
        logger.info('[%s] 解析得到 %d 篇文章', self.name, len(results))
        return results

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    @staticmethod
    def _to_iso_date(text: str) -> str:
        """从 '2024年09月25日 ~ 2026年09月25日' 中提取首个日期为 ISO 形式"""
        if not text:
            return ''
        m = re.search(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})', text)
        if not m:
            return text.strip()
        y, mo, d = m.groups()
        return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'

    def _normalize_raw_items(self, raw_items) -> List[dict]:
        articles: List[dict] = []
        for it in raw_items or []:
            title = (it.get('title') or '').strip()
            if not title:
                continue
            pkid = (it.get('pkid') or '').strip()
            if pkid:
                # 尝试拼成 SPA 详情 URL
                url = (
                    f'https://www.cdhtqyfw.cn/#/policyCalendarDetail'
                    f'?pkid={pkid}'
                )
            else:
                # 退化方案：用标题构造稳定的合成 URL，保证去重
                slug = urllib.parse.quote(title)
                url = f'https://www.cdhtqyfw.cn/#/zct?title={slug}'

            articles.append({
                'title': title,
                'url': url,
                'publish_date': self._to_iso_date(it.get('dateText') or ''),
            })
        return articles
