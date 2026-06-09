# -*- coding: utf-8 -*-
"""
定时任务调度模块 - 使用 APScheduler 周期性触发爬取
"""

import importlib
import inspect
import pkgutil
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from config import CRAWL_INTERVAL
from database import get_db, get_websites


_scheduler = None
_lock = threading.Lock()


def _iter_spider_classes():
    """遍历 spiders 包下的所有爬虫类。

    约定：
      - 类名以 'Spider' 结尾（区分于基类 BaseSpider/Spider 本身）
      - 拥有 run() 方法
    """
    try:
        import spiders  # type: ignore
    except Exception as exc:  # noqa: BLE001
        print(f'[scheduler] 加载 spiders 包失败: {exc}')
        return

    if not hasattr(spiders, '__path__'):
        return

    seen = set()
    for _, modname, _ in pkgutil.iter_modules(spiders.__path__):
        full_name = f'spiders.{modname}'
        try:
            module = importlib.import_module(full_name)
        except Exception as exc:  # noqa: BLE001
            print(f'[scheduler] 导入 {full_name} 失败: {exc}')
            continue

        for attr_name, attr in inspect.getmembers(module, inspect.isclass):
            if attr.__module__ != full_name:
                continue
            if not attr_name.endswith('Spider'):
                continue
            if attr_name in ('BaseSpider', 'Spider'):
                continue
            if attr in seen:
                continue
            if not hasattr(attr, 'run'):
                continue
            seen.add(attr)
            yield attr


def _log_crawl(website_name, status, start_time, article_count=0, error_message=''):
    """写入 crawl_logs"""
    try:
        conn = get_db()
        conn.execute(
            'INSERT INTO crawl_logs (website_name, start_time, end_time, status, '
            'article_count, error_message) VALUES (?, ?, ?, ?, ?, ?)',
            (
                website_name,
                start_time,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                status,
                article_count,
                error_message,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:  # noqa: BLE001
        print(f'[scheduler] 写入日志失败: {exc}')


def run_crawl_job(website_name=None):
    """执行一次爬取。website_name 为 None 时爬取所有网站。

    爬虫类需要符合 spiders 模块的命名约定。如果暂时没有任何爬虫，
    此函数将仅记录一条日志，便于调度器与 UI 联调。
    """
    target_label = website_name or 'ALL'
    print(f'[scheduler] 开始执行爬取任务: {target_label}')

    spiders_found = list(_iter_spider_classes())

    if not spiders_found:
        # 爬虫尚未实现也允许调度器运行，记录占位日志
        print('[scheduler] 未发现任何爬虫类，跳过本次执行')
        _log_crawl(
            website_name=website_name or 'ALL',
            status='skipped',
            start_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            error_message='no spiders registered',
        )
        return

    # 数据库中的网站，用于根据 website_name 过滤
    db_sites = {s['name']: s for s in get_websites()}

    for spider_cls in spiders_found:
        # 通过爬虫类的 name/website_name 属性匹配（如果设置了）
        spider_target = (
            getattr(spider_cls, 'website_name', None)
            or getattr(spider_cls, 'name', None)
        )
        if website_name and spider_target and spider_target != website_name:
            continue

        start = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            spider = spider_cls()
            result = spider.run()
            count = 0
            if isinstance(result, int):
                count = result
            elif isinstance(result, (list, tuple)):
                count = len(result)
            _log_crawl(
                website_name=spider_target or spider_cls.__name__,
                status='success',
                start_time=start,
                article_count=count,
            )
            print(f'[scheduler] {spider_cls.__name__} 执行完成，新增 {count} 条')
        except Exception as exc:  # noqa: BLE001
            _log_crawl(
                website_name=spider_target or spider_cls.__name__,
                status='error',
                start_time=start,
                error_message=str(exc),
            )
            print(f'[scheduler] {spider_cls.__name__} 执行失败: {exc}')


def start_scheduler(app=None):
    """启动后台定时调度。重复调用会被忽略。"""
    global _scheduler
    with _lock:
        if _scheduler is not None and _scheduler.running:
            return _scheduler

        scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
        scheduler.add_job(
            run_crawl_job,
            trigger='interval',
            hours=CRAWL_INTERVAL,
            id='crawl_all_sites',
            replace_existing=True,
            next_run_time=None,  # 启动时不立刻执行
        )
        scheduler.start()
        _scheduler = scheduler
        print(f'[scheduler] 定时任务已启动，每 {CRAWL_INTERVAL} 小时执行一次')
    return _scheduler


def stop_scheduler():
    global _scheduler
    with _lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            _scheduler = None
