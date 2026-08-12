#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性修复脚本：让水电抄表与真实资产/租户关联。

1) 公寓单元回填 current_contract_id / current_customer_id：
   从 HT-AP 合同（contracts.code LIKE 'HT-AP%' 且 unit_id 指向该公寓单元）反向匹配。
2) 清理脱离的演示抄表数据：
   meter_reading_records 中指向旧种子铺位（A-01/B-01/C-001，units.id IN (1,2,13)）的 6 条记录删除。
   这些 tenant 是种子客户，与导入的真实资产无关，且页面将改为按「应抄表单元」派生，无需保留。

幂等：重复运行无副作用。
"""
import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "park.db")


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # ---- 1) 公寓单元回填合同/客户关联 ----
    rows = c.execute(
        """SELECT u.id AS uid, ct.id AS cid, ct.customer_id AS cust
           FROM units u
           JOIN contracts ct ON ct.unit_id = u.id
           WHERE u.type='公寓' AND ct.code LIKE 'HT-AP%'"""
    ).fetchall()
    fixed = 0
    for r in rows:
        c.execute(
            "UPDATE units SET current_contract_id=?, current_customer_id=? WHERE id=?",
            (r["cid"], r["cust"], r["uid"]),
        )
        fixed += 1
    print(f"[1] 公寓单元回填合同关联：更新 {fixed} 个单元")

    # ---- 2) 清理脱离的演示抄表数据 ----
    # 种子铺位 units.id：1=A-01(厂房在租), 2=B-01(厂房空置), 13=C-001(公寓在租)
    before = c.execute("SELECT COUNT(*) n FROM meter_reading_records").fetchone()["n"]
    c.execute(
        "DELETE FROM meter_reading_records WHERE unit_id IN (1,2,13)"
    )
    after = c.execute("SELECT COUNT(*) n FROM meter_reading_records").fetchone()["n"]
    print(f"[2] 清理演示抄表数据：{before} -> {after}（删除 {before - after} 条）")

    conn.commit()
    conn.close()

    # ---- 校验 ----
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    ap_none = conn.execute(
        "SELECT COUNT(*) n FROM units WHERE type='公寓' AND current_contract_id IS NULL"
    ).fetchone()["n"]
    ap_total = conn.execute("SELECT COUNT(*) n FROM units WHERE type='公寓'").fetchone()["n"]
    print(f"[校验] 公寓单元 {ap_total} 个，仍有 {ap_none} 个未关联合同")
    conn.close()


if __name__ == "__main__":
    main()
