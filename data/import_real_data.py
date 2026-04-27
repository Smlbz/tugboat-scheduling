"""
data/import_real_data.py
从方案文档中的 Excel 导入真实拖轮数据
源文件: ../../方案文档/拖轮数据总.xlsx

使用方法:
    python data/import_real_data.py
    # 输出: real_tugs.json
"""
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional

DATA_DIR = Path(__file__).parent
EXCEL_PATH = DATA_DIR.parent.parent / "方案文档" / "拖轮数据总.xlsx"


def import_tug_data(excel_path: Optional[str] = None) -> List[Dict]:
    """
    从 Excel 导入拖轮数据
    需要 pandas + openpyxl
    """
    path = Path(excel_path) if excel_path else EXCEL_PATH
    if not path.exists():
        print(f"[错误] 源文件不存在: {path}")
        return []

    try:
        import pandas as pd
    except ImportError:
        print("[错误] 需要安装 pandas: pip install pandas openpyxl")
        return []

    xls = pd.ExcelFile(path)
    all_tugs = {}
    for sheet_name in xls.sheet_names:
        df = xls.parse(sheet_name)
        for _, row in df.iterrows():
            tug_id_raw = row.get("拖轮ID")
            if pd.isna(tug_id_raw):
                continue
            # 统一转为 int 字符串，避免 float 的 ".0" 尾缀
            tug_id = str(int(tug_id_raw)).strip()
            if not tug_id:
                continue

            hp_raw = row.get("拖轮马力")
            hp = float(hp_raw) if not pd.isna(hp_raw) else 5000.0

            fatigue_raw = row.get("当班累计作业时间（min）")
            fatigue = min(float(fatigue_raw) / 60.0, 15.0) if not pd.isna(fatigue_raw) else 0.0

            work_raw = row.get("当日作业量")
            work = float(work_raw) * 0.5 if not pd.isna(work_raw) else 0.0

            lng_raw = row.get("经度")
            lat_raw = row.get("纬度")
            lng = float(lng_raw) if not pd.isna(lng_raw) else 120.38
            lat = float(lat_raw) if not pd.isna(lat_raw) else 36.07

            status_cn = str(row.get("拖轮状态", "")).strip()
            name = str(row.get("拖轮名", "")).strip()

            all_tugs[tug_id] = {
                "id": tug_id,
                "name": name,
                "horsepower": hp,
                "position": {"lng": lng, "lat": lat},
                "status": _map_status(status_cn),
                "fatigue_value": fatigue,
                "today_work_hours": work,
                "ship_age": 10,
            }

    return list(all_tugs.values())


def _map_status(status_cn: str) -> str:
    mapping = {
        "空闲": "AVAILABLE",
        "作业中": "BUSY",
        "停修": "MAINTENANCE",
        "外派": "LOCKED_BY_FRMS",
    }
    return mapping.get(status_cn, "AVAILABLE")


if __name__ == "__main__":
    tugs = import_tug_data()
    if tugs:
        output = DATA_DIR / "real_tugs.json"
        with open(output, "w", encoding="utf-8") as f:
            json.dump({"tugs": tugs}, f, ensure_ascii=False, indent=2)
        print(f"[成功] 导入 {len(tugs)} 艘拖轮到 {output}")
    else:
        print("[跳过] 未导入数据（文件不存在或格式不匹配）")
