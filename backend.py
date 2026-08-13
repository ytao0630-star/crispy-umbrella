#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工业园区资产管理系统 · 本地原型后端
零外部依赖：仅用 Python 标准库 (http.server + sqlite3)
运行：python3 backend.py   然后浏览器打开 http://localhost:8000
数据全部存在本地 park.db，绝不出园区。
"""
import http.server
import socketserver
import sqlite3
import json
import os
import datetime
import urllib.parse
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "park.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# 公寓水电计价（演示用）
WATER_RATE = 5.0    # 元/吨
ELECTRIC_RATE = 0.8  # 元/度

ROLES = ["系统管理员", "招商专员", "财务", "物业", "园区领导"]


def dict_factory(cursor, row):
    return {cursor.description[i][0]: row[i] for i in range(len(cursor.description))}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today():
    return datetime.datetime.now().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# 初始化数据库 + 种子数据
# ---------------------------------------------------------------------------
def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS buildings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, name TEXT, type TEXT, address TEXT,
        floors INTEGER, total_area REAL
    );
    CREATE TABLE IF NOT EXISTS units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, building_id INTEGER, type TEXT, area REAL,
        rent_price REAL, property_price REAL,
        sellable INTEGER, rentable INTEGER, status TEXT,
        current_contract_id INTEGER, current_customer_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT, name TEXT, contact TEXT, phone TEXT,
        credit_code TEXT, id_number TEXT, address TEXT,
        source TEXT, stage TEXT, owner TEXT, industry TEXT,
        scale TEXT, demand TEXT, tags TEXT, budget REAL,
        last_follow TEXT, next_follow TEXT,
        created_at TEXT, biz_type TEXT, channel_id INTEGER,
        entered_c_date TEXT, entered_b_date TEXT, entered_a_date TEXT
    );
    CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT, name TEXT, code TEXT, biz_type TEXT, note TEXT, sort INTEGER
    );
    CREATE TABLE IF NOT EXISTS crm_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER, month INTEGER, biz_type TEXT,
        plan_lead INTEGER DEFAULT 0, plan_C INTEGER DEFAULT 0,
        plan_B INTEGER DEFAULT 0, plan_A INTEGER DEFAULT 0, note TEXT
    );
    CREATE TABLE IF NOT EXISTS contracts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, type TEXT, unit_id INTEGER, customer_id INTEGER,
        start_date TEXT, end_date TEXT, amount REAL, pay_cycle TEXT,
        deposit REAL, status TEXT, sign_date TEXT, note TEXT,
        lease_months REAL, free_days INTEGER DEFAULT 0,
        deposit_status TEXT DEFAULT '已收',
        notice_date TEXT, actual_end_date TEXT, move_out_reason TEXT,
        original_contract_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contract_id INTEGER, unit_id INTEGER, customer_id INTEGER,
        amount REAL, type TEXT, date TEXT, note TEXT
    );
    CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contract_id INTEGER, unit_id INTEGER, customer_id INTEGER,
        item_type TEXT, period TEXT, amount REAL, due_date TEXT,
        paid_amount REAL DEFAULT 0, status TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bill_id INTEGER, amount REAL, method TEXT, date TEXT,
        operator TEXT, voucher_no TEXT
    );
    CREATE TABLE IF NOT EXISTS meter_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        unit_id INTEGER, meter_type TEXT, prev_reading REAL,
        curr_reading REAL, usage REAL, bill_month TEXT, bill_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS meter_reading_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meter_no TEXT,
        unit_id INTEGER,
        unit_code TEXT,
        tenant_name TEXT,
        reading_date TEXT,
        bill_month TEXT,
        water_prev REAL, water_curr REAL, water_price REAL,
        water_usage REAL, water_fee REAL,
        electric_prev REAL, electric_curr REAL, electric_price REAL,
        electric_usage REAL, electric_fee REAL,
        total_fee REAL,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS work_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, unit_id INTEGER, reporter TEXT, type TEXT,
        description TEXT, assignee TEXT, status TEXT,
        created_at TEXT, completed_at TEXT, rating INTEGER
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, username TEXT, password TEXT, phone TEXT, email TEXT,
        role TEXT, role_id INTEGER, department_id INTEGER, status TEXT DEFAULT '启用'
    );
    CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, name TEXT, parent_id INTEGER, manager TEXT, sort INTEGER
    );
    CREATE TABLE IF NOT EXISTS sys_roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, name TEXT, description TEXT, sort INTEGER
    );
    CREATE TABLE IF NOT EXISTS role_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_id INTEGER, resource TEXT, action TEXT, allowed INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS sys_menus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, name TEXT, icon TEXT, parent_id INTEGER, sort INTEGER, visible INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT, action TEXT, module TEXT, detail TEXT, ip TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS system_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, name TEXT, value TEXT, description TEXT
    );
    CREATE TABLE IF NOT EXISTS data_dict (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT, code TEXT, name TEXT, sort INTEGER, enabled INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS market_research (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, type TEXT, area REAL, sale_price REAL, rent_price REAL,
        status TEXT, address TEXT, distance TEXT, advantage TEXT, note TEXT,
        created_at TEXT,
        -- 建筑指标
        floor_height REAL, load_bearing REAL, column_span REAL, plot_ratio REAL,
        power_capacity REAL, fire_rating TEXT,
        delivery_floor TEXT, delivery_wall TEXT, delivery_roof TEXT, delivery_door TEXT,
        -- 费用配套
        property_fee REAL, water_fee REAL, electricity_fee REAL, parking_fee REAL,
        parking_count INTEGER, canteen TEXT, dormitory TEXT, office_facility TEXT,
        logistics_facility TEXT, surrounding_biz TEXT,
        -- 交通
        dist_expressway REAL, dist_subway REAL, dist_airport REAL, bus_lines TEXT,
        -- 招商信息
        target_industry TEXT, policy TEXT, commission_rate REAL,
        contact_name TEXT, contact_title TEXT, contact_phone TEXT,
        -- 竞争分析/调研记录
        our_advantage TEXT, our_weakness TEXT, follow_up_plan TEXT,
        research_date TEXT, researcher TEXT
    );
    CREATE TABLE IF NOT EXISTS crm_followups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER, date TEXT, type TEXT,
        content TEXT, next_plan TEXT, operator TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS apartment_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        floor TEXT, room_no TEXT, room_category TEXT, orientation TEXT,
        room_status TEXT DEFAULT '空置',
        company_name TEXT, occupant_name TEXT, contact_phone TEXT,
        occupancy_count INTEGER DEFAULT 0,
        check_in_date TEXT, check_out_date TEXT, stay_days INTEGER,
        deposit REAL DEFAULT 0, monthly_rent REAL DEFAULT 0,
        payment_status TEXT DEFAULT '待缴', electric_balance REAL DEFAULT 0,
        meter_no TEXT, key_card TEXT, room_password TEXT, fingerprint TEXT,
        handler TEXT, note TEXT, created_at TEXT, updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS apartment_rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        floor TEXT, room_no TEXT, room_category TEXT, orientation TEXT,
        meter_no TEXT, room_note TEXT,
        created_at TEXT, updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS apartment_rentals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id INTEGER,
        company_name TEXT, occupant_name TEXT, contact_phone TEXT,
        occupancy_count INTEGER DEFAULT 0,
        check_in_date TEXT, check_out_date TEXT, stay_days INTEGER,
        deposit REAL DEFAULT 0, monthly_rent REAL DEFAULT 0,
        payment_status TEXT DEFAULT '待缴', electric_balance REAL DEFAULT 0,
        key_card TEXT, room_password TEXT, fingerprint TEXT,
        handler TEXT, note TEXT,
        created_at TEXT, updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS apartment_fees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id INTEGER,
        rental_id INTEGER,
        fee_type TEXT,
        amount REAL DEFAULT 0,
        fee_date TEXT,
        pay_method TEXT,
        status TEXT DEFAULT '已收',
        operator TEXT,
        note TEXT,
        created_at TEXT, updated_at TEXT
    );
    """)
    conn.commit()
    # 兼容性：旧库自动加字段、加表
    _ensure_columns(conn)
    _ensure_table_deposits(conn)
    _ensure_sys_tables(conn)
    _ensure_market_seed(conn)
    _ensure_crm_defaults(conn)
    _ensure_channels_seed(conn)
    _ensure_apartment_records(conn)
    _ensure_apartment_fees(conn)
    _ensure_apartment_seed(conn)
    _migrate_apartment_model(conn)
    _ensure_apartment_sync_columns(conn)
    _migrate_apartment_contracts(conn)
    _ensure_units_note_column(conn)
    _ensure_meter_records(conn)
    _ensure_merchants(conn)
    _ensure_merchants_seed(conn)
    # 若为空则灌入演示数据
    cnt = c.execute("SELECT COUNT(*) AS n FROM buildings").fetchone()["n"]
    if cnt == 0:
        seed_demo(conn)


def _ensure_columns(conn):
    cols = [
        ("contracts", "lease_months", "REAL"),
        ("contracts", "free_days", "INTEGER DEFAULT 0"),
        ("contracts", "deposit_status", "TEXT DEFAULT '已收'"),
        ("contracts", "notice_date", "TEXT"),
        ("contracts", "actual_end_date", "TEXT"),
        ("contracts", "move_out_reason", "TEXT"),
        ("contracts", "original_contract_id", "INTEGER"),
        ("users", "username", "TEXT"),
        ("users", "password", "TEXT"),
        ("users", "phone", "TEXT"),
        ("users", "email", "TEXT"),
        ("users", "role_id", "INTEGER"),
        ("users", "department_id", "INTEGER"),
        ("users", "status", "TEXT DEFAULT '启用'"),
        ("customers", "source", "TEXT"),
        ("customers", "stage", "TEXT"),
        ("customers", "owner", "TEXT"),
        ("customers", "industry", "TEXT"),
        ("customers", "scale", "TEXT"),
        ("customers", "demand", "TEXT"),
        ("customers", "tags", "TEXT"),
        ("customers", "budget", "REAL"),
        ("customers", "last_follow", "TEXT"),
        ("customers", "next_follow", "TEXT"),
        ("customers", "created_at", "TEXT"),
        ("customers", "biz_type", "TEXT"),
        ("customers", "channel_id", "INTEGER"),
        ("customers", "entered_c_date", "TEXT"),
        ("customers", "entered_b_date", "TEXT"),
        ("customers", "entered_a_date", "TEXT"),
        # market_research 下钻详情字段（兼容老库自动加列）
        ("market_research", "floor_height", "REAL"),
        ("market_research", "load_bearing", "REAL"),
        ("market_research", "column_span", "REAL"),
        ("market_research", "plot_ratio", "REAL"),
        ("market_research", "power_capacity", "REAL"),
        ("market_research", "fire_rating", "TEXT"),
        ("market_research", "delivery_floor", "TEXT"),
        ("market_research", "delivery_wall", "TEXT"),
        ("market_research", "delivery_roof", "TEXT"),
        ("market_research", "delivery_door", "TEXT"),
        ("market_research", "property_fee", "REAL"),
        ("market_research", "water_fee", "REAL"),
        ("market_research", "electricity_fee", "REAL"),
        ("market_research", "parking_fee", "REAL"),
        ("market_research", "parking_count", "INTEGER"),
        ("market_research", "canteen", "TEXT"),
        ("market_research", "dormitory", "TEXT"),
        ("market_research", "office_facility", "TEXT"),
        ("market_research", "logistics_facility", "TEXT"),
        ("market_research", "surrounding_biz", "TEXT"),
        ("market_research", "dist_expressway", "REAL"),
        ("market_research", "dist_subway", "REAL"),
        ("market_research", "dist_airport", "REAL"),
        ("market_research", "bus_lines", "TEXT"),
        ("market_research", "target_industry", "TEXT"),
        ("market_research", "policy", "TEXT"),
        ("market_research", "commission_rate", "REAL"),
        ("market_research", "contact_name", "TEXT"),
        ("market_research", "contact_title", "TEXT"),
        ("market_research", "contact_phone", "TEXT"),
        ("market_research", "our_advantage", "TEXT"),
        ("market_research", "our_weakness", "TEXT"),
        ("market_research", "follow_up_plan", "TEXT"),
        ("market_research", "research_date", "TEXT"),
        ("market_research", "researcher", "TEXT"),
    ]
    for table, col, defn in cols:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")
            conn.commit()
        except sqlite3.OperationalError:
            pass


def _ensure_table_deposits(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contract_id INTEGER, unit_id INTEGER, customer_id INTEGER,
        amount REAL, type TEXT, date TEXT, note TEXT
    )
    """)
    conn.commit()


def _ensure_sys_tables(conn):
    tables = [
        """CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT, name TEXT, parent_id INTEGER, manager TEXT, sort INTEGER)""",
        """CREATE TABLE IF NOT EXISTS sys_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT, name TEXT, description TEXT, sort INTEGER)""",
        """CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER, resource TEXT, action TEXT, allowed INTEGER DEFAULT 1)""",
        """CREATE TABLE IF NOT EXISTS sys_menus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT, name TEXT, icon TEXT, parent_id INTEGER, sort INTEGER, visible INTEGER DEFAULT 1)""",
        """CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT, action TEXT, module TEXT, detail TEXT, ip TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS system_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT, name TEXT, value TEXT, description TEXT)""",
        """CREATE TABLE IF NOT EXISTS data_dict (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT, code TEXT, name TEXT, sort INTEGER, enabled INTEGER DEFAULT 1)""",
    ]
    for sql in tables:
        conn.execute(sql)
    conn.commit()


def _ensure_market_seed(conn):
    c = conn.cursor()
    n = c.execute("SELECT COUNT(*) AS n FROM market_research").fetchone()["n"]
    if n > 0:
        return
    samples = [
        ("科创园B区", "标准厂房", 8000, 8500, 1.2, "招商中", "园区东侧产业带", "1.5km", "层高8米，货梯齐全，配套食堂", "园区标杆竞品"),
        ("智造小镇", "独栋厂房", 12000, 9200, 1.4, "部分空置", "北区智造产业带", "3km", "可分割，配套宿舍", "政府补贴力度大"),
        ("联东U谷", "分层厂房", 5000, 9800, 1.5, "满租", "高新区核心", "5km", "品牌园区，入驻率高", "租金偏高"),
        ("民营小微园", "钢结构厂房", 6000, 7800, 1.0, "在售", "城南工业园", "4km", "价格低，产权可分割", "配套较弱"),
        ("国资标准厂房", "标准厂房", 15000, 8200, 1.1, "招商中", "经开区核心区", "6km", "国企背景，稳定性强", "审批流程较慢"),
    ]
    for name, mtype, area, sale, rent, status, addr, dist, adv, note in samples:
        c.execute(
            "INSERT INTO market_research (name,type,area,sale_price,rent_price,status,address,distance,advantage,note,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (name, mtype, area, sale, rent, status, addr, dist, adv, note, now()))
    conn.commit()


def _ensure_crm_defaults(conn):
    c = conn.cursor()
    # 老库补齐 CRM 阶段/来源默认值（仅填充为空者，幂等，不覆盖用户已填值）
    c.execute("UPDATE customers SET stage='线索' WHERE stage IS NULL OR stage=''")
    c.execute("UPDATE customers SET source='其他' WHERE source IS NULL OR source=''")
    # 阶段分级对齐漏斗模型：意向→意向(B类) / 成交→成单(A类) / 洽谈→潜在(C类)
    c.execute("UPDATE customers SET stage='意向(B类)' WHERE stage='意向'")
    c.execute("UPDATE customers SET stage='成单(A类)' WHERE stage='成交'")
    c.execute("UPDATE customers SET stage='潜在(C类)' WHERE stage='洽谈'")
    c.execute("UPDATE customers SET stage='线索' WHERE stage IS NULL OR stage=''")
    # 业务线默认销售（双线漏斗：销售/租赁）
    c.execute("UPDATE customers SET biz_type='销售' WHERE biz_type IS NULL OR biz_type=''")
    # 漏斗里程碑日期回填：新客户=进入C类；已成单=进入A类
    c.execute("UPDATE customers SET created_at=datetime('now','localtime') WHERE created_at IS NULL")
    c.execute("UPDATE customers SET entered_c_date=created_at WHERE entered_c_date IS NULL AND created_at IS NOT NULL")
    c.execute("UPDATE customers SET entered_a_date=created_at WHERE entered_a_date IS NULL AND stage='成单(A类)' AND created_at IS NOT NULL")
    conn.commit()


def _ensure_channels_seed(conn):
    c = conn.cursor()
    n = c.execute("SELECT COUNT(*) AS n FROM channels").fetchone()["n"]
    if n > 0:
        return
    # 渠道分类直接来自《月度执行管控》Excel：6 大类 / 14 子类
    seed = [
        ("中介渠道", "二手房中介", "1.1", 1),
        ("中介渠道", "产业园中介", "1.2", 2),
        ("中介渠道", "独立经纪人", "1.3", 3),
        ("老业主渠道", "老业主", "2.1", 4),
        ("全民营销渠道", "政府招商部门", "3.1", 5),
        ("全民营销渠道", "合作伙伴企业", "3.2", 6),
        ("全民营销渠道", "商协会", "3.3", 7),
        ("全民营销渠道", "校友会、老乡会等", "3.4", 8),
        ("电话及短信", "短信", "4.1", 9),
        ("电话及短信", "电call", "4.2", 10),
        ("广告", "线上如58同城端口", "5.1", 11),
        ("广告", "线下广告如横幅、传单", "5.2", 12),
        ("自然到访", "自然到访", "6", 13),
    ]
    for category, name, code, sort in seed:
        c.execute(
            "INSERT INTO channels (category,name,code,biz_type,sort) VALUES (?,?,?,?,?)",
            (category, name, code, "通用", sort))
    conn.commit()


def _ensure_apartment_records(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS apartment_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        floor TEXT, room_no TEXT, room_category TEXT, orientation TEXT,
        room_status TEXT DEFAULT '空置',
        company_name TEXT, occupant_name TEXT, contact_phone TEXT,
        occupancy_count INTEGER DEFAULT 0,
        check_in_date TEXT, check_out_date TEXT, stay_days INTEGER,
        deposit REAL DEFAULT 0, monthly_rent REAL DEFAULT 0,
        payment_status TEXT DEFAULT '待缴', electric_balance REAL DEFAULT 0,
        meter_no TEXT, key_card TEXT, room_password TEXT, fingerprint TEXT,
        handler TEXT, note TEXT, created_at TEXT, updated_at TEXT
    )
    """)
    conn.commit()


def _ensure_apartment_fees(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS apartment_fees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id INTEGER,
        rental_id INTEGER,
        fee_type TEXT,
        amount REAL DEFAULT 0,
        fee_date TEXT,
        pay_method TEXT,
        status TEXT DEFAULT '已收',
        operator TEXT,
        note TEXT,
        created_at TEXT, updated_at TEXT
    )
    """)
    conn.commit()


def _ensure_apartment_seed(conn):
    c = conn.cursor()
    n = c.execute("SELECT COUNT(*) AS n FROM apartment_records").fetchone()["n"]
    if n > 0:
        return
    sample_rows = [
        ("3", "301", "双人间", "朝南", "在住", "宏达精密制造有限公司", "王强", "13800001001", 2,
         "2026-01-15", "2026-07-14", 2000, 1800, "已缴", 120.5,
         "D-301", "KF-301", "301888", "已录", "招商小李", "企业长包房"),
        ("5", "502", "单人间", "朝东", "在住", "蓝海电子科技", "李娜", "13800001002", 1,
         "2026-03-01", "2026-08-31", 1500, 1200, "待缴", 0,
         "D-502", "KF-502", "502666", "-", "招商小李", "临时住宿"),
        ("7", "703", "四人间", "朝北", "已预订", "未来科技", "-", "-", 0,
         "2026-09-01", "2027-08-31", 3000, 3200, "待缴", 0,
         "D-703", "KF-703", "703999", "-", "物业小赵", "员工宿舍"),
        ("2", "208", "单人间", "朝南", "空置", "", "", "", 0,
         "", "", 1000, 1000, "-", 0,
         "D-208", "KF-208", "208111", "-", "", "可出租"),
        ("4", "406", "双人间", "朝西", "待退房", "腾飞物流", "张涛", "13800001006", 2,
         "2026-02-01", "2026-08-10", 2000, 1600, "已缴", 88.0,
         "D-406", "KF-406", "406777", "已录", "招商小李", "合同到期"),
    ]
    for row in sample_rows:
        floor, room_no, room_category, orientation, room_status, company_name, occupant_name, contact_phone, occupancy_count, check_in_date, check_out_date, deposit, monthly_rent, payment_status, electric_balance, meter_no, key_card, room_password, fingerprint, handler, note = row
        stay_days = _calc_stay_days(check_in_date, check_out_date)
        c.execute(
            "INSERT INTO apartment_records (floor,room_no,room_category,orientation,room_status,company_name,occupant_name,contact_phone,occupancy_count,check_in_date,check_out_date,stay_days,deposit,monthly_rent,payment_status,electric_balance,meter_no,key_card,room_password,fingerprint,handler,note,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (floor, room_no, room_category, orientation, room_status, company_name, occupant_name,
             contact_phone, occupancy_count, check_in_date, check_out_date, stay_days,
             deposit, monthly_rent, payment_status, electric_balance, meter_no, key_card,
             room_password, fingerprint, handler, note, now(), now()))
    conn.commit()


def _migrate_apartment_model(conn):
    """把旧的 apartment_records 按房号拆入 apartment_rooms + apartment_rentals（幂等）。"""
    c = conn.cursor()
    # 已有房间主档则跳过
    cnt = c.execute("SELECT COUNT(*) AS n FROM apartment_rooms").fetchone()["n"]
    if cnt > 0:
        return
    rows = c.execute("SELECT * FROM apartment_records ORDER BY floor, room_no, check_in_date").fetchall()
    for r in rows:
        r = dict(r)
        room_no = r.get("room_no") or ""
        if not room_no:
            continue
        # 主档：同一房号只建一行
        ex = c.execute("SELECT id FROM apartment_rooms WHERE room_no=?", (room_no,)).fetchone()
        if ex:
            room_id = ex["id"]
        else:
            cur = c.execute(
                "INSERT INTO apartment_rooms (floor,room_no,room_category,orientation,meter_no,room_note,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (r.get("floor"), room_no, r.get("room_category"), r.get("orientation"),
                 r.get("meter_no"), r.get("note"), now(), now()))
            room_id = cur.lastrowid
        # 出租记录：每条 apartment_records 对应一条
        c.execute(
            "INSERT INTO apartment_rentals (room_id,company_name,occupant_name,contact_phone,occupancy_count,"
            "check_in_date,check_out_date,stay_days,deposit,monthly_rent,payment_status,electric_balance,"
            "key_card,room_password,fingerprint,handler,note,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (room_id, r.get("company_name"), r.get("occupant_name"), r.get("contact_phone"),
             r.get("occupancy_count") or 0, r.get("check_in_date"), r.get("check_out_date"),
             r.get("stay_days"), r.get("deposit") or 0, r.get("monthly_rent") or 0,
             r.get("payment_status"), r.get("electric_balance") or 0, r.get("key_card"),
             r.get("room_password"), r.get("fingerprint"), r.get("handler"), r.get("note"),
             now(), now()))
    conn.commit()


def _ensure_apartment_sync_columns(conn):
    """收费→公寓租赁同步 + 智能门锁字段（幂等）。"""
    c = conn.cursor()
    for sql in (
        "ALTER TABLE apartment_rentals ADD COLUMN contract_id INTEGER",
        "ALTER TABLE apartment_fees ADD COLUMN source TEXT DEFAULT '手工'",
        "ALTER TABLE apartment_fees ADD COLUMN bill_id INTEGER",
        "ALTER TABLE apartment_rooms ADD COLUMN unit_id INTEGER",
        # 智能门锁：房卡/密码/指纹（DDL 有但旧表缺列，补 ALTER）
        "ALTER TABLE apartment_rooms ADD COLUMN key_card TEXT",
        "ALTER TABLE apartment_rooms ADD COLUMN room_password TEXT",
        "ALTER TABLE apartment_rooms ADD COLUMN fingerprint TEXT",
        # 抄表记录 → 收费账单 联动关联
        "ALTER TABLE meter_reading_records ADD COLUMN bill_id INTEGER",
    ):
        try:
            c.execute(sql)
        except Exception:
            pass
    conn.commit()


def _migrate_apartment_contracts(conn):
    """方案A：每个在住房间 = 1 个租赁合同，与 apartment_rentals 1:1 关联。

    房间已通过导入/种子关联到资产单元(units)，此处为每间房建/复用房间级租赁合同
    （code=HT-AP-<单元号>），并把 apartment_rentals.contract_id 指向它，
    作为「中心收费 → 公寓租赁」同步的关联键。幂等、可重复执行。
    """
    c = conn.cursor()
    ts = now()
    # 1) 清理历史遗留的坏合同（code 后缀为空，如 'HT-AP-'）
    bad = c.execute("SELECT id, code FROM contracts WHERE code LIKE 'HT-AP-%'").fetchall()
    bad_ids = [r["id"] for r in bad if (r["code"] or "").rstrip("-").strip() in ("HT-AP", "")]
    if bad_ids:
        c.executemany("UPDATE apartment_rentals SET contract_id=NULL WHERE contract_id=?",
                      [(i,) for i in bad_ids])
        c.executemany("DELETE FROM bills WHERE contract_id=?", [(i,) for i in bad_ids])
        c.executemany("DELETE FROM contracts WHERE id=?", [(i,) for i in bad_ids])
        conn.commit()

    # 2) 逐间房建/复用合同（room_no/unit 经 JOIN 取得，不再依赖 apartment_rentals 上的列）
    rows = c.execute(
        "SELECT r.id AS rid, r.contract_id, r.company_name, r.occupant_name, "
        "ar.room_no, ar.unit_id, u.code AS unit_code, u.building_id "
        "FROM apartment_rentals r "
        "LEFT JOIN apartment_rooms ar ON ar.id=r.room_id "
        "LEFT JOIN units u ON u.id=ar.unit_id").fetchall()
    for r in rows:
        r = dict(r)
        if r.get("contract_id") is not None:
            continue
        unit_id = r.get("unit_id")
        if not unit_id:
            continue
        room_no = (r.get("room_no") or "").strip()
        unit_code = (r.get("unit_code") or "").strip()
        # 租客名称：公司优先，其次入住人，再兜底
        tenant = (r.get("company_name") or "").strip() or (r.get("occupant_name") or "").strip()
        if not tenant:
            tenant = f"住户-{unit_code or room_no}"
        # 客户
        cust = c.execute("SELECT * FROM customers WHERE name=?", (tenant,)).fetchone()
        if not cust:
            ctype = "企业" if any(k in tenant for k in ("公司", "科技", "物流", "集团", "厂", "企业", "有限")) else "个人"
            c.execute("INSERT INTO customers (type,name,contact,phone,address) VALUES (?,?,?,?,?)",
                      (ctype, tenant, "", "", "园区公寓"))
            cust_id = c.lastrowid
        else:
            cust_id = cust["id"]
        # 复用该房间单元已有的 HT-AP 合同，否则新建（挂在房间已有单元上，不新建重复单元）
        code = f"HT-AP-{unit_code or room_no}"
        ex = c.execute("SELECT * FROM contracts WHERE code=? AND unit_id=?", (code, unit_id)).fetchone()
        if ex:
            contract_id = ex["id"]
        else:
            c.execute(
                "INSERT INTO contracts (code,type,unit_id,customer_id,start_date,end_date,amount,pay_cycle,deposit,status,sign_date,note,lease_months,free_days,deposit_status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (code, "租赁", unit_id, cust_id, ts[:10], "", 0, "月", 0, "生效",
                 ts[:10], "公寓房间租赁(房间级同步)", 12, 0, "不涉及"))
            contract_id = c.lastrowid
        c.execute("UPDATE apartment_rentals SET contract_id=? WHERE id=?", (contract_id, r["rid"]))
    conn.commit()


def _ensure_units_note_column(conn):
    """资产台账单元补充 note 列，用于保留导入台账的原始状态说明（如玻璃厂转租/自用/自持）。"""
    c = conn.cursor()
    cols = {r["name"] for r in c.execute("PRAGMA table_info(units)").fetchall()}
    if "note" not in cols:
        try:
            c.execute("ALTER TABLE units ADD COLUMN note TEXT")
            conn.commit()
        except Exception:
            pass


def _ensure_meter_records(conn):
    """综合水电抄表台账（一行水+电，对应《水电抄表管理》页面）。幂等：表已存在时仅在建表并空表时灌示例。"""
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS meter_reading_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meter_no TEXT, unit_id INTEGER, unit_code TEXT, tenant_name TEXT,
        reading_date TEXT, bill_month TEXT,
        water_prev REAL, water_curr REAL, water_price REAL,
        water_usage REAL, water_fee REAL,
        electric_prev REAL, electric_curr REAL, electric_price REAL,
        electric_usage REAL, electric_fee REAL,
        total_fee REAL, created_at TEXT)""")
    # 不再灌演示数据：抄表记录由「水电抄表」页面按资产台账的应抄表单元录入。
    conn.commit()


def _calc_stay_days(check_in, check_out):
    if not check_in or not check_out:
        return None
    try:
        d1 = datetime.datetime.strptime(check_in, "%Y-%m-%d").date()
        d2 = datetime.datetime.strptime(check_out, "%Y-%m-%d").date()
        return max(0, (d2 - d1).days)
    except Exception:
        return None


def _ensure_merchants(conn):
    """商户管理主表：租户信息 / 租赁周期 / 租金方式 / 分成 / 电费。"""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS merchants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT,
        name TEXT,
        customer_id INTEGER,
        unit_id INTEGER,
        category TEXT,
        contact TEXT,
        phone TEXT,
        enter_date TEXT,
        status TEXT,
        start_date TEXT,
        end_date TEXT,
        pay_cycle TEXT,
        rent_type TEXT,
        fixed_rent REAL,
        base_amount REAL,
        split_ratio REAL,
        property_fee REAL,
        monthly_revenue REAL,
        electric_meter_no TEXT,
        electric_price REAL,
        electric_usage REAL,
        electric_paid REAL,
        note TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    conn.commit()


def _ensure_merchants_seed(conn):
    """商户管理演示数据：仅在表为空时灌入（兼容已有库也能看到示例）。"""
    cnt = conn.execute("SELECT COUNT(*) AS n FROM merchants").fetchone()["n"]
    if cnt > 0:
        return
    demo = [
        ("M001", "星耀餐饮", None, None, "餐饮", "张明", "13800001111", "2024-03-01", "在租",
         "2024-03-01", "2026-02-28", "月付", "保底+分成", 8000, 6000, 8, 1500, 120000,
         "D-102", 0.85, 3200, 2400, "B区一层临街铺位"),
        ("M002", "云仓零售", None, None, "零售", "李华", "13900002222", "2023-09-15", "在租",
         "2023-09-15", "2025-09-14", "季付", "固定租金", 12000, 0, 0, 2000, 0,
         "D-205", 0.85, 1800, 1800, "A区二层标准铺位"),
        ("M003", "智造工坊", None, None, "制造", "王强", "13700003333", "2025-01-10", "在租",
         "2025-01-10", "2027-01-09", "月付", "纯分成", 0, 0, 5, 0, 300000,
         "E-310", 0.80, 5400, 3000, "厂房区三层"),
        ("M004", "优选便利", None, None, "零售", "赵敏", "13600004444", "2024-06-01", "退租",
         "2024-06-01", "2025-05-31", "月付", "固定租金", 6000, 0, 0, 1000, 0,
         "D-118", 0.85, 0, 0, "已退租结清"),
    ]
    ts = now()
    for d in demo:
        conn.execute(
            "INSERT INTO merchants "
            "(code,name,customer_id,unit_id,category,contact,phone,enter_date,status,"
            "start_date,end_date,pay_cycle,rent_type,fixed_rent,base_amount,split_ratio,"
            "property_fee,monthly_revenue,electric_meter_no,electric_price,electric_usage,"
            "electric_paid,note,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            d + (ts, ts))
    conn.commit()


def seed_demo(conn):
    c = conn.cursor()
    # 楼栋
    c.execute("INSERT INTO buildings (code,name,type,address,floors,total_area) VALUES (?,?,?,?,?,?)",
              ("A", "A 栋标准厂房", "厂房", "园区北区 1 号", 3, 12000))
    c.execute("INSERT INTO buildings (code,name,type,address,floors,total_area) VALUES (?,?,?,?,?,?)",
              ("B", "B 栋标准厂房", "厂房", "园区北区 2 号", 3, 9000))
    c.execute("INSERT INTO buildings (code,name,type,address,floors,total_area) VALUES (?,?,?,?,?,?)",
              ("C", "C 栋公寓楼", "公寓", "园区南区 1 号", 12, 6000))
    # 厂房单元
    units = []
    for b in (1, 2):
        for i in range(1, 7):
            code = f"A-{i:02d}" if b == 1 else f"B-{i:02d}"
            area = 600 + i * 80
            units.append((code, b, "厂房", area, area * 25, 3.5, 1, 1, "空置"))
    # 公寓单元
    for i in range(1, 9):
        code = f"C-{i:03d}"
        area = 45 + (i % 4) * 8
        units.append((code, 3, "公寓", area, 1800, 2.5, 0, 1, "空置"))
    c.executemany(
        "INSERT INTO units (code,building_id,type,area,rent_price,property_price,sellable,rentable,status) "
        "VALUES (?,?,?,?,?,?,?,?,?)", units)

    # 客户
    c.execute("INSERT INTO customers (type,name,contact,phone,credit_code,address) VALUES (?,?,?,?,?,?)",
              ("企业", "宏达精密制造有限公司", "王总", "13800000001", "91310000XXXXXXXX1", "上海市..."))
    c.execute("INSERT INTO customers (type,name,contact,phone,credit_code,address) VALUES (?,?,?,?,?,?)",
              ("企业", "蓝海电子科技", "李经理", "13800000002", "91310000XXXXXXXX2", "苏州市..."))
    c.execute("INSERT INTO customers (type,name,contact,phone,id_number,address) VALUES (?,?,?,?,?,?)",
              ("个人", "张伟", "张伟", "13900000003", "320000000000000003", "园区宿舍"))
    c.execute("INSERT INTO customers (type,name,contact,phone,id_number,address) VALUES (?,?,?,?,?,?)",
              ("个人", "刘芳", "刘芳", "13900000004", "320000000000000004", "园区宿舍"))

    # 合同
    c.execute("INSERT INTO contracts (code,type,unit_id,customer_id,start_date,end_date,amount,pay_cycle,deposit,status,sign_date,note,lease_months,free_days,deposit_status) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("HT-L-0001", "租赁", 1, 1, "2026-01-01", "2026-12-31", 180000, "年", 15000, "生效", "2025-12-20", "厂房年租", 12, 0, "已收"))
    c.execute("INSERT INTO contracts (code,type,unit_id,customer_id,start_date,end_date,amount,pay_cycle,deposit,status,sign_date,note,lease_months,free_days,deposit_status) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("HT-L-0002", "租赁", 13, 3, "2026-03-01", "2027-02-28", 21600, "年", 2000, "生效", "2026-02-25", "公寓年租", 12, 0, "已收"))
    c.execute("INSERT INTO contracts (code,type,unit_id,customer_id,start_date,end_date,amount,pay_cycle,deposit,status,sign_date,note,lease_months,free_days,deposit_status) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("HT-S-0001", "销售", 3, 2, "2026-05-10", "2026-05-10", 3600000, "一次性", 0, "已售", "2026-05-10", "厂房出售", 0, 0, "不涉及"))

    # 单元状态联动
    c.execute("UPDATE units SET status='在租', current_contract_id=1, current_customer_id=1 WHERE id=1")
    c.execute("UPDATE units SET status='在租', current_contract_id=2, current_customer_id=3 WHERE id=13")
    c.execute("UPDATE units SET status='已售', current_contract_id=3, current_customer_id=2 WHERE id=3")

    # 账单（历史几期，含一笔欠费）
    c.execute("INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
              "VALUES (?,?,?,?,?,?,?,?,?,?)", (1, 1, 1, "租金", "2026-01", 15000, "2026-01-31", 15000, "已收", now()))
    c.execute("INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
              "VALUES (?,?,?,?,?,?,?,?,?,?)", (1, 1, 1, "物业", "2026-01", 2100, "2026-01-31", 2100, "已收", now()))
    c.execute("INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
              "VALUES (?,?,?,?,?,?,?,?,?,?)", (1, 1, 1, "租金", "2026-07", 15000, "2026-07-31", 0, "欠费", now()))
    c.execute("INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
              "VALUES (?,?,?,?,?,?,?,?,?,?)", (2, 13, 3, "租金", "2026-07", 1800, "2026-07-31", 1800, "已收", now()))
    c.execute("INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
              "VALUES (?,?,?,?,?,?,?,?,?,?)", (3, 3, 2, "房款", "2026-05", 3600000, "2026-05-31", 3600000, "已收", now()))
    # 已售厂房的物业费（业主交）
    c.execute("INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
              "VALUES (?,?,?,?,?,?,?,?,?,?)", (3, 3, 2, "物业", "2026-07", 2240, "2026-07-31", 0, "欠费", now()))
    # 公寓水电（本月抄表）
    c.execute("INSERT INTO meter_readings (unit_id,meter_type,prev_reading,curr_reading,usage,bill_month,bill_id) "
              "VALUES (?,?,?,?,?,?,?)", (13, "电", 1200, 1560, 360, "2026-07", None))
    c.execute("INSERT INTO meter_readings (unit_id,meter_type,prev_reading,curr_reading,usage,bill_month,bill_id) "
              "VALUES (?,?,?,?,?,?,?)", (13, "水", 80, 96, 16, "2026-07", None))
    electric_amt = 360 * ELECTRIC_RATE
    water_amt = 16 * WATER_RATE
    c.execute("INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
              "VALUES (?,?,?,?,?,?,?,?,?,?)", (2, 13, 3, "水电", "2026-07", electric_amt + water_amt, "2026-07-31", 0, "待收", now()))

    # 收款记录（让营收趋势有数据：房款 2026-05、公寓租金 2026-07）
    # 账单 id 顺序：1租金01 2物业01 3租金07(欠) 4公寓租金07 5房款05 6物业07(欠) 7水电07
    c.execute("INSERT INTO receipts (bill_id,amount,method,date,operator,voucher_no) VALUES (?,?,?,?,?,?)",
              (5, 3600000, "转账", "2026-05-15", "财务", "R-0001"))
    c.execute("INSERT INTO receipts (bill_id,amount,method,date,operator,voucher_no) VALUES (?,?,?,?,?,?)",
              (4, 1800, "线上", "2026-07-05", "财务", "R-0002"))

    # 押金台账（演示：两笔租赁押金已收）
    c.execute("INSERT INTO deposits (contract_id,unit_id,customer_id,amount,type,date,note) VALUES (?,?,?,?,?,?,?)",
              (1, 1, 1, 15000, "收", "2026-01-01", "厂房租赁押金"))
    c.execute("INSERT INTO deposits (contract_id,unit_id,customer_id,amount,type,date,note) VALUES (?,?,?,?,?,?,?)",
              (2, 13, 3, 2000, "收", "2026-03-01", "公寓租赁押金"))

    # 工单
    c.execute("INSERT INTO work_orders (code,unit_id,reporter,type,description,assignee,status,created_at,completed_at,rating) "
              "VALUES (?,?,?,?,?,?,?,?,?,?)",
              ("WO-0001", 13, "张伟", "报修", "卫生间水龙头漏水", "维修组-赵师傅", "处理中", now(), None, None))
    c.execute("INSERT INTO work_orders (code,unit_id,reporter,type,description,assignee,status,created_at,completed_at,rating) "
              "VALUES (?,?,?,?,?,?,?,?,?,?)",
              ("WO-0002", 1, "王总", "报修", "车间配电箱异响", "维修组-钱师傅", "待派", now(), None, None))
    c.execute("INSERT INTO work_orders (code,unit_id,reporter,type,description,assignee,status,created_at,completed_at,rating) "
              "VALUES (?,?,?,?,?,?,?,?,?,?)",
              ("WO-0003", 3, "李经理", "巡检", "月度消防巡检", "安保组", "已完成", now(), now(), 5))

    # 部门
    c.execute("INSERT INTO departments (code,name,parent_id,manager,sort) VALUES (?,?,?,?,?)",
              ("BM001", "总经办", None, "张总", 1))
    c.execute("INSERT INTO departments (code,name,parent_id,manager,sort) VALUES (?,?,?,?,?)",
              ("BM002", "招商部", None, "李经理", 2))
    c.execute("INSERT INTO departments (code,name,parent_id,manager,sort) VALUES (?,?,?,?,?)",
              ("BM003", "财务部", None, "王经理", 3))
    c.execute("INSERT INTO departments (code,name,parent_id,manager,sort) VALUES (?,?,?,?,?)",
              ("BM004", "物业部", None, "赵经理", 4))

    # 系统角色
    role_rows = [(1, "admin", "系统管理员", "全部权限", 1),
                 (2, "sales", "招商专员", "资产、客户、合同、租期", 2),
                 (3, "finance", "财务", "收费、收款、抄表、押金", 3),
                 (4, "property", "物业", "工单", 4),
                 (5, "leader", "园区领导", "只读看板", 5)]
    for rid, code, name, desc, sort in role_rows:
        c.execute("INSERT INTO sys_roles (id,code,name,description,sort) VALUES (?,?,?,?,?)",
                  (rid, code, name, desc, sort))

    # 人员
    users = [
        ("admin", "管理员", "13800000001", "admin@park.local", "系统管理员", 1, 1),
        ("sales1", "招商小李", "13800000002", "sales@park.local", "招商专员", 2, 2),
        ("finance1", "财务小王", "13800000003", "finance@park.local", "财务", 3, 3),
        ("property1", "物业小赵", "13800000004", "property@park.local", "物业", 4, 4),
        ("leader1", "园区领导", "13800000005", "leader@park.local", "园区领导", 5, 1),
    ]
    for u in users:
        c.execute("""INSERT INTO users
                     (username,name,phone,email,role,role_id,department_id,status)
                     VALUES (?,?,?,?,?,?,?,?)""",
                  (u[0], u[1], u[2], u[3], u[4], u[5], u[6], "启用"))

    # 权限配置（演示：给每个角色分配资源）
    resources = ["dashboard", "assets", "leases", "factories", "customers",
                 "contracts", "billing", "workorders", "system"]
    for rid in range(1, 6):
        for res in resources:
            allowed = 1 if rid == 1 else (0 if (rid == 5 and res == "system") else 1)
            c.execute("INSERT INTO role_permissions (role_id,resource,action,allowed) VALUES (?,?,?,?)",
                      (rid, res, "view", allowed))
            if rid == 1:
                c.execute("INSERT INTO role_permissions (role_id,resource,action,allowed) VALUES (?,?,?,?)",
                          (rid, res, "edit", 1))

    # 菜单
    menus = [
        ("dashboard", "看板", "📊", None, 1),
        ("assets", "资产台账", "🏢", None, 2),
        ("leases", "公寓管理", "🏠", None, 3),
        ("factories", "厂房管理", "🏭", None, 4),
        ("customers", "客户", "👥", None, 5),
        ("contracts", "合同", "📄", None, 6),
        ("billing", "收费", "💰", None, 7),
        ("workorders", "工单", "🔧", None, 8),
        ("system", "系统", "⚙️", None, 9),
        ("sys_users", "人员管理", "", 9, 1),
        ("sys_depts", "部门管理", "", 9, 2),
        ("sys_roles", "角色管理", "", 9, 3),
        ("sys_perms", "权限配置", "", 9, 4),
        ("sys_menus", "菜单管理", "", 9, 5),
        ("sys_calendar", "项目日历", "", 9, 6),
        ("sys_rules", "系统规则", "", 9, 7),
        ("sys_audit", "审计日志", "", 9, 8),
        ("sys_dict", "数据字典", "", 9, 9),
    ]
    for code, name, icon, parent, sort in menus:
        c.execute("INSERT INTO sys_menus (code,name,icon,parent_id,sort,visible) VALUES (?,?,?,?,?,?)",
                  (code, name, icon, parent, sort, 1))

    # 系统规则
    rules = [
        ("LEASE_NOTICE_DAYS", "租期到期提前提醒天数", "30", "到期前多少天开始提醒"),
        ("RENT_DUE_DAY", "租金账单截止日", "5", "每月几号为租金截止日"),
        ("LATE_FEE_RATE", "滞纳金比例(‰/天)", "1", "逾期每天收取的滞纳金比例"),
    ]
    for code, name, value, desc in rules:
        c.execute("INSERT INTO system_rules (code,name,value,description) VALUES (?,?,?,?)",
                  (code, name, value, desc))

    # 数据字典
    dicts = [
        ("contract_type", "租赁", "租赁", 1),
        ("contract_type", "销售", "销售", 2),
        ("unit_status", "空置", "空置", 1),
        ("unit_status", "在租", "在租", 2),
        ("unit_status", "在售", "在售", 3),
        ("unit_status", "已售", "已售", 4),
        ("bill_item", "租金", "租金", 1),
        ("bill_item", "物业费", "物业费", 2),
        ("bill_item", "水电费", "水电费", 3),
        ("bill_item", "房款", "房款", 4),
    ]
    for t, code, name, sort in dicts:
        c.execute("INSERT INTO data_dict (type,code,name,sort,enabled) VALUES (?,?,?,?,?)",
                  (t, code, name, sort, 1))

    # 审计日志
    logs = [
        ("admin", "登录", "系统", "管理员登录系统", "127.0.0.1", now()),
        ("sales1", "新增", "客户", "新增客户：宏达精密制造有限公司", "127.0.0.1", now()),
        ("finance1", "收款", "收费", "收取厂房租金 ¥15,000", "127.0.0.1", now()),
    ]
    for user, action, module, detail, ip, created in logs:
        c.execute("INSERT INTO audit_logs (user,action,module,detail,ip,created_at) VALUES (?,?,?,?,?,?)",
                  (user, action, module, detail, ip, created))

    conn.commit()


# ---------------------------------------------------------------------------
# 业务辅助
# ---------------------------------------------------------------------------
def recompute_bill_status(bill_id, conn):
    c = conn.cursor()
    b = c.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not b:
        return
    paid = b["paid_amount"] or 0
    if paid <= 0:
        status = "欠费" if b["due_date"] < today() else "待收"
    elif paid >= b["amount"]:
        status = "已收"
    else:
        status = "部分"
    c.execute("UPDATE bills SET status=? WHERE id=?", (status, bill_id))
    conn.commit()


def sync_bill_to_apartment(conn, bill_id):
    """收费账单变动后，同步到对应公寓出租记录：更新缴费状态 + 生成公寓收费台账。
    幂等：同一 bill_id 的公寓费用记录先删后插。"""
    c = conn.cursor()
    b = c.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not b:
        return
    # 定位资产单元类型（优先 unit_id，其次经 contract 反查）
    unit = None
    if b["unit_id"]:
        unit = c.execute("SELECT * FROM units WHERE id=?", (b["unit_id"],)).fetchone()
    if not unit and b["contract_id"]:
        ct = c.execute("SELECT * FROM contracts WHERE id=?", (b["contract_id"],)).fetchone()
        if ct:
            unit = c.execute("SELECT * FROM units WHERE id=?", (ct["unit_id"],)).fetchone()
    if not unit or unit["type"] != "公寓":
        return
    # 找关联出租记录（按合同）
    rentals = []
    if b["contract_id"]:
        rentals = c.execute("SELECT * FROM apartment_rentals WHERE contract_id=?",
                            (b["contract_id"],)).fetchall()
    if not rentals:
        return
    paid = b["paid_amount"] or 0
    amt = b["amount"] or 0
    if paid >= amt and amt > 0:
        pstat = "已缴"
    elif paid > 0:
        pstat = "部分"
    elif b["status"] == "欠费":
        pstat = "欠费"
    else:
        pstat = "待缴"
    # 账单状态 -> 公寓费用台账状态
    fee_status = {"已收": "已收", "部分": "已收", "欠费": "待收", "待收": "待收"}.get(b["status"], "待收")
    # 公寓收费口径：水电账单拆为「水费」「电费」两条（有抄表明细按明细拆分，否则合并为水电）
    if b["item_type"] == "水电":
        meter = c.execute("SELECT water_fee, electric_fee FROM meter_reading_records WHERE bill_id=?",
                          (bill_id,)).fetchone()
        if meter:
            wf = float(meter["water_fee"] or 0)
            ef = float(meter["electric_fee"] or 0)
            fee_rows = [("水费", wf), ("电费", ef)]
        else:
            fee_rows = [("水电", amt)]
    else:
        fee_rows = [(b["item_type"], amt)]
    fee_date = b["due_date"] or (b["created_at"] or now())[:10]
    c.execute("DELETE FROM apartment_fees WHERE bill_id=?", (bill_id,))
    for r in rentals:
        c.execute("UPDATE apartment_rentals SET payment_status=?, updated_at=? WHERE id=?",
                  (pstat, now(), r["id"]))
        for ftype, famt in fee_rows:
            if famt <= 0:
                continue
            c.execute(
                "INSERT INTO apartment_fees (room_id,rental_id,fee_type,amount,fee_date,pay_method,status,operator,note,source,bill_id,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["room_id"], r["id"], ftype, famt, fee_date,
                 "", fee_status, "", "中心收费同步", "收费", bill_id, now(), now()))
    conn.commit()


def sync_all_apartment_bills(conn):
    """全量同步：遍历所有公寓类账单，重建公寓收费台账与缴费状态。返回统计。"""
    c = conn.cursor()
    bills = c.execute(
        "SELECT b.* FROM bills b JOIN units u ON b.unit_id=u.id WHERE u.type='公寓'").fetchall()
    for b in bills:
        sync_bill_to_apartment(conn, b["id"])
    bills2 = c.execute(
        "SELECT b.* FROM bills b JOIN contracts ct ON b.contract_id=ct.id "
        "JOIN units u ON ct.unit_id=u.id WHERE u.type='公寓' AND b.unit_id IS NULL").fetchall()
    for b in bills2:
        sync_bill_to_apartment(conn, b["id"])
    n = c.execute("SELECT COUNT(*) AS n FROM apartment_fees WHERE source='收费'").fetchone()["n"]
    return {"synced_bills": n}


def generate_monthly_bills(month):
    """为所有生效中的租赁合同生成本月账单：厂房=租金+物业费，公寓=租金（水电按表单独出）。已存在则跳过。"""
    conn = get_db()
    c = conn.cursor()
    contracts = c.execute(
        "SELECT * FROM contracts WHERE type='租赁' AND status='生效'").fetchall()
    created = 0
    for ct in contracts:
        unit = c.execute("SELECT * FROM units WHERE id=?", (ct["unit_id"],)).fetchone()
        if not unit:
            continue
        # 租金所有租赁都收
        items = [("租金", unit["rent_price"])]
        # 物业费仅厂房按面积收取
        if unit["type"] == "厂房":
            prop_amt = round((unit["property_price"] or 0) * (unit["area"] or 0), 2)
            items.append(("物业", prop_amt))
        for item_type, amt in items:
            exists = c.execute(
                "SELECT id FROM bills WHERE contract_id=? AND item_type=? AND period=?",
                (ct["id"], item_type, month)).fetchone()
            if exists:
                continue
            due = f"{month}-28"
            c.execute(
                "INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ct["id"], ct["unit_id"], ct["customer_id"], item_type, month, amt, due, 0, "待收", now()))
            created += 1
    conn.commit()
    conn.close()
    return created


# ---------------------------------------------------------------------------
# HTTP 处理
# ---------------------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _db(self):
        return get_db()

    # ---- GET ----
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        def q(key):
            return qs.get(key, [None])[0]

        # 静态资源
        if path == "/" or path == "/index.html":
            return self._send_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
        if path.startswith("/static/"):
            f = os.path.basename(path)
            ext = os.path.splitext(f)[1]
            ctype = {"js": "application/javascript", "css": "text/css",
                     "html": "text/html", "svg": "image/svg+xml"}.get(ext[1:], "application/octet-stream")
            return self._send_file(os.path.join(STATIC_DIR, f), ctype)

        # API
        if path == "/api/dashboard":
            return self._send_json(self.api_dashboard())
        if path == "/api/buildings":
            return self._send_json(self.api_list("buildings"))
        if path == "/api/units":
            return self._send_json(self.api_units(q("status"), q("type"), q("building_id")))
        if path == "/api/factory-year-view":
            return self._send_json(self.api_factory_year_view(q("year")))
        if path == "/api/customers":
            return self._send_json(self.api_list("customers"))
        if path == "/api/contracts":
            return self._send_json(self.api_contracts(q("type"), q("status"), q("unit_id")))
        if path == "/api/bills":
            return self._send_json(self.api_bills(q("status"), q("item_type"), q("unit_id"), q("customer_id")))
        if path == "/api/meter-readings":
            return self._send_json(self.api_list("meter_readings"))
        if path == "/api/meter-records":
            return self._send_json(self.api_list("meter_reading_records"))
        if path == "/api/meter-units":
            return self._send_json(self.api_meter_units(q("biz")))
        if path == "/api/work-orders":
            return self._send_json(self.api_work_orders(q("status")))
        if path == "/api/roles":
            return self._send_json(ROLES)
        if path == "/api/leases":
            return self._send_json(self.api_leases(q("filter"), q("unit_type")))
        if path == "/api/leases/summary":
            return self._send_json(self.api_leases_summary())
        if path == "/api/factories":
            return self._send_json(self.api_factories(q("filter")))
        if path == "/api/factories/summary":
            return self._send_json(self.api_factories_summary())
        if path == "/api/apartments":
            return self._send_json(self.api_apartments(q("filter")))
        if path == "/api/apartments/summary":
            return self._send_json(self.api_apartments_summary())
        if path == "/api/apartment-records":
            return self._send_json(self.api_apartment_records(q("filter")))
        if path == "/api/apartment-records/summary":
            return self._send_json(self.api_apartment_records_summary())
        # 房间主档 + 出租记录（新模型）
        if path == "/api/apartment-rooms":
            return self._send_json(self.api_apartment_rooms())
        if path == "/api/apartment-rentals":
            return self._send_json(self.api_apartment_rentals(room_id=q("room_id"), year=q("year")))
        if path == "/api/apartment-rentals/summary":
            return self._send_json(self.api_apartment_rentals_summary())
        if path == "/api/apartment-year-view":
            return self._send_json(self.api_apartment_year_view(q("year")))
        if path == "/api/apartment-fees":
            return self._send_json(self.api_apartment_fees(room_id=q("room_id"), rental_id=q("rental_id")))
        if path == "/api/apartment-fees/summary":
            return self._send_json(self.api_apartment_fees_summary(room_id=q("room_id"), rental_id=q("rental_id")))
        if path == "/api/deposits":
            return self._send_json(self.api_deposits())
        # 商户管理
        if path == "/api/merchants":
            return self._send_json(self.api_list("merchants"))
        # 系统管理
        if path == "/api/users":
            return self._send_json(self.api_users())
        if path == "/api/departments":
            return self._send_json(self.api_departments())
        if path == "/api/sys_roles":
            return self._send_json(self.api_list("sys_roles"))
        if path == "/api/role_permissions":
            return self._send_json(self.api_role_permissions(q("role_id")))
        if path == "/api/sys_menus":
            return self._send_json(self.api_menus())
        if path == "/api/audit_logs":
            return self._send_json(self.api_list("audit_logs"))
        if path == "/api/system_rules":
            return self._send_json(self.api_list("system_rules"))
        if path == "/api/data_dict":
            return self._send_json(self.api_data_dict(q("type")))
        # 市场调研 / CRM
        if path == "/api/market-research":
            return self._send_json(self.api_list("market_research"))
        if path == "/api/crm/summary":
            return self._send_json(self.api_crm_summary())
        if path == "/api/crm/followups":
            return self._send_json(self.api_crm_followups(q("customer_id")))
        # 渠道分类（来自月度执行管控 Excel）
        if path == "/api/channels":
            return self._send_json(self.api_list("channels"))
        # 月度执行管控计划
        if path == "/api/crm-plans":
            return self._send_json(self.api_crm_plans(q("year")))
        # 月度执行管控看板聚合
        if path == "/api/crm/control":
            return self._send_json(self.api_crm_control(q("year") or str(datetime.date.today().year)))
        return self._send_json({"error": "not found"}, 404)

    # ---- POST / PUT ----
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._body()

        if path == "/api/buildings":
            return self._send_json(self.api_insert("buildings", body), 201)
        if path == "/api/units":
            return self._send_json(self.api_insert("units", body), 201)
        if path == "/api/customers":
            body = dict(body)
            # 新客户进入漏斗C类，记录创建时间与进入C类时间
            body["created_at"] = now()
            if not body.get("entered_c_date"):
                body["entered_c_date"] = now()
            return self._send_json(self.api_insert("customers", body), 201)
        if path == "/api/contracts":
            return self._send_json(self.api_insert_contract(body), 201)
        if path == "/api/bills/generate":
            month = body.get("month") or today()[:7]
            n = generate_monthly_bills(month)
            conn = self._db()
            sync_all_apartment_bills(conn)
            conn.close()
            return self._send_json({"created": n, "month": month, "apartment_synced": True})
        if path == "/api/bills":
            return self._send_json(self.api_insert("bills", body), 201)
        if path == "/api/meter-readings":
            return self._send_json(self.api_insert_meter(body), 201)
        if path == "/api/meter-records":
            return self._send_json(self.api_save_meter_record(body, None), 201)
        if path == "/api/work-orders":
            return self._send_json(self.api_insert("work_orders", body), 201)
        if path == "/api/reset":
            init_db()
            return self._send_json({"ok": True})
        if path.startswith("/api/bills/") and path.endswith("/receipt"):
            bid = path.split("/")[-2]
            return self._send_json(self.api_receipt(bid, body), 200)
        if path.startswith("/api/contracts/") and path.endswith("/renew"):
            cid = path.split("/")[-2]
            return self._send_json(self.api_renew_contract(cid, body), 201)
        if path.startswith("/api/contracts/") and path.endswith("/terminate"):
            cid = path.split("/")[-2]
            return self._send_json(self.api_terminate_contract(cid, body))
        if path == "/api/deposits":
            return self._send_json(self.api_insert("deposits", body), 201)
        # 商户管理
        if path == "/api/merchants":
            body = dict(body)
            body["created_at"] = now()
            body["updated_at"] = now()
            return self._send_json(self.api_insert("merchants", body), 201)
        if path == "/api/apartment-records":
            return self._send_json(self.api_insert_apartment(body), 201)
        # 房间主档 + 出租记录
        if path == "/api/apartment-rooms":
            return self._send_json(self.api_insert_apartment_room(body), 201)
        if path == "/api/apartment-rentals":
            return self._send_json(self.api_insert_apartment_rental(body), 201)
        if path == "/api/apartment-fees":
            return self._send_json(self.api_insert_apartment_fee(body), 201)
        if path == "/api/apartment-fees/batch":
            return self._send_json(self.api_create_apartment_fees_batch(body), 201)
        if path == "/api/apartment/sync":
            conn = self._db()
            res = sync_all_apartment_bills(conn)
            conn.close()
            return self._send_json({"ok": True, **res})
        # 系统管理
        if path == "/api/users":
            return self._send_json(self.api_insert("users", body), 201)
        if path == "/api/departments":
            return self._send_json(self.api_insert("departments", body), 201)
        if path == "/api/sys_roles":
            return self._send_json(self.api_insert("sys_roles", body), 201)
        if path == "/api/role_permissions":
            return self._send_json(self.api_insert("role_permissions", body), 201)
        if path == "/api/sys_menus":
            return self._send_json(self.api_insert("sys_menus", body), 201)
        if path == "/api/system_rules":
            return self._send_json(self.api_insert("system_rules", body), 201)
        if path == "/api/data_dict":
            return self._send_json(self.api_insert("data_dict", body), 201)
        # 市场调研 / CRM 跟进
        if path == "/api/market-research":
            return self._send_json(self.api_insert("market_research", body), 201)
        if path == "/api/crm/followups":
            return self._send_json(self.api_insert("crm_followups", body), 201)
        # 渠道分类 / 月度执行管控计划
        if path == "/api/channels":
            return self._send_json(self.api_insert("channels", body), 201)
        if path == "/api/crm-plans":
            return self._send_json(self.api_insert("crm_plans", body), 201)
        # 水电抄表 → 收费账单 联动
        if re.match(r"^/api/meter-records/\d+/bill$", path):
            mid = path.split("/")[-2]
            return self._send_json(self.api_meter_to_bill(int(mid)), 201)
        return self._send_json({"error": "not found"}, 404)

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._body()
        # 市场调研 / CRM 跟进
        if path.startswith("/api/market-research/"):
            uid = path.split("/")[-1]
            return self._send_json(self.api_update("market_research", uid, body))
        if path.startswith("/api/crm/followups/"):
            fid = path.split("/")[-1]
            return self._send_json(self.api_update("crm_followups", fid, body))
        # 客户（维护漏斗里程碑日期）
        if path.startswith("/api/customers/"):
            uid = path.split("/")[-1]
            return self._send_json(self.api_update_customer(uid, body))
        # 渠道分类 / 月度执行管控计划
        if path.startswith("/api/channels/"):
            uid = path.split("/")[-1]
            return self._send_json(self.api_update("channels", uid, body))
        if path.startswith("/api/crm-plans/"):
            uid = path.split("/")[-1]
            return self._send_json(self.api_update("crm_plans", uid, body))
        # /api/units/<id>
        if path.startswith("/api/units/"):
            uid = path.split("/")[-1]
            return self._send_json(self.api_update("units", uid, body))
        if path.startswith("/api/work-orders/"):
            wid = path.split("/")[-1]
            return self._send_json(self.api_update("work_orders", wid, body))
        if path.startswith("/api/apartment-records/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_update_apartment(rid, body))
        if path.startswith("/api/apartment-rooms/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_update_apartment_room(rid, body))
        if path.startswith("/api/apartment-rentals/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_update_apartment_rental(rid, body))
        if path.startswith("/api/apartment-fees/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_update_apartment_fee(rid, body))
        if path.startswith("/api/meter-records/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_save_meter_record(body, rid))
        # 商户管理
        if path.startswith("/api/merchants/"):
            rid = path.split("/")[-1]
            body = dict(body)
            body["updated_at"] = now()
            return self._send_json(self.api_update("merchants", rid, body))
        if path.startswith("/api/bills/") and path.endswith("/receipt"):
            bid = path.split("/")[-2]
            return self._send_json(self.api_receipt(bid, body))
        # 系统管理
        for table in ["users", "departments", "sys_roles", "role_permissions", "sys_menus", "system_rules", "data_dict"]:
            if path.startswith(f"/api/{table}/"):
                rid = path.split("/")[-1]
                return self._send_json(self.api_update(table, rid, body))
        return self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/market-research/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_delete("market_research", rid))
        if path.startswith("/api/crm/followups/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_delete("crm_followups", rid))
        if path.startswith("/api/apartment-records/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_delete("apartment_records", rid))
        if path.startswith("/api/apartment-rooms/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_delete_apartment_room(rid))
        if path.startswith("/api/apartment-rentals/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_delete("apartment_rentals", rid))
        if path.startswith("/api/apartment-fees/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_delete("apartment_fees", rid))
        if path.startswith("/api/meter-records/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_delete("meter_reading_records", rid))
        for table in ["users", "departments", "sys_roles", "role_permissions", "sys_menus", "system_rules", "data_dict"]:
            if path.startswith(f"/api/{table}/"):
                rid = path.split("/")[-1]
                return self._send_json(self.api_delete(table, rid))
        # 客户 / 渠道 / 月度计划
        if path.startswith("/api/customers/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_delete("customers", rid))
        if path.startswith("/api/channels/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_delete("channels", rid))
        # 商户管理
        if path.startswith("/api/merchants/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_delete("merchants", rid))
        if path.startswith("/api/crm-plans/"):
            rid = path.split("/")[-1]
            return self._send_json(self.api_delete("crm_plans", rid))
        return self._send_json({"error": "not found"}, 404)

    # ---- API 实现 ----
    def api_list(self, table):
        conn = self._db()
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY id DESC").fetchall()
        conn.close()
        return rows

    def api_insert(self, table, body):
        conn = self._db()
        c = conn.cursor()
        cols = [k for k in body if k != "id"]
        vals = [body[k] for k in cols]
        ph = ",".join("?" * len(cols))
        c.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph})", vals)
        conn.commit()
        new_id = c.lastrowid
        row = c.execute(f"SELECT * FROM {table} WHERE id=?", (new_id,)).fetchone()
        conn.close()
        return row

    def api_update(self, table, rid, body):
        conn = self._db()
        c = conn.cursor()
        cols = [k for k in body if k != "id"]
        sets = ",".join(f"{k}=?" for k in cols)
        vals = [body[k] for k in cols] + [rid]
        c.execute(f"UPDATE {table} SET {sets} WHERE id=?", vals)
        conn.commit()
        row = c.execute(f"SELECT * FROM {table} WHERE id=?", (rid,)).fetchone()
        conn.close()
        return row

    def api_delete(self, table, rid):
        conn = self._db()
        c = conn.cursor()
        c.execute(f"DELETE FROM {table} WHERE id=?", (rid,))
        conn.commit()
        conn.close()
        return {"ok": True}

    def api_update_customer(self, rid, body):
        conn = self._db()
        c = conn.cursor()
        cur = c.execute("SELECT stage FROM customers WHERE id=?", (rid,)).fetchone()
        cols = [k for k in body if k != "id"]
        sets = ",".join(f"{k}=?" for k in cols)
        vals = [body[k] for k in cols] + [rid]
        c.execute(f"UPDATE customers SET {sets} WHERE id=?", vals)
        # 维护漏斗里程碑日期（仅首次进入时记录，保留最早时间）
        new_stage = body.get("stage")
        if new_stage:
            if new_stage == "意向(B类)" and (not cur or cur["stage"] != "意向(B类)"):
                c.execute("UPDATE customers SET entered_b_date=? WHERE id=? AND (entered_b_date IS NULL OR entered_b_date='')", (now(), rid))
            if new_stage == "成单(A类)" and (not cur or cur["stage"] != "成单(A类)"):
                c.execute("UPDATE customers SET entered_a_date=? WHERE id=? AND (entered_a_date IS NULL OR entered_a_date='')", (now(), rid))
        conn.commit()
        row = c.execute("SELECT * FROM customers WHERE id=?", (rid,)).fetchone()
        conn.close()
        return row

    def api_crm_plans(self, year):
        conn = self._db()
        sql = "SELECT * FROM crm_plans"
        args = []
        if year:
            sql += " WHERE year=?"
            args.append(int(year))
        sql += " ORDER BY year, month, biz_type"
        rows = conn.execute(sql, args).fetchall()
        conn.close()
        return rows

    def api_crm_control(self, year):
        """月度执行管控看板聚合：销售/租赁双线，12 个月，
        实际值由客户里程碑日期自动算出，计划值来自 crm_plans。"""
        year = int(year)
        conn = self._db()
        c = conn.cursor()
        plans = c.execute("SELECT * FROM crm_plans WHERE year=?", (year,)).fetchall()
        plan_map = {(p["biz_type"], p["month"]): p for p in plans}
        result = {}
        for biz in ["销售", "租赁"]:
            months = []
            cum_C = cum_B = cum_A = 0
            for m in range(1, 13):
                mp = f"{year}-{m:02d}"
                a_C = c.execute("SELECT COUNT(*) AS n FROM customers WHERE biz_type=? AND substr(entered_c_date,1,7)=?", (biz, mp)).fetchone()["n"]
                a_B = c.execute("SELECT COUNT(*) AS n FROM customers WHERE biz_type=? AND substr(entered_b_date,1,7)=?", (biz, mp)).fetchone()["n"]
                a_A = c.execute("SELECT COUNT(*) AS n FROM customers WHERE biz_type=? AND substr(entered_a_date,1,7)=?", (biz, mp)).fetchone()["n"]
                p = plan_map.get((biz, m))
                cum_C += a_C; cum_B += a_B; cum_A += a_A
                months.append({
                    "month": m,
                    "plan_C": p["plan_C"] if p else 0,
                    "plan_B": p["plan_B"] if p else 0,
                    "plan_A": p["plan_A"] if p else 0,
                    "actual_C": a_C, "actual_B": a_B, "actual_A": a_A,
                    "cum_C": cum_C, "cum_B": cum_B, "cum_A": cum_A,
                    "rate_C": round(a_C / p["plan_C"], 4) if (p and p["plan_C"]) else None,
                    "rate_A": round(a_A / p["plan_A"], 4) if (p and p["plan_A"]) else None,
                    "cum_rate_A": round(cum_A / p["plan_A"], 4) if (p and p["plan_A"]) else None,
                    "conv_BA": round(a_A / a_B, 4) if a_B else None,
                    "cum_conv_BA": round(cum_A / cum_B, 4) if cum_B else None,
                })
            result[biz] = {"months": months}
        conn.close()
        return {"year": year, "biz_types": result}

    def api_users(self):
        conn = self._db()
        rows = conn.execute("""
            SELECT u.*, d.name AS department_name, r.name AS role_name
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            LEFT JOIN sys_roles r ON u.role_id = r.id
            ORDER BY u.id
        """).fetchall()
        conn.close()
        return rows

    def api_departments(self):
        conn = self._db()
        rows = conn.execute("SELECT * FROM departments ORDER BY sort, id").fetchall()
        conn.close()
        return rows

    def api_role_permissions(self, role_id):
        conn = self._db()
        sql = "SELECT * FROM role_permissions"
        args = []
        if role_id:
            sql += " WHERE role_id=?"
            args.append(role_id)
        sql += " ORDER BY role_id, resource"
        rows = conn.execute(sql, args).fetchall()
        conn.close()
        return rows

    def api_menus(self):
        conn = self._db()
        rows = conn.execute("SELECT * FROM sys_menus ORDER BY parent_id, sort, id").fetchall()
        conn.close()
        return rows

    def api_data_dict(self, dtype):
        conn = self._db()
        sql = "SELECT * FROM data_dict"
        args = []
        if dtype:
            sql += " WHERE type=?"
            args.append(dtype)
        sql += " ORDER BY type, sort, id"
        rows = conn.execute(sql, args).fetchall()
        conn.close()
        return rows

    def api_crm_summary(self):
        conn = self._db()
        c = conn.cursor()
        rows = c.execute("SELECT stage, source, next_follow FROM customers").fetchall()
        by_stage = {}
        by_source = {}
        for r in rows:
            st = r["stage"] or "线索"
            so = r["source"] or "其他"
            by_stage[st] = by_stage.get(st, 0) + 1
            by_source[so] = by_source.get(so, 0) + 1
        today = datetime.date.today().isoformat()
        due = 0
        for r in rows:
            if r["stage"] in ("成单(A类)", "流失"):
                continue
            if r["next_follow"] and r["next_follow"] <= today:
                due += 1
        conn.close()
        return {"total": len(rows), "by_stage": by_stage, "by_source": by_source, "follow_due": due}

    def api_crm_followups(self, customer_id):
        conn = self._db()
        sql = "SELECT * FROM crm_followups"
        args = []
        if customer_id:
            sql += " WHERE customer_id=?"
            args.append(customer_id)
        sql += " ORDER BY date DESC, id DESC"
        rows = conn.execute(sql, args).fetchall()
        conn.close()
        return rows

    def api_units(self, status, utype, building_id):
        conn = self._db()
        sql = "SELECT * FROM units WHERE 1=1"
        args = []
        if status:
            sql += " AND status=?"; args.append(status)
        if utype:
            sql += " AND type=?"; args.append(utype)
        if building_id:
            sql += " AND building_id=?"; args.append(building_id)
        sql += " ORDER BY code"
        rows = conn.execute(sql, args).fetchall()
        conn.close()
        return rows

    def api_contracts(self, ctype, status, unit_id=None):
        conn = self._db()
        sql = "SELECT ct.*, cu.name AS customer_name FROM contracts ct LEFT JOIN customers cu ON ct.customer_id=cu.id WHERE 1=1"
        args = []
        if ctype:
            sql += " AND ct.type=?"; args.append(ctype)
        if status:
            sql += " AND ct.status=?"; args.append(status)
        if unit_id:
            sql += " AND ct.unit_id=?"; args.append(unit_id)
        sql += " ORDER BY ct.id DESC"
        rows = conn.execute(sql, args).fetchall()
        conn.close()
        return rows

    def api_bills(self, status, item_type, unit_id, customer_id):
        conn = self._db()
        sql = "SELECT * FROM bills WHERE 1=1"
        args = []
        if status:
            sql += " AND status=?"; args.append(status)
        if item_type:
            sql += " AND item_type=?"; args.append(item_type)
        if unit_id:
            sql += " AND unit_id=?"; args.append(unit_id)
        if customer_id:
            sql += " AND customer_id=?"; args.append(customer_id)
        sql += " ORDER BY period DESC, id DESC"
        rows = conn.execute(sql, args).fetchall()
        conn.close()
        return rows

    def api_work_orders(self, status):
        conn = self._db()
        sql = "SELECT * FROM work_orders WHERE 1=1"
        args = []
        if status:
            sql += " AND status=?"; args.append(status)
        sql += " ORDER BY id DESC"
        rows = conn.execute(sql, args).fetchall()
        conn.close()
        return rows

    def api_insert_contract(self, body):
        conn = self._db()
        c = conn.cursor()
        cols = [k for k in body if k != "id"]
        vals = [body[k] for k in cols]
        ph = ",".join("?" * len(cols))
        c.execute(f"INSERT INTO contracts ({','.join(cols)}) VALUES ({ph})", vals)
        conn.commit()
        new_id = c.lastrowid
        ct = c.execute("SELECT * FROM contracts WHERE id=?", (new_id,)).fetchone()
        # 联动单元状态
        if ct["type"] == "销售" and ct["status"] == "已售":
            c.execute("UPDATE units SET status='已售', current_contract_id=?, current_customer_id=? WHERE id=?",
                      (new_id, ct["customer_id"], ct["unit_id"]))
            # 自动生成房款账单
            period = ct["sign_date"][:7] if ct.get("sign_date") else today()[:7]
            due = ct["sign_date"] if ct.get("sign_date") else today()
            c.execute(
                "INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (new_id, ct["unit_id"], ct["customer_id"], "房款", period, ct.get("amount", 0), due, 0, "待收", now()))
        elif ct["type"] == "租赁" and ct["status"] == "生效":
            c.execute("UPDATE units SET status='在租', current_contract_id=?, current_customer_id=? WHERE id=?",
                      (new_id, ct["customer_id"], ct["unit_id"]))
        conn.commit()
        conn.close()
        return ct

    def api_insert_meter(self, body):
        conn = self._db()
        c = conn.cursor()
        usage = (body.get("curr_reading") or 0) - (body.get("prev_reading") or 0)
        rate = ELECTRIC_RATE if body.get("meter_type") == "电" else WATER_RATE
        # 关联合同生成水电账单
        unit = c.execute("SELECT * FROM units WHERE id=?", (body["unit_id"],)).fetchone()
        contract = c.execute(
            "SELECT * FROM contracts WHERE unit_id=? AND type='租赁' AND status='生效' ORDER BY id DESC LIMIT 1",
            (body["unit_id"],)).fetchone()
        c.execute(
            "INSERT INTO meter_readings (unit_id,meter_type,prev_reading,curr_reading,usage,bill_month,bill_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (body["unit_id"], body["meter_type"], body["prev_reading"], body["curr_reading"], usage,
             body.get("bill_month"), None))
        mid = c.lastrowid
        # 生成/累计水电账单
        if contract:
            cust = contract["customer_id"]
            cid = contract["id"]
        else:
            cust = unit["current_customer_id"] if unit else None
            cid = unit["current_contract_id"] if unit else None
        amt = round(usage * rate, 2)
        month = body.get("bill_month")
        exist = c.execute(
            "SELECT * FROM bills WHERE contract_id=? AND item_type='水电' AND period=?",
            (cid, month)).fetchone() if cid else None
        if exist:
            new_amt = exist["amount"] + amt
            c.execute("UPDATE bills SET amount=? WHERE id=?", (new_amt, exist["id"]))
            bill_id = exist["id"]
        else:
            due = f"{month}-28"
            c.execute(
                "INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (cid, body["unit_id"], cust, "水电", month, amt, due, 0, "待收", now()))
            bill_id = c.lastrowid
        c.execute("UPDATE meter_readings SET bill_id=? WHERE id=?", (bill_id, mid))
        conn.commit()
        row = c.execute("SELECT * FROM meter_readings WHERE id=?", (mid,)).fetchone()
        conn.close()
        return row

    def api_save_meter_record(self, body, rid=None):
        """水电抄表台账：一行同时含水/电读数，自动计算用量与费用、生成编号、联动铺位编码。"""
        conn = self._db()
        c = conn.cursor()
        body = dict(body or {})
        wp = float(body.get("water_prev") or 0)
        wc = float(body.get("water_curr") or 0)
        wpr = float(body.get("water_price") or 0)
        ep = float(body.get("electric_prev") or 0)
        ec = float(body.get("electric_curr") or 0)
        epr = float(body.get("electric_price") or 0)
        wu = round(max(0, wc - wp), 2)
        eu = round(max(0, ec - ep), 2)
        wf = round(wu * wpr, 2)
        ef = round(eu * epr, 2)
        data = {
            "meter_no": body.get("meter_no") or "",
            "unit_id": body.get("unit_id") or None,
            "unit_code": body.get("unit_code") or "",
            "tenant_name": body.get("tenant_name") or "",
            "reading_date": body.get("reading_date") or today(),
            "bill_month": body.get("bill_month") or (body.get("reading_date") or today())[:7],
            "water_prev": wp, "water_curr": wc, "water_price": wpr,
            "water_usage": wu, "water_fee": wf,
            "electric_prev": ep, "electric_curr": ec, "electric_price": epr,
            "electric_usage": eu, "electric_fee": ef,
            "total_fee": round(wf + ef, 2),
        }
        # 自动联动铺位编码 / 租户名
        if data["unit_id"]:
            u = c.execute("SELECT code,current_customer_id FROM units WHERE id=?", (data["unit_id"],)).fetchone()
            if u:
                data["unit_code"] = u["code"]
                if not data["tenant_name"] and u["current_customer_id"]:
                    cust = c.execute("SELECT name FROM customers WHERE id=?", (u["current_customer_id"],)).fetchone()
                    if cust:
                        data["tenant_name"] = cust["name"]
        if rid:
            old = c.execute("SELECT * FROM meter_reading_records WHERE id=?", (rid,)).fetchone()
            if not old:
                conn.close(); return {"error": "not found"}
            merged = dict(old)
            for k in ("meter_no", "unit_id", "unit_code", "tenant_name", "reading_date", "bill_month",
                      "water_prev", "water_curr", "water_price", "electric_prev", "electric_curr", "electric_price"):
                if k in body and body[k] is not None:
                    merged[k] = body[k]
            wp = float(merged.get("water_prev") or 0); wc = float(merged.get("water_curr") or 0); wpr = float(merged.get("water_price") or 0)
            ep = float(merged.get("electric_prev") or 0); ec = float(merged.get("electric_curr") or 0); epr = float(merged.get("electric_price") or 0)
            wu = round(max(0, wc - wp), 2); eu = round(max(0, ec - ep), 2)
            wf = round(wu * wpr, 2); ef = round(eu * epr, 2)
            merged["water_usage"] = wu; merged["water_fee"] = wf
            merged["electric_usage"] = eu; merged["electric_fee"] = ef; merged["total_fee"] = round(wf + ef, 2)
            if merged.get("unit_id"):
                u = c.execute("SELECT code,current_customer_id FROM units WHERE id=?", (merged["unit_id"],)).fetchone()
                if u:
                    merged["unit_code"] = u["code"]
                    if not merged.get("tenant_name") and u["current_customer_id"]:
                        cust = c.execute("SELECT name FROM customers WHERE id=?", (u["current_customer_id"],)).fetchone()
                        if cust: merged["tenant_name"] = cust["name"]
            cols = ["meter_no", "unit_id", "unit_code", "tenant_name", "reading_date", "bill_month",
                    "water_prev", "water_curr", "water_price", "water_usage", "water_fee",
                    "electric_prev", "electric_curr", "electric_price", "electric_usage", "electric_fee", "total_fee"]
            sets = ",".join(f"{k}=?" for k in cols)
            vals = [merged.get(k) for k in cols] + [rid]
            c.execute(f"UPDATE meter_reading_records SET {sets} WHERE id=?", vals)
            new_id = rid
        else:
            # 生成编号：取最大编号+1
            if not data["meter_no"]:
                mx = c.execute("SELECT MAX(CAST(meter_no AS INTEGER)) AS m FROM meter_reading_records WHERE meter_no GLOB '0*'").fetchone()
                nxt = (mx["m"] or 0) + 1
                data["meter_no"] = str(nxt).zfill(5)
            cols = list(data.keys())
            ph = ",".join("?" * len(cols))
            c.execute(f"INSERT INTO meter_reading_records ({','.join(cols)},created_at) VALUES ({ph},?)",
                      [data[k] for k in cols] + [now()])
            new_id = c.lastrowid
        conn.commit()
        row = c.execute("SELECT * FROM meter_reading_records WHERE id=?", (new_id,)).fetchone()
        conn.close()
        return row

    def api_meter_to_bill(self, mid):
        """水电抄表 → 收费账单 联动：为一条抄表记录生成（或返回已有）一笔『水电』账单，
        挂到该单元当前生效合同/客户上，并回填 meter_reading_records.bill_id。
        计费金额 = 抄表 total_fee，周期 = 抄表 bill_month。"""
        conn = self._db()
        c = conn.cursor()
        m = c.execute("SELECT * FROM meter_reading_records WHERE id=?", (mid,)).fetchone()
        if not m:
            conn.close(); return {"error": "抄表记录不存在"}
        m = dict(m)
        # 已生成过账单
        if m.get("bill_id"):
            b = c.execute("SELECT * FROM bills WHERE id=?", (m["bill_id"],)).fetchone()
            if b:
                sync_bill_to_apartment(conn, m["bill_id"])  # 兼容历史账单：确保公寓收费已同步
                conn.commit()
                conn.close()
                return {"bill_id": m["bill_id"], "already": True, "bill": dict(b)}
        uid = m.get("unit_id")
        if not uid:
            conn.close(); return {"error": "该抄表记录未关联资产单元，无法生成账单"}
        u = c.execute("SELECT id,code,current_contract_id,current_customer_id FROM units WHERE id=?", (uid,)).fetchone()
        if not u:
            conn.close(); return {"error": "关联单元不存在"}
        u = dict(u)
        contract_id = u.get("current_contract_id")
        customer_id = u.get("current_customer_id")
        if not customer_id:
            conn.close(); return {"error": f"单元 {u.get('code')} 当前无关联客户，无法生成账单（请先维护租赁合同/客户）"}
        amount = float(m.get("total_fee") or 0)
        period = m.get("bill_month") or (m.get("reading_date") or today())[:7]
        c.execute(
            "INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (contract_id, uid, customer_id, "水电", period, amount,
             period + "-28" if len(period) == 7 else None, 0.0, "待收", now()))
        bill_id = c.lastrowid
        c.execute("UPDATE meter_reading_records SET bill_id=? WHERE id=?", (bill_id, mid))
        sync_bill_to_apartment(conn, bill_id)  # 方案B：同步写入公寓收费（水费/电费）
        conn.commit()
        row = c.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
        conn.close()
        return {"bill_id": bill_id, "already": False, "bill": dict(row) if row else None}

    def api_meter_units(self, biz=None):
        """水电抄表「应抄表单元」：以资产台账中签约生效的合同单元为基准，
        派生出 公寓租赁 / 厂房租赁 / 厂房销售 三类需抄表单元，并统计其抄表情况。
        与水电抄表记录(meter_reading_records)双向关联：unit_id 相同即关联。"""
        conn = self._db()
        c = conn.cursor()
        # 单元 + 当前生效/已售合同 + 合同客户；按合同类型与单元业态归类业务线
        sql = """
            SELECT u.id unit_id, u.code unit_code, u.type unit_type, u.status unit_status,
                   b.name building_name,
                   ct.id contract_id, ct.code contract_code, ct.type contract_type, ct.status contract_status,
                   k.name customer_name,
                   (SELECT COUNT(*) FROM meter_reading_records m WHERE m.unit_id = u.id) AS meter_count,
                   (SELECT MAX(m.bill_month) FROM meter_reading_records m WHERE m.unit_id = u.id) AS last_month
            FROM units u
            JOIN contracts ct ON ct.id = u.current_contract_id
            LEFT JOIN buildings b ON b.id = u.building_id
            LEFT JOIN customers k ON k.id = ct.customer_id
            WHERE (u.type='公寓' AND ct.type='租赁' AND ct.status='生效')
               OR (u.type='厂房' AND ct.type='租赁' AND ct.status='生效')
               OR (u.type='厂房' AND ct.type='销售')
            ORDER BY u.type, u.code
        """
        rows = c.execute(sql).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d["unit_type"] == "公寓":
                d["biz"] = "公寓租赁"
            elif d["contract_type"] == "租赁":
                d["biz"] = "厂房租赁"
            else:
                d["biz"] = "厂房销售"
            out.append(d)
        conn.close()
        if biz:
            out = [x for x in out if x["biz"] == biz]
        return out

    def api_receipt(self, bill_id, body):
        conn = self._db()
        c = conn.cursor()
        amt = float(body.get("amount", 0))
        c.execute(
            "INSERT INTO receipts (bill_id,amount,method,date,operator,voucher_no) VALUES (?,?,?,?,?,?)",
            (bill_id, amt, body.get("method"), body.get("date", today()),
             body.get("operator"), body.get("voucher_no")))
        b = c.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
        new_paid = (b["paid_amount"] or 0) + amt
        c.execute("UPDATE bills SET paid_amount=? WHERE id=?", (new_paid, bill_id))
        conn.commit()
        recompute_bill_status(bill_id, conn)
        sync_bill_to_apartment(conn, bill_id)
        row = c.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
        conn.close()
        return row

    def api_leases(self, lease_filter=None, unit_type=None):
        conn = self._db()
        sql = """SELECT ct.* FROM contracts ct JOIN units u ON ct.unit_id=u.id WHERE ct.type='租赁'"""
        args = []
        if lease_filter:
            sql += " AND ct.status=?"
            args.append(lease_filter)
        if unit_type:
            sql += " AND u.type=?"
            args.append(unit_type)
        sql += " ORDER BY ct.end_date"
        rows = conn.execute(sql, args).fetchall()
        today = datetime.date.today()
        enriched = []
        for r in rows:
            try:
                end = datetime.datetime.strptime(r["end_date"], "%Y-%m-%d").date()
            except Exception:
                end = today
            days = (end - today).days
            if r["status"] == "退租":
                stage = "已退租"
            elif r["status"] == "生效":
                if days < 0:
                    stage = "已过期"
                elif days <= 7:
                    stage = "7天内到期"
                elif days <= 30:
                    stage = "30天内到期"
                else:
                    stage = "正常"
            else:
                stage = r["status"]
            item = dict(r)
            item["days_left"] = days
            item["stage"] = stage
            enriched.append(item)
        conn.close()
        return enriched

    def api_leases_summary(self):
        conn = self._db()
        c = conn.cursor()
        today = datetime.date.today()
        rows = c.execute("""
            SELECT ct.* FROM contracts ct JOIN units u ON ct.unit_id=u.id
            WHERE ct.type='租赁' AND u.type='公寓'
        """).fetchall()
        active = [r for r in rows if r["status"] == "生效"]
        expiring7 = 0
        expiring30 = 0
        expired = 0
        for r in active:
            try:
                end = datetime.datetime.strptime(r["end_date"], "%Y-%m-%d").date()
            except Exception:
                continue
            days = (end - today).days
            if days < 0:
                expired += 1
            elif days <= 7:
                expiring7 += 1
            elif days <= 30:
                expiring30 += 1
        terminated = len([r for r in rows if r["status"] == "退租"])
        apartments = c.execute("SELECT COUNT(*) AS n FROM units WHERE type='公寓'").fetchone()["n"]
        rented = c.execute("SELECT COUNT(*) AS n FROM units WHERE type='公寓' AND status='在租'").fetchone()["n"]
        vacant = apartments - rented
        deposits = c.execute("""
            SELECT COALESCE(SUM(d.amount),0) AS s FROM deposits d
            JOIN contracts ct ON d.contract_id=ct.id
            JOIN units u ON ct.unit_id=u.id
            WHERE d.type='收' AND u.type='公寓'
        """).fetchone()["s"] or 0
        refunded = c.execute("""
            SELECT COALESCE(SUM(d.amount),0) AS s FROM deposits d
            JOIN contracts ct ON d.contract_id=ct.id
            JOIN units u ON ct.unit_id=u.id
            WHERE d.type='退' AND u.type='公寓'
        """).fetchone()["s"] or 0
        conn.close()
        return {
            "active": len(active), "expiring7": expiring7, "expiring30": expiring30,
            "expired": expired, "terminated": terminated,
            "apartments": apartments, "rented": rented, "vacant": vacant,
            "deposit_held": round(deposits - refunded, 2),
        }

    def api_factories_summary(self):
        conn = self._db()
        c = conn.cursor()
        total = c.execute("SELECT COUNT(*) AS n FROM units WHERE type='厂房'").fetchone()["n"]
        rented = c.execute("SELECT COUNT(*) AS n FROM units WHERE type='厂房' AND status='在租'").fetchone()["n"]
        vacant = c.execute("SELECT COUNT(*) AS n FROM units WHERE type='厂房' AND status='空置'").fetchone()["n"]
        for_sale = c.execute("SELECT COUNT(*) AS n FROM units WHERE type='厂房' AND (status='在售' OR status='空置') AND sellable=1").fetchone()["n"]
        sold = c.execute("SELECT COUNT(*) AS n FROM units WHERE type='厂房' AND status='已售'").fetchone()["n"]
        sale_contracts = c.execute("SELECT * FROM contracts WHERE type='销售'").fetchall()
        # 已售厂房中已回款
        sale_paid = 0
        sale_total = 0
        for sc in sale_contracts:
            bills = c.execute("SELECT * FROM bills WHERE contract_id=? AND item_type='房款'", (sc["id"],)).fetchall()
            sale_total += sum(b["amount"] for b in bills)
            sale_paid += sum(b["paid_amount"] for b in bills)
        conn.close()
        return {
            "total": total, "rented": rented, "vacant": vacant,
            "for_sale": for_sale, "sold": sold,
            "sale_total": round(sale_total, 2), "sale_paid": round(sale_paid, 2),
            "sale_unpaid": round(sale_total - sale_paid, 2),
        }

    def api_factories(self, factory_filter):
        conn = self._db()
        c = conn.cursor()
        today = datetime.date.today()
        rows = c.execute("""
            SELECT u.*, b.name AS building_name
            FROM units u LEFT JOIN buildings b ON u.building_id=b.id
            WHERE u.type='厂房'
            ORDER BY u.code
        """).fetchall()
        enriched = []
        for u in rows:
            item = dict(u)
            contract = None
            if u["current_contract_id"]:
                contract = c.execute("SELECT * FROM contracts WHERE id=?", (u["current_contract_id"],)).fetchone()
            customer = None
            if contract and contract["customer_id"]:
                customer = c.execute("SELECT * FROM customers WHERE id=?", (contract["customer_id"],)).fetchone()
            item["contract"] = dict(contract) if contract else None
            item["customer_name"] = customer["name"] if customer else ""
            # 租赁增强
            if contract and contract["type"] == "租赁":
                try:
                    end = datetime.datetime.strptime(contract["end_date"], "%Y-%m-%d").date()
                    days = (end - today).days
                except Exception:
                    days = None
                if contract["status"] == "退租":
                    stage = "已退租"
                elif contract["status"] == "生效":
                    if days is None:
                        stage = "正常"
                    elif days < 0:
                        stage = "已过期"
                    elif days <= 7:
                        stage = "7天内到期"
                    elif days <= 30:
                        stage = "30天内到期"
                    else:
                        stage = "正常"
                else:
                    stage = contract["status"]
                item["days_left"] = days
                item["stage"] = stage
            # 销售增强
            if contract and contract["type"] == "销售":
                bills = c.execute("SELECT * FROM bills WHERE contract_id=? AND item_type='房款'", (contract["id"],)).fetchall()
                total = sum(b["amount"] for b in bills)
                paid = sum(b["paid_amount"] for b in bills)
                item["sale_total"] = round(total, 2)
                item["sale_paid"] = round(paid, 2)
                item["sale_unpaid"] = round(total - paid, 2)
                item["sale_status"] = "已结清" if total > 0 and paid >= total else "回款中"
            enriched.append(item)
        conn.close()
        if factory_filter == "租赁":
            enriched = [x for x in enriched if x["contract"] and x["contract"]["type"] == "租赁"]
        elif factory_filter == "销售":
            enriched = [x for x in enriched if x["contract"] and x["contract"]["type"] == "销售"]
        return enriched

    def api_factory_year_view(self, year=None):
        """厂房按年视图：从 contracts 计算每栋厂房逐月占用。
        租赁：按 start_date→end_date 跨月铺满；销售：标记签约月为“已售”。
        同时覆盖厂房租赁与厂房销售两条线。"""
        if not year:
            year = str(datetime.date.today().year)
        conn = self._db()
        c = conn.cursor()
        units = c.execute("SELECT * FROM units WHERE type='厂房' ORDER BY code").fetchall()
        contracts = c.execute("""
            SELECT ct.*, cu.name AS customer_name
            FROM contracts ct LEFT JOIN customers cu ON ct.customer_id=cu.id
            WHERE ct.unit_id IN (SELECT id FROM units WHERE type='厂房')
              AND (
                (ct.type='租赁' AND (
                    strftime('%Y', ct.start_date)=?
                    OR strftime('%Y', ct.end_date)=?
                    OR (ct.start_date<=? AND (ct.end_date>=? OR ct.end_date='' OR ct.end_date IS NULL OR ct.end_date='至今'))
                ))
                OR (ct.type='销售' AND strftime('%Y', ct.start_date)=?)
              )
        """, (year, year, f"{year}-12-31", f"{year}-01-01", year)).fetchall()
        cells = {}
        for ct in contracts:
            ctype = ct.get("type")
            ci = ct.get("start_date") or ""
            co = ct.get("end_date") or ""
            if ctype == '租赁':
                if not ci:
                    continue
                try:
                    m_start = int(ci[5:7]) if ci >= f"{year}-01-01" else 1
                except Exception:
                    m_start = 1
                m_end = 12
                try:
                    if co and co <= f"{year}-12-31" and co >= f"{year}-01-01":
                        m_end = int(co[5:7])
                    elif co and co > f"{year}-12-31":
                        m_end = 12
                    elif not co or co in ('', '至今'):
                        m_end = 12
                except Exception:
                    m_end = 12
                for m in range(m_start, m_end + 1):
                    rec = dict(ct); rec["kind"] = "租赁"
                    cells.setdefault(ct["unit_id"], {})[m] = rec
            elif ctype == '销售':
                if not ci:
                    continue
                try:
                    m_sale = int(ci[5:7])
                except Exception:
                    continue
                rec = dict(ct); rec["kind"] = "销售"
                # 销售月：仅在该月无租赁占用时标记“已售”
                if not cells.get(ct["unit_id"], {}).get(m_sale):
                    cells.setdefault(ct["unit_id"], {})[m_sale] = rec
        out = []
        for u in units:
            u = dict(u)
            u["months"] = {m: cells.get(u["id"], {}).get(m) for m in range(1, 13)}
            out.append(u)
        conn.close()
        return {"year": year, "units": out}

    def api_apartments(self, apt_filter=None):
        conn = self._db()
        c = conn.cursor()
        today = datetime.date.today()
        rows = c.execute("""
            SELECT u.*, b.name AS building_name
            FROM units u LEFT JOIN buildings b ON u.building_id=b.id
            WHERE u.type='公寓'
            ORDER BY u.code
        """).fetchall()
        enriched = []
        for u in rows:
            item = dict(u)
            contract = None
            if u["current_contract_id"]:
                contract = c.execute("SELECT * FROM contracts WHERE id=?", (u["current_contract_id"],)).fetchone()
            customer = None
            if contract and contract["customer_id"]:
                customer = c.execute("SELECT * FROM customers WHERE id=?", (contract["customer_id"],)).fetchone()
            item["contract"] = dict(contract) if contract else None
            item["customer_name"] = customer["name"] if customer else ""
            if contract and contract["type"] == "租赁":
                try:
                    end = datetime.datetime.strptime(contract["end_date"], "%Y-%m-%d").date()
                    days = (end - today).days
                except Exception:
                    days = None
                if contract["status"] == "退租":
                    stage = "已退租"
                elif contract["status"] == "生效":
                    if days is None:
                        stage = "正常"
                    elif days < 0:
                        stage = "已过期"
                    elif days <= 7:
                        stage = "7天内到期"
                    elif days <= 30:
                        stage = "30天内到期"
                    else:
                        stage = "正常"
                else:
                    stage = contract["status"]
                item["days_left"] = days
                item["stage"] = stage
            enriched.append(item)
        conn.close()
        if apt_filter == "租赁":
            enriched = [x for x in enriched if x["contract"] and x["contract"]["type"] == "租赁"]
        return enriched

    def api_apartments_summary(self):
        return self.api_leases_summary()

    def api_apartment_records(self, status_filter=None):
        conn = self._db()
        c = conn.cursor()
        sql = "SELECT * FROM apartment_records WHERE 1=1"
        args = []
        if status_filter:
            sql += " AND room_status=?"
            args.append(status_filter)
        sql += " ORDER BY floor, room_no"
        rows = c.execute(sql, args).fetchall()
        enriched = []
        for r in rows:
            item = dict(r)
            item["stay_days"] = _calc_stay_days(item.get("check_in_date"), item.get("check_out_date"))
            enriched.append(item)
        conn.close()
        return enriched

    def api_apartment_records_summary(self):
        conn = self._db()
        c = conn.cursor()
        rows = c.execute("SELECT * FROM apartment_records").fetchall()
        total = len(rows)
        occupied = sum(1 for r in rows if r["room_status"] == "在住")
        vacant = sum(1 for r in rows if r["room_status"] == "空置")
        reserved = sum(1 for r in rows if r["room_status"] == "已预订")
        checkout = sum(1 for r in rows if r["room_status"] == "待退房")
        this_month = datetime.date.today().strftime("%Y-%m")
        new_this_month = sum(1 for r in rows if r["check_in_date"] and r["check_in_date"].startswith(this_month))
        deposit_total = sum(r["deposit"] or 0 for r in rows)
        rent_total = sum(r["monthly_rent"] or 0 for r in rows)
        pending_pay = sum(1 for r in rows if r["payment_status"] == "待缴")
        conn.close()
        return {
            "total": total, "occupied": occupied, "vacant": vacant,
            "reserved": reserved, "checkout": checkout,
            "new_this_month": new_this_month,
            "deposit_total": round(deposit_total, 2),
            "rent_total": round(rent_total, 2),
            "pending_pay": pending_pay,
        }

    def api_insert_apartment(self, body):
        body = dict(body)
        body["stay_days"] = _calc_stay_days(body.get("check_in_date"), body.get("check_out_date"))
        body["created_at"] = now()
        body["updated_at"] = now()
        return self.api_insert("apartment_records", body)

    def api_update_apartment(self, rid, body):
        body = dict(body)
        body["stay_days"] = _calc_stay_days(body.get("check_in_date"), body.get("check_out_date"))
        body["updated_at"] = now()
        return self.api_update("apartment_records", rid, body)

    # ---- 公寓新模型：房间主档 + 出租记录 ----
    def api_apartment_rooms(self):
        conn = self._db()
        c = conn.cursor()
        rooms = c.execute("SELECT * FROM apartment_rooms ORDER BY floor, room_no").fetchall()
        out = []
        for r in rooms:
            r = dict(r)
            # 当前在住记录（退房日期为空或晚于今天）
            today = datetime.date.today().isoformat()
            cur = c.execute(
                "SELECT * FROM apartment_rentals WHERE room_id=? ORDER BY check_in_date DESC LIMIT 1",
                (r["id"],)).fetchone()
            r["current"] = dict(cur) if cur else None
            out.append(r)
        conn.close()
        return out

    def api_apartment_rentals(self, room_id=None, year=None):
        conn = self._db()
        c = conn.cursor()
        sql = "SELECT * FROM apartment_rentals WHERE 1=1"
        args = []
        if room_id:
            sql += " AND room_id=?"
            args.append(room_id)
        if year:
            sql += " AND (strftime('%Y', check_in_date)=? OR strftime('%Y', check_out_date)=? OR (check_in_date<=? AND (check_out_date>=? OR check_out_date='' OR check_out_date IS NULL)))"
            args += [year, year, f"{year}-12-31", f"{year}-01-01"]
        sql += " ORDER BY check_in_date"
        rows = c.execute(sql, args).fetchall()
        enriched = []
        for r in rows:
            item = dict(r)
            item["stay_days"] = _calc_stay_days(item.get("check_in_date"), item.get("check_out_date"))
            enriched.append(item)
        conn.close()
        return enriched

    def api_apartment_rentals_summary(self):
        conn = self._db()
        c = conn.cursor()
        rooms = c.execute("SELECT COUNT(*) AS n FROM apartment_rooms").fetchone()["n"]
        rentals = c.execute("SELECT * FROM apartment_rentals").fetchall()
        today = datetime.date.today().isoformat()
        occupied_rooms = set()
        for r in rentals:
            ci, co = r["check_in_date"] or "", r["check_out_date"] or ""
            if ci and (not co or co >= today):
                occupied_rooms.add(r["room_id"])
        vacant = rooms - len(occupied_rooms)
        deposit_total = sum(r["deposit"] or 0 for r in rentals)
        rent_total = sum(r["monthly_rent"] or 0 for r in rentals)
        pending = sum(1 for r in rentals if r["payment_status"] == "待缴")
        conn.close()
        return {
            "total": rooms, "occupied": len(occupied_rooms), "vacant": vacant,
            "deposit_total": round(deposit_total, 2), "rent_total": round(rent_total, 2),
            "pending_pay": pending,
        }

    def api_apartment_year_view(self, year=None):
        if not year:
            year = str(datetime.date.today().year)
        conn = self._db()
        c = conn.cursor()
        rooms = c.execute("SELECT * FROM apartment_rooms ORDER BY floor, room_no").fetchall()
        rentals = c.execute(
            "SELECT * FROM apartment_rentals WHERE strftime('%Y', check_in_date)=? "
            "OR strftime('%Y', check_out_date)=? "
            "OR (check_in_date<=? AND (check_out_date>=? OR check_out_date='' OR check_out_date IS NULL))",
            (year, year, f"{year}-12-31", f"{year}-01-01")).fetchall()
        # 构造 房号 -> {月份: 出租记录}
        cells = {}
        for r in rentals:
            ci = r["check_in_date"] or ""
            co = r["check_out_date"] or ""
            if not ci:
                continue
            try:
                m_start = int(ci[5:7]) if ci >= f"{year}-01-01" else 1
            except Exception:
                m_start = 1
            m_end = 12
            try:
                if co and co <= f"{year}-12-31" and co >= f"{year}-01-01":
                    m_end = int(co[5:7])
                elif co and co > f"{year}-12-31":
                    m_end = 12
                elif not co:
                    m_end = 12
            except Exception:
                m_end = 12
            for m in range(m_start, m_end + 1):
                cells.setdefault(r["room_id"], {})[m] = dict(r)
        out = []
        for room in rooms:
            room = dict(room)
            room["months"] = {m: cells.get(room["id"], {}).get(m) for m in range(1, 13)}
            out.append(room)
        conn.close()
        return {"year": year, "rooms": out}

    def api_insert_apartment_room(self, body):
        body = dict(body)
        body["created_at"] = now()
        body["updated_at"] = now()
        return self.api_insert("apartment_rooms", body)

    def api_update_apartment_room(self, rid, body):
        body = dict(body)
        body["updated_at"] = now()
        return self.api_update("apartment_rooms", rid, body)

    def api_delete_apartment_room(self, rid):
        conn = self._db()
        c = conn.cursor()
        # 级联删除出租记录
        c.execute("DELETE FROM apartment_rentals WHERE room_id=?", (rid,))
        c.execute("DELETE FROM apartment_rooms WHERE id=?", (rid,))
        conn.commit()
        conn.close()
        return {"ok": True}

    def api_insert_apartment_rental(self, body):
        body = dict(body)
        body["stay_days"] = _calc_stay_days(body.get("check_in_date"), body.get("check_out_date"))
        body["created_at"] = now()
        body["updated_at"] = now()
        return self.api_insert("apartment_rentals", body)

    def api_update_apartment_rental(self, rid, body):
        body = dict(body)
        body["stay_days"] = _calc_stay_days(body.get("check_in_date"), body.get("check_out_date"))
        body["updated_at"] = now()
        return self.api_update("apartment_rentals", rid, body)

    def api_apartment_fees(self, room_id=None, rental_id=None):
        conn = self._db()
        c = conn.cursor()
        params = []
        where = ["1=1"]
        if room_id:
            where.append("f.room_id=?"); params.append(room_id)
        if rental_id:
            where.append("f.rental_id=?"); params.append(rental_id)
        sql = ("SELECT f.*, r.room_no "
               "FROM apartment_fees f "
               "LEFT JOIN apartment_rooms r ON f.room_id=r.id "
               "WHERE " + " AND ".join(where) + " ORDER BY f.fee_date DESC, f.id DESC")
        rows = c.execute(sql, params).fetchall()
        conn.close()
        return rows

    def api_apartment_fees_summary(self, room_id=None, rental_id=None):
        conn = self._db()
        c = conn.cursor()
        params = []
        where = ["1=1"]
        if room_id:
            where.append("room_id=?"); params.append(room_id)
        if rental_id:
            where.append("rental_id=?"); params.append(rental_id)
        sql = "SELECT * FROM apartment_fees WHERE " + " AND ".join(where)
        rows = c.execute(sql, params).fetchall()
        total = 0.0
        income = 0.0
        refund = 0.0
        by_type = {}
        for r in rows:
            amt = float(r["amount"] or 0)
            if r["status"] == "已退":
                refund += amt
            else:
                income += amt
                total += amt
            by_type[r["fee_type"] or "其他"] = by_type.get(r["fee_type"] or "其他", 0) + amt
        # 押金结余 = 收入类押金 - 退款类押金
        deposit_in = sum(float(r["amount"] or 0) for r in rows if r["fee_type"] == "押金" and r["status"] != "已退")
        deposit_out = sum(float(r["amount"] or 0) for r in rows if r["fee_type"] == "押金" and r["status"] == "已退")
        conn.close()
        return {
            "count": len(rows),
            "total": total,
            "income": income,
            "refund": refund,
            "deposit_balance": deposit_in - deposit_out,
            "by_type": by_type,
        }

    def api_insert_apartment_fee(self, body):
        body = dict(body)
        body["created_at"] = now()
        body["updated_at"] = now()
        return self.api_insert("apartment_fees", body)

    def api_create_apartment_fees_batch(self, body):
        items = body.get("items") or []
        if not items:
            return {"error": "empty batch"}
        conn = self._db()
        c = conn.cursor()
        created = []
        try:
            for item in items:
                item = dict(item)
                item["created_at"] = now()
                item["updated_at"] = now()
                cols = [k for k in item if k != "id"]
                vals = [item[k] for k in cols]
                ph = ",".join("?" * len(cols))
                c.execute(f"INSERT INTO apartment_fees ({','.join(cols)}) VALUES ({ph})", vals)
                new_id = c.lastrowid
                row = c.execute("SELECT * FROM apartment_fees WHERE id=?", (new_id,)).fetchone()
                created.append(row)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()
        return {"created": created, "count": len(created)}

    def api_update_apartment_fee(self, rid, body):
        body = dict(body)
        body["updated_at"] = now()
        return self.api_update("apartment_fees", rid, body)

    def api_deposits(self):
        conn = self._db()
        rows = conn.execute(
            "SELECT d.*, u.code AS unit_code, b.name AS building_name "
            "FROM deposits d "
            "LEFT JOIN units u ON d.unit_id = u.id "
            "LEFT JOIN buildings b ON u.building_id = b.id "
            "ORDER BY d.id DESC").fetchall()
        conn.close()
        return rows

    def api_renew_contract(self, cid, body):
        conn = self._db()
        c = conn.cursor()
        old = c.execute("SELECT * FROM contracts WHERE id=?", (cid,)).fetchone()
        if not old:
            return {"error": "contract not found"}
        # 旧合同到期
        c.execute("UPDATE contracts SET status='到期', actual_end_date=? WHERE id=?",
                  (old["end_date"], cid))
        # 创建新合同
        new_code = body.get("code") or (old["code"] + "-续")
        c.execute(
            "INSERT INTO contracts (code,type,unit_id,customer_id,start_date,end_date,amount,pay_cycle,deposit,status,sign_date,note,lease_months,free_days,deposit_status,original_contract_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (new_code, "租赁", old["unit_id"], old["customer_id"],
             body.get("start_date"), body.get("end_date"), body.get("amount", old["amount"]),
             body.get("pay_cycle", old["pay_cycle"]), body.get("deposit", old["deposit"]),
             "生效", today(), body.get("note", "续租"), body.get("lease_months"), 0, "已收", cid))
        new_id = c.lastrowid
        c.execute("UPDATE units SET current_contract_id=?, current_customer_id=? WHERE id=?",
                  (new_id, old["customer_id"], old["unit_id"]))
        conn.commit()
        row = c.execute("SELECT * FROM contracts WHERE id=?", (new_id,)).fetchone()
        conn.close()
        return row

    def api_terminate_contract(self, cid, body):
        conn = self._db()
        c = conn.cursor()
        ct = c.execute("SELECT * FROM contracts WHERE id=?", (cid,)).fetchone()
        if not ct:
            return {"error": "contract not found"}
        move_out = body.get("actual_end_date") or today()
        # 更新合同状态
        c.execute(
            "UPDATE contracts SET status='退租', actual_end_date=?, move_out_reason=?, deposit_status=? WHERE id=?",
            (move_out, body.get("move_out_reason", "到期退租"), body.get("deposit_status", "待退"), cid))
        # 单元置空
        c.execute("UPDATE units SET status='空置', current_contract_id=NULL, current_customer_id=NULL WHERE id=?",
                  (ct["unit_id"],))
        # 押金处理
        dep_type = body.get("deposit_action")
        dep_amt = float(body.get("deposit_amount") or 0)
        if dep_type and dep_amt:
            c.execute(
                "INSERT INTO deposits (contract_id,unit_id,customer_id,amount,type,date,note) VALUES (?,?,?,?,?,?,?)",
                (cid, ct["unit_id"], ct["customer_id"], dep_amt,
                 dep_type, today(), body.get("deposit_note", "退租结算")))
        # 末月租金按天结算（如果设置了金额）
        final_rent = body.get("final_rent")
        if final_rent is not None:
            due = today()[:8] + "28"
            c.execute(
                "INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (cid, ct["unit_id"], ct["customer_id"], "租金", move_out[:7], float(final_rent), due, 0, "待收", now()))
        # 末月水电（如果设置了）
        final_util = body.get("final_utility")
        if final_util is not None:
            due = today()[:8] + "28"
            c.execute(
                "INSERT INTO bills (contract_id,unit_id,customer_id,item_type,period,amount,due_date,paid_amount,status,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (cid, ct["unit_id"], ct["customer_id"], "水电", move_out[:7], float(final_util), due, 0, "待收", now()))
        conn.commit()
        row = c.execute("SELECT * FROM contracts WHERE id=?", (cid,)).fetchone()
        conn.close()
        return row

    def api_dashboard(self):
        conn = self._db()
        c = conn.cursor()
        units = c.execute("SELECT * FROM units").fetchall()
        total = len(units)
        by_status = {}
        for u in units:
            by_status[u["status"]] = by_status.get(u["status"], 0) + 1

        # 按业态分组
        factory_units = [u for u in units if u["type"] == "厂房"]
        apt_units = [u for u in units if u["type"] == "公寓"]

        def _kpis(us, can_sell=False):
            rentable = [u for u in us if u["rentable"]]
            st = {}
            for u in us:
                st[u["status"]] = st.get(u["status"], 0) + 1
            rented = st.get("在租", 0)
            sold = st.get("已售", 0)
            vacant = st.get("空置", 0)
            # 销售去化率：已售 / (已售 + 仍可售)，已售单元不再重复计入可售分母
            available_for_sale = [u for u in us if u["sellable"] and u["status"] in ("空置", "在售")]
            sale_total_units = sold + len(available_for_sale)
            return {
                "total": len(us),
                "rentable": len(rentable),
                "available_for_sale": len(available_for_sale),
                "rented": rented,
                "sold": sold,
                "vacant": vacant,
                "lease_rate": round(rented / len(rentable) * 100, 1) if rentable else 0,
                "sale_rate": round(sold / sale_total_units * 100, 1) if sale_total_units else 0,
            }

        factory = _kpis(factory_units, can_sell=True)
        apt = _kpis(apt_units, can_sell=False)

        # 间夜出租率（当年实际占用间夜 / 365*房间数）
        def _night_rate(unit_type):
            today = datetime.date.today()
            year_start = datetime.date(today.year, 1, 1)
            year_end = datetime.date(today.year, 12, 31)
            days_in_year = (year_end - year_start).days + 1
            unit_rows = c.execute("SELECT id FROM units WHERE type = ?", (unit_type,)).fetchall()
            total_units = len(unit_rows)
            if total_units == 0:
                return {"night_rate": 0, "occupied_nights": 0, "total_nights": 0}
            contracts = c.execute("""
                SELECT ct.start_date, ct.end_date
                FROM contracts ct
                JOIN units u ON ct.unit_id = u.id
                WHERE u.type = ? AND ct.type = '租赁'
            """, (unit_type,)).fetchall()
            occupied = 0
            for ct in contracts:
                if not ct["start_date"] or not ct["end_date"]:
                    continue
                try:
                    sd = datetime.datetime.strptime(ct["start_date"], "%Y-%m-%d").date()
                    ed = datetime.datetime.strptime(ct["end_date"], "%Y-%m-%d").date()
                except ValueError:
                    continue
                start = max(sd, year_start)
                end = min(ed, year_end)
                if start <= end:
                    occupied += (end - start).days + 1
            total_nights = total_units * days_in_year
            rate = round(occupied / total_nights * 100, 1) if total_nights else 0
            return {"night_rate": rate, "occupied_nights": occupied, "total_nights": total_nights}

        factory_night = _night_rate("厂房")
        apt_night = _night_rate("公寓")
        total_nights_all = factory_night["total_nights"] + apt_night["total_nights"]
        occupied_all = factory_night["occupied_nights"] + apt_night["occupied_nights"]
        overall_night_rate = round(occupied_all / total_nights_all * 100, 1) if total_nights_all else 0

        # 收费：按 unit 类型汇总（通过 bills → units）
        def _financial(unit_type):
            rows = c.execute("""
                SELECT b.amount, b.paid_amount
                FROM bills b
                JOIN units u ON b.unit_id = u.id
                WHERE u.type = ?
            """, (unit_type,)).fetchall()
            ar = sum(r["amount"] or 0 for r in rows)
            paid = sum(r["paid_amount"] or 0 for r in rows)
            arr = sum((r["amount"] or 0) - (r["paid_amount"] or 0)
                      for r in rows if (r["amount"] or 0) > (r["paid_amount"] or 0))
            return {
                "ar": round(ar, 2),
                "paid": round(paid, 2),
                "arrears": round(arr, 2),
                "collection_rate": round(paid / ar * 100, 1) if ar else 0,
            }

        factory_fin = _financial("厂房")
        apt_fin = _financial("公寓")

        wos = c.execute("SELECT status, COUNT(*) AS n FROM work_orders GROUP BY status").fetchall()
        wo_stat = {w["status"]: w["n"] for w in wos}

        # 营收趋势（近 6 个月实收，按自然月去重）
        months = []
        y, m = datetime.date.today().year, datetime.date.today().month
        for i in range(5, -1, -1):
            mm = m - i
            yy = y
            while mm <= 0:
                mm += 12
                yy -= 1
            months.append(f"{yy}-{mm:02d}")
        trend = []
        for m in months:
            recs = c.execute(
                "SELECT COALESCE(SUM(amount),0) AS s FROM receipts WHERE date LIKE ?", (m + "%",)).fetchall()
            trend.append({"month": m, "amount": recs[0]["s"] if recs else 0})

        # 业态分布
        type_stat = {}
        for u in units:
            type_stat[u["type"]] = type_stat.get(u["type"], 0) + 1

        # 整体指标（兼容旧看板字段）
        total_rentable = factory["rentable"] + apt["rentable"]
        total_rented = factory["rented"] + apt["rented"]
        total_sold = factory["sold"] + apt["sold"]
        total_vacant = factory["vacant"] + apt["vacant"]
        total_available_for_sale = factory["available_for_sale"] + apt["available_for_sale"]
        total_sellable_units = total_sold + total_available_for_sale

        conn.close()
        return {
            "total_units": total,
            "by_status": by_status,
            "factory": {**factory, **factory_fin, **factory_night},
            "apartment": {**apt, **apt_fin, **apt_night},
            "night_rate": overall_night_rate,
            "occupied_nights": occupied_all,
            "total_nights": total_nights_all,
            "total_ar": round(factory_fin["ar"] + apt_fin["ar"], 2),
            "total_paid": round(factory_fin["paid"] + apt_fin["paid"], 2),
            "arrears": round(factory_fin["arrears"] + apt_fin["arrears"], 2),
            "collection_rate": round((factory_fin["paid"] + apt_fin["paid"]) /
                                      (factory_fin["ar"] + apt_fin["ar"]) * 100, 1) if (factory_fin["ar"] + apt_fin["ar"]) else 0,
            "lease_rate": round(total_rented / total_rentable * 100, 1) if total_rentable else 0,
            "sale_rate": round(total_sold / total_sellable_units * 100, 1) if total_sellable_units else 0,
            "rented": total_rented, "sold": total_sold, "vacant": total_vacant,
            "work_orders": wo_stat,
            "revenue_trend": trend,
            "type_stat": type_stat,
        }

    def log_message(self, *args):
        pass  # 静默日志


def main():
    init_db()
    port = int(os.environ.get("PORT", 8000))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", port), Handler) as httpd:
        print(f"园区资管系统已启动 -> http://localhost:{port}  (数据文件: {DB_PATH})")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
