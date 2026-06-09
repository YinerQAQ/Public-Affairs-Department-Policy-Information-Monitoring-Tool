# -*- coding: utf-8 -*-
"""
数据库模块 - 使用 sqlite3 标准库管理数据持久化
"""

import os
import sqlite3
from datetime import datetime

from config import DATABASE_PATH, KEYWORDS, WEBSITES


def get_db():
    """获取数据库连接（启用外键约束、Row 工厂便于按列名访问）"""
    # 确保数据库目录存在
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


def init_db():
    """初始化数据库及全部数据表"""
    conn = get_db()
    cursor = conn.cursor()

    # websites 表 - 监控网站列表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS websites (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            url             TEXT    NOT NULL,
            level           TEXT,
            buttons         TEXT,
            status          TEXT    DEFAULT 'active',
            last_crawl_time TEXT
        )
    ''')

    # articles 表 - 抓取到的文章/政策
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            title             TEXT    NOT NULL,
            url               TEXT    NOT NULL,
            source_name       TEXT,
            source_url        TEXT,
            publish_date      TEXT,
            summary           TEXT,
            matched_keywords  TEXT,
            crawl_time        TEXT,
            level             TEXT
        )
    ''')

    # crawl_logs 表 - 爬取任务日志
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawl_logs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            website_name  TEXT    NOT NULL,
            start_time    TEXT,
            end_time      TEXT,
            status        TEXT,
            article_count INTEGER DEFAULT 0,
            error_message TEXT
        )
    ''')

    # keywords 表 - 关键词库（用户可在 UI 编辑）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keywords (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword      TEXT    NOT NULL,
            category     TEXT    NOT NULL DEFAULT 'general',
            created_time TEXT,
            UNIQUE(keyword, category)
        )
    ''')

    conn.commit()

    # 首次启动时从 config.py 导入默认关键词
    cursor.execute('SELECT COUNT(*) AS c FROM keywords')
    if cursor.fetchone()['c'] == 0:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for category, words in KEYWORDS.items():
            for word in words:
                try:
                    cursor.execute(
                        'INSERT INTO keywords (keyword, category, created_time) '
                        'VALUES (?, ?, ?)',
                        (word, category, now),
                    )
                except sqlite3.IntegrityError:
                    pass
        conn.commit()

    # 首次启动时从 config.py 导入默认网址
    cursor.execute('SELECT COUNT(*) AS c FROM websites')
    if cursor.fetchone()['c'] == 0:
        for site in WEBSITES:
            cursor.execute(
                'INSERT INTO websites (name, url, level, buttons, status) '
                'VALUES (?, ?, ?, ?, ?)',
                (
                    site['name'],
                    site['url'],
                    site.get('level', ''),
                    ','.join(site.get('buttons', [])),
                    'active',
                ),
            )
        conn.commit()

    conn.close()


# ---------------------------------------------------------------- #
# Websites CRUD
# ---------------------------------------------------------------- #

def get_websites():
    """返回所有网站，按 id 排序。buttons 拆分为列表"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM websites ORDER BY id ASC')
    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        raw = d.get('buttons') or ''
        d['buttons_list'] = [
            b.strip() for b in raw.replace('，', ',').split(',') if b.strip()
        ]
        rows.append(d)
    conn.close()
    return rows


def get_website(website_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM websites WHERE id = ?', (website_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def _normalize_buttons(buttons):
    """将 list 或逗号分隔字符串转为逗号分隔字符串"""
    if isinstance(buttons, list):
        items = [str(b).strip() for b in buttons if str(b).strip()]
    else:
        raw = (buttons or '').replace('，', ',')
        items = [s.strip() for s in raw.split(',') if s.strip()]
    return ','.join(items)


def add_website(name, url, level='国家', buttons=''):
    name = (name or '').strip()
    url = (url or '').strip()
    if not name or not url:
        return False, '网站名称与 URL 不能为空', None
    if level not in ('国家', '省', '市'):
        level = '国家'
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO websites (name, url, level, buttons, status) '
        'VALUES (?, ?, ?, ?, ?)',
        (name, url, level, _normalize_buttons(buttons), 'active'),
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return True, '添加成功', new_id


def update_website(website_id, name=None, url=None, level=None, buttons=None):
    fields, params = [], []
    if name is not None:
        fields.append('name = ?')
        params.append(name.strip())
    if url is not None:
        fields.append('url = ?')
        params.append(url.strip())
    if level is not None and level in ('国家', '省', '市'):
        fields.append('level = ?')
        params.append(level)
    if buttons is not None:
        fields.append('buttons = ?')
        params.append(_normalize_buttons(buttons))
    if not fields:
        return False, '没有需要更新的字段'
    params.append(website_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        f'UPDATE websites SET {", ".join(fields)} WHERE id = ?',
        params,
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0, '更新成功' if affected else '网站不存在'


def delete_website(website_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM websites WHERE id = ?', (website_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def article_exists(title, source, publish_date=None):
    """检查文章是否已存在（按 标题 + 来源网站 [+ 发布日期] 判重）"""
    title = (title or '').strip()
    source = (source or '').strip()
    if not title or not source:
        return False
    conn = get_db()
    try:
        if publish_date:
            cursor = conn.execute(
                'SELECT 1 FROM articles WHERE title = ? AND source_name = ? '
                'AND publish_date = ? LIMIT 1',
                (title, source, publish_date),
            )
        else:
            cursor = conn.execute(
                'SELECT 1 FROM articles WHERE title = ? AND source_name = ? LIMIT 1',
                (title, source),
            )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def update_website_crawl_status(name, status='success', last_crawl_time=None):
    """供爬虫使用：更新某个网站的状态与最后爬取时间"""
    last_crawl_time = last_crawl_time or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    conn.execute(
        'UPDATE websites SET status = ?, last_crawl_time = ? WHERE name = ?',
        (status, last_crawl_time, name),
    )
    conn.commit()
    conn.close()


def get_keywords(category=None):
    """读取关键词列表"""
    conn = get_db()
    cursor = conn.cursor()
    if category:
        cursor.execute(
            'SELECT * FROM keywords WHERE category = ? ORDER BY id ASC',
            (category,),
        )
    else:
        cursor.execute('SELECT * FROM keywords ORDER BY category ASC, id ASC')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_keywords_grouped():
    """按分类分组返回 {category: [keyword,...]}"""
    grouped = {}
    for row in get_keywords():
        grouped.setdefault(row['category'], []).append(row['keyword'])
    return grouped


def add_keyword(keyword, category='general'):
    """添加单个关键词，返回 (success, message)"""
    keyword = (keyword or '').strip()
    if not keyword:
        return False, '关键词不能为空'
    if category not in ('general', 'ivd'):
        category = 'general'
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO keywords (keyword, category, created_time) VALUES (?, ?, ?)',
            (keyword, category, now),
        )
        conn.commit()
        return True, '添加成功'
    except sqlite3.IntegrityError:
        return False, f'关键词 "{keyword}" 已存在'
    finally:
        conn.close()


def add_keywords_batch(text, category='general'):
    """批量添加（逗号或中文逗号分隔），返回统计信息"""
    raw = (text or '').replace('，', ',')
    items = [s.strip() for s in raw.split(',') if s.strip()]
    added, skipped = [], []
    for kw in items:
        ok, _ = add_keyword(kw, category)
        if ok:
            added.append(kw)
        else:
            skipped.append(kw)
    return {'added': added, 'skipped': skipped, 'total': len(items)}


def delete_keyword(keyword_id):
    """删除关键词"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM keywords WHERE id = ?', (keyword_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


if __name__ == '__main__':
    init_db()
    print(f'数据库初始化完成: {DATABASE_PATH}')
