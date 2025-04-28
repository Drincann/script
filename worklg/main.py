#!/usr/bin/env python3
import typer
from rich import print
from rich.console import Console
from rich.table import Table
from datetime import datetime, timedelta
from typing import Optional

from storage import read_tasks, write_tasks
from utils import (
    now_iso,
    today_date,
    smart_ljust,
    smart_rjust,
    smart_truncate,
    gen_id,
    duration_minutes,
    format_duration,
    pick_color_rgb,
)

app = typer.Typer()
view_app = typer.Typer()
app.add_typer(view_app, name="view")

console = Console()


def select_task(tasks, selector: str):
    """根据编号或者关键词选择已有任务，如果没有匹配，返回 None"""
    # sort by start_time
    tasks.sort(key=lambda t: datetime.fromisoformat(t["sessions"][0]["start_time"]))
    if selector.isdigit():
        index = int(selector) - 1
        if 0 <= index < len(tasks):
            return tasks[index]
        else:
            print("[red]编号超出范围[/red]")
            raise typer.Exit()
    else:
        matched = [task for task in tasks if selector in task["description"]]
        if len(matched) == 0:
            return None
        elif len(matched) == 1:
            return matched[0]
        else:
            print("匹配到多条，请选择：")
            for idx, task in enumerate(matched, 1):
                print(f"[{idx}] {task['description']}")
            choice = int(input("请输入编号: ")) - 1
            if 0 <= choice < len(matched):
                return matched[choice]
            else:
                print("[red]选择无效[/red]")
                raise typer.Exit()


@app.command()
def start(selector: str):
    """开始或继续一个任务 (支持编号/关键词，新建任务也可以；智能连接最近session)"""
    date_str = today_date()
    tasks = read_tasks(date_str)

    # 检查是否已有活跃任务
    for task in tasks:
        for sess in task["sessions"]:
            if sess["end_time"] is None:
                print("[red]已有正在进行中的任务，请先 stop 或 push[/red]")
                raise typer.Exit()

    task = select_task(tasks, selector)

    if task is None:
        # 没有匹配，创建新的任务
        task = {"id": gen_id(), "description": selector, "sessions": []}
        tasks.append(task)
        print(f"[green]新建任务:[/green] {selector}")

    now = datetime.now()

    # 查找最后一个 session
    last_session = task["sessions"][-1] if task["sessions"] else None

    if last_session and last_session["end_time"]:
        end_time = datetime.fromisoformat(last_session["end_time"])
        diff_sec = (now - end_time).total_seconds()

        if diff_sec <= 60:
            # 恢复上一个 session
            last_session["end_time"] = None
            print(f"[green]继续上一个session (距上次结束{int(diff_sec)}秒内)[/green]")
        else:
            # 新开session
            task["sessions"].append({"start_time": now_iso(), "end_time": None})
            print(f"[green]开始新的session (与上次间隔超过1分钟)[/green]")
    else:
        # 没有历史session，正常新建
        task["sessions"].append({"start_time": now_iso(), "end_time": None})

    write_tasks(date_str, tasks)
    print(f"[green]已开始任务:[/green] {task['description']}")


@app.command()
def stop(*, from_cmd: bool = False):
    """停止当前任务"""
    date_str = today_date()
    tasks = read_tasks(date_str)
    for task in tasks:
        for session in task["sessions"]:
            if session["end_time"] is None:
                session["end_time"] = now_iso()
                write_tasks(date_str, tasks)
                if not from_cmd:
                    print(f"[green]已结束当前任务:[/green] {task['description']}")
                return
    if not from_cmd:
      print("[red]没有正在进行中的任务[/red]")


@app.command()
def push(selector: str):
    """切换到新的任务 (支持编号/关键词)"""
    stop(from_cmd=True)
    start(selector)

@app.command()
def pop():
    """结束当前任务并恢复上一个任务"""
    date_str = today_date()
    tasks = read_tasks(date_str)

    now = now_iso()

    active_task = None
    for task in tasks:
        for sess in task['sessions']:
            if sess['end_time'] is None:
                active_task = task
                sess['end_time'] = now
                break
        if active_task:
            break

    # 找最近一个已经结束的session
    latest_end_time = None
    latest_task = None
    for task in tasks:
        for sess in task['sessions']:
            if sess['end_time'] is not None and task != active_task:
                sess_end = datetime.fromisoformat(sess['end_time'])
                if latest_end_time is None or sess_end > latest_end_time:
                    latest_end_time = sess_end
                    latest_task = task

    if latest_task:
        latest_task['sessions'].append({
            "start_time": now,
            "end_time": None
        })
        write_tasks(date_str, tasks)

        if active_task:
            print(f"[green]已结束当前任务:[/green] {active_task['description']}")
        print(f"[green]恢复上一个任务:[/green] {latest_task['description']}")
    else:
        print("[yellow]没有找到可以恢复的上一个任务[/yellow]")

@app.command()
def split(new_description: str):
    """把当前进行中的任务一分为二，补录新的任务"""
    date_str = today_date()
    tasks = read_tasks(date_str)

    # 找到当前进行中的任务
    current_task = None
    for task in tasks:
        for sess in task["sessions"]:
            if sess["end_time"] is None:
                current_task = (task, sess)
                break
        if current_task:
            break

    if not current_task:
        print("[yellow]当前没有正在进行的任务，无法split[/yellow]")
        raise typer.Exit()
    if current_task[0]["description"] == new_description:
        print("[red]新任务描述不能和当前任务相同[/red]")
        raise typer.Exit()

    task, session = current_task

    # 询问打断的时间
    interrupt_time = input("请输入被打断的时间 (格式 HH:MM): ").strip()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        interrupt_dt = datetime.fromisoformat(f"{today}T{interrupt_time}:00")
        now_dt = datetime.now()

        # 校验时间合法
        if interrupt_dt < datetime.fromisoformat(session["start_time"]):
            print("[red]打断时间不能早于session开始时间[/red]")
            raise typer.Exit()
        if interrupt_dt > now_dt:
            print("[red]打断时间不能晚于现在[/red]")
            raise typer.Exit(f"{interrupt_time} > {now_dt.strftime('%H:%M')}")
    except Exception as e:
        print(f"[red]输入时间格式错误: {e}[/red]")
        raise typer.Exit()

    # 切割
    session["end_time"] = interrupt_dt.isoformat(timespec="seconds")

    # 新建一个新的任务
    new_task = {
        "id": gen_id(),
        "description": new_description,
        "sessions": [
            {
                "start_time": interrupt_dt.isoformat(timespec="seconds"),
                "end_time": now_iso(),
            }
        ],
    }
    tasks.append(new_task)

    write_tasks(date_str, tasks)
    print(f"[green]已补录新任务:[/green] {new_description}")
    print("[yellow]当前没有正在进行的任务，请根据需要重新 start/push[/yellow]")


@app.command()
def current():
    """查看当前正在进行的任务"""
    date_str = today_date()
    tasks = read_tasks(date_str)

    for task in tasks:
        for sess in task["sessions"]:
            if sess["end_time"] is None:
                start = datetime.fromisoformat(sess["start_time"])
                now = datetime.now()
                dur_min = int((now - start).total_seconds() / 60)
                print(
                    f"[green]正在进行:[/green] {task['description']}，已持续 {format_duration(dur_min)}"
                )
                return
    print("[yellow]当前没有正在进行的任务[/yellow]")


@view_app.command("timeline")
def view_timeline(
    from_date: Optional[str] = typer.Option(None, "--from", help="起始日期 YYYY-MM-DD"),
    to_date: Optional[str] = typer.Option(None, "--to", help="结束日期 YYYY-MM-DD"),
):
    """专业版 Timeline View (支持跨天；单天=小时/session粒度，跨天=天/task粒度)"""
    if not from_date:
        from_date = today_date()
    if not to_date:
        to_date = from_date

    from_dt = datetime.fromisoformat(from_date)
    to_dt = datetime.fromisoformat(to_date)

    if from_dt > to_dt:
        print("[red]起始时间不能晚于结束时间[/red]")
        raise typer.Exit()

    console.print("[bold underline green]Timeline View[/bold underline green]\n")

    # 收集所有 session
    sessions = []
    current_day = from_dt
    while current_day <= to_dt:
        day_str = current_day.strftime("%Y-%m-%d")
        tasks = read_tasks(day_str)
        for task in tasks:
            for sess in task["sessions"]:
                sessions.append(
                    {
                        "date": day_str,
                        "task_id": task["id"],
                        "description": task["description"],
                        "start_time": sess["start_time"],
                        "end_time": sess["end_time"] or now_iso() if sess["end_time"] is None else sess["end_time"],
                        "is_running": sess["end_time"] is None,
                        "note": sess.get("note", None),
                    }
                )
        current_day += timedelta(days=1)

    if not sessions:
        print("[yellow]指定日期范围内没有任务记录[/yellow]")
        return

    sessions = sorted(sessions, key=lambda s: s["start_time"])

    # 单天 vs 跨天分支
    if from_date == to_date:
        render_single_day_timeline(sessions)
    else:
        render_multi_day_timeline(sessions)


def render_single_day_timeline(sessions):
    """渲染单天 session 粒度 timeline"""
    max_duration = min(60, max(
        duration_minutes(s["start_time"], s["end_time"]) for s in sessions
    ))

    first_start = datetime.fromisoformat(sessions[0]["start_time"]).replace(
        minute=0, second=0
    )
    last_end = datetime.fromisoformat(sessions[-1]["end_time"]).replace(
        minute=0, second=0
    ) + timedelta(hours=1)

    current_hour = first_start
    idx = 0
    session_count = len(sessions)

    while current_hour < last_end:
        console.print(f"[bold cyan]{current_hour.strftime('%H:%M')}[/bold cyan]")

        next_hour = current_hour + timedelta(hours=1)
        while idx < session_count:
            sess = sessions[idx]
            start = datetime.fromisoformat(sess["start_time"])
            end = datetime.fromisoformat(sess["end_time"])
            desc = sess["description"]
            note = sess["note"]
            color = pick_color_rgb(desc)

            if current_hour <= start < next_hour and end <= next_hour:
                render_session(
                    start, end, desc, color, sess["is_running"], max_duration, note
                )
                idx += 1
            elif current_hour <= start < next_hour and end > next_hour:
                render_session(start, next_hour, desc, color, False, max_duration, note)
                sessions[idx]["start_time"] = next_hour.isoformat()
                break
            else:
                break

        console.print("[dim]" + "-" * 70 + "[/dim]")
        current_hour = next_hour


from collections import defaultdict

from collections import defaultdict

def render_multi_day_timeline(sessions):
    """渲染多天 task 聚合粒度 timeline，带跨天session分割和起止时间"""
    # 每天 {task -> {"minutes":总分钟数, "start":最早start, "end":最晚end}}
    day_task_info = defaultdict(lambda: defaultdict(lambda: {"minutes": 0, "start": None, "end": None}))

    now_dt = datetime.now()

    for sess in sessions:
        desc = sess['description']
        start_dt = datetime.fromisoformat(sess['start_time'])
        end_dt = datetime.fromisoformat(sess['end_time']) if sess['end_time'] else now_dt

        current_day = start_dt.date()

        while current_day <= end_dt.date():
            day_start = datetime.combine(current_day, datetime.min.time())
            day_end = datetime.combine(current_day, datetime.max.time())

            seg_start = max(start_dt, day_start)
            seg_end = min(end_dt, day_end)

            if seg_start < seg_end:
                duration = (seg_end - seg_start).total_seconds() / 60
                date_str = current_day.strftime('%Y-%m-%d')
                task_info = day_task_info[date_str][desc]
                task_info["minutes"] += int(duration)

                if task_info["start"] is None or seg_start < task_info["start"]:
                    task_info["start"] = seg_start
                if task_info["end"] is None or seg_end > task_info["end"]:
                    task_info["end"] = seg_end

            current_day += timedelta(days=1)

    # 渲染
    for date, task_infos in sorted(day_task_info.items()):
        console.print(f"[bold cyan]{date}[/bold cyan]")

        max_task_minutes = max(info["minutes"] for info in task_infos.values())

        for desc, info in sorted(task_infos.items(), key=lambda x: -x[1]["minutes"]):
            dur_min = info["minutes"]
            start_str = info["start"].strftime('%H:%M') if info["start"] else "--:--"
            end_str = info["end"].strftime('%H:%M') if info["end"] else "--:--"
            time_range = f"[{start_str} -> {end_str}]"

            color = pick_color_rgb(desc)
            bar_len = max(1, int(dur_min / max_task_minutes * 10))
            bar = "▓" * bar_len
            dur_fmt = smart_ljust(format_duration(dur_min), 5)
            desc = smart_truncate(desc, 50)  # 为了加 time_range留空间
            desc = smart_ljust(desc, 50)

            line = f"  {time_range} [{color}]{desc}[/] {dur_fmt} {bar}"
            console.print(line)

        console.print("[dim]" + "-" * 70 + "[/dim]")



def render_session(start, end, desc, color, is_running, max_duration, note=None):
    """渲染单个session块，兼容中文、自动截断、自动对齐，加上轻量note"""
    start_str = start.strftime("%H:%M")
    end_str = end.strftime("%H:%M") if not is_running else "--:--"
    time_range = smart_ljust(f"[{start_str} -> {end_str}]", 12)

    if note:
        desc = f"{desc} ({note})"
    desc = smart_truncate(desc, 50)
    desc = smart_ljust(desc, 50)

    dur_min = int((end - start).total_seconds() / 60)
    dur_fmt = smart_ljust(format_duration(dur_min), 5)

    bar_len = max(1, int((dur_min / max_duration) * 10))
    bar = "▓" * bar_len

    line = f"  {time_range} [{color}]{desc}[/] {'[red]' if is_running else ''}{dur_fmt} {bar}{'[/red]' if is_running else ''}"

    console.print(line)


@view_app.command("task")
def view_task(selector: str):
    """查看单个任务的所有 session 详细信息 (带Time Bar)"""
    date_str = today_date()
    tasks = read_tasks(date_str)

    task = select_task(tasks, selector)

    if not task:
        print("[red]没有找到符合条件的任务[/red]")
        raise typer.Exit()

    sessions = task["sessions"]
    sessions.sort(key=lambda s: s["start_time"])

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("No.", width=3)
    table.add_column("Start", width=6)
    table.add_column("End", width=6)
    table.add_column("Duration", width=8)
    table.add_column("")
    table.add_column("Note", overflow="fold")

    # 计算最大session时长
    max_session_minutes = max(
        duration_minutes(sess["start_time"], sess["end_time"] or now_iso())
        for sess in sessions
    )

    for idx, sess in enumerate(sessions, 1):
        start = datetime.fromisoformat(sess["start_time"]).strftime("%H:%M")
        end = (
            datetime.fromisoformat(sess["end_time"]).strftime("%H:%M")
            if sess["end_time"]
            else "--:--"
        )
        dur_min = duration_minutes(sess["start_time"], sess["end_time"] or now_iso())
        dur_fmt = format_duration(dur_min)
        note = sess.get("note", "")

        bar_len = max(1, int(dur_min / max_session_minutes * 10))
        bar = "▓" * bar_len

        table.add_row(str(idx), start, end, dur_fmt, bar, note)

    console.print(
        f"[bold underline green]Task Detail:[/bold underline green] {task['description']}\n"
    )
    console.print(table)


@view_app.command("tasks")
def view_tasks():
    """按任务维度的表格视图 (带编号)"""
    date_str = today_date()
    tasks = read_tasks(date_str)

    if not tasks:
        print("[yellow]当天没有任务记录[/yellow]")
        return

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("No.", width=3)
    table.add_column("Task", width=50)
    table.add_column("Start", width=6)
    table.add_column("End", width=6)
    table.add_column("Duration", width=8)
    table.add_column("")

    total_minutes = 0
    task_infos = []

    for task in tasks:
        sessions = task["sessions"]
        start_time = datetime.fromisoformat(sessions[0]["start_time"])
        end_session = sessions[-1]
        is_running = end_session["end_time"] is None
        end_time = datetime.fromisoformat(end_session["end_time"] or now_iso())

        dur = sum(
            duration_minutes(s["start_time"], s["end_time"] or now_iso())
            for s in sessions
        )
        total_minutes = max(total_minutes, dur)

        task_infos.append(
            {
                "description": task["description"],
                "start_time": start_time,
                "end_time": end_time,
                "duration": dur,
                "is_running": is_running,
                "task_id": task["id"],
            }
        )

    task_infos.sort(key=lambda x: x["start_time"])

    # 找最近结束过的task (非进行中)
    latest_end_time = None
    top_task_id = None
    for info in task_infos:
        if not info['is_running']:
            if latest_end_time is None or info['end_time'] > latest_end_time:
                latest_end_time = info['end_time']
                top_task_id = info['task_id']

    for idx, info in enumerate(task_infos, 1):
        description_str = info["description"]
        if info['task_id'] == top_task_id:
            description_str = f"[blue](top)[/]" + description_str
        start_str = info["start_time"].strftime("%H:%M")
        end_str = (
            "[yellow]进行中[/yellow]"
            if info["is_running"]
            else info["end_time"].strftime("%H:%M")
        )
        dur_fmt = format_duration(info["duration"])

        bar_len = max(1, int(info["duration"] / total_minutes * 10))
        bar = "▓" * bar_len

        table.add_row(str(idx), description_str, start_str, end_str, dur_fmt, bar)

    console.print(table)


def has_conflict(tasks, new_start: datetime, new_end: datetime):
    """检查新的时间段是否与现有session冲突"""
    for task in tasks:
        for sess in task["sessions"]:
            sess_start = datetime.fromisoformat(sess["start_time"])
            sess_end = datetime.fromisoformat(sess["end_time"] or now_iso())

            if sess_start < new_end and new_start < sess_end:
                return True, task["description"], sess_start, sess_end

    return False, None, None, None


@app.command()
def retro(description: str):
    """补录一个已经发生但忘记start的任务 (带冲突检测)"""
    date_str = today_date()
    tasks = read_tasks(date_str)

    start_input = input("请输入任务开始时间 (格式 HH:MM): ").strip()
    end_input = input("请输入任务结束时间 (格式 HH:MM): ").strip()

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        start_dt = datetime.fromisoformat(f"{today}T{start_input}:00")
        end_dt = datetime.fromisoformat(f"{today}T{end_input}:00")

        if start_dt >= end_dt:
            print("[red]开始时间必须早于结束时间[/red]")
            raise typer.Exit()
        if end_dt > datetime.now():
            print("[red]结束时间不能晚于现在[/red]")
            raise typer.Exit()

    except Exception as e:
        print(f"[red]输入时间格式错误: {e}[/red]")
        raise typer.Exit()

    # 冲突检测
    conflict, desc, s, e = has_conflict(tasks, start_dt, end_dt)
    if conflict:
        print(
            f"[red]时间段与任务 [{desc}] 的 {s.strftime('%H:%M')}~{e.strftime('%H:%M')} 冲突，无法补录[/red]"
        )
        raise typer.Exit()

    # 查找任务
    matched_tasks = [task for task in tasks if description in task["description"]]

    if not matched_tasks:
        # 新建任务
        task = {"id": gen_id(), "description": description, "sessions": []}
        tasks.append(task)
        print(f"[green]新建任务:[/green] {description}")
    elif len(matched_tasks) == 1:
        task = matched_tasks[0]
        print(f"[green]找到已存在任务:[/green] {task['description']}")
    else:
        print("匹配到多条，请选择：")
        for idx, task in enumerate(matched_tasks, 1):
            print(f"[{idx}] {task['description']}")
        choice = int(input("请输入编号: ")) - 1
        if 0 <= choice < len(matched_tasks):
            task = matched_tasks[choice]
        else:
            print("[red]选择无效[/red]")
            raise typer.Exit()

    # 补session
    task["sessions"].append(
        {
            "start_time": start_dt.isoformat(timespec="seconds"),
            "end_time": end_dt.isoformat(timespec="seconds"),
        }
    )

    write_tasks(date_str, tasks)
    print(f"[green]已补录session:[/green] {start_input} - {end_input} -> {description}")


@app.command()
def note(content: str):
    """给当前进行中的 session 添加备注"""
    date_str = today_date()
    tasks = read_tasks(date_str)
    for task in tasks:
        for sess in task["sessions"]:
            if sess["end_time"] is None:
                record_time_str = datetime.fromisoformat(now_iso()).strftime("%H:%M")
                sess["note"] = sess.get("note", "") +  ("\n\n" if "note" in sess else "") + f"[{record_time_str}] {content}"
                write_tasks(date_str, tasks)
                print(f"[green]已为当前session添加备注:[/green] {content}")
                return

    print("[red]当前没有正在进行的任务，无法添加备注[/red]")


@app.command()
def note_select():
    """选择历史 session 添加备注"""
    date_str = today_date()
    tasks = read_tasks(date_str)

    sessions = []
    for task in tasks:
        for idx, sess in enumerate(task["sessions"]):
            start = datetime.fromisoformat(sess["start_time"]).strftime("%H:%M")
            end = (
                datetime.fromisoformat(sess["end_time"]).strftime("%H:%M")
                if sess["end_time"]
                else "进行中"
            )
            sessions.append((task, idx, f"{task['description']} {start} - {end}"))

    if not sessions:
        print("[yellow]当天没有任何session记录[/yellow]")
        raise typer.Exit()

    for i, (_, _, desc) in enumerate(sessions, 1):
        print(f"[{i}] {desc}")

    choice = int(input("请选择session编号: ")) - 1
    if not (0 <= choice < len(sessions)):
        print("[red]选择无效[/red]")
        raise typer.Exit()

    note_content = input("请输入备注内容: ").strip()

    task, idx, _ = sessions[choice]
    task["sessions"][idx]["note"] = note_content
    write_tasks(date_str, tasks)

    print(f"[green]已添加备注:[/green] {note_content}")


if __name__ == "__main__":
    app()
