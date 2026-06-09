# 公共事务部政策信息监控工具

## 快速启动

```bash
cd d:\python-code\paqu

# 激活虚拟环境
venv\Scripts\activate

# 安装依赖（首次使用时执行）
pip install -r requirements.txt

# 启动应用
python app.py
```

浏览器打开：http://127.0.0.1:5000

> 提示：虚拟环境已创建在 `venv/` 目录中，每次使用前需要先激活。

## 功能说明

- **仪表盘**：查看爬取统计和最新动态
- **爬取结果**：按来源、级别、日期、关键词筛选查看
- **关键词管理**：添加/删除监控关键词
- **网址管理**：添加/编辑/删除监控网站
- **手动爬取**：立即触发爬取任务

## 自动爬取

应用启动后每4小时自动爬取一次（可在 `config.py` 中修改 `CRAWL_INTERVAL`）。

## 项目结构

```
├── app.py              # Flask 应用入口
├── config.py           # 全局配置（网站列表、关键词、爬取间隔）
├── database.py         # SQLite 数据库管理
├── scheduler.py        # APScheduler 定时爬取调度
├── requirements.txt    # Python 依赖
├── spiders/            # 爬虫模块
│   ├── base.py         # 爬虫基类（请求、解析、持久化）
│   ├── national.py     # 国家级网站爬虫（科技部、工信部、卫健委、发改委）
│   ├── sichuan.py      # 四川省级网站爬虫（经信厅、科技厅、卫健委、发改委、药监局）
│   ├── chengdu.py      # 成都市级网站爬虫（经信局、科技局、卫健委、发改委、高新区）
│   └── gaoxintong.py   # 高新通平台爬虫
├── templates/          # Jinja2 页面模板
├── static/             # 静态资源（CSS/JS）
└── data/               # SQLite 数据库文件（自动创建）
```

## 监控网站（15个）

| 级别 | 网站 |
|------|------|
| 国家 | 科技管理信息系统、工信部、卫健委、发改委 |
| 省   | 四川经信厅、科技厅、卫健委、发改委、药监局 |
| 市   | 成都经信局、科技局、卫健委、发改委、高新区管委会、高新通 |

## 调试模式

如需开启调试模式（热重载）：

```bash
set FLASK_DEBUG=1
python app.py
```
