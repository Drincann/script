import hashlib
from datetime import datetime
import uuid

def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')

def today_date() -> str:
    return datetime.now().strftime('%Y-%m-%d')

def gen_id() -> str:
    return str(uuid.uuid4())[:8]

def duration_minutes(start_iso, end_iso):
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    return int((end - start).total_seconds() / 60)

def format_duration(minutes):
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h{mins:02d}m"

def pick_color_rgb(description):
    h = hashlib.md5(description.encode()).hexdigest()
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return f"rgb({r},{g},{b})"

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
