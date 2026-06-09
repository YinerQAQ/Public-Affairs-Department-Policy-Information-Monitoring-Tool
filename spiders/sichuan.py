# -*- coding: utf-8 -*-
"""
四川省级网站爬虫实现：

- ScJxtSpider   ：四川省经信厅官网
- ScKjtSpider   ：四川省科技厅官网
- ScWsjkwSpider ：四川省卫健委官网
- ScFgwSpider   ：四川发改委官网
- ScYjjSpider   ：四川省药监局官网

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
# ScJxtSpider - 四川省经信厅
# ----------------------------------------------------------------------
class ScJxtSpider(BaseSpider):
    """四川省经济和信息化厅（通知、公告公示）"""

    name = '四川省经信厅官网'
    base_url = 'https://jxt.sc.gov.cn'
    level = '省'
    fallback_urls = [
        'https://jxt.sc.gov.cn/scjxt/c104452/list.shtml',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# ScKjtSpider - 四川省科技厅
# ----------------------------------------------------------------------
class ScKjtSpider(BaseSpider):
    """四川省科学技术厅（通知、公告公示）"""

    name = '四川省科技厅官网'
    base_url = 'https://kjt.sc.gov.cn/'
    level = '省'
    fallback_urls = [
        'https://kjt.sc.gov.cn/kjt/tzgg/list.shtml',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# ScWsjkwSpider - 四川省卫健委
# ----------------------------------------------------------------------
class ScWsjkwSpider(BaseSpider):
    """四川省卫生健康委员会（政策文件、公告公示）"""

    name = '四川省卫健委官网'
    base_url = 'https://wsjkw.sc.gov.cn/'
    level = '省'
    fallback_urls = [
        'https://wsjkw.sc.gov.cn/scwsjkw/zcwj/zhengcefg.shtml',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# ScFgwSpider - 四川发改委
# ----------------------------------------------------------------------
class ScFgwSpider(BaseSpider):
    """四川省发展和改革委员会（通知公告）"""

    name = '四川发改委官网'
    base_url = 'https://fgw.sc.gov.cn/'
    level = '省'
    fallback_urls = [
        'https://fgw.sc.gov.cn/sfgw/tzgg/index.shtml',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# ScYjjSpider - 四川省药监局
# ----------------------------------------------------------------------
class ScYjjSpider(BaseSpider):
    """四川省药品监督管理局（工作通知、公示公告）"""

    name = '四川省药监局官网'
    base_url = 'https://yjj.sc.gov.cn/'
    level = '省'
    fallback_urls = [
        'https://yjj.sc.gov.cn/scyjj/gztz/list.shtml',
    ]

    def parse(self, response) -> List[dict]:
        soup = BeautifulSoup(response.text, 'lxml')
        return _generic_parse_list(soup, response.url or self.base_url)


# ----------------------------------------------------------------------
# 汇总：方便外部统一调用
# ----------------------------------------------------------------------
SICHUAN_SPIDERS = [
    ScJxtSpider,
    ScKjtSpider,
    ScWsjkwSpider,
    ScFgwSpider,
    ScYjjSpider,
]


def run_all_sichuan() -> List[dict]:
    """依次运行 5 个四川省级爬虫，单个失败不影响其他"""
    results = []
    for spider_cls in SICHUAN_SPIDERS:
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
