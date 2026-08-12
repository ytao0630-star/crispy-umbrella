#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导入《三号楼/八号楼公寓入住人员信息台账》到园区系统。
- 新建楼栋 buildings(type=公寓)
- 新建资产单元 units(type=公寓, 挂楼栋, status=在住) -> 资产台账
- 新建公寓房间主档 apartment_rooms(挂 unit_id)
- 新建占用出租记录 apartment_rentals(check_in=今日, occupancy_count=人数)
幂等：以 unit.code / (room_no,unit_id) / (room_id,未退房) 去重，重复执行安全。
"""
import xlrd
import sqlite3
import os
import datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "park.db")
FILES = {
    "三号楼": "/Users/yangtao/Desktop/1.三号楼公寓入住人员信息台账~~.xls",
    "八号楼": "/Users/yangtao/Desktop/1.八号楼公寓入住人员信息台账~~.xls",
}
BUILDING_NUM = {"三号楼": "3", "八号楼": "8"}
CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

NOW = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
TODAY = datetime.date.today().isoformat()


def ensure_columns(conn):
    c = conn.cursor()
    for sql in (
        "ALTER TABLE apartment_rentals ADD COLUMN contract_id INTEGER",
        "ALTER TABLE apartment_fees ADD COLUMN source TEXT DEFAULT '手工'",
        "ALTER TABLE apartment_fees ADD COLUMN bill_id INTEGER",
        "ALTER TABLE apartment_rooms ADD COLUMN unit_id INTEGER",
    ):
        try:
            c.execute(sql)
        except Exception:
            pass
    conn.commit()


def floor_to_num(v):
    s = str(v).strip()
    if not s:
        return ""
    ch = s[0]
    if ch in CN_NUM:
        return str(CN_NUM[ch])
    try:
        return str(int(float(s)))
    except Exception:
        return s


def room_to_str(v):
    s = str(v).strip()
    try:
        return str(int(float(s)))
    except Exception:
        return s


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    ensure_columns(conn)

    report = []
    for bname, fpath in FILES.items():
        if not os.path.exists(fpath):
            report.append(f"[跳过] 文件不存在: {fpath}")
            continue
        bnum = BUILDING_NUM.get(bname, bname)
        # 楼栋
        b = c.execute("SELECT * FROM buildings WHERE name=?", (bname,)).fetchone()
        if not b:
            c.execute(
                "INSERT INTO buildings (code,name,type,address,floors,total_area) VALUES (?,?,?,?,?,?)",
                (bnum, bname, "公寓", "园区公寓", 12, 0))
            bid = c.lastrowid
            report.append(f"[新建楼栋] {bname} (id={bid})")
        else:
            bid = b["id"]

        # 解析房间
        wb = xlrd.open_workbook(fpath)
        rooms = {}
        for sh in wb.sheets():
            for i in range(2, sh.nrows):
                rv = sh.cell_value(i, 2)
                if rv == "" or rv is None:
                    continue
                room_no = room_to_str(rv)
                floor = floor_to_num(sh.cell_value(i, 1))
                key = (floor, room_no)
                rooms[key] = rooms.get(key, 0) + 1

        added_units = added_rooms = added_rentals = 0
        for (floor, room_no), cnt in sorted(rooms.items(), key=lambda x: (int(x[0][0]) if x[0][0].isdigit() else 99, x[0][1])):
            code = f"{bnum}-{room_no}"
            ex = c.execute("SELECT * FROM units WHERE code=?", (code,)).fetchone()
            if ex:
                uid = ex["id"]
                c.execute("UPDATE units SET type='公寓', building_id=?, status='在住', rentable=1 WHERE id=?",
                          (bid, uid))
            else:
                c.execute(
                    "INSERT INTO units (code,building_id,type,area,rent_price,property_price,sellable,rentable,status) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (code, bid, "公寓", 45, 0, 2.5, 0, 1, "在住"))
                uid = c.lastrowid
                added_units += 1

            rm = c.execute("SELECT * FROM apartment_rooms WHERE room_no=? AND unit_id=?",
                           (room_no, uid)).fetchone()
            if rm:
                rid = rm["id"]
                c.execute("UPDATE apartment_rooms SET floor=?, unit_id=? WHERE id=?", (floor, uid, rid))
            else:
                c.execute(
                    "INSERT INTO apartment_rooms (floor,room_no,room_category,orientation,meter_no,room_note,unit_id,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (floor, room_no, "标准间", "", "", f"入住台账导入·{cnt}人", uid, NOW, NOW))
                rid = c.lastrowid
                added_rooms += 1

            # 占用出租记录（仅当无在住记录时补一条）
            occ = c.execute(
                "SELECT * FROM apartment_rentals WHERE room_id=? AND (check_out_date IS NULL OR check_out_date='') "
                "ORDER BY id DESC LIMIT 1", (rid,)).fetchone()
            if not occ:
                c.execute(
                    "INSERT INTO apartment_rentals "
                    "(room_id,company_name,occupant_name,contact_phone,occupancy_count,check_in_date,check_out_date,"
                    "stay_days,deposit,monthly_rent,payment_status,electric_balance,key_card,room_password,"
                    "fingerprint,handler,note,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rid, "", "", "", cnt, TODAY, "", 0, 0, 0, "待缴", 0, "", "", "", "台账导入",
                     f"入住台账导入·{cnt}人", NOW, NOW))
                added_rentals += 1

        conn.commit()
        report.append(f"[{bname}] 房间 {len(rooms)} 间 | 新建单元 {added_units} | 新建房间主档 {added_rooms} | 新建占用记录 {added_rentals}")

    conn.close()
    print("\n".join(report))
    print("导入完成。")


if __name__ == "__main__":
    main()
