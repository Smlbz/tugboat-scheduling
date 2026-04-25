"""XLSX导入脚本 — 将"影响拖轮调配的因素"导入为规则"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent  # Project/
XLSX_PATH = BASE_DIR / "tugboat-scheduling" / "影响拖轮调配的因素.xlsx"
RULES_JSON_PATH = BASE_DIR / "tugboat-scheduling" / "data" / "rules.json"
OUTPUT_PATH = BASE_DIR / "tugboat-scheduling" / "data" / "rules_factors.json"

def load_existing_rules():
    with open(RULES_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {r["id"]: r for r in data["rules"]}

# XLSX 19因素 → JSON规则的手工映射
# 已知与R001-R010重叠的规则，直接合并描述
OVERLAP_MAP = {
    "新老拖轮使用": "R002",
    "连续作业": "R007",
    "名称": "R001",
    "夜间作业": "R005",
    "疲劳度": "R004",
    "作业量": "R009",
    "内外档": "R006",
    "带船": "R010",
}

def match_overlap(name, desc):
    """模糊匹配重叠规则 — name匹配优先，其次最长关键词"""
    matches = []
    for keyword, rule_id in OVERLAP_MAP.items():
        in_name = keyword in name
        in_desc = keyword in desc
        if in_name or in_desc:
            # (name匹配优先, 关键词长度, rule_id)
            matches.append((not in_name, len(keyword), rule_id))
    if not matches:
        return None
    matches.sort()  # False(0) < True(1), 所以name匹配排前面; 然后长关键词
    return matches[0][2]

def read_xlsx_factors():
    """用 openpyxl 读取 xlsx"""
    import openpyxl
    wb = openpyxl.load_workbook(XLSX_PATH)
    ws = wb.active
    factors = []
    for row in ws.iter_rows(min_row=3, max_row=21, values_only=True):
        seq = row[0]
        name = str(row[1]).strip() if row[1] else ""
        factor = str(row[2]).strip() if row[2] else ""
        note = str(row[3]).strip() if row[3] else ""
        if seq is None or str(seq).strip() == "":
            # 续行：补充到上一条的condition_text
            if factors:
                if factor:
                    factors[-1]["condition_text"] += "；" + factor
                if note:
                    factors[-1]["note"] += "；" + note
            continue
        factors.append({
            "seq": int(float(seq)),
            "name": name,
            "condition_text": factor,
            "note": note,
        })
    return factors

def build_rules(factors, existing_rules):
    """合并XLSX因素到规则，输出rules_factors.json"""
    merged = {}
    new_rules = []

    for f in factors:
        name = f["name"]
        desc = f["condition_text"]
        note = f["note"]
        full_desc = desc + ("。" + note if note else "")

        matched_id = match_overlap(name, desc)

        if matched_id and matched_id in existing_rules:
            # 重叠：合并到已有规则
            er = existing_rules[matched_id]
            er["source"] = "xlsx+manual"
            # 在description末尾追加XLSX原文
            xlsx_suffix = f"[XLSX#{f['seq']}] {full_desc}"
            if xlsx_suffix not in er.get("description", ""):
                er["description"] += " | " + xlsx_suffix
            if "来源参考" not in er:
                er["来源参考"] = []
            er["来源参考"].append(f"XLSX#{f['seq']} {name}")
            merged[matched_id] = er
        else:
            # 新增规则
            rid = f"F{str(f['seq']).zfill(2)}"
            rule = {
                "id": rid,
                "name": name or f"因素{f['seq']}",
                "rule_type": "DISPATCH_FACTOR",
                "category": "EFFICIENCY",
                "severity": "MEDIUM",
                "description": full_desc,
                "check_logic": "",
                "keywords": [name] if name else [],
                "conditions": None,
                "result": None,
                "source": "xlsx",
                "enabled": True,
            }
            new_rules.append(rule)

    return list(merged.values()), new_rules

def main():
    factors = read_xlsx_factors()
    existing = load_existing_rules()
    print(f"XLSX读取到 {len(factors)} 条因素")
    print(f"现有JSON规则: {len(existing)} 条")

    merged_overlaps, new_rules = build_rules(factors, existing)

    # 读取原始rules.json，保留不变
    with open(RULES_JSON_PATH, "r", encoding="utf-8") as f:
        orig_data = json.load(f)

    output = {
        "version": "1.0",
        "description": "拖轮调配因素规则(来自XLSX)",
        "rules": merged_overlaps + new_rules,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"重叠合并: {len(merged_overlaps)} 条")
    print(f"新增因素: {len(new_rules)} 条")
    print(f"总输出: {len(output['rules'])} 条 → {OUTPUT_PATH}")
    for r in new_rules:
        print(f"  + 新增 {r['id']}: {r['name']}")

if __name__ == "__main__":
    main()
