# -*- coding: utf-8 -*-
"""
厂房租赁/销售占位合同导入脚本
================================
将《中兴通物业台账.xlsx》已导入的厂房单元（code 以 FW 开头）中，
状态为「在租」的建租赁合同、「已售」的建销售合同，并回填到资产单元
的 current_contract_id / current_customer_id，使「厂房租赁」「厂房销售」
两个业务模块能显示对应租户/买方。

说明：
- 台账源数据只有 楼号/户号/面积/状态，没有客户名称、租金、售价、租期、签约日。
- 因此合同采用占位客户「（待补充）」、金额/租金/售价 0，并在 note 标注
  “台账导入·客户/金额/租期(签约日)待补充”，后续可在“租赁/销售”弹窗补真实信息。
- FW13 已售·玻璃厂转租：note 追加“（玻璃厂转租）”。
- 幂等：按合同 code 去重；仅当单元 current_contract_id 为空时回填。

用法：
    python3 import_factory_contracts.py
"""
import sqlite3
import os
import sys

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "park.db")
PLACEHOLDER_CUSTOMER = "（待补充）"


def get_or_create_placeholder_customer(c):
    row = c.execute("SELECT * FROM customers WHERE name=?", (PLACEHOLDER_CUSTOMER,)).fetchone()
    if row:
        return row["id"]
    c.execute(
        "INSERT INTO customers (type,name,contact,phone,address,source,stage) "
        "VALUES (?,?,?,?,?,?,?)",
        ("企业", PLACEHOLDER_CUSTOMER, "", "", "园区厂房", "台账导入", "C类"),
    )
    return c.lastrowid


def main():
    if not os.path.exists(DB):
        print("未找到 park.db：", DB)
        sys.exit(1)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    placeholder_id = get_or_create_placeholder_customer(c)
    print("占位客户 id =", placeholder_id)

    # 取导入的真实厂房单元（FW 开头），仅在租/已售需要建合同
    units = c.execute(
        "SELECT * FROM units WHERE type='厂房' AND code LIKE 'FW%' "
        "AND status IN ('在租','已售') ORDER BY code"
    ).fetchall()

    lease_created = 0
    sale_created = 0
    linked = 0
    skipped = 0

    for u in units:
        is_lease = u["status"] == "在租"
        ctype = "租赁" if is_lease else "销售"
        prefix = "HT-L-" if is_lease else "HT-S-"
        code = prefix + u["code"]
        note = "台账导入（中兴通物业台账）· 客户/金额/租期" + ("/签约日" if not is_lease else "") + "待补充"
        if "玻璃厂转租" in (u["note"] or ""):
            note += "（玻璃厂转租）"

        # 幂等：合同 code 已存在则跳过创建
        existing = c.execute("SELECT * FROM contracts WHERE code=?", (code,)).fetchone()
        if existing:
            contract_id = existing["id"]
            skipped += 1
        else:
            c.execute(
                "INSERT INTO contracts "
                "(code,type,unit_id,customer_id,start_date,end_date,amount,pay_cycle,deposit,status,sign_date,note,lease_months,free_days,deposit_status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (code, ctype, u["id"], placeholder_id, None, None, 0, "月", 0,
                 "生效", None, note, 0, 0, "已收"),
            )
            contract_id = c.lastrowid
            if is_lease:
                lease_created += 1
            else:
                sale_created += 1

        # 回填单元关联键（仅当尚未关联）
        if u["current_contract_id"] is None:
            c.execute(
                "UPDATE units SET current_contract_id=?, current_customer_id=? WHERE id=?",
                (contract_id, placeholder_id, u["id"]),
            )
            linked += 1

    conn.commit()

    print(f"新建租赁合同：{lease_created} 条")
    print(f"新建销售合同：{sale_created} 条")
    print(f"已存在跳过（幂等）：{skipped} 条")
    print(f"回填单元关联键：{linked} 条")
    print("完成。可在【厂房租赁】【厂房销售】查看；客户/金额待补充项请用“租赁/销售”弹窗编辑。")

    conn.close()


if __name__ == "__main__":
    main()
