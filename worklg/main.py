#!/usr/bin/env python3
import typer
from rich import print
from rich.console import Console
from rich.table import Table
from datetime import datetime, timedelta
from typing import Optional

from storage import read_tasks, write_tasks
from utils import (
    a_month_ago,
    now_iso,
    percent,
    today_date,
    smart_ljust,
    smart_truncate,
    gen_id,
    duration_minutes,
    format_duration,
    pick_color_rgb,
    weekday,
)

app = typer.Typer()
view_app = typer.Typer()
app.add_typer(view_app, name="view")

console = Console()


def select_task(tasks, selector: str):
    """根据编号或者关键词选择已有任务，如果没有匹配，返回 None"""
    # sort by staot_time

    tasks = merged_by_description(tasks)
    tasks.sort(key=lambda t: datetime.fromisoformat(t["sessions"][-1]["end_time"]))
    if selector.isdigit():
        index = int(selector) - 1
        if 0 <= index < len(tasks):
            return tasks[index]
        else:
            print("[red]编号超出范围[/red]")
            raise typer.Exit()
    else:
        matched = [task for task in reversed(tasks) if selector in task["description"]]
        if len(matched) == 0:
            return None
        elif len(matched) == 1:
            return matched[0]
        else:
            print("匹配到多条，请选择：")
            for idx, task in enumerate(matched, 1):
                print(f"[{idx}] ({weekday(task['sessions'][-1]['end_time'][:10])[:3]} {task['sessions'][-1]['end_time'][:10]} {task['sessions'][-1]['end_time'][11:16]}) {task['description']}")
            choice = int(input("请输入编号: ")) - 1
            if 0 <= choice < len(matched):
                return matched[choice]
            else:
                print("[red]选择无效[/red]")
                raise typer.Exit()

def merged_by_description(tasks):
    """合并相同描述的任务"""
    merged = {}
    for task in tasks:
        desc = task["description"]
        if desc not in merged:
            merged[desc] = {
                "id": task["id"],
                "description": desc,
                "sessions": []
            }
        merged[desc]["sessions"].extend(task["sessions"])
        merged[desc]["sessions"].sort(key=lambda s: s["end_time"])
    
    return list(merged.values())

@app.command()
def start(
    selector: str,
    at: Optional[str] = typer.Option(None, "--at", help="开始时间 hh:mm"),
    search_from: Optional[str] = typer.Option(None, "--search-from", help="回溯直到这个时间点 (格式 YYYY-MM-DD), 默认仅搜索当天任务"),
):
    """开始或继续一个任务 (支持编号/关键词，新建任务也可以；智能连接最近session)"""
    date_str = today_date()
    tasks = read_tasks(date_str)

    # 检查是否已有活跃任务
    for task in tasks:
        for sess in task["sessions"]:
            if sess["end_time"] is None:
                print("[red]已有正在进行中的任务，请先 stop 或 push[/red]")
                raise typer.Exit()

    search_date = datetime.fromisoformat(date_str)
    history_tasks = []
    if not search_from:
        search_from = date_str
    while search_date >= datetime.fromisoformat(search_from):
        history_tasks.extend(read_tasks(search_date.strftime("%Y-%m-%d")))
        search_date = search_date - timedelta(days=1)

    task = select_task(history_tasks, selector)
    if task is None:
        # 没有匹配，创建新的任务
        task = {"id": gen_id(), "description": selector, "sessions": []}
        tasks.append(task)
        print(f"[green]新建任务:[/green] {selector}")
    elif task is not None:
        print(f"[green]找到任务:[/green] {task['description']} ({task['sessions'][-1]['end_time'][:10]})")

        exists_task = [task for task in tasks if task["description"] == task["description"]]
        exists_task = exists_task[0] if len(exists_task) > 0 else None
        if exists_task:
            task = exists_task
        else:
            task['sessions'] = []
            tasks.append(task)

    start_at = datetime.now() if at == None else datetime.fromisoformat(f"{date_str}T{at}:00")

    # 查找最后一个 session
    last_session = task["sessions"][-1] if task["sessions"] else None

    if last_session and last_session["end_time"]:
        end_time = datetime.fromisoformat(last_session["end_time"])
        diff_sec = (start_at - end_time).total_seconds()

        if diff_sec <= 60:
            # 恢复上一个 session
            last_session["end_time"] = None
            print(f"[green]继续上一个session (距上次结束{int(diff_sec)}秒内)[/green]")
        else:
            # 新开session
            task["sessions"].append({
                "start_time": start_at.isoformat(timespec="seconds"),
                "end_time": None
            })
            print(f"[green]开始新的session (与上次间隔超过1分钟)[/green]")
    else:
        # 没有历史session，正常新建
        task["sessions"].append({
            "start_time": start_at.isoformat(timespec="seconds"),
            "end_time": None
        })

    write_tasks(date_str, tasks)
    print(f"[green]已开始任务:[/green] {task['description']}")


@app.command()
def stop(
    at: Optional[str] = typer.Option(None, "--at", help="结束时间 hh:mm"),
    from_cmd: bool = False, 
):
    """停止当前任务"""
    date_str = today_date()
    tasks = read_tasks(date_str)
    for task in tasks:
        for session in task["sessions"]:
            if session["end_time"] is None:
                if at != None:
                    end_time = datetime.fromisoformat(f"{date_str}T{at}:00")
                    if end_time > datetime.now():
                        print("[red]结束时间不能晚于现在[/red]")
                        raise typer.Exit()
                else:
                    end_time = datetime.now()
                session["end_time"] = end_time.isoformat(timespec="seconds")
                write_tasks(date_str, tasks)
                if not from_cmd:
                    print(f"[green]已结束当前任务:[/green] {task['description']}")
                return
    if not from_cmd:
        print("[red]没有正在进行中的任务[/red]")


@app.command()
def push(
    selector: str,
    start_at: Optional[str] = typer.Option(None, "--at", help="起始时间 hh:mm"),
):
    """切换到新的任务 (支持编号/关键词)"""
    stop(from_cmd=True, at=start_at)
    start(selector, at=start_at, search_from=a_month_ago().isoformat())

@app.command()
def pop(
    delete: bool = typer.Option(False, "--delete", help="删除当前任务"),
):
    """结束当前任务并恢复上一个任务"""
    if delete:
        date_str = today_date()
        tasks = read_tasks(date_str)
        for task in tasks:
            for sess in task['sessions']:
                if sess['end_time'] is None:
                    task['sessions'].remove(sess)
                    write_tasks(date_str, tasks)
                    print(f"[green]已删除当前 session:[/green] {task['description']}")
                    return
        print("[red]没有正在进行中的任务[/red]")
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
def curr():
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


@app.command("tl")
def view_timeline(
    from_date: Optional[str] = typer.Option(None, "--from", "--at", help="起始日期 YYYY-MM-DD"),
    to_date: Optional[str] = typer.Option(None, "--to", help="结束日期 YYYY-MM-DD"),
    filter_str: Optional[str] = typer.Option(None, "--filter", help="只显示任务描述中包含该字符串的任务"),
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

    # 收集所有 session
    sessions = []
    current_day = from_dt
    while current_day <= to_dt:
        day_str = current_day.strftime("%Y-%m-%d")
        tasks = read_tasks(day_str)
        for task in tasks:
            if filter_str and filter_str not in task["description"]:
                continue
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

    console.print(f"[bold underline green]Timeline View[/bold underline green] {format_duration(calc_total_minutes(sessions))}\n")

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
    total_minutes = calc_total_minutes(sessions)

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
                    start, end, desc, color, sess["is_running"], max_duration, total_minutes
                )
                idx += 1
            elif current_hour <= start < next_hour and end > next_hour:
                render_session(start, next_hour, desc, color, False, max_duration, total_minutes, note)
                sessions[idx]["start_time"] = next_hour.isoformat()
                break
            else:
                break

        console.print("[dim]" + "-" * 70 + "[/dim]")
        current_hour = next_hour


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

        max_task_minutes = max(info["minutes"] for info in task_infos.values())
        total_minutes = sum(info["minutes"] for info in task_infos.values())

        console.print(f"[bold cyan]{date}[/bold cyan] {format_duration(total_minutes)}")

        for desc, info in sorted(task_infos.items(), key=lambda x: -x[1]["minutes"]):
            dur_min = info["minutes"]
            start_str = info["start"].strftime('%H:%M') if info["start"] else "--:--"
            end_str = info["end"].strftime('%H:%M') if info["end"] else "--:--"
            time_range = f"[{start_str} -> {end_str}]"

            color = pick_color_rgb(desc)
            bar_len = max(1, int(dur_min / max_task_minutes * 10))
            bar = '[green]' + "▄" * bar_len + '[/]' + "▁" * (10 - bar_len) + f" {percent(dur_min / total_minutes)}"
            dur_fmt = smart_ljust(format_duration(dur_min), 5)
            desc = smart_truncate(desc, 50)  # 为了加 time_range留空间
            desc = smart_ljust(desc, 50)

            line = f"  {time_range} [{color}]{desc}[/] {dur_fmt} {bar}"
            console.print(line)

        console.print("[dim]" + "-" * 70 + "[/dim]")



def render_session(start, end, desc, color, is_running, max_duration, total_minutes, note=None):
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
    bar = f"[{'#F59E0B' if is_running else 'green'}]" + "▄" * bar_len + '[/]' + f"[{'#FEF3C7' if is_running else 'white'}]" + "▁" * (10 - bar_len) + '[/]' + f" {percent(dur_min / total_minutes)}"

    line = f"{' 🕒' if is_running else '   '}{time_range} [{color}]{desc}[/] {dur_fmt} {bar}"

    console.print(line)


@app.command("task")
def view_task(
    selector: Optional[str] = typer.Argument(None),
    at: Optional[str] = typer.Option(None, "--at", help="日期 YYYY-MM-DD"),
):
    """查看单个任务的所有 session 详细信息 (带Time Bar)"""
    date_str = today_date() if at is None else at
    tasks = read_tasks(date_str)

    task = select_task(tasks, selector)

    if not task:
        print("[red]没有找到符合条件的任务[/red]")
        raise typer.Exit()

    sessions = task["sessions"]
    sessions.sort(key=lambda s: s["start_time"])
    total_minutes = calc_total_minutes(sessions)

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("No.", width=3)
    table.add_column("Start", width=6)
    table.add_column("End", width=6)
    table.add_column("Duration", width=8)
    table.add_column(format_duration(total_minutes), width=18)
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
        bar = '[green]' + "▄" * bar_len + '[/]' + "▁" * (10 - bar_len) + f" {percent(dur_min / total_minutes)}"

        table.add_row(str(idx), start, end, dur_fmt, bar, note)

    console.print(
        f"[bold underline green]Task Detail:[/bold underline green] {task['description']}\n"
    )
    console.print(table)

def calc_total_minutes(sessions):
    return sum(
        duration_minutes(s["start_time"], s["end_time"] or now_iso())
        for s in sessions
    )

@app.command("ls")
def view_tasks(
    selector: Optional[str] = typer.Argument(None),
    at: Optional[str] = typer.Option(None, "--at", help="日期 YYYY-MM-DD"),
    week: bool = typer.Option(False, "--week", help="查看整周任务汇总"),
    from_date: Optional[str] = typer.Option(None, "--from", help="起始日期 YYYY-MM-DD"),
    to_date: Optional[str] = typer.Option(None, "--to", help="结束日期 YYYY-MM-DD"),
    filter_str: Optional[str] = typer.Option(None, "--filter", help="只显示任务描述中包含该字符串的任务"),
):
    """按任务维度的表格视图（支持单天、周报、跨天聚合）"""

    if selector is not None:
        view_task(selector, at)
        return

    # 判断是否为跨天聚合视图
    if week or from_date or to_date:
        # ✅ 多日聚合逻辑
        base = datetime.fromisoformat(at) if at else datetime.today()
        from_dt = datetime.fromisoformat(from_date) if from_date else (base - timedelta(days=base.weekday()) if week else base)
        to_dt = datetime.fromisoformat(to_date) if to_date else (from_dt + timedelta(days=6) if week else from_dt)

        if from_dt > to_dt:
            print("[red]起始日期不能晚于结束日期[/red]")
            raise typer.Exit()

        from collections import defaultdict
        grouped = defaultdict(lambda: {
            "duration": 0,
            "start_time": None,
            "end_time": None,
            "is_running": False
        })

        current = from_dt
        while current <= to_dt:
            date_str = current.strftime("%Y-%m-%d")
            tasks = read_tasks(date_str)
            for task in tasks:
                for sess in task["sessions"]:
                    start = datetime.fromisoformat(sess["start_time"])
                    end = datetime.fromisoformat(sess["end_time"] or now_iso())
                    dur = (end - start).total_seconds() / 60
                    desc = task["description"]
                    if filter_str and filter_str not in desc:
                        continue
                    grouped[desc]["duration"] += dur
                    grouped[desc]["is_running"] |= (sess["end_time"] is None)
                    grouped[desc]["start_time"] = min(grouped[desc]["start_time"], start) if grouped[desc]["start_time"] else start
                    grouped[desc]["end_time"] = max(grouped[desc]["end_time"], end) if grouped[desc]["end_time"] else end
            current += timedelta(days=1)

        if not grouped:
            print("[yellow]指定日期范围内没有任务记录[/yellow]")
            return

        top_minutes = max(g["duration"] for g in grouped.values())
        total_minutes = sum(g["duration"] for g in grouped.values())

        table = Table(show_header=True, header_style="bold blue")
        table.add_column("No.", width=3)
        table.add_column("Task", width=50)
        table.add_column("Start", width=6)
        table.add_column("End", width=6)
        table.add_column("Duration", width=8)
        table.add_column(f"{format_duration(total_minutes)}", width=18)

        for idx, (desc, g) in enumerate(sorted(grouped.items(), key=lambda x: -x[1]["duration"]), 1):
            start_str = g["start_time"].strftime("%m-%d")
            end_str = "[yellow]进行中[/yellow]" if g["is_running"] else g["end_time"].strftime("%m-%d")
            dur_fmt = format_duration(int(g["duration"]))
            bar_len = max(1, int(g["duration"] / top_minutes * 10))
            bar = '[green]' + "▄" * bar_len + '[/]' + "▁" * (10 - bar_len) + f" {percent(g['duration'] / total_minutes)}"
            table.add_row(str(idx), desc, start_str, end_str, dur_fmt, bar)

        console.print(
            f"[bold underline green]Task Summary:[/bold underline green] {from_dt.strftime('%Y-%m-%d')} ~ {to_dt.strftime('%Y-%m-%d')}"
        )
        console.print(table)
        return

    # ✅ 默认单天视图逻辑（保留原逻辑）
    if selector != None:
        view_task(selector, at)
        return

    date_str = today_date() if at is None else at
    tasks = read_tasks(date_str)

    if not tasks:
        print("[yellow]当天没有任务记录[/yellow]")
        return

    top_minutes = 0
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
        total_minutes += dur
        top_minutes = max(top_minutes, dur)

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

    # render
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("No.", width=3)
    table.add_column("Task", width=50)
    table.add_column("Start", width=6)
    table.add_column("End", width=6)
    table.add_column("Duration", width=8)
    table.add_column(format_duration(total_minutes), width=18)

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

        bar_len = max(1, int(info["duration"] / top_minutes * 10))
        bar = '[green]' + "▄" * bar_len + '[/]' + "▁" * (10 - bar_len) + f" {percent(info['duration'] / total_minutes)}"

        table.add_row(str(idx), description_str, start_str, end_str, dur_fmt, bar)

    console.print(table)


def has_conflict(tasks, new_start: datetime, new_end: datetime):
    """检查新的时间段是否与现有session冲突"""
    for task in tasks:
        for sess in task["sessions"]:
            sess_start = datetime.fromisoformat(sess["start_time"])
            sess_end = datetime.fromisoformat(sess["end_time"] or now_iso())

            if new_end != None and sess_start < new_end and new_start < sess_end:
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
        end_dt = datetime.fromisoformat(f"{today}T{end_input}:00") if len(end_input) != 0 else None

        if end_dt != None and start_dt >= end_dt:
            print("[red]开始时间必须早于结束时间[/red]")
            raise typer.Exit()
        if end_dt != None and end_dt > datetime.now():
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
            "end_time": end_dt.isoformat(timespec="seconds") if end_dt != None else None,
        }
    )

    write_tasks(date_str, tasks)
    print(f"[green]已补录session:[/green] {start_input} -> {end_input}  {task['description']}")


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

    record_time_str = datetime.fromisoformat(now_iso()).strftime("%H:%M")
    task["sessions"][idx]["note"] = task["sessions"][idx].get("note", "") +  ("\n\n" if "note" in task["sessions"][idx] else "") + f"[{record_time_str}] {note_content}"

    write_tasks(date_str, tasks)

    print(f"[green]已添加备注:[/green] {note_content}")


if __name__ == "__main__":
    app()
