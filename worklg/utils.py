import colorsys
import hashlib
from datetime import datetime, timedelta
import uuid

def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')

def today_date() -> str:
    return datetime.now().strftime('%Y-%m-%d')

def last_week_monday() -> datetime:
    today = datetime.now()
    days_since_monday = (today.weekday() + 1) % 7  # 0=Monday, 6=Sunday
    last_monday = today - timedelta(days=days_since_monday + 7)
    return last_monday.replace(hour=0, minute=0, second=0, microsecond=0)

def a_month_ago() -> datetime:
    today = datetime.now()
    return today - timedelta(days=30)

def weekday(date_str: str) -> str:
    """返回给定日期字符串的星期几"""
    date = datetime.fromisoformat(date_str)
    return date.strftime('%A')  # 返回完整的星期几名称，如 'Monday'

def gen_id() -> str:
    return str(uuid.uuid4())[:8]

def duration_minutes(start_iso, end_iso):
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    return int((end - start).total_seconds() / 60)

def format_duration(minutes):
    hours = int(minutes) // 60
    mins = int(minutes) % 60
    return f"{hours}h{mins:02d}m"

used_colors = []
used_colors_map = {}

def color_distance(c1, c2):
    """返回两个 RGB 颜色的欧几里得距离"""
    return ((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2 + (c1[2]-c2[2])**2) ** 0.5

def pick_color_rgb(description, max_retry=20, similarity_threshold=60):
    global used_colors
    global used_colors_map

    if description in used_colors_map:
        return used_colors_map[description]

    salt = 0
    for _ in range(max_retry):
        h = hashlib.md5((description + str(salt)).encode()).hexdigest()
        raw_hue = int(h[0:256], 16)

        # 避开紫色、深蓝区间：只用 0–220 和 320–360
        allowed_ranges = [(0, 220), (320, 360)]
        total_range = sum(end - start for start, end in allowed_ranges)
        hue_selector = raw_hue % total_range
        for start, end in allowed_ranges:
            length = end - start
            if hue_selector < length:
                hue = start + hue_selector
                break
            hue_selector -= length

        saturation = 0.85 + (int(h[6:8], 16) / 255) * 0.15
        value = 0.9 + (int(h[8:10], 16) / 255) * 0.1

        r, g, b = colorsys.hsv_to_rgb(hue / 360, saturation, value)
        rgb = (int(r * 255), int(g * 255), int(b * 255))

        # 距离判定：是否太接近已使用的颜色
        if all(color_distance(rgb, used) >= similarity_threshold for used in used_colors):
            used_colors.append(rgb)
            used_colors_map[description] = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
            return f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"

        # 否则 hash 加点随机偏移，尝试生成下一个候选颜色
        salt += 1

    # 如果多次尝试都太像，就无奈接受最后一个
    used_colors.append(rgb)
    used_colors_map[description] = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
    return f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"

from wcwidth import wcswidth

def smart_ljust(text, width):
    pad_len = width - wcswidth(text)
    return text + ' ' * max(0, pad_len)

def smart_rjust(text, width):
    pad_len = width - wcswidth(text)
    return ' ' * max(0, pad_len) + text

def smart_truncate(text, max_width):
    """根据显示宽度智能截断，末尾加..."""
    from wcwidth import wcswidth
    text = text.replace('\n', '')
    text = text.replace('\r', '')
    if wcswidth(text) <= max_width:
        return text

    truncated = ''
    current_width = 0

    for char in text:
        char_width = wcswidth(char)
        if current_width + char_width > max_width - 3:  # 留出3列给...
            break
        truncated += char
        current_width += char_width

    return truncated + '...'

def percent(floatValue):
    """格式化百分比，保留两位小数"""
    return f"{floatValue:.2%}"
