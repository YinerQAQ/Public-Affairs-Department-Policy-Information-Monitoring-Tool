# -*- coding: utf-8 -*-
"""
成都市级网站爬虫实现：

- CdJxSpider  ：成都市经信局官网
- CdStSpider  ：成都市科技局官网
- CdWjwSpider ：成都市卫健委官网
- CdDrcSpider ：成都市发改委官网
- CdHtSpider  ：成都市高新区管委会

注意：政府网站的实际 URL 结构会随着改版而变化。下面每个爬虫
中给出的列表页 URL 均为最常见、最合理的猜测；parse() 方法
复用 national.py 中的 _generic_parse_list，对常见的 ul>li、
table 结构都做了兼容处理，并对解析失败做了保护，单个网站异常
不会影响整体调度。
"""

import logging
from typing import List

from bs4 import BeautifulSoup

from .base import BaseSpider
from .national import _generic_parse_list


logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# CdJxSpider - 成都市经信局
# ----------------------------------------------------------------------
class CdJxSpider(BaseSpider):
    """成都市经济和信息化局（通知公告、双公示）"""

    name = '成都市经信局官网'
    base_url = 'https://cdjx.chengdu.gov.cn/'
    level = '市'
    fallback_urls = [
        'https://cdjx.chengdu.gov.cn/cdjxj/c132333/list.shtml',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# CdStSpider - 成都市科技局
# ----------------------------------------------------------------------
class CdStSpider(BaseSpider):
    """成都市科学技术局（通知公告）"""

    name = '成都市科技局官网'
    base_url = 'https://cdst.chengdu.gov.cn/cdskxjsj/index.shtml'
    level = '市'
    fallback_urls = [
        'https://cdst.chengdu.gov.cn/cdkjj/c132333/list.shtml',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# CdWjwSpider - 成都市卫健委
# ----------------------------------------------------------------------
class CdWjwSpider(BaseSpider):
    """成都市卫生健康委员会（通知公告）"""

    name = '成都市卫健委官网'
    base_url = 'https://cdwjw.chengdu.gov.cn/'
    level = '市'
    fallback_urls = [
        'https://cdwjw.chengdu.gov.cn/cdwjw/c132333/list.shtml',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# CdDrcSpider - 成都市发改委
# ----------------------------------------------------------------------
class CdDrcSpider(BaseSpider):
    """成都市发展和改革委员会（公告公示）"""

    name = '成都市发改委官网'
    base_url = 'https://cddrc.chengdu.gov.cn/'
    level = '市'
    # 实际站点路径前缀为 /cdsfzggw/，主页导航顶层只有
    # 政务公开 / 发改工作 / 发展改革动态 等，没有直接的 “通知公告”，
    # 通知公告/政策文件/公示公告 等内容均位于政务公开下的二级栏目。
    fallback_urls = [
        # 公示公告（最常见的通知/公告聚合页）
        'https://cddrc.chengdu.gov.cn/cdsfzggw/gsgg/GkmlList.shtml?classId=1580486716740964354',
        # 部门文件（政策文件）
        'https://cddrc.chengdu.gov.cn/cdsfzggw/bmwj/DepartmentalDocumentsNew.shtml',
        # 发展改革动态（新闻动态）
        'https://cddrc.chengdu.gov.cn/cdsfzggw/fzggdt/list_mainInfo.shtml',
        # 政策解读
        'https://cddrc.chengdu.gov.cn/cdsfzggw/zcjd1/PolicyList.shtml',
        # 政务公开汇总页（兜底）
        'https://cddrc.chengdu.gov.cn/cdsfzggw/zwgk/publiccolumn.shtml',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# CdHtSpider - 成都市高新区管委会
# ----------------------------------------------------------------------
class CdHtSpider(BaseSpider):
    """成都市高新区管理委员会（产业政策、通知公告）"""

    name = '成都市高新区管委会'
    base_url = 'https://www.cdht.gov.cn/cdht/shouye/sy.shtml'
    level = '市'
    fallback_urls = [
        'https://www.cdht.gov.cn/cdht/c132333/list.shtml',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# 汇总：方便外部统一调用
# ----------------------------------------------------------------------
CHENGDU_SPIDERS = [
    CdJxSpider,
    CdStSpider,
    CdWjwSpider,
    CdDrcSpider,
    CdHtSpider,
]


def run_all_chengdu() -> List[dict]:
    """依次运行 5 个成都市级爬虫，单个失败不影响其他"""
    results = []
    for spider_cls in CHENGDU_SPIDERS:
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
