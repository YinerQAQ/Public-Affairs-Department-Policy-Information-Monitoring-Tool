# 政策信息监控工具

> 公共事务部政策信息自动监控系统

## 功能特性
- 自动爬取国家/省/市三级政府网站政策信息
- 64个关键词智能匹配过滤
- Web管理界面（查看、筛选、导出）
- 选择性爬取 + 时间范围过滤
- 实时爬取进度可视化
- Excel/CSV 一键导出
- MySQL数据库（自动回退SQLite）
- 文件日志（按天轮转30天）
- 嵌入式Python免安装部署

## 快速开始

### 一键启动（推荐）
**双击根目录下的 `政策监控工具.exe`** —— 自动启动服务并打开浏览器，无需任何命令行操作。

> 注意：EXE 必须与 `python\` 目录、`app.py` 保持同层级。

### 数据库配置
- **默认**：无需配置，自动使用 SQLite（data/paqu.db）
- **MySQL**：修改 `config.py` 中的 `MYSQL_CONFIG`，填入连接信息
- **MySQL 8.0**：使用 `caching_sha2_password` 认证插件时需要 `cryptography` 包（已包含在 `requirements.txt` 中）

### 定时爬取开关
默认 **关闭**，由用户在 Web 面板手动点击爬取按钮触发。
服务器部署时如需自动定时爬取，请编辑 `config.py`：

```python
ENABLE_SCHEDULER = True  # 改为 True 启用按 CRAWL_INTERVAL 小时定时爬取
```

## 目录结构

```
政策监控工具.exe   ← 用户双击入口
app.py             ← 主程序
config.py          ← 配置（关键词/网站/MySQL/调度开关）
database.py        ← 数据库
launcher.py        ← EXE 源码
crawl_export.py    ← 离线爬取导出
scheduler.py       ← 定时调度器
requirements.txt   ← 依赖列表

python/            ← 嵌入式 Python 运行环境
spiders/           ← 各网站爬虫实现
templates/         ← 前端模板
static/            ← 前端静态资源
docs/              ← 设计文档（架构图/ER图/时序图等）
data/              ← SQLite 数据库
logs/              ← 运行日志（按天轮转 30 天）
output/            ← 导出文件
tools/             ← 高级用户工具与说明（见下文）
```

## 高级用户工具（`tools/` 目录）

普通用户只需双击 `政策监控工具.exe` 即可，以下脚本面向命令行 / 服务器部署场景。

| 脚本 | 说明 |
|------|------|
| `tools/install.bat` | 首次初始化（创建数据库表） |
| `tools/start.bat` | 命令行启动应用（替代 EXE） |
| `tools/stop.bat` | 停止应用（按端口 5000 杀进程） |
| `tools/crawl_now.bat` | 立即执行一次爬取并导出 |
| `tools/deploy_server.bat` | 部署到 Windows 服务器（含开机自启） |

附带说明文档：
- `tools/MySQL安装指南.txt` —— 服务器 MySQL 安装步骤
- `tools/README_部署说明.txt` —— 服务器部署详细说明
- `tools/构建阅读.md` —— EXE 打包与构建流程

> 所有 BAT 脚本会自动切换到项目根目录后再执行，无需关心当前路径。

## 日志
运行日志保存在 `logs/app.log`，按天轮转，保留 30 天。

## 技术文档
详细设计文档在 `docs/` 目录：
- 系统架构图
- ER图（数据库设计）
- 时序图（核心流程）
- 技术栈说明
- 部署架构图

## 技术栈
- Python 3.13 + Flask
- Playwright（无头浏览器爬虫）
- MySQL / SQLite（双后端自动切换）
- APScheduler（定时任务，可关）
- 前端：HTML + CSS + JavaScript

## 服务器部署
1. 把整个目录拷到服务器
2. 修改 `config.py`：`ENABLE_SCHEDULER = True`，按需修改 `MYSQL_CONFIG`
3. 双击运行 `tools/deploy_server.bat`
4. 详细步骤见 `tools/README_部署说明.txt` 与 `tools/MySQL安装指南.txt`
