# -*- coding: utf-8 -*-
"""
数据库模块

优先使用 MySQL（pymysql），若 MySQL 不可用则自动回退到 SQLite。
对外提供统一的连接包装器：
- 上层代码继续使用 ``?`` 作为占位符，由包装器在 MySQL 后端自动翻译为 ``%s``。
- ``cursor.fetchone() / fetchall()`` 返回的行对象同时支持
  ``row['col']`` 与 ``dict(row)``（SQLite 借助 Row 工厂，MySQL 使用 DictCursor）。
"""

import os
import sqlite3
import logging
from datetime import datetime

from config import DATABASE_PATH, KEYWORDS, WEBSITES

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# 后端选择：MySQL 优先，pymysql 不可用或连不上时回退到 SQLite
# ----------------------------------------------------------------------
try:
    from config import MYSQL_CONFIG  # type: ignore
except Exception:  # noqa: BLE001
    MYSQL_CONFIG = None

try:
    import pymysql
    from pymysql.cursors import DictCursor
    _PYMYSQL_OK = True
except Exception:  # noqa: BLE001
    pymysql = None
    DictCursor = None
    _PYMYSQL_OK = False

# 当前使用的后端：'mysql' 或 'sqlite'，None 表示尚未探测
_BACKEND = None

# 统一的 IntegrityError 元组，便于 except 同时捕获两种后端的异常
_INTEGRITY_ERRORS = [sqlite3.IntegrityError]
if _PYMYSQL_OK:
    try:
        _INTEGRITY_ERRORS.append(pymysql.err.IntegrityError)
    except Exception:  # noqa: BLE001
        pass
INTEGRITY_ERROR = tuple(_INTEGRITY_ERRORS)


def _try_init_mysql():
    """尝试连接 MySQL 并确保目标数据库存在；返回 True 表示可用。"""
    if not (_PYMYSQL_OK and MYSQL_CONFIG):
        return False
    cfg = dict(MYSQL_CONFIG)
    db_name = cfg.pop('database', 'paqu')
    try:
        conn = pymysql.connect(
            host=cfg.get('host', '127.0.0.1'),
            port=int(cfg.get('port', 3306)),
            user=cfg.get('user', 'root'),
            password=cfg.get('password', ''),
            charset=cfg.get('charset', 'utf8mb4'),
            connect_timeout=3,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning('MySQL 连接失败，将回退到 SQLite：%s', exc)
        return False


def _detect_backend():
    """探测一次后端，并缓存结果。"""
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    if _try_init_mysql():
        _BACKEND = 'mysql'
        cfg = MYSQL_CONFIG or {}
        logger.info(
            '数据库后端：MySQL  %s:%s/%s',
            cfg.get('host'), cfg.get('port'), cfg.get('database'),
        )
    else:
        _BACKEND = 'sqlite'
        logger.info('数据库后端：SQLite  %s', DATABASE_PATH)
    return _BACKEND


def get_backend():
    """返回当前使用的后端名称。"""
    return _detect_backend()


# ----------------------------------------------------------------------
# 连接 / 游标包装器
# ----------------------------------------------------------------------
class _Cursor:
    """统一游标：MySQL 后端自动把 ``?`` 占位符翻译为 ``%s``。"""

    def __init__(self, cursor, backend):
        self._cursor = cursor
        self._backend = backend

    def _translate(self, sql):
        if self._backend == 'mysql' and sql:
            return sql.replace('?', '%s')
        return sql

    def execute(self, sql, params=None):
        sql = self._translate(sql)
        if params is None:
            return self._cursor.execute(sql)
        return self._cursor.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        sql = self._translate(sql)
        return self._cursor.executemany(sql, seq_of_params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        if size is None:
            return self._cursor.fetchmany()
        return self._cursor.fetchmany(size)

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        try:
            self._cursor.close()
        except Exception:  # noqa: BLE001
            pass

    def __iter__(self):
        return iter(self._cursor)


class _Connection:
    """统一连接：兼容 sqlite3.Connection 与 pymysql.Connection 常用方法。"""

    def __init__(self, conn, backend):
        self._conn = conn
        self._backend = backend

    @property
    def backend(self):
        return self._backend

    def cursor(self):
        return _Cursor(self._conn.cursor(), self._backend)

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        try:
            self._conn.commit()
        except Exception:  # noqa: BLE001
            pass

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:  # noqa: BLE001
            pass

    def close(self):
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass


def get_db():
    """获取数据库连接（统一包装器）。"""
    backend = _detect_backend()
    if backend == 'mysql':
        cfg = dict(MYSQL_CONFIG or {})
        conn = pymysql.connect(
            host=cfg.get('host', '127.0.0.1'),
            port=int(cfg.get('port', 3306)),
            user=cfg.get('user', 'root'),
            password=cfg.get('password', ''),
            database=cfg.get('database', 'paqu'),
            charset=cfg.get('charset', 'utf8mb4'),
            cursorclass=DictCursor,
            autocommit=False,
        )
        return _Connection(conn, 'mysql')

    # SQLite fallback
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return _Connection(conn, 'sqlite')


# ----------------------------------------------------------------------
# 建表 SQL（双后端）
# ----------------------------------------------------------------------
_MYSQL_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS websites (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        name            VARCHAR(200) NOT NULL,
        url             VARCHAR(500) NOT NULL,
        level           VARCHAR(20),
        buttons         VARCHAR(500),
        status          VARCHAR(20)  DEFAULT 'active',
        last_crawl_time VARCHAR(30)
    ) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS articles (
        id                INT AUTO_INCREMENT PRIMARY KEY,
        title             VARCHAR(500) NOT NULL,
        url               VARCHAR(1000) NOT NULL,
        source_name       VARCHAR(200),
        source_url        VARCHAR(500),
        publish_date      VARCHAR(30),
        summary           TEXT,
        matched_keywords  VARCHAR(500),
        crawl_time        VARCHAR(30),
        level             VARCHAR(20),
        INDEX idx_articles_source (source_name),
        INDEX idx_articles_publish (publish_date),
        INDEX idx_articles_url (url(255))
    ) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS crawl_logs (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        website_name  VARCHAR(200) NOT NULL,
        start_time    VARCHAR(30),
        end_time      VARCHAR(30),
        status        VARCHAR(20),
        article_count INT DEFAULT 0,
        error_message TEXT,
        INDEX idx_logs_website (website_name)
    ) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS keywords (
        id           INT AUTO_INCREMENT PRIMARY KEY,
        keyword      VARCHAR(100) NOT NULL,
        category     VARCHAR(30)  NOT NULL DEFAULT 'general',
        created_time VARCHAR(30),
        UNIQUE KEY uniq_keyword_category (keyword, category)
    ) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]

_SQLITE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS websites (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT    NOT NULL,
        url             TEXT    NOT NULL,
        level           TEXT,
        buttons         TEXT,
        status          TEXT    DEFAULT 'active',
        last_crawl_time TEXT
    )
    """,
    """
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
    """,
    """
    CREATE TABLE IF NOT EXISTS crawl_logs (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        website_name  TEXT    NOT NULL,
        start_time    TEXT,
        end_time      TEXT,
        status        TEXT,
        article_count INTEGER DEFAULT 0,
        error_message TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS keywords (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword      TEXT    NOT NULL,
        category     TEXT    NOT NULL DEFAULT 'general',
        created_time TEXT,
        UNIQUE(keyword, category)
    )
    """,
]


def init_db():
    """初始化数据库及全部数据表，并在首次启动时导入默认关键词与网站。"""
    backend = _detect_backend()
    conn = get_db()
    cursor = conn.cursor()

    table_sqls = _MYSQL_TABLES if backend == 'mysql' else _SQLITE_TABLES
    for sql in table_sqls:
        cursor.execute(sql)
    conn.commit()

    # 首次启动导入默认关键词
    cursor.execute('SELECT COUNT(*) AS c FROM keywords')
    row = cursor.fetchone()
    if (row['c'] if row else 0) == 0:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for category, words in (KEYWORDS or {}).items():
            for word in words:
                try:
                    cursor.execute(
                        'INSERT INTO keywords (keyword, category, created_time) '
                        'VALUES (?, ?, ?)',
                        (word, category, now),
                    )
                except INTEGRITY_ERROR:
                    pass
        conn.commit()

    # 首次启动导入默认网址
    cursor.execute('SELECT COUNT(*) AS c FROM websites')
    row = cursor.fetchone()
    if (row['c'] if row else 0) == 0:
        for site in (WEBSITES or []):
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


# ----------------------------------------------------------------------
# Websites CRUD
# ----------------------------------------------------------------------
def get_websites():
    """返回所有网站，按 id 排序，buttons 拆分为列表。"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM websites ORDER BY id ASC')
    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        raw = d.get('buttons') or ''
        d['buttons_list'] = [
            b.strip() for b in str(raw).replace('，', ',').split(',') if b.strip()
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
    """将 list 或逗号分隔字符串转为逗号分隔字符串。"""
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
    """检查文章是否已存在（按 标题 + 来源网站 [+ 发布日期] 判重）。"""
    title = (title or '').strip()
    source = (source or '').strip()
    if not title or not source:
        return False
    conn = get_db()
    try:
        if publish_date:
            cursor = conn.execute(
                'SELECT 1 AS x FROM articles WHERE title = ? AND source_name = ? '
                'AND publish_date = ? LIMIT 1',
                (title, source, publish_date),
            )
        else:
            cursor = conn.execute(
                'SELECT 1 AS x FROM articles WHERE title = ? AND source_name = ? LIMIT 1',
                (title, source),
            )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def update_website_crawl_status(name, status='success', last_crawl_time=None):
    """供爬虫使用：更新某个网站的状态与最后爬取时间。"""
    last_crawl_time = last_crawl_time or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    conn.execute(
        'UPDATE websites SET status = ?, last_crawl_time = ? WHERE name = ?',
        (status, last_crawl_time, name),
    )
    conn.commit()
    conn.close()


def get_keywords(category=None):
    """读取关键词列表。"""
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
    """按分类分组返回 {category: [keyword,...]}。"""
    grouped = {}
    for row in get_keywords():
        grouped.setdefault(row['category'], []).append(row['keyword'])
    return grouped


def add_keyword(keyword, category='general'):
    """添加单个关键词，返回 (success, message)。"""
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
    except INTEGRITY_ERROR:
        return False, f'关键词 "{keyword}" 已存在'
    finally:
        conn.close()


def add_keywords_batch(text, category='general'):
    """批量添加（逗号或中文逗号分隔），返回统计信息。"""
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
    """删除关键词。"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM keywords WHERE id = ?', (keyword_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


if __name__ == '__main__':
    init_db()
    print(f'数据库初始化完成（后端：{get_backend()}）')
