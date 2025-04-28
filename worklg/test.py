import json
from datetime import datetime, timedelta
from pathlib import Path

def generate_sample_data(date_str):
    base_dt = datetime.fromisoformat(f"{date_str}T00:00:00")
    sample_tasks = [
        {
            "description": "写复盘",
            "sessions": [
                {"start_offset": 16 * 60 + 18, "duration": 1, "note": "准备引言"},
                {"start_offset": 16 * 60 + 19, "duration": 22},
            ]
        },
        {
            "description": "离线接入二期",
            "sessions": [
                {"start_offset": 16 * 60 + 19, "duration": 0},
                {"start_offset": 16 * 60 + 42, "duration": 17},
                {"start_offset": 17 * 60 + 0, "duration": 2},
                {"start_offset": 17 * 60 + 15, "duration": 19},
            ]
        },
        {
            "description": "客诉大模型数据临时需求跟进",
            "sessions": [
                {"start_offset": 17 * 60 + 4, "duration": 10},
                {"start_offset": 17 * 60 + 34, "duration": 0},
                {"start_offset": 17 * 60 + 41, "duration": 0},
            ]
        },
        {
            "description": "客诉需求1",
            "sessions": [
                {"start_offset": 17 * 60 + 38, "duration": 2},
                {"start_offset": 17 * 60 + 41, "duration": 19},
                {"start_offset": 18 * 60 + 0, "duration": 7},
                {"start_offset": 18 * 60 + 48, "duration": 11, "note": "实现接口 1"},
                {"start_offset": 19 * 60 + 0, "duration": None, "note": "实现接口 1优化"},  # ongoing
            ]
        }
    ]

    output = []

    def fmt(dt):
        return dt.isoformat(timespec='seconds')

    for task in sample_tasks:
        task_entry = {
            "id": fmt(base_dt + timedelta(minutes=task["sessions"][0]["start_offset"]))[-8:],  # 简单生成id
            "description": task["description"],
            "sessions": []
        }
        for sess in task["sessions"]:
            start_time = base_dt + timedelta(minutes=sess["start_offset"])
            if sess["duration"] is None:
                end_time = None  # ongoing
            else:
                end_time = start_time + timedelta(minutes=sess["duration"])
            task_entry["sessions"].append({
                "start_time": fmt(start_time),
                "end_time": fmt(end_time) if end_time else None,
                "note": sess.get("note")
            })
        output.append(task_entry)

    save_path = Path.home() / ".worklog_cli" / f"{date_str}.json"
    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 样例数据已生成到 {save_path}")

# 用法
generate_sample_data("2025-04-27")
