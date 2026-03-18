#!/usr/bin/env python3
"""Tests for Daily Habit Tracker CLI."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner
from habit_tracker import (
    DATA_DIR,
    DATA_FILE,
    _calculate_completion_rate,
    _calculate_streaks,
    _get_week_boundaries,
    _identify_at_risk_habits,
    _load_data,
    _save_data,
    _validate_import_data,
    cli,
)


@pytest.fixture
def runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Use a temporary directory for data storage during tests."""
    test_data_dir = tmp_path / ".habit_tracker"
    test_data_file = test_data_dir / "data.json"

    monkeypatch.setattr("habit_tracker.DATA_DIR", test_data_dir)
    monkeypatch.setattr("habit_tracker.DATA_FILE", test_data_file)

    return test_data_dir


class TestDataPersistence:
    """Tests for data loading and saving."""

    def test_load_data_missing_file(self, temp_data_dir):
        """Loading data when no file exists returns empty structure."""
        data = _load_data()
        assert data == {"habits": {}, "completions": {}}

    def test_load_data_empty_dir(self, temp_data_dir):
        """Loading data when directory doesn't exist creates it."""
        assert not temp_data_dir.exists()
        data = _load_data()
        assert temp_data_dir.exists()
        assert data == {"habits": {}, "completions": {}}

    def test_save_and_load_data(self, temp_data_dir):
        """Data saved is correctly loaded back."""
        test_data = {
            "habits": {"1": {"name": "Exercise"}},
            "completions": {"1": ["2024-01-01", "2024-01-02"]},
        }
        _save_data(test_data)
        loaded = _load_data()
        assert loaded == test_data

    def test_data_persists_across_operations(self, runner, temp_data_dir):
        """Data remains after multiple CLI operations."""
        runner.invoke(cli, ["habits", "add", "Meditate"])
        runner.invoke(cli, ["habits", "add", "Read"])

        data = _load_data()
        assert len(data["habits"]) == 2

        habit_names = [h["name"] for h in data["habits"].values()]
        assert "Meditate" in habit_names
        assert "Read" in habit_names


class TestCreateHabit:
    """Tests for habit creation."""

    def test_add_habit_success(self, runner, temp_data_dir):
        """Adding a new habit succeeds."""
        result = runner.invoke(cli, ["habits", "add", "Exercise"])
        assert result.exit_code == 0
        assert "Added habit 'Exercise'" in result.output

        data = _load_data()
        assert len(data["habits"]) == 1
        assert data["habits"]["1"]["name"] == "Exercise"

    def test_add_duplicate_habit_fails(self, runner, temp_data_dir):
        """Adding a habit with the same name fails."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["habits", "add", "Exercise"])

        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_add_habit_case_insensitive_duplicate(self, runner, temp_data_dir):
        """Duplicate detection is case-insensitive."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["habits", "add", "EXERCISE"])

        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_add_empty_habit_fails(self, runner, temp_data_dir):
        """Adding a habit with empty name fails."""
        result = runner.invoke(cli, ["habits", "add", "   "])
        assert result.exit_code == 1
        assert "cannot be empty" in result.output

    def test_list_habits(self, runner, temp_data_dir):
        """Listing habits shows all tracked habits."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["habits", "add", "Read"])

        result = runner.invoke(cli, ["habits", "list"])
        assert result.exit_code == 0
        assert "Exercise" in result.output
        assert "Read" in result.output

    def test_remove_habit(self, runner, temp_data_dir):
        """Removing a habit deletes it and its completions."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise"])

        result = runner.invoke(cli, ["habits", "remove", "Exercise"])
        assert result.exit_code == 0
        assert "Removed habit 'Exercise'" in result.output

        data = _load_data()
        assert len(data["habits"]) == 0
        assert "1" not in data["completions"]


class TestLogCompletion:
    """Tests for logging habit completions."""

    def test_log_done_today(self, runner, temp_data_dir):
        """Logging a completion for today succeeds."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["log", "done", "Exercise"])

        assert result.exit_code == 0
        assert "Logged 'Exercise' as done" in result.output

        data = _load_data()
        today = date.today().isoformat()
        assert today in data["completions"]["1"]

    def test_log_done_specific_date(self, runner, temp_data_dir):
        """Logging a completion for a specific date succeeds."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-15"])

        assert result.exit_code == 0
        assert "2024-06-15" in result.output

        data = _load_data()
        assert "2024-06-15" in data["completions"]["1"]

    def test_log_done_duplicate_ignored(self, runner, temp_data_dir):
        """Logging the same completion twice is handled gracefully."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-15"])
        result = runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-15"])

        assert result.exit_code == 0
        assert "already marked done" in result.output

    def test_log_done_invalid_date(self, runner, temp_data_dir):
        """Logging with invalid date format fails."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["log", "done", "Exercise", "--date", "06-15-2024"])

        assert result.exit_code == 1
        assert "Invalid date format" in result.output

    def test_log_done_nonexistent_habit(self, runner, temp_data_dir):
        """Logging a completion for nonexistent habit fails."""
        result = runner.invoke(cli, ["log", "done", "Exercise"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_log_undo(self, runner, temp_data_dir):
        """Undoing a completion removes the record."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-15"])
        result = runner.invoke(cli, ["log", "undo", "Exercise", "--date", "2024-06-15"])

        assert result.exit_code == 0
        assert "Removed completion" in result.output

        data = _load_data()
        assert "2024-06-15" not in data["completions"].get("1", [])


class TestCalculateStreak:
    """Tests for streak calculation logic."""

    def test_empty_completions(self):
        """Empty completion list returns zero streaks."""
        current, longest = _calculate_streaks([])
        assert current == 0
        assert longest == 0

    def test_single_completion_today(self):
        """Single completion today gives streak of 1."""
        today = date.today().isoformat()
        current, longest = _calculate_streaks([today])
        assert current == 1
        assert longest == 1

    def test_single_completion_yesterday(self):
        """Single completion yesterday gives streak of 1."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        current, longest = _calculate_streaks([yesterday])
        assert current == 1
        assert longest == 1

    def test_consecutive_days_streak(self):
        """Consecutive completions form a streak."""
        today = date.today()
        dates = [(today - timedelta(days=i)).isoformat() for i in range(5)]
        current, longest = _calculate_streaks(dates)
        assert current == 5
        assert longest == 5

    def test_broken_streak(self):
        """Gap in dates resets current streak."""
        today = date.today()
        dates = [
            today.isoformat(),
            (today - timedelta(days=1)).isoformat(),
            (today - timedelta(days=3)).isoformat(),
            (today - timedelta(days=4)).isoformat(),
        ]
        current, longest = _calculate_streaks(dates)
        assert current == 2
        assert longest == 2

    def test_longest_streak_in_past(self):
        """Longest streak can be from the past, not current."""
        today = date.today()
        dates = [
            today.isoformat(),
            (today - timedelta(days=10)).isoformat(),
            (today - timedelta(days=11)).isoformat(),
            (today - timedelta(days=12)).isoformat(),
            (today - timedelta(days=13)).isoformat(),
            (today - timedelta(days=14)).isoformat(),
        ]
        current, longest = _calculate_streaks(dates)
        assert current == 1
        assert longest == 5

    def test_streak_with_reference_date(self):
        """Streak calculation works with a specific reference date."""
        ref_date = date(2024, 6, 15)
        dates = ["2024-06-15", "2024-06-14", "2024-06-13"]
        current, longest = _calculate_streaks(dates, reference_date=ref_date)
        assert current == 3
        assert longest == 3

    def test_no_current_streak_if_gap_from_today(self):
        """Current streak is 0 if last completion was more than 1 day ago."""
        today = date.today()
        old_date = (today - timedelta(days=5)).isoformat()
        current, longest = _calculate_streaks([old_date])
        assert current == 0
        assert longest == 1


class TestProgressCommands:
    """Tests for progress viewing commands."""

    def test_progress_show_single_habit(self, runner, temp_data_dir):
        """Progress show displays stats for a single habit."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise"])

        result = runner.invoke(cli, ["progress", "show", "Exercise"])
        assert result.exit_code == 0
        assert "Exercise:" in result.output
        assert "Total completions: 1" in result.output

    def test_progress_show_all_habits(self, runner, temp_data_dir):
        """Progress show without argument displays all habits."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["habits", "add", "Read"])

        result = runner.invoke(cli, ["progress", "show"])
        assert result.exit_code == 0
        assert "Exercise:" in result.output
        assert "Read:" in result.output

    def test_progress_streaks(self, runner, temp_data_dir):
        """Progress streaks shows streaks for all habits."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise"])

        result = runner.invoke(cli, ["progress", "streaks"])
        assert result.exit_code == 0
        assert "Exercise:" in result.output
        assert "day(s) current" in result.output

    def test_progress_history(self, runner, temp_data_dir):
        """Progress history shows recent completion history."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise"])

        result = runner.invoke(cli, ["progress", "history", "Exercise"])
        assert result.exit_code == 0
        assert "[x]" in result.output or "[ ]" in result.output


class TestHabitMetadata:
    """Tests for habit metadata (description and frequency)."""

    def test_add_habit_with_description(self, runner, temp_data_dir):
        """Adding a habit with description stores it."""
        result = runner.invoke(cli, ["habits", "add", "Exercise", "--description", "Daily workout"])
        assert result.exit_code == 0

        data = _load_data()
        assert data["habits"]["1"]["description"] == "Daily workout"

    def test_add_habit_with_frequency(self, runner, temp_data_dir):
        """Adding a habit with frequency stores it."""
        result = runner.invoke(cli, ["habits", "add", "Exercise", "--frequency", "daily"])
        assert result.exit_code == 0

        data = _load_data()
        assert data["habits"]["1"]["frequency"] == "daily"

    def test_add_habit_with_all_metadata(self, runner, temp_data_dir):
        """Adding a habit with all metadata stores everything."""
        result = runner.invoke(
            cli,
            [
                "habits",
                "add",
                "Exercise",
                "--description",
                "Morning run",
                "--frequency",
                "weekdays",
            ],
        )
        assert result.exit_code == 0

        data = _load_data()
        assert data["habits"]["1"]["name"] == "Exercise"
        assert data["habits"]["1"]["description"] == "Morning run"
        assert data["habits"]["1"]["frequency"] == "weekdays"

    def test_add_habit_invalid_frequency(self, runner, temp_data_dir):
        """Adding a habit with invalid frequency fails."""
        result = runner.invoke(cli, ["habits", "add", "Exercise", "--frequency", "biweekly"])
        assert result.exit_code == 1
        assert "Invalid frequency" in result.output
        assert "biweekly" in result.output

    def test_frequency_case_insensitive(self, runner, temp_data_dir):
        """Frequency validation is case-insensitive."""
        result = runner.invoke(cli, ["habits", "add", "Exercise", "--frequency", "DAILY"])
        assert result.exit_code == 0

        data = _load_data()
        assert data["habits"]["1"]["frequency"] == "daily"

    def test_update_habit_description(self, runner, temp_data_dir):
        """Updating habit description works."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(
            cli, ["habits", "update", "Exercise", "--description", "New description"]
        )

        assert result.exit_code == 0
        assert "description" in result.output

        data = _load_data()
        assert data["habits"]["1"]["description"] == "New description"

    def test_update_habit_frequency(self, runner, temp_data_dir):
        """Updating habit frequency works."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["habits", "update", "Exercise", "--frequency", "weekends"])

        assert result.exit_code == 0
        assert "frequency" in result.output

        data = _load_data()
        assert data["habits"]["1"]["frequency"] == "weekends"

    def test_update_habit_clear_description(self, runner, temp_data_dir):
        """Clearing description with empty string works."""
        runner.invoke(cli, ["habits", "add", "Exercise", "--description", "Old desc"])
        result = runner.invoke(cli, ["habits", "update", "Exercise", "--description", ""])

        assert result.exit_code == 0
        assert "cleared" in result.output

        data = _load_data()
        assert "description" not in data["habits"]["1"]

    def test_update_habit_clear_frequency(self, runner, temp_data_dir):
        """Clearing frequency with empty string works."""
        runner.invoke(cli, ["habits", "add", "Exercise", "--frequency", "daily"])
        result = runner.invoke(cli, ["habits", "update", "Exercise", "--frequency", ""])

        assert result.exit_code == 0
        assert "cleared" in result.output

        data = _load_data()
        assert "frequency" not in data["habits"]["1"]

    def test_update_habit_invalid_frequency(self, runner, temp_data_dir):
        """Updating with invalid frequency fails."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["habits", "update", "Exercise", "--frequency", "never"])

        assert result.exit_code == 1
        assert "Invalid frequency" in result.output

    def test_update_habit_name(self, runner, temp_data_dir):
        """Updating habit name works."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["habits", "update", "Exercise", "--name", "Workout"])

        assert result.exit_code == 0
        assert "name" in result.output
        assert "Exercise" in result.output
        assert "Workout" in result.output

        data = _load_data()
        assert data["habits"]["1"]["name"] == "Workout"

    def test_update_habit_name_preserves_completions(self, runner, temp_data_dir):
        """Renaming a habit preserves its completion records."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-15"])
        runner.invoke(cli, ["habits", "update", "Exercise", "--name", "Workout"])

        data = _load_data()
        assert "2024-06-15" in data["completions"]["1"]
        assert data["habits"]["1"]["name"] == "Workout"

    def test_update_habit_name_empty_fails(self, runner, temp_data_dir):
        """Renaming to empty name fails."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["habits", "update", "Exercise", "--name", "   "])

        assert result.exit_code == 1
        assert "cannot be empty" in result.output

    def test_update_habit_name_duplicate_fails(self, runner, temp_data_dir):
        """Renaming to an existing habit name fails."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["habits", "add", "Workout"])
        result = runner.invoke(cli, ["habits", "update", "Exercise", "--name", "Workout"])

        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_update_habit_name_case_insensitive_duplicate(self, runner, temp_data_dir):
        """Renaming to a case-variant of an existing name fails."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["habits", "add", "Workout"])
        result = runner.invoke(cli, ["habits", "update", "Exercise", "--name", "WORKOUT"])

        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_update_habit_name_same_case_change(self, runner, temp_data_dir):
        """Changing case of the same habit name is allowed."""
        runner.invoke(cli, ["habits", "add", "exercise"])
        result = runner.invoke(cli, ["habits", "update", "exercise", "--name", "Exercise"])

        assert result.exit_code == 0

        data = _load_data()
        assert data["habits"]["1"]["name"] == "Exercise"

    def test_update_habit_no_options(self, runner, temp_data_dir):
        """Updating without any options fails."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["habits", "update", "Exercise"])

        assert result.exit_code == 1
        assert "Provide at least one option" in result.output

    def test_update_nonexistent_habit(self, runner, temp_data_dir):
        """Updating nonexistent habit fails."""
        result = runner.invoke(cli, ["habits", "update", "NoHabit", "--description", "Test"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_show_habit_with_metadata(self, runner, temp_data_dir):
        """Show command displays all metadata."""
        runner.invoke(
            cli,
            [
                "habits",
                "add",
                "Exercise",
                "--description",
                "Morning workout",
                "--frequency",
                "daily",
            ],
        )
        result = runner.invoke(cli, ["habits", "show", "Exercise"])

        assert result.exit_code == 0
        assert "Exercise" in result.output
        assert "Morning workout" in result.output
        assert "daily" in result.output

    def test_show_habit_without_metadata(self, runner, temp_data_dir):
        """Show command handles missing metadata gracefully."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["habits", "show", "Exercise"])

        assert result.exit_code == 0
        assert "Exercise" in result.output
        assert "(none)" in result.output

    def test_show_nonexistent_habit(self, runner, temp_data_dir):
        """Show command for nonexistent habit fails."""
        result = runner.invoke(cli, ["habits", "show", "NoHabit"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_list_habits_shows_frequency(self, runner, temp_data_dir):
        """List shows frequency in compact format."""
        runner.invoke(cli, ["habits", "add", "Exercise", "--frequency", "daily"])
        runner.invoke(cli, ["habits", "add", "Read"])

        result = runner.invoke(cli, ["habits", "list"])

        assert result.exit_code == 0
        assert "(daily)" in result.output
        assert "Exercise" in result.output
        assert "Read" in result.output

    def test_list_habits_verbose(self, runner, temp_data_dir):
        """List verbose mode shows all metadata."""
        runner.invoke(
            cli,
            [
                "habits",
                "add",
                "Exercise",
                "--description",
                "Morning workout",
                "--frequency",
                "weekdays",
            ],
        )

        result = runner.invoke(cli, ["habits", "list", "--verbose"])

        assert result.exit_code == 0
        assert "Morning workout" in result.output
        assert "weekdays" in result.output

    def test_all_valid_frequencies(self, runner, temp_data_dir):
        """All documented frequencies are accepted."""
        valid = ["daily", "weekdays", "weekends", "weekly", "monthly"]
        for i, freq in enumerate(valid):
            result = runner.invoke(cli, ["habits", "add", f"Habit{i}", "--frequency", freq])
            assert result.exit_code == 0, f"Frequency '{freq}' should be valid"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_find_habit_by_id(self, runner, temp_data_dir):
        """Habits can be referenced by ID."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["log", "done", "1"])

        assert result.exit_code == 0
        assert "Logged 'Exercise' as done" in result.output

    def test_find_habit_by_name_case_insensitive(self, runner, temp_data_dir):
        """Habit lookup by name is case-insensitive."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        result = runner.invoke(cli, ["log", "done", "exercise"])

        assert result.exit_code == 0
        assert "Logged 'Exercise' as done" in result.output

    def test_completions_sorted(self, runner, temp_data_dir):
        """Completions are stored in sorted order."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-20"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-10"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-15"])

        data = _load_data()
        completions = data["completions"]["1"]
        assert completions == ["2024-06-10", "2024-06-15", "2024-06-20"]


class TestDataExport:
    """Tests for data export functionality."""

    def test_export_empty_data(self, runner, temp_data_dir, tmp_path):
        """Exporting with no data creates valid empty file."""
        export_file = tmp_path / "export.json"
        result = runner.invoke(cli, ["data", "export", str(export_file)])

        assert result.exit_code == 0
        assert "Exported 0 habit(s) and 0 completion(s)" in result.output

        with open(export_file) as f:
            exported = json.load(f)
        assert exported == {"habits": {}, "completions": {}}

    def test_export_with_data(self, runner, temp_data_dir, tmp_path):
        """Exporting preserves all habits and completions."""
        runner.invoke(cli, ["habits", "add", "Exercise", "--frequency", "daily"])
        runner.invoke(cli, ["habits", "add", "Read", "--description", "Read books"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-15"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-16"])
        runner.invoke(cli, ["log", "done", "Read", "--date", "2024-06-15"])

        export_file = tmp_path / "export.json"
        result = runner.invoke(cli, ["data", "export", str(export_file)])

        assert result.exit_code == 0
        assert "Exported 2 habit(s) and 3 completion(s)" in result.output

        with open(export_file) as f:
            exported = json.load(f)

        assert len(exported["habits"]) == 2
        assert exported["habits"]["1"]["name"] == "Exercise"
        assert exported["habits"]["1"]["frequency"] == "daily"
        assert exported["habits"]["2"]["name"] == "Read"
        assert exported["habits"]["2"]["description"] == "Read books"
        assert "2024-06-15" in exported["completions"]["1"]
        assert "2024-06-16" in exported["completions"]["1"]
        assert "2024-06-15" in exported["completions"]["2"]

    def test_export_refuses_overwrite(self, runner, temp_data_dir, tmp_path):
        """Export refuses to overwrite existing file without --force."""
        export_file = tmp_path / "export.json"
        export_file.write_text("{}")

        result = runner.invoke(cli, ["data", "export", str(export_file)])

        assert result.exit_code == 1
        assert "already exists" in result.output
        assert "--force" in result.output

    def test_export_force_overwrites(self, runner, temp_data_dir, tmp_path):
        """Export with --force overwrites existing file."""
        runner.invoke(cli, ["habits", "add", "Exercise"])

        export_file = tmp_path / "export.json"
        export_file.write_text('{"old": "data"}')

        result = runner.invoke(cli, ["data", "export", str(export_file), "--force"])

        assert result.exit_code == 0

        with open(export_file) as f:
            exported = json.load(f)
        assert "habits" in exported
        assert "old" not in exported

    def test_export_creates_parent_directories(self, runner, temp_data_dir, tmp_path):
        """Export creates parent directories if needed."""
        export_file = tmp_path / "subdir" / "nested" / "export.json"
        result = runner.invoke(cli, ["data", "export", str(export_file)])

        assert result.exit_code == 0
        assert export_file.exists()


class TestDataImport:
    """Tests for data import functionality."""

    def test_import_valid_data(self, runner, temp_data_dir, tmp_path):
        """Importing valid data replaces current data."""
        import_data = {
            "habits": {
                "1": {"name": "Meditate", "frequency": "daily"},
                "2": {"name": "Journal", "description": "Write daily thoughts"},
            },
            "completions": {"1": ["2024-06-15", "2024-06-16"], "2": ["2024-06-15"]},
        }
        import_file = tmp_path / "import.json"
        with open(import_file, "w") as f:
            json.dump(import_data, f)

        result = runner.invoke(cli, ["data", "import", str(import_file)])

        assert result.exit_code == 0
        assert "Imported 2 habit(s) and 3 completion(s)" in result.output

        loaded = _load_data()
        assert loaded == import_data

    def test_import_empty_data(self, runner, temp_data_dir, tmp_path):
        """Importing empty but valid structure works."""
        import_data = {"habits": {}, "completions": {}}
        import_file = tmp_path / "import.json"
        with open(import_file, "w") as f:
            json.dump(import_data, f)

        result = runner.invoke(cli, ["data", "import", str(import_file)])

        assert result.exit_code == 0
        assert "Imported 0 habit(s) and 0 completion(s)" in result.output

    def test_import_refuses_without_force(self, runner, temp_data_dir, tmp_path):
        """Import refuses to replace existing data without --force."""
        runner.invoke(cli, ["habits", "add", "Exercise"])

        import_data = {"habits": {"1": {"name": "New"}}, "completions": {}}
        import_file = tmp_path / "import.json"
        with open(import_file, "w") as f:
            json.dump(import_data, f)

        result = runner.invoke(cli, ["data", "import", str(import_file)])

        assert result.exit_code == 1
        assert "Current data exists" in result.output
        assert "--force" in result.output

        loaded = _load_data()
        assert loaded["habits"]["1"]["name"] == "Exercise"

    def test_import_force_replaces_data(self, runner, temp_data_dir, tmp_path):
        """Import with --force replaces existing data."""
        runner.invoke(cli, ["habits", "add", "Exercise"])

        import_data = {"habits": {"5": {"name": "Yoga"}}, "completions": {}}
        import_file = tmp_path / "import.json"
        with open(import_file, "w") as f:
            json.dump(import_data, f)

        result = runner.invoke(cli, ["data", "import", str(import_file), "--force"])

        assert result.exit_code == 0

        loaded = _load_data()
        assert len(loaded["habits"]) == 1
        assert loaded["habits"]["5"]["name"] == "Yoga"

    def test_import_invalid_json(self, runner, temp_data_dir, tmp_path):
        """Import rejects invalid JSON."""
        import_file = tmp_path / "bad.json"
        import_file.write_text("not valid json {")

        result = runner.invoke(cli, ["data", "import", str(import_file)])

        assert result.exit_code == 1
        assert "Invalid JSON" in result.output

    def test_import_missing_habits_field(self, runner, temp_data_dir, tmp_path):
        """Import rejects data missing habits field."""
        import_file = tmp_path / "import.json"
        with open(import_file, "w") as f:
            json.dump({"completions": {}}, f)

        result = runner.invoke(cli, ["data", "import", str(import_file)])

        assert result.exit_code == 1
        assert "missing" in result.output

    def test_import_missing_completions_field(self, runner, temp_data_dir, tmp_path):
        """Import rejects data missing completions field."""
        import_file = tmp_path / "import.json"
        with open(import_file, "w") as f:
            json.dump({"habits": {}}, f)

        result = runner.invoke(cli, ["data", "import", str(import_file)])

        assert result.exit_code == 1
        assert "missing" in result.output

    def test_import_invalid_habit_structure(self, runner, temp_data_dir, tmp_path):
        """Import rejects habit without name."""
        import_data = {"habits": {"1": {"description": "No name field"}}, "completions": {}}
        import_file = tmp_path / "import.json"
        with open(import_file, "w") as f:
            json.dump(import_data, f)

        result = runner.invoke(cli, ["data", "import", str(import_file)])

        assert result.exit_code == 1
        assert "missing 'name'" in result.output

    def test_import_invalid_frequency(self, runner, temp_data_dir, tmp_path):
        """Import rejects invalid frequency value."""
        import_data = {
            "habits": {"1": {"name": "Test", "frequency": "biweekly"}},
            "completions": {},
        }
        import_file = tmp_path / "import.json"
        with open(import_file, "w") as f:
            json.dump(import_data, f)

        result = runner.invoke(cli, ["data", "import", str(import_file)])

        assert result.exit_code == 1
        assert "frequency" in result.output

    def test_import_invalid_date_format(self, runner, temp_data_dir, tmp_path):
        """Import rejects invalid date format in completions."""
        import_data = {"habits": {"1": {"name": "Test"}}, "completions": {"1": ["06-15-2024"]}}
        import_file = tmp_path / "import.json"
        with open(import_file, "w") as f:
            json.dump(import_data, f)

        result = runner.invoke(cli, ["data", "import", str(import_file)])

        assert result.exit_code == 1
        assert "Invalid" in result.output

    def test_import_nonexistent_file(self, runner, temp_data_dir, tmp_path):
        """Import fails gracefully for nonexistent file."""
        result = runner.invoke(cli, ["data", "import", str(tmp_path / "missing.json")])

        assert result.exit_code != 0


class TestValidateImportData:
    """Tests for import data validation logic."""

    def test_valid_complete_data(self):
        """Valid data with all fields passes validation."""
        data = {
            "habits": {
                "1": {"name": "Exercise", "description": "Daily workout", "frequency": "daily"}
            },
            "completions": {"1": ["2024-06-15"]},
        }
        is_valid, error = _validate_import_data(data)
        assert is_valid
        assert error is None

    def test_valid_minimal_data(self):
        """Minimal valid data passes validation."""
        data = {"habits": {}, "completions": {}}
        is_valid, error = _validate_import_data(data)
        assert is_valid
        assert error is None

    def test_invalid_root_type(self):
        """Non-object root fails validation."""
        is_valid, error = _validate_import_data([])
        assert not is_valid
        assert "root must be a JSON object" in error

    def test_invalid_habits_type(self):
        """Non-object habits field fails validation."""
        data = {"habits": [], "completions": {}}
        is_valid, error = _validate_import_data(data)
        assert not is_valid
        assert "'habits' must be an object" in error

    def test_invalid_completions_type(self):
        """Non-object completions field fails validation."""
        data = {"habits": {}, "completions": []}
        is_valid, error = _validate_import_data(data)
        assert not is_valid
        assert "'completions' must be an object" in error

    def test_invalid_habit_entry_type(self):
        """Non-object habit entry fails validation."""
        data = {"habits": {"1": "not an object"}, "completions": {}}
        is_valid, error = _validate_import_data(data)
        assert not is_valid
        assert "must be an object" in error

    def test_empty_habit_name(self):
        """Empty habit name fails validation."""
        data = {"habits": {"1": {"name": "   "}}, "completions": {}}
        is_valid, error = _validate_import_data(data)
        assert not is_valid
        assert "non-empty string" in error

    def test_invalid_description_type(self):
        """Non-string description fails validation."""
        data = {"habits": {"1": {"name": "Test", "description": 123}}, "completions": {}}
        is_valid, error = _validate_import_data(data)
        assert not is_valid
        assert "description" in error

    def test_invalid_completion_list_type(self):
        """Non-array completion list fails validation."""
        data = {"habits": {}, "completions": {"1": "not a list"}}
        is_valid, error = _validate_import_data(data)
        assert not is_valid
        assert "must be an array" in error

    def test_invalid_completion_date_type(self):
        """Non-string completion date fails validation."""
        data = {"habits": {}, "completions": {"1": [20240615]}}
        is_valid, error = _validate_import_data(data)
        assert not is_valid
        assert "dates must be strings" in error


class TestEditingAndCorrections:
    """Tests for editing and correction workflows (Task 07)."""

    def test_undo_removes_completion(self, runner, temp_data_dir):
        """Log undo removes the completion record for the specified date."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-15"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-16"])

        result = runner.invoke(cli, ["log", "undo", "Exercise", "--date", "2024-06-15"])

        assert result.exit_code == 0
        assert "Removed completion" in result.output

        data = _load_data()
        assert "2024-06-15" not in data["completions"]["1"]
        assert "2024-06-16" in data["completions"]["1"]

    def test_undo_nonexistent_completion(self, runner, temp_data_dir):
        """Log undo for a date with no completion is handled gracefully."""
        runner.invoke(cli, ["habits", "add", "Exercise"])

        result = runner.invoke(cli, ["log", "undo", "Exercise", "--date", "2024-06-15"])

        assert result.exit_code == 0
        assert "No completion record" in result.output

    def test_undo_updates_streak_immediately(self, runner, temp_data_dir):
        """Streak reflects corrected data immediately after undo."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        day_before = today - timedelta(days=2)

        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", day_before.isoformat()])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", yesterday.isoformat()])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", today.isoformat()])

        result = runner.invoke(cli, ["progress", "show", "Exercise"])
        assert "Current streak:    3 day(s)" in result.output

        runner.invoke(cli, ["log", "undo", "Exercise", "--date", yesterday.isoformat()])

        result = runner.invoke(cli, ["progress", "show", "Exercise"])
        assert "Current streak:    1 day(s)" in result.output

    def test_rename_updates_show_output(self, runner, temp_data_dir):
        """Show command displays updated name after rename."""
        runner.invoke(cli, ["habits", "add", "Exercise", "--description", "Morning workout"])
        runner.invoke(cli, ["habits", "update", "Exercise", "--name", "Workout"])

        result = runner.invoke(cli, ["habits", "show", "Workout"])

        assert result.exit_code == 0
        assert "Workout" in result.output
        assert "Morning workout" in result.output

    def test_rename_updates_list_output(self, runner, temp_data_dir):
        """List command displays updated name after rename."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["habits", "update", "Exercise", "--name", "Daily Workout"])

        result = runner.invoke(cli, ["habits", "list"])

        assert result.exit_code == 0
        assert "Daily Workout" in result.output
        assert "Exercise" not in result.output

    def test_rename_updates_progress_output(self, runner, temp_data_dir):
        """Progress shows updated name after rename."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise"])
        runner.invoke(cli, ["habits", "update", "Exercise", "--name", "Workout"])

        result = runner.invoke(cli, ["progress", "show", "Workout"])

        assert result.exit_code == 0
        assert "Workout:" in result.output
        assert "Total completions: 1" in result.output

    def test_update_description_reflects_in_show(self, runner, temp_data_dir):
        """Updated description reflects in show command."""
        runner.invoke(cli, ["habits", "add", "Exercise", "--description", "Old description"])
        runner.invoke(cli, ["habits", "update", "Exercise", "--description", "New description"])

        result = runner.invoke(cli, ["habits", "show", "Exercise"])

        assert result.exit_code == 0
        assert "New description" in result.output
        assert "Old description" not in result.output

    def test_combined_edit_name_and_description(self, runner, temp_data_dir):
        """Can update name and description in a single command."""
        runner.invoke(cli, ["habits", "add", "Exercise", "--description", "Old"])
        result = runner.invoke(
            cli,
            [
                "habits",
                "update",
                "Exercise",
                "--name",
                "Workout",
                "--description",
                "New description",
            ],
        )

        assert result.exit_code == 0

        data = _load_data()
        assert data["habits"]["1"]["name"] == "Workout"
        assert data["habits"]["1"]["description"] == "New description"


class TestWeekBoundaries:
    """Tests for week boundary calculation."""

    def test_week_boundaries_monday(self):
        """Monday is the start of its own week."""
        monday = date(2024, 6, 17)
        start, end = _get_week_boundaries(monday)
        assert start == date(2024, 6, 17)
        assert end == date(2024, 6, 23)

    def test_week_boundaries_sunday(self):
        """Sunday is the end of its week."""
        sunday = date(2024, 6, 23)
        start, end = _get_week_boundaries(sunday)
        assert start == date(2024, 6, 17)
        assert end == date(2024, 6, 23)

    def test_week_boundaries_wednesday(self):
        """Mid-week day returns correct boundaries."""
        wednesday = date(2024, 6, 19)
        start, end = _get_week_boundaries(wednesday)
        assert start == date(2024, 6, 17)
        assert end == date(2024, 6, 23)


class TestCompletionRate:
    """Tests for completion rate calculation."""

    def test_completion_rate_empty(self):
        """Empty completion list returns zero."""
        completed, total, rate = _calculate_completion_rate(
            [], date(2024, 6, 10), date(2024, 6, 16)
        )
        assert completed == 0
        assert total == 7
        assert rate == 0.0

    def test_completion_rate_full(self):
        """Full completions return 100%."""
        dates = [
            "2024-06-10",
            "2024-06-11",
            "2024-06-12",
            "2024-06-13",
            "2024-06-14",
            "2024-06-15",
            "2024-06-16",
        ]
        completed, total, rate = _calculate_completion_rate(
            dates, date(2024, 6, 10), date(2024, 6, 16)
        )
        assert completed == 7
        assert total == 7
        assert rate == 100.0

    def test_completion_rate_partial(self):
        """Partial completions calculate correct percentage."""
        dates = ["2024-06-10", "2024-06-12", "2024-06-14"]
        completed, total, rate = _calculate_completion_rate(
            dates, date(2024, 6, 10), date(2024, 6, 16)
        )
        assert completed == 3
        assert total == 7
        assert abs(rate - 42.857) < 0.01

    def test_completion_rate_excludes_outside_dates(self):
        """Dates outside range are not counted."""
        dates = ["2024-06-08", "2024-06-10", "2024-06-12", "2024-06-18"]
        completed, total, rate = _calculate_completion_rate(
            dates, date(2024, 6, 10), date(2024, 6, 16)
        )
        assert completed == 2
        assert total == 7

    def test_completion_rate_single_day(self):
        """Single day range works correctly."""
        dates = ["2024-06-15"]
        completed, total, rate = _calculate_completion_rate(
            dates, date(2024, 6, 15), date(2024, 6, 15)
        )
        assert completed == 1
        assert total == 1
        assert rate == 100.0


class TestAtRiskHabits:
    """Tests for at-risk habit identification."""

    def test_no_habits_at_risk_when_empty(self):
        """Empty data returns no at-risk habits."""
        at_risk = _identify_at_risk_habits({}, {})
        assert at_risk == []

    def test_habit_with_streak_completed_today_not_at_risk(self):
        """Habit completed today is not at risk."""
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        day_before = (date.today() - timedelta(days=2)).isoformat()

        habits = {"1": {"name": "Exercise"}}
        completions = {"1": [day_before, yesterday, today]}

        at_risk = _identify_at_risk_habits(habits, completions)
        assert at_risk == []

    def test_habit_with_streak_not_completed_today_is_at_risk(self):
        """Habit with streak not completed today is at risk."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        day_before = (date.today() - timedelta(days=2)).isoformat()

        habits = {"1": {"name": "Exercise"}}
        completions = {"1": [day_before, yesterday]}

        at_risk = _identify_at_risk_habits(habits, completions)
        assert len(at_risk) == 1
        assert at_risk[0][1] == "Exercise"
        assert at_risk[0][2] == 2

    def test_habit_with_short_streak_not_at_risk(self):
        """Habit with streak less than 2 days is not at risk."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        habits = {"1": {"name": "Exercise"}}
        completions = {"1": [yesterday]}

        at_risk = _identify_at_risk_habits(habits, completions)
        assert at_risk == []

    def test_multiple_at_risk_sorted_by_streak(self):
        """Multiple at-risk habits are sorted by streak length (descending)."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        day_before = (date.today() - timedelta(days=2)).isoformat()
        day_before_2 = (date.today() - timedelta(days=3)).isoformat()

        habits = {
            "1": {"name": "Exercise"},
            "2": {"name": "Read"},
        }
        completions = {
            "1": [day_before, yesterday],
            "2": [day_before_2, day_before, yesterday],
        }

        at_risk = _identify_at_risk_habits(habits, completions)
        assert len(at_risk) == 2
        assert at_risk[0][1] == "Read"
        assert at_risk[0][2] == 3
        assert at_risk[1][1] == "Exercise"
        assert at_risk[1][2] == 2


class TestWeeklyCommand:
    """Tests for weekly summary command."""

    def test_weekly_shows_summary(self, runner, temp_data_dir):
        """Weekly command displays summary information."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise"])

        result = runner.invoke(cli, ["progress", "weekly"])

        assert result.exit_code == 0
        assert "Weekly Summary" in result.output
        assert "Exercise" in result.output
        assert "Completed:" in result.output
        assert "Streak:" in result.output

    def test_weekly_with_offset(self, runner, temp_data_dir):
        """Weekly command accepts week offset."""
        runner.invoke(cli, ["habits", "add", "Exercise"])

        result = runner.invoke(cli, ["progress", "weekly", "--week-offset", "1"])

        assert result.exit_code == 0
        assert "Weekly Summary" in result.output

    def test_weekly_no_habits(self, runner, temp_data_dir):
        """Weekly command handles no habits gracefully."""
        result = runner.invoke(cli, ["progress", "weekly"])

        assert result.exit_code == 0
        assert "No habits tracked yet" in result.output


class TestAtRiskCommand:
    """Tests for at-risk command."""

    def test_at_risk_shows_at_risk_habits(self, runner, temp_data_dir):
        """At-risk command shows habits at risk."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        day_before = (date.today() - timedelta(days=2)).isoformat()

        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", day_before])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", yesterday])

        result = runner.invoke(cli, ["progress", "at-risk"])

        assert result.exit_code == 0
        assert "Exercise" in result.output
        assert "streak" in result.output

    def test_at_risk_no_habits_at_risk(self, runner, temp_data_dir):
        """At-risk command handles no at-risk habits."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise"])

        result = runner.invoke(cli, ["progress", "at-risk"])

        assert result.exit_code == 0
        assert "No habits at risk" in result.output

    def test_at_risk_no_habits(self, runner, temp_data_dir):
        """At-risk command handles no habits."""
        result = runner.invoke(cli, ["progress", "at-risk"])

        assert result.exit_code == 0
        assert "No habits tracked yet" in result.output


class TestRateCommand:
    """Tests for completion rate command."""

    def test_rate_shows_completion_rate(self, runner, temp_data_dir):
        """Rate command shows completion rate."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-15"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-16"])

        result = runner.invoke(
            cli, ["progress", "rate", "--start", "2024-06-15", "--end", "2024-06-21"]
        )

        assert result.exit_code == 0
        assert "Completion Rate" in result.output
        assert "2/7" in result.output

    def test_rate_single_habit(self, runner, temp_data_dir):
        """Rate command works for a single habit."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["habits", "add", "Read"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-15"])

        result = runner.invoke(
            cli, ["progress", "rate", "--start", "2024-06-15", "--end", "2024-06-21", "Exercise"]
        )

        assert result.exit_code == 0
        assert "Exercise" in result.output
        assert "Read" not in result.output

    def test_rate_defaults_end_to_today(self, runner, temp_data_dir):
        """Rate command defaults end date to today."""
        runner.invoke(cli, ["habits", "add", "Exercise"])

        result = runner.invoke(cli, ["progress", "rate", "--start", "2024-06-01"])

        assert result.exit_code == 0
        assert date.today().isoformat() in result.output

    def test_rate_invalid_date_range(self, runner, temp_data_dir):
        """Rate command rejects end before start."""
        runner.invoke(cli, ["habits", "add", "Exercise"])

        result = runner.invoke(
            cli, ["progress", "rate", "--start", "2024-06-20", "--end", "2024-06-15"]
        )

        assert result.exit_code == 1
        assert "Start date must be before" in result.output

    def test_rate_invalid_start_date(self, runner, temp_data_dir):
        """Rate command rejects invalid start date."""
        runner.invoke(cli, ["habits", "add", "Exercise"])

        result = runner.invoke(cli, ["progress", "rate", "--start", "bad-date"])

        assert result.exit_code == 1
        assert "Invalid date format" in result.output

    def test_rate_nonexistent_habit(self, runner, temp_data_dir):
        """Rate command fails for nonexistent habit."""
        runner.invoke(cli, ["habits", "add", "Exercise"])

        result = runner.invoke(cli, ["progress", "rate", "--start", "2024-06-01", "NoHabit"])

        assert result.exit_code == 1
        assert "not found" in result.output


class TestReportCommand:
    """Tests for the comprehensive report command."""

    def test_report_shows_overview(self, runner, temp_data_dir):
        """Report command displays comprehensive overview."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise"])

        result = runner.invoke(cli, ["progress", "report"])

        assert result.exit_code == 0
        assert "HABIT TRACKER REPORT" in result.output
        assert "THIS WEEK" in result.output
        assert "Exercise" in result.output

    def test_report_shows_at_risk(self, runner, temp_data_dir):
        """Report command shows at-risk habits."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        day_before = (date.today() - timedelta(days=2)).isoformat()

        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", day_before])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", yesterday])

        result = runner.invoke(cli, ["progress", "report"])

        assert result.exit_code == 0
        assert "STREAKS AT RISK" in result.output
        assert "Exercise" in result.output

    def test_report_shows_trends(self, runner, temp_data_dir):
        """Report command shows week-over-week trends."""
        today = date.today()
        for i in range(14):
            d = today - timedelta(days=i)
            runner.invoke(cli, ["habits", "add", "Exercise"]) if i == 0 else None
            if i < 7 and i % 2 == 0:
                runner.invoke(cli, ["log", "done", "Exercise", "--date", d.isoformat()])

        result = runner.invoke(cli, ["progress", "report"])

        assert result.exit_code == 0
        assert "This week overall" in result.output

    def test_report_no_habits(self, runner, temp_data_dir):
        """Report command handles no habits gracefully."""
        result = runner.invoke(cli, ["progress", "report"])

        assert result.exit_code == 0
        assert "No habits tracked yet" in result.output


class TestExportImportRoundTrip:
    """Tests for export/import round-trip integrity."""

    def test_round_trip_preserves_data(self, runner, temp_data_dir, tmp_path):
        """Data survives export and import without changes."""
        runner.invoke(
            cli,
            ["habits", "add", "Exercise", "--frequency", "daily", "--description", "Daily workout"],
        )
        runner.invoke(cli, ["habits", "add", "Read", "--frequency", "weekends"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-15"])
        runner.invoke(cli, ["log", "done", "Exercise", "--date", "2024-06-16"])
        runner.invoke(cli, ["log", "done", "Read", "--date", "2024-06-15"])

        original_data = _load_data()

        export_file = tmp_path / "backup.json"
        runner.invoke(cli, ["data", "export", str(export_file)])

        runner.invoke(cli, ["habits", "remove", "Exercise"])
        runner.invoke(cli, ["habits", "remove", "Read"])

        runner.invoke(cli, ["data", "import", str(export_file)])

        restored_data = _load_data()
        assert restored_data == original_data

    def test_transfer_between_environments(self, runner, temp_data_dir, tmp_path, monkeypatch):
        """Data can be transferred between different data directories."""
        runner.invoke(cli, ["habits", "add", "Exercise"])
        runner.invoke(cli, ["log", "done", "Exercise"])

        export_file = tmp_path / "transfer.json"
        runner.invoke(cli, ["data", "export", str(export_file)])

        new_data_dir = tmp_path / "new_env" / ".habit_tracker"
        new_data_file = new_data_dir / "data.json"
        monkeypatch.setattr("habit_tracker.DATA_DIR", new_data_dir)
        monkeypatch.setattr("habit_tracker.DATA_FILE", new_data_file)

        result = runner.invoke(cli, ["data", "import", str(export_file)])

        assert result.exit_code == 0

        loaded = _load_data()
        assert len(loaded["habits"]) == 1
        assert loaded["habits"]["1"]["name"] == "Exercise"
