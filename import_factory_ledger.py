#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导入《中兴通物业台账.xlsx》中的「厂房租售台账」到园区系统资产台账。
- 新建 17 栋厂房楼栋 buildings(type=厂房, code=FW1..FW17)
- 按「楼号 / 户号 / 面积 / 房间状态」新建资产单元 units(type=厂房) -> 资产台账
- 状态映射(已售/在租/空置/自持)，原始台账状态保留在 units.note
- 楼栋 total_area = 该楼栋面积合计
幂等：以 building.code(FWx) / unit.code(FWx-户号) 去重，重复执行安全（刷新最新台账）。
"""
import sqlite3
import os
import re
import openpyxl

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "park.db")
XLSX = "/Users/yangtao/Desktop/中兴通物业台账.xlsx"

# 原始房间状态 -> (系统status, sellable, rentable, note)
STATUS_MAP = {
    "已售": ("已售", 0, 0, "已售"),
    "已售（玻璃厂转租）": ("已售", 0, 0, "已售·玻璃厂转租"),
    "已租": ("在租", 0, 1, "已租"),
    "自持（已租）": ("在租", 0, 1, "自持·已出租"),
    "空置": ("空置", 1, 1, "空置"),
    "空置（玻璃厂自用）": ("自持", 0, 0, "空置·玻璃厂自用"),
    "自持（空置）": ("自持", 0, 0, "自持·空置待启用"),
    "自持公寓": ("自持", 0, 0, "自持公寓"),
}


def ensure_columns(conn):
    c = conn.cursor()
    cols = {r["name"] for r in c.execute("PRAGMA table_info(units)").fetchall()}
    if "note" not in cols:
        try:
            c.execute("ALTER TABLE units ADD COLUMN note TEXT")
        except Exception:
            pass
    conn.commit()


def sanitize_code_part(h):
    """户号 -> 安全的 code 片段。整栋为空 -> '整栋'；'2层、3层' -> '2层-3层'。"""
    s = str(h).strip()
    if not s:
        return "整栋"
    s = s.replace("、", "-").replace("，", "-").replace(",", "-").replace("／", "-").replace("/", "-")
    return s


def parse_floor(h):
    """从户号推断楼层（如 101->1, 201->2, 2层-3层->2）。无法推断返回 0。"""
    s = str(h).strip()
    m = re.match(r"(\d+)", s)
    if m:
        return int(m.group(1))
    return 0


def read_rows():
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    ws = wb["Sheet1"]
    rows = []
    last_b = None
    for r in ws.iter_rows(min_row=3, values_only=True):  # 跳过空行1 + 表头行2
        b, h, a, s = (r + (None, None, None, None))[:4]
        if b not in (None, ""):
            last_b = str(b).strip()
        building = last_b
        house = "" if h is None else str(h).strip()
        area = a
        status = "" if s is None else str(s).strip()
        if building is None:
            continue
        if house == "" and (area in (None, "", 0)) and status == "":
            continue
        area_v = 0.0
        if area not in (None, ""):
            try:
                area_v = float(area)
            except Exception:
                area_v = 0.0
        rows.append((building, house, area_v, status))
    return rows


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    ensure_columns(conn)

    rows = read_rows()
    # 按楼号分组
    by_bld = {}
    for b, h, a, s in rows:
        by_bld.setdefault(b, []).append((h, a, s))

    report = []
    total_units = 0
    for bnum in sorted(by_bld.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        items = by_bld[bnum]
        code = f"FW{bnum}"
        name = f"{bnum}号厂房"
        b = c.execute("SELECT * FROM buildings WHERE code=?", (code,)).fetchone()
        total_area = round(sum(a for _, a, _ in items), 2)
        max_floor = 0
        for h, _, _ in items:
            f = parse_floor(h)
            if f > max_floor:
                max_floor = f
        floors = max_floor if max_floor > 0 else 1
        if not b:
            c.execute(
                "INSERT INTO buildings (code,name,type,address,floors,total_area) VALUES (?,?,?,?,?,?)",
                (code, name, "厂房", "园区", floors, total_area))
            bid = c.lastrowid
            report.append(f"[新建楼栋] {name} (id={bid}, 面积合计 {total_area})")
        else:
            bid = b["id"]
            c.execute("UPDATE buildings SET floors=?, total_area=? WHERE id=?", (floors, total_area, bid))
            report.append(f"[更新楼栋] {name} (id={bid}, 面积合计 {total_area})")

        added = updated = 0
        for h, a, s in sorted(items, key=lambda x: (parse_floor(x[0]), x[0])):
            cp = sanitize_code_part(h)
            ucode = f"{code}-{cp}"
            status_sys, sellable, rentable, note = STATUS_MAP.get(s, ("空置", 1, 1, s or ""))
            ex = c.execute("SELECT * FROM units WHERE code=?", (ucode,)).fetchone()
            if ex:
                c.execute(
                    "UPDATE units SET building_id=?, type='厂房', area=?, sellable=?, rentable=?, status=?, note=? WHERE id=?",
                    (bid, a, sellable, rentable, status_sys, note, ex["id"]))
                updated += 1
            else:
                c.execute(
                    "INSERT INTO units (code,building_id,type,area,rent_price,property_price,sellable,rentable,status,note) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (ucode, bid, "厂房", a, 0, 0, sellable, rentable, status_sys, note))
                added += 1
            total_units += 1
        report.append(f"  └ 单元 {len(items)} 户 | 新建 {added} | 更新 {updated}")
        conn.commit()

    report.append(f"\n合计：楼栋 {len(by_bld)} 栋 | 资产单元 {total_units} 户")
    conn.close()
    print("\n".join(report))
    print("厂房租售台账导入完成。")


if __name__ == "__main__":
    main()
