# -*- coding: utf-8 -*-
"""
公共事务部信息爬取工具 - 全局配置文件
"""

# 爬取间隔（小时）
CRAWL_INTERVAL = 4

# 定时爬取开关
# - False（默认）：本地分发版本，用户手动点击爬取按钮触发
# - True：服务器部署时启用，按 CRAWL_INTERVAL 周期自动爬取
ENABLE_SCHEDULER = False

# SQLite 数据库路径（MySQL 不可用时的 fallback）
DATABASE_PATH = 'data/paqu.db'

# MySQL 数据库配置
# 部署到服务器时请按实际情况修改 password 等字段。
# 若该机器上没有可用的 MySQL，程序会自动回退到上面的 SQLite。
MYSQL_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': 'root',  # 部署时修改为真实密码
    'database': 'paqu',
    'charset': 'utf8mb4',
}

# 网站配置列表
WEBSITES = [
    {
        'name': '国家科技管理信息系统',
        'url': 'https://service.most.gov.cn',
        'level': '国家',
        'buttons': ['公开公示', '项目申报'],
    },
    {
        'name': '国家工信部官网',
        'url': 'https://wap.miit.gov.cn/',
        'level': '国家',
        'buttons': ['最新政策'],
    },
    {
        'name': '国家卫健委官网',
        'url': 'https://www.nhc.gov.cn/',
        'level': '国家',
        'buttons': ['政策解读'],
    },
    {
        'name': '国家发改委官网',
        'url': 'https://www.ndrc.gov.cn/',
        'level': '国家',
        'buttons': ['通知公告'],
    },
    {
        'name': '四川省经信厅官网',
        'url': 'https://jxt.sc.gov.cn',
        'level': '省',
        'buttons': ['通知', '公告公示'],
    },
    {
        'name': '四川省科技厅官网',
        'url': 'https://kjt.sc.gov.cn/',
        'level': '省',
        'buttons': ['通知', '公告公示'],
    },
    {
        'name': '四川省卫健委官网',
        'url': 'https://wsjkw.sc.gov.cn/',
        'level': '省',
        'buttons': ['政策文件', '公告公示'],
    },
    {
        'name': '四川发改委官网',
        'url': 'https://fgw.sc.gov.cn/',
        'level': '省',
        'buttons': ['通知公告'],
    },
    {
        'name': '四川省药监局官网',
        'url': 'https://yjj.sc.gov.cn/',
        'level': '省',
        'buttons': ['工作通知', '公示公告'],
    },
    {
        'name': '成都市经信局官网',
        'url': 'https://cdjx.chengdu.gov.cn/',
        'level': '市',
        'buttons': ['通知公告', '双公示'],
    },
    {
        'name': '成都市科技局官网',
        'url': 'https://cdst.chengdu.gov.cn/cdskxjsj/index.shtml',
        'level': '市',
        'buttons': ['通知公告'],
    },
    {
        'name': '成都市卫健委官网',
        'url': 'https://cdwjw.chengdu.gov.cn/',
        'level': '市',
        'buttons': ['通知公告'],
    },
    {
        'name': '成都市发改委官网',
        'url': 'https://cddrc.chengdu.gov.cn/',
        'level': '市',
        # 实测主页可见的顶层导航：政务公开 / 发改工作 / 发展改革动态
        'buttons': ['政务公开', '发展改革动态', '发改工作'],
    },
    {
        'name': '成都市高新区管委会',
        'url': 'https://www.cdht.gov.cn/cdht/shouye/sy.shtml',
        'level': '市',
        'buttons': ['产业政策', '通知公告'],
    },
    {
        'name': '高新通',
        'url': 'https://www.cdhtqyfw.cn/',
        'level': '市',
        'buttons': ['政策日历'],
    },
]

# 关键词库
KEYWORDS = {
    'general': [
        '医疗器械', '医疗健康', '医疗卫生', '生物医药', '医药健康产业链',
        '医药工业', '医工融合', '医工试点', '创新医疗器械融合应用试点',
        '智改数转', '攻关揭榜', '重大专项', '成果转化', '揭榜挂帅',
        '研发平台', '首台（套）重大技术装备', '高端医疗装备推广应用',
        '医药制造', '专精特新（医疗器械）', '生物医药重大专项', '科技计划',
        '医疗器械科技攻关', '国家重点研发计划', '体外诊断关键技术',
        '医工交叉', '技改', '科创补贴', '医药产业化', '研发补助',
        '创新奖励', '诊疗装备', '临床医学研究中心', '企业技术中心',
        '工程技术研究中心', '重点实验室', '科技创新', '智慧化',
        '智能化', '人工智能', '高端制造',
    ],
    'ivd': [
        '体外诊断', 'IVD', '检验检测', '生化', '免疫', '凝血', '尿液',
        '血球', '输血', '临检', '分子诊断', 'POCT', '化学发光', '免疫比浊',
        '血细胞', '分析仪', '全自动检验流水线', '试剂', '临床检验',
        '医学实验室', '量值溯源',
    ],
}
