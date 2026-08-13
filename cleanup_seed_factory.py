#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理 A栋/B栋 12 户种子演示厂房数据（幂等）。

范围（严格按需求）：
  units id 1-12  (A-01..B-06)
  contracts id 1,3 (HT-L-0001, HT-S-0001，挂在 unit 1/3)
  customers id 1,2 (宏达精密, 蓝海电子 —— 仅被上述种子合同引用)
  buildings id 1,2 (A栋标准厂房, B栋标准厂房)
  bills id 1,2,3,5,6 (种子账单) 及 references 它们的 receipts

不在范围（公寓种子，按需另清）：
  contract 2 (HT-L-0002, unit 13 C-001 公寓) / customer 3 / unit 13
"""
import sqlite3, sys

DB = "park.db"

def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row

    def cnt(tbl, where=""):
        sql = f"SELECT COUNT(*) n FROM {tbl}" + (f" WHERE {where}" if where else "")
        return c.execute(sql).fetchone()["n"]

    # 预检：种子客户是否被真实合同引用（防误伤）
    for cid in (1, 2):
        used = c.execute(
            "SELECT COUNT(*) n FROM contracts WHERE customer_id=? AND id NOT IN (1,3)",
            (cid,)).fetchone()["n"]
        if used:
            print(f"[ABORT] customer {cid} 被 {used} 个非种子合同引用，终止以防误删")
            sys.exit(1)

    print("=== 清理前 ===")
    print(f"  units(1-12): {cnt('units','id BETWEEN 1 AND 12')}  contracts(1,3): {cnt('contracts','id IN (1,3)')}  "
          f"customers(1,2): {cnt('customers','id IN (1,2)')}  buildings(1,2): {cnt('buildings','id IN (1,2)')}")
    print(f"  seed bills: {cnt('bills','id IN (1,2,3,5,6)')}")

    # 1) receipts 引用种子账单
    c.execute("DELETE FROM receipts WHERE bill_id IN (1,2,3,5,6)")
    # 2) 种子账单
    c.execute("DELETE FROM bills WHERE id IN (1,2,3,5,6)")
    # 3) 种子合同
    c.execute("DELETE FROM contracts WHERE id IN (1,3)")
    # 4) 种子单元
    c.execute("DELETE FROM units WHERE id BETWEEN 1 AND 12")
    # 5) 种子客户（仅被种子合同引用，已预检）
    c.execute("DELETE FROM customers WHERE id IN (1,2)")
    # 6) 种子楼栋
    c.execute("DELETE FROM buildings WHERE id IN (1,2)")
    c.commit()

    print("=== 清理后 ===")
    print(f"  units(1-12): {cnt('units','id BETWEEN 1 AND 12')}  contracts(1,3): {cnt('contracts','id IN (1,3)')}  "
          f"customers(1,2): {cnt('customers','id IN (1,2)')}  buildings(1,2): {cnt('buildings','id IN (1,2)')}")
    print(f"  total units now: {cnt('units')}  total contracts: {cnt('contracts')}  total buildings: {cnt('buildings')}")
    print("OK: 种子演示厂房数据已清理")

if __name__ == "__main__":
    main()
