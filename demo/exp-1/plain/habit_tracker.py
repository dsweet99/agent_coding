#!/usr/bin/env python3
"""Daily Habit Tracker CLI - Track daily habits and maintain consistency."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import click

DATA_DIR = Path.home() / ".habit_tracker"
DATA_FILE = DATA_DIR / "data.json"


def _ensure_data_dir():
    """Create data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_data():
    """Load habit data from file, returning empty structure if not found."""
    _ensure_data_dir()
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"habits": {}, "completions": {}}


def _save_data(data):
    """Save habit data to file."""
    _ensure_data_dir()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _get_next_id(habits):
    """Get the next available habit ID."""
    if not habits:
        return 1
    return max(int(k) for k in habits.keys()) + 1


def _find_habit(habits, identifier):
    """Find a habit by ID or name. Returns (id, habit_data) or (None, None)."""
    if identifier in habits:
        return identifier, habits[identifier]
    for habit_id, habit_data in habits.items():
        if habit_data["name"].lower() == identifier.lower():
            return habit_id, habit_data
    return None, None


def _parse_date(date_str):
    """Parse a date string in YYYY-MM-DD format. Returns (date, error_message)."""
    if date_str is None:
        return date.today(), None
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
        return parsed, None
    except ValueError:
        return None, f"Invalid date format: '{date_str}'. Use YYYY-MM-DD format."


VALID_FREQUENCIES = ["daily", "weekdays", "weekends", "weekly", "monthly"]


def _validate_frequency(frequency):
    """Validate frequency value. Returns (normalized_frequency, error_message)."""
    if frequency is None:
        return None, None
    freq_lower = frequency.lower().strip()
    if freq_lower not in VALID_FREQUENCIES:
        valid_list = ", ".join(VALID_FREQUENCIES)
        return None, f"Invalid frequency: '{frequency}'. Valid options: {valid_list}."
    return freq_lower, None


def _calculate_streaks(completion_dates, reference_date=None):
    """Calculate current and longest streak from a list of date strings.

    Current streak counts consecutive days ending on reference_date (or yesterday if
    reference_date wasn't completed). Longest streak is the maximum consecutive run.

    Returns (current_streak, longest_streak).
    """
    if not completion_dates:
        return 0, 0

    if reference_date is None:
        reference_date = date.today()

    dates = sorted(datetime.strptime(d, "%Y-%m-%d").date() for d in completion_dates)

    longest_streak = 1
    current_run = 1

    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            current_run += 1
            longest_streak = max(longest_streak, current_run)
        else:
            current_run = 1

    current_streak = 0
    check_date = reference_date

    if check_date not in dates:
        check_date = reference_date - timedelta(days=1)

    if check_date in dates:
        current_streak = 1
        prev_date = check_date - timedelta(days=1)
        while prev_date in dates:
            current_streak += 1
            prev_date -= timedelta(days=1)

    return current_streak, longest_streak


@click.group()
@click.version_option(version="0.1.0", prog_name="habit-tracker")
def cli():
    """Daily Habit Tracker - Track your habits and build consistency.

    A simple command-line tool to define habits, log daily completions,
    and view your progress over time.
    """
    pass


@cli.group()
def habits():
    """Manage your habits (add, list, remove)."""
    pass


@habits.command("add")
@click.argument("name")
@click.option("--description", "-d", default=None, help="Optional description of the habit.")
@click.option(
    "--frequency",
    "-f",
    default=None,
    help="Target frequency (daily, weekdays, weekends, weekly, monthly).",
)
def habits_add(name, description, frequency):
    """Add a new habit to track."""
    name = name.strip()
    if not name:
        click.echo("Error: Habit name cannot be empty.", err=True)
        raise SystemExit(1)

    freq, error = _validate_frequency(frequency)
    if error:
        click.echo(f"Error: {error}", err=True)
        raise SystemExit(1)

    data = _load_data()

    for habit_data in data["habits"].values():
        if habit_data["name"].lower() == name.lower():
            click.echo(f"Error: Habit '{name}' already exists.", err=True)
            raise SystemExit(1)

    habit_id = str(_get_next_id(data["habits"]))
    habit_entry = {"name": name}
    if description:
        habit_entry["description"] = description.strip()
    if freq:
        habit_entry["frequency"] = freq
    data["habits"][habit_id] = habit_entry
    _save_data(data)

    click.echo(f"Added habit '{name}' (id: {habit_id})")


@habits.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Show metadata details.")
def habits_list(verbose):
    """List all habits being tracked."""
    data = _load_data()
    habits = data["habits"]

    if not habits:
        click.echo("No habits tracked yet. Use 'habits add <name>' to add one.")
        return

    click.echo("Habits:")
    for habit_id, habit_data in sorted(habits.items(), key=lambda x: int(x[0])):
        line = f"  [{habit_id}] {habit_data['name']}"

        if verbose:
            click.echo(line)
            if "description" in habit_data:
                click.echo(f"        Description: {habit_data['description']}")
            if "frequency" in habit_data:
                click.echo(f"        Frequency:   {habit_data['frequency']}")
        else:
            meta_parts = []
            if "frequency" in habit_data:
                meta_parts.append(habit_data["frequency"])
            if meta_parts:
                line += f" ({', '.join(meta_parts)})"
            click.echo(line)


@habits.command("remove")
@click.argument("identifier")
def habits_remove(identifier):
    """Remove a habit from tracking.

    IDENTIFIER can be the habit ID or name.
    """
    data = _load_data()
    habit_id, habit_data = _find_habit(data["habits"], identifier)

    if habit_id is None:
        click.echo(f"Error: Habit '{identifier}' not found.", err=True)
        raise SystemExit(1)

    habit_name = habit_data["name"]
    del data["habits"][habit_id]

    if habit_id in data["completions"]:
        del data["completions"][habit_id]

    _save_data(data)
    click.echo(f"Removed habit '{habit_name}' (id: {habit_id})")


@habits.command("update")
@click.argument("identifier")
@click.option("--name", "-n", default=None, help="New name for the habit.")
@click.option(
    "--description", "-d", default=None, help="New description (use empty string to clear)."
)
@click.option(
    "--frequency",
    "-f",
    default=None,
    help="New frequency (daily, weekdays, weekends, weekly, monthly, or empty to clear).",
)
def habits_update(identifier, name, description, frequency):
    """Update a habit's name, description, or frequency.

    IDENTIFIER can be the habit ID or name.
    Use an empty string to clear a field (e.g., --description "").
    """
    if name is None and description is None and frequency is None:
        click.echo(
            "Error: Provide at least one option to update (--name, --description, or --frequency).",
            err=True,
        )
        raise SystemExit(1)

    data = _load_data()
    habit_id, habit_data = _find_habit(data["habits"], identifier)

    if habit_id is None:
        click.echo(f"Error: Habit '{identifier}' not found.", err=True)
        raise SystemExit(1)

    original_name = habit_data["name"]
    updates = []

    if name is not None:
        name_stripped = name.strip()
        if not name_stripped:
            click.echo("Error: Habit name cannot be empty.", err=True)
            raise SystemExit(1)
        if name_stripped.lower() != original_name.lower():
            for other_id, other_data in data["habits"].items():
                if other_id != habit_id and other_data["name"].lower() == name_stripped.lower():
                    click.echo(f"Error: Habit '{name_stripped}' already exists.", err=True)
                    raise SystemExit(1)
        data["habits"][habit_id]["name"] = name_stripped
        updates.append(f"name ('{original_name}' -> '{name_stripped}')")

    if description is not None:
        desc_stripped = description.strip()
        if desc_stripped:
            data["habits"][habit_id]["description"] = desc_stripped
            updates.append("description")
        else:
            data["habits"][habit_id].pop("description", None)
            updates.append("description (cleared)")

    if frequency is not None:
        freq_stripped = frequency.strip()
        if freq_stripped:
            freq, error = _validate_frequency(freq_stripped)
            if error:
                click.echo(f"Error: {error}", err=True)
                raise SystemExit(1)
            data["habits"][habit_id]["frequency"] = freq
            updates.append("frequency")
        else:
            data["habits"][habit_id].pop("frequency", None)
            updates.append("frequency (cleared)")

    _save_data(data)
    click.echo(f"Updated '{original_name}': {', '.join(updates)}.")


@habits.command("show")
@click.argument("identifier")
def habits_show(identifier):
    """Show detailed information about a habit.

    IDENTIFIER can be the habit ID or name.
    """
    data = _load_data()
    habit_id, habit_data = _find_habit(data["habits"], identifier)

    if habit_id is None:
        click.echo(f"Error: Habit '{identifier}' not found.", err=True)
        raise SystemExit(1)

    click.echo(f"Habit: {habit_data['name']} (id: {habit_id})")

    if "description" in habit_data:
        click.echo(f"  Description: {habit_data['description']}")
    else:
        click.echo("  Description: (none)")

    if "frequency" in habit_data:
        click.echo(f"  Frequency:   {habit_data['frequency']}")
    else:
        click.echo("  Frequency:   (none)")


@cli.group()
def log():
    """Log habit completions."""
    pass


@log.command("done")
@click.argument("habit")
@click.option(
    "--date",
    "-d",
    "date_str",
    default=None,
    help="Date of completion (YYYY-MM-DD). Defaults to today.",
)
def log_done(habit, date_str):
    """Mark a habit as completed."""
    completion_date, error = _parse_date(date_str)
    if error:
        click.echo(f"Error: {error}", err=True)
        raise SystemExit(1)

    data = _load_data()
    habit_id, habit_data = _find_habit(data["habits"], habit)

    if habit_id is None:
        click.echo(f"Error: Habit '{habit}' not found.", err=True)
        raise SystemExit(1)

    date_key = completion_date.isoformat()

    if habit_id not in data["completions"]:
        data["completions"][habit_id] = []

    if date_key in data["completions"][habit_id]:
        click.echo(f"'{habit_data['name']}' already marked done for {date_key}.")
        return

    data["completions"][habit_id].append(date_key)
    data["completions"][habit_id].sort()
    _save_data(data)

    click.echo(f"Logged '{habit_data['name']}' as done for {date_key}.")


@log.command("undo")
@click.argument("habit")
@click.option(
    "--date", "-d", "date_str", default=None, help="Date to undo (YYYY-MM-DD). Defaults to today."
)
def log_undo(habit, date_str):
    """Remove a completion record for a habit."""
    completion_date, error = _parse_date(date_str)
    if error:
        click.echo(f"Error: {error}", err=True)
        raise SystemExit(1)

    data = _load_data()
    habit_id, habit_data = _find_habit(data["habits"], habit)

    if habit_id is None:
        click.echo(f"Error: Habit '{habit}' not found.", err=True)
        raise SystemExit(1)

    date_key = completion_date.isoformat()

    if habit_id not in data["completions"] or date_key not in data["completions"][habit_id]:
        click.echo(f"No completion record for '{habit_data['name']}' on {date_key}.")
        return

    data["completions"][habit_id].remove(date_key)
    _save_data(data)

    click.echo(f"Removed completion for '{habit_data['name']}' on {date_key}.")


@cli.group()
def progress():
    """View habit progress and statistics."""
    pass


@progress.command("show")
@click.argument("habit", required=False)
def progress_show(habit):
    """Show progress for a habit or all habits.

    Displays total completions, current streak, and longest streak.
    """
    data = _load_data()
    habits_data = data["habits"]
    completions = data["completions"]

    if not habits_data:
        click.echo("No habits tracked yet. Use 'habits add <name>' to add one.")
        return

    if habit:
        habit_id, habit_info = _find_habit(habits_data, habit)
        if habit_id is None:
            click.echo(f"Error: Habit '{habit}' not found.", err=True)
            raise SystemExit(1)
        habits_to_show = [(habit_id, habit_info)]
    else:
        habits_to_show = sorted(habits_data.items(), key=lambda x: int(x[0]))

    for habit_id, habit_info in habits_to_show:
        habit_completions = completions.get(habit_id, [])
        total = len(habit_completions)
        current, longest = _calculate_streaks(habit_completions)

        click.echo(f"{habit_info['name']}:")
        click.echo(f"  Total completions: {total}")
        click.echo(f"  Current streak:    {current} day(s)")
        click.echo(f"  Longest streak:    {longest} day(s)")


@progress.command("streaks")
def progress_streaks():
    """Show current and longest streaks for all habits."""
    data = _load_data()
    habits = data["habits"]
    completions = data["completions"]

    if not habits:
        click.echo("No habits tracked yet. Use 'habits add <name>' to add one.")
        return

    click.echo("Streaks:")
    for habit_id, habit_data in sorted(habits.items(), key=lambda x: int(x[0])):
        habit_completions = completions.get(habit_id, [])
        current, longest = _calculate_streaks(habit_completions)
        click.echo(f"  {habit_data['name']}: {current} day(s) current, {longest} day(s) longest")


@progress.command("history")
@click.argument("habit", required=False)
@click.option("--days", "-n", default=7, help="Number of days to show (default: 7).")
def progress_history(habit, days):
    """Show recent completion history.

    Displays a day-by-day view of completions for the specified number of days.
    """
    data = _load_data()
    habits_data = data["habits"]
    completions = data["completions"]

    if not habits_data:
        click.echo("No habits tracked yet. Use 'habits add <name>' to add one.")
        return

    if habit:
        habit_id, habit_info = _find_habit(habits_data, habit)
        if habit_id is None:
            click.echo(f"Error: Habit '{habit}' not found.", err=True)
            raise SystemExit(1)
        habits_to_show = [(habit_id, habit_info)]
    else:
        habits_to_show = sorted(habits_data.items(), key=lambda x: int(x[0]))

    today = date.today()
    date_range = [today - timedelta(days=i) for i in range(days)]

    for habit_id, habit_info in habits_to_show:
        habit_completions = set(completions.get(habit_id, []))
        click.echo(f"{habit_info['name']}:")

        for d in date_range:
            date_str = d.isoformat()
            status = "[x]" if date_str in habit_completions else "[ ]"
            day_name = d.strftime("%a")
            click.echo(f"  {date_str} ({day_name}): {status}")

        if len(habits_to_show) > 1:
            click.echo()


def _get_week_boundaries(reference_date=None):
    """Get the start (Monday) and end (Sunday) of the week containing the reference date."""
    if reference_date is None:
        reference_date = date.today()
    weekday = reference_date.weekday()
    week_start = reference_date - timedelta(days=weekday)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def _calculate_completion_rate(completion_dates, start_date, end_date):
    """Calculate completion rate for a date range.

    Returns (completed_count, total_days, rate_percentage).
    """
    total_days = (end_date - start_date).days + 1
    if total_days <= 0:
        return 0, 0, 0.0

    completed_count = sum(
        1
        for d in completion_dates
        if start_date <= datetime.strptime(d, "%Y-%m-%d").date() <= end_date
    )
    rate = (completed_count / total_days) * 100
    return completed_count, total_days, rate


def _identify_at_risk_habits(habits_data, completions):
    """Identify habits at risk of losing their streak.

    A habit is at risk if:
    - It has a current streak of 2+ days, AND
    - It was NOT completed today

    Returns list of (habit_id, habit_name, current_streak).
    """
    at_risk = []
    today = date.today()
    today_str = today.isoformat()

    for habit_id, habit_info in habits_data.items():
        habit_completions = completions.get(habit_id, [])
        current, _ = _calculate_streaks(habit_completions)

        if current >= 2 and today_str not in habit_completions:
            at_risk.append((habit_id, habit_info["name"], current))

    return sorted(at_risk, key=lambda x: -x[2])


@progress.command("weekly")
@click.option("--week-offset", "-w", default=0, help="Weeks ago (0=current, 1=last week, etc.).")
def progress_weekly(week_offset):
    """Show weekly summary report across all habits.

    Displays completion rates and streak status for the week.
    """
    data = _load_data()
    habits_data = data["habits"]
    completions = data["completions"]

    if not habits_data:
        click.echo("No habits tracked yet. Use 'habits add <name>' to add one.")
        return

    reference_date = date.today() - timedelta(weeks=week_offset)
    week_start, week_end = _get_week_boundaries(reference_date)

    click.echo(f"Weekly Summary: {week_start.isoformat()} to {week_end.isoformat()}")
    click.echo("=" * 50)

    total_completions = 0
    total_possible = 0

    for habit_id, habit_info in sorted(habits_data.items(), key=lambda x: int(x[0])):
        habit_completions = completions.get(habit_id, [])
        completed, days, rate = _calculate_completion_rate(habit_completions, week_start, week_end)
        current_streak, longest_streak = _calculate_streaks(habit_completions)

        total_completions += completed
        total_possible += days

        click.echo(f"\n{habit_info['name']}:")
        click.echo(f"  Completed: {completed}/{days} days ({rate:.0f}%)")
        click.echo(f"  Streak:    {current_streak} day(s) current, {longest_streak} day(s) best")

        week_dates = [week_start + timedelta(days=i) for i in range(7)]
        week_grid = ""
        for d in week_dates:
            day_abbrev = d.strftime("%a")[0]
            if d.isoformat() in habit_completions:
                week_grid += f"[{day_abbrev}]"
            else:
                week_grid += f" {day_abbrev} "
        click.echo(f"  Week:      {week_grid}")

    click.echo("\n" + "=" * 50)
    if total_possible > 0:
        overall_rate = (total_completions / total_possible) * 100
        click.echo(
            f"Overall: {total_completions}/{total_possible} completions ({overall_rate:.0f}%)"
        )
    else:
        click.echo("Overall: No data for this period.")


@progress.command("at-risk")
def progress_at_risk():
    """Show habits at risk of losing their streak.

    Lists habits with a streak of 2+ days that haven't been completed today.
    """
    data = _load_data()
    habits_data = data["habits"]
    completions = data["completions"]

    if not habits_data:
        click.echo("No habits tracked yet. Use 'habits add <name>' to add one.")
        return

    at_risk = _identify_at_risk_habits(habits_data, completions)

    if not at_risk:
        click.echo("No habits at risk of losing their streak.")
        click.echo("(All streaks are either maintained today or are less than 2 days.)")
        return

    click.echo("Habits at risk of losing their streak:")
    click.echo("-" * 40)

    for habit_id, habit_name, current_streak in at_risk:
        click.echo(f"  {habit_name}: {current_streak} day streak (not done today!)")

    click.echo("\nComplete these today to keep your streaks going!")


@progress.command("rate")
@click.option("--start", "-s", "start_str", required=True, help="Start date (YYYY-MM-DD).")
@click.option(
    "--end", "-e", "end_str", default=None, help="End date (YYYY-MM-DD). Defaults to today."
)
@click.argument("habit", required=False)
def progress_rate(start_str, end_str, habit):
    """Show completion rate for a date range.

    Calculates completion percentage for the specified period.
    """
    start_date, error = _parse_date(start_str)
    if error:
        click.echo(f"Error: {error}", err=True)
        raise SystemExit(1)

    if end_str:
        end_date, error = _parse_date(end_str)
        if error:
            click.echo(f"Error: {error}", err=True)
            raise SystemExit(1)
    else:
        end_date = date.today()

    if start_date > end_date:
        click.echo("Error: Start date must be before or equal to end date.", err=True)
        raise SystemExit(1)

    data = _load_data()
    habits_data = data["habits"]
    completions = data["completions"]

    if not habits_data:
        click.echo("No habits tracked yet. Use 'habits add <name>' to add one.")
        return

    if habit:
        habit_id, habit_info = _find_habit(habits_data, habit)
        if habit_id is None:
            click.echo(f"Error: Habit '{habit}' not found.", err=True)
            raise SystemExit(1)
        habits_to_show = [(habit_id, habit_info)]
    else:
        habits_to_show = sorted(habits_data.items(), key=lambda x: int(x[0]))

    total_days = (end_date - start_date).days + 1
    click.echo(
        f"Completion Rate: {start_date.isoformat()} to {end_date.isoformat()} ({total_days} days)"
    )
    click.echo("-" * 50)

    total_completions = 0
    total_possible = 0

    for habit_id, habit_info in habits_to_show:
        habit_completions = completions.get(habit_id, [])
        completed, days, rate = _calculate_completion_rate(habit_completions, start_date, end_date)

        total_completions += completed
        total_possible += days

        bar_width = 20
        filled = int(rate / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        click.echo(f"  {habit_info['name']}: {completed}/{days} ({rate:.1f}%) {bar}")

    if len(habits_to_show) > 1:
        click.echo("-" * 50)
        if total_possible > 0:
            overall_rate = (total_completions / total_possible) * 100
            click.echo(f"  Total: {total_completions}/{total_possible} ({overall_rate:.1f}%)")


@progress.command("report")
def progress_report():
    """Show an at-a-glance report useful for planning the next week.

    Combines weekly summary, at-risk habits, and recent trends.
    """
    data = _load_data()
    habits_data = data["habits"]
    completions = data["completions"]

    if not habits_data:
        click.echo("No habits tracked yet. Use 'habits add <name>' to add one.")
        return

    today = date.today()
    this_week_start, this_week_end = _get_week_boundaries(today)
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start - timedelta(days=1)

    click.echo("=" * 60)
    click.echo("                    HABIT TRACKER REPORT")
    click.echo(f"                    {today.isoformat()}")
    click.echo("=" * 60)

    at_risk = _identify_at_risk_habits(habits_data, completions)
    if at_risk:
        click.echo("\n⚠ STREAKS AT RISK (complete today!):")
        for _, habit_name, streak in at_risk[:5]:
            click.echo(f"    • {habit_name} ({streak} day streak)")

    click.echo(f"\nTHIS WEEK ({this_week_start.isoformat()} - {this_week_end.isoformat()}):")
    click.echo("-" * 60)

    this_week_total = 0
    this_week_possible = 0
    last_week_total = 0
    last_week_possible = 0

    for habit_id, habit_info in sorted(habits_data.items(), key=lambda x: int(x[0])):
        habit_completions = completions.get(habit_id, [])

        tw_completed, tw_days, tw_rate = _calculate_completion_rate(
            habit_completions, this_week_start, this_week_end
        )
        lw_completed, lw_days, lw_rate = _calculate_completion_rate(
            habit_completions, last_week_start, last_week_end
        )

        this_week_total += tw_completed
        this_week_possible += tw_days
        last_week_total += lw_completed
        last_week_possible += lw_days

        current_streak, _ = _calculate_streaks(habit_completions)

        trend = ""
        if lw_rate > 0:
            if tw_rate > lw_rate:
                trend = " ↑"
            elif tw_rate < lw_rate:
                trend = " ↓"
            else:
                trend = " →"

        click.echo(
            f"  {habit_info['name']}: {tw_completed}/{tw_days} ({tw_rate:.0f}%){trend}  [streak: {current_streak}d]"
        )

    click.echo("\n" + "-" * 60)

    if this_week_possible > 0:
        this_week_rate = (this_week_total / this_week_possible) * 100
        click.echo(
            f"This week overall: {this_week_total}/{this_week_possible} ({this_week_rate:.0f}%)"
        )

    if last_week_possible > 0:
        last_week_rate = (last_week_total / last_week_possible) * 100
        click.echo(
            f"Last week overall: {last_week_total}/{last_week_possible} ({last_week_rate:.0f}%)"
        )

        if this_week_possible > 0:
            diff = this_week_rate - last_week_rate
            if diff > 0:
                click.echo(f"Trend: +{diff:.0f}% improvement from last week")
            elif diff < 0:
                click.echo(f"Trend: {diff:.0f}% from last week")
            else:
                click.echo("Trend: Steady from last week")

    click.echo("\n" + "=" * 60)


@cli.group()
def data():
    """Import and export tracking data."""
    pass


def _validate_import_data(data):
    """Validate structure and content of imported data.

    Returns (is_valid, error_message).
    """
    if not isinstance(data, dict):
        return False, "Invalid format: root must be a JSON object."

    if "habits" not in data or "completions" not in data:
        return False, "Invalid format: missing 'habits' or 'completions' field."

    if not isinstance(data["habits"], dict):
        return False, "Invalid format: 'habits' must be an object."

    if not isinstance(data["completions"], dict):
        return False, "Invalid format: 'completions' must be an object."

    for habit_id, habit_data in data["habits"].items():
        if not isinstance(habit_data, dict):
            return False, f"Invalid habit entry for id '{habit_id}': must be an object."

        if "name" not in habit_data:
            return False, f"Invalid habit entry for id '{habit_id}': missing 'name' field."

        if not isinstance(habit_data["name"], str) or not habit_data["name"].strip():
            return (
                False,
                f"Invalid habit entry for id '{habit_id}': 'name' must be a non-empty string.",
            )

        if "description" in habit_data and not isinstance(habit_data["description"], str):
            return (
                False,
                f"Invalid habit entry for id '{habit_id}': 'description' must be a string.",
            )

        if "frequency" in habit_data:
            freq = habit_data["frequency"]
            if not isinstance(freq, str) or freq.lower() not in VALID_FREQUENCIES:
                valid_list = ", ".join(VALID_FREQUENCIES)
                return (
                    False,
                    f"Invalid habit entry for id '{habit_id}': 'frequency' must be one of: {valid_list}.",
                )

    for habit_id, completion_list in data["completions"].items():
        if not isinstance(completion_list, list):
            return False, f"Invalid completions for habit id '{habit_id}': must be an array."

        for date_str in completion_list:
            if not isinstance(date_str, str):
                return (
                    False,
                    f"Invalid completion date for habit id '{habit_id}': dates must be strings.",
                )

            parsed, error = _parse_date(date_str)
            if error:
                return False, f"Invalid completion date for habit id '{habit_id}': {error}"

    return True, None


@data.command("export")
@click.argument("filepath", type=click.Path())
@click.option("--force", "-f", is_flag=True, help="Overwrite existing file without prompting.")
def data_export(filepath, force):
    """Export all tracking data to a file.

    FILEPATH is the path where the data will be saved.
    """
    export_path = Path(filepath)

    if export_path.exists() and not force:
        click.echo(f"Error: File '{filepath}' already exists. Use --force to overwrite.", err=True)
        raise SystemExit(1)

    data = _load_data()

    try:
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        click.echo(f"Error: Could not write to '{filepath}': {e}", err=True)
        raise SystemExit(1)

    habit_count = len(data["habits"])
    completion_count = sum(len(c) for c in data["completions"].values())
    click.echo(
        f"Exported {habit_count} habit(s) and {completion_count} completion(s) to '{filepath}'."
    )


@data.command("import")
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--force", "-f", is_flag=True, help="Replace existing data without prompting.")
def data_import(filepath, force):
    """Import tracking data from a file.

    FILEPATH is the path to the file to import.

    Warning: This replaces all current data.
    """
    import_path = Path(filepath)

    try:
        with open(import_path, "r") as f:
            import_data = json.load(f)
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON in '{filepath}': {e}", err=True)
        raise SystemExit(1)
    except OSError as e:
        click.echo(f"Error: Could not read '{filepath}': {e}", err=True)
        raise SystemExit(1)

    is_valid, error = _validate_import_data(import_data)
    if not is_valid:
        click.echo(f"Error: {error}", err=True)
        raise SystemExit(1)

    current_data = _load_data()
    has_existing_data = bool(current_data["habits"]) or bool(current_data["completions"])

    if has_existing_data and not force:
        click.echo("Error: Current data exists. Use --force to replace it.", err=True)
        raise SystemExit(1)

    _save_data(import_data)

    habit_count = len(import_data["habits"])
    completion_count = sum(len(c) for c in import_data["completions"].values())
    click.echo(
        f"Imported {habit_count} habit(s) and {completion_count} completion(s) from '{filepath}'."
    )


if __name__ == "__main__":
    cli()
