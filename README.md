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

### 免安装版本（推荐）
1. 解压整个文件夹
2. 双击 `install.bat` 初始化
3. 双击 `start.bat` 启动
4. 浏览器打开 http://127.0.0.1:5000

### 数据库配置
- **默认**：无需配置，自动使用 SQLite（data/paqu.db）
- **MySQL**：修改 `config.py` 中的 `MYSQL_CONFIG`，填入 MySQL 连接信息

## BAT 工具说明
| 文件 | 说明 |
|------|------|
| install.bat | 初始化（创建数据库表） |
| start.bat | 启动应用 |
| stop.bat | 停止应用 |
| crawl_now.bat | 立即执行一次爬取 |
| deploy_server.bat | 服务器部署（开机自启） |

## 日志
运行日志保存在 `logs/app.log`，按天轮转，保留30天。

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
- MySQL / SQLite（双后端）
- APScheduler（定时任务）
- 前端：HTML + CSS + JavaScript

## 服务器部署
参考 `MySQL安装指南.txt` 和 `deploy_server.bat`
