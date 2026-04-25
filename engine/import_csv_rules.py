"""CSV导入脚本 — 将usage_rules.csv解析为结构化参数规则"""
import csv
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent  # Project/
CSV_PATH = BASE_DIR / "usage_rules.csv"
OUTPUT_PATH = BASE_DIR / "tugboat-scheduling" / "data" / "rules_usage.json"

def parse_length(text):
    """解析长度表达式 -> (min, max, 单位)
    '≥265米' -> (265, None)
    '235米-265米' -> (235, 265)
    '>390米' -> (390, None)
    '<100米' -> (None, 100)
    '大港cape' -> None (特殊)
    """
    text = text.strip()
    if not text or text == '/' or text == '':
        return None
    if '大港' in text or 'cape' in text.lower():
        return ('special', text)
    text = text.replace('米', '').replace(' ', '')
    m = re.match(r'≥(\d+\.?\d*)-(\d+\.?\d*)', text)
    if m: return (float(m.group(1)), float(m.group(2)))
    m = re.match(r'>(\d+\.?\d*)-(\d+\.?\d*)', text)
    if m: return (float(m.group(1)), float(m.group(2)))
    m = re.match(r'(\d+\.?\d*)-(\d+\.?\d*)', text)
    if m: return (float(m.group(1)), float(m.group(2)))
    m = re.match(r'≥(\d+\.?\d*)', text)
    if m: return (float(m.group(1)), None)
    m = re.match(r'>(\d+\.?\d*)', text)
    if m: return (float(m.group(1)), None)
    m = re.match(r'<(\d+\.?\d*)', text)
    if m: return (None, float(m.group(1)))
    m = re.match(r'≤(\d+\.?\d*)', text)
    if m: return (None, float(m.group(1)))
    return None


def parse_draft(text):
    """解析吃水表达式 -> (min, max, empty_bool)
    '≥18m' -> (18, None, False)
    '15m≤D<18m' -> (15, 18, False)
    'D<15m' -> (None, 15, False)
    '空载' -> (None, None, True)
    '>12.5m' -> (12.5, None, False)
    '10-13m' -> (10, 13, False)
    '<12m' -> (None, 12, False)
    '>9m' -> (9, None, False)
    '<9m' -> (None, 9, False)
    '>12m' -> (12, None, False)
    '<12m' -> (None, 12, False)
    '16-18m' -> (16, 18, False)
    '/' -> None
    """
    text = text.strip()
    if not text or text == '/' or text == '':
        return None
    if '空载' in text:
        return (None, None, True)
    text = text.replace(' ', '')
    # 15m≤D<18m
    m = re.match(r'(\d+\.?\d*)m?≤?D<(\d+\.?\d*)m?', text)
    if m: return (float(m.group(1)), float(m.group(2)), False)
    # D<15m
    m = re.match(r'D<(\d+\.?\d*)m?', text)
    if m: return (None, float(m.group(1)), False)
    # ≥18m 或 >18m
    m = re.match(r'[≥>](\d+\.?\d*)m?', text)
    if m: return (float(m.group(1)), None, False)
    # <12m
    m = re.match(r'<(\d+\.?\d*)m?', text)
    if m: return (None, float(m.group(1)), False)
    # 10-13m 或 16-18m
    m = re.match(r'(\d+\.?\d*)-(\d+\.?\d*)m?', text)
    if m: return (float(m.group(1)), float(m.group(2)), False)
    # plain number
    m = re.match(r'(\d+\.?\d*)', text)
    if m: return (float(m.group(1)), None, False)
    return None


def parse_power(text):
    """解析马力需求 -> (min, max)
    '27000- 33000HP' -> (27000, 33000)
    '>5000HP' -> (5000, None)
    '0' -> (0, 0)
    '可无需拖轮' -> (0, 0)
    '/' -> None
    """
    text = text.strip()
    if not text or text == '/' or text == '':
        return None
    if '可无需拖轮' in text or text in ('0', '无需'):
        return (0, 0)
    text = text.replace('HP', '').replace(' ', '')
    m = re.match(r'>(\d+)', text)
    if m: return (int(m.group(1)), None)
    m = re.match(r'(\d+)-(\d+)', text)
    if m: return (int(m.group(1)), int(m.group(2)))
    m = re.match(r'(\d+)', text)
    if m: return (int(m.group(1)), None)
    return None


def parse_tug_count(text):
    """解析拖轮条数
    '≥1' -> (1, None)
    '>3' -> (3, None)
    '>2' -> (2, None)
    '0' -> (0, 0)
    '/' -> None
    """
    text = text.strip()
    if not text or text == '/' or text == '':
        return None
    m = re.match(r'[≥>](\d+)', text)
    if m: return (int(m.group(1)), None)
    m = re.match(r'(\d+)', text)
    if m: return (int(m.group(1)), int(m.group(1)))
    return None


def build_keywords(ship_type, operation, draft_text):
    """从条件生成搜索关键词"""
    kw = [ship_type]
    if operation != "靠离":
        kw.append(operation)
    if draft_text and draft_text.strip() not in ('/', ''):
        kw.append(draft_text.strip())
    return kw


def main():
    rules = []
    seq = 0

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header

        for row in reader:
            if len(row) < 7:
                continue
            ship_type = row[1].strip()
            length_text = row[2].strip()
            operation = row[3].strip()
            draft_text = row[4].strip()
            power_text = row[5].strip()
            count_text = row[6].strip()
            tug_op_text = row[7].strip() if len(row) > 7 else ''

            if not ship_type:
                continue

            length_parsed = parse_length(length_text)
            draft_parsed = parse_draft(draft_text)
            power_parsed = parse_power(power_text)
            count_parsed = parse_tug_count(count_text)

            is_empty = draft_parsed and draft_parsed[2] if draft_parsed else False

            if operation == '靠离':
                operations = ['靠', '离']
            else:
                operations = [operation]

            for op in operations:
                seq += 1
                rid = f"U{str(seq).zfill(3)}"
                conditions = {
                    "ship_type": ship_type,
                    "operation": op,
                }
                if length_parsed == ('special', '大港cape'):
                    conditions["length_special"] = "大港cape"
                elif length_parsed:
                    conditions["length_min"] = length_parsed[0]
                    conditions["length_max"] = length_parsed[1]

                if draft_parsed and not is_empty:
                    conditions["draft_min"] = draft_parsed[0]
                    conditions["draft_max"] = draft_parsed[1]
                if is_empty:
                    conditions["empty_draft"] = True

                result = {}
                if power_parsed:
                    result["horsepower_min"] = power_parsed[0]
                    result["horsepower_max"] = power_parsed[1]
                if count_parsed:
                    result["tug_count_min"] = count_parsed[0]
                    result["tug_count_max"] = count_parsed[1]
                if tug_op_text and tug_op_text != '/':
                    result["tug_operation"] = tug_op_text.strip()

                rule = {
                    "id": rid,
                    "name": f"{ship_type}{length_text}{op}功率需求",
                    "rule_type": "USAGE_SPEC",
                    "category": "COMPLIANCE",
                    "severity": "MEDIUM",
                    "description": f"{ship_type}{length_text}，{op}，吃水{draft_text} → 功率{power_text}，{count_text if count_text else '—'}条",
                    "check_logic": "",
                    "keywords": [ship_type, op],
                    "conditions": conditions,
                    "result": result,
                    "source": "csv",
                    "enabled": True,
                }
                rules.append(rule)

    output = {
        "version": "1.0",
        "description": "拖轮功率需求参数规则(来自usage_rules.csv)",
        "rules": rules,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"CSV导入完成: {len(rules)} 条规则 → {OUTPUT_PATH}")
    # 统计各船型
    from collections import Counter
    sc = Counter(r['conditions']['ship_type'] for r in rules)
    for st, cnt in sc.most_common():
        print(f"  {st}: {cnt} 条")
    print(f"  (含'靠离'拆分为靠+离)")


if __name__ == "__main__":
    main()
