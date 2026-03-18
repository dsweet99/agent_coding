use assert_cmd::Command;
use predicates::prelude::*;
use std::fs;
use std::path::PathBuf;
use tempfile::TempDir;

struct TestEnv {
    temp: TempDir,
}

impl TestEnv {
    fn new() -> Self {
        let temp = TempDir::new().unwrap();
        Self { temp }
    }

    fn cmd(&self) -> Command {
        let mut cmd = Command::cargo_bin("habit-tracker").unwrap();
        cmd.env("HOME", self.temp.path());
        cmd
    }

    fn path(&self) -> PathBuf {
        self.temp.path().to_path_buf()
    }
}

fn setup_test_env() -> TestEnv {
    TestEnv::new()
}

mod test_data_persistence {
    use super::*;

    #[test]
    fn test_load_data_missing_file() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "list"])
            .assert()
            .success()
            .stdout(predicate::str::contains("No habits tracked yet"));
    }

    #[test]
    fn test_data_persists_across_operations() {
        let env = setup_test_env();

        env.cmd().args(["habits", "add", "Meditate"]).assert().success();
        env.cmd().args(["habits", "add", "Read"]).assert().success();

        env.cmd()
            .args(["habits", "list"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Meditate"))
            .stdout(predicate::str::contains("Read"));
    }
}

mod test_create_habit {
    use super::*;

    #[test]
    fn test_add_habit_success() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Added habit 'Exercise'"));
    }

    #[test]
    fn test_add_duplicate_habit_fails() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["habits", "add", "Exercise"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("already exists"));
    }

    #[test]
    fn test_add_habit_case_insensitive_duplicate() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["habits", "add", "EXERCISE"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("already exists"));
    }

    #[test]
    fn test_add_empty_habit_fails() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "   "])
            .assert()
            .failure()
            .stderr(predicate::str::contains("cannot be empty"));
    }

    #[test]
    fn test_list_habits() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["habits", "add", "Read"]).assert().success();

        env.cmd()
            .args(["habits", "list"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Exercise"))
            .stdout(predicate::str::contains("Read"));
    }

    #[test]
    fn test_remove_habit() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["log", "done", "Exercise"]).assert().success();

        env.cmd()
            .args(["habits", "remove", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Removed habit 'Exercise'"));

        env.cmd()
            .args(["habits", "list"])
            .assert()
            .success()
            .stdout(predicate::str::contains("No habits tracked yet"));
    }
}

mod test_log_completion {
    use super::*;

    #[test]
    fn test_log_done_today() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Logged 'Exercise' as done"));
    }

    #[test]
    fn test_log_done_specific_date() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success()
            .stdout(predicate::str::contains("2024-06-15"));
    }

    #[test]
    fn test_log_done_duplicate_ignored() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success()
            .stdout(predicate::str::contains("already marked done"));
    }

    #[test]
    fn test_log_done_invalid_date() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "06-15-2024"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("Invalid date format"));
    }

    #[test]
    fn test_log_done_nonexistent_habit() {
        let env = setup_test_env();
        env.cmd()
            .args(["log", "done", "Exercise"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("not found"));
    }

    #[test]
    fn test_log_undo() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success();
        env.cmd()
            .args(["log", "undo", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Removed completion"));
    }
}

mod test_progress_commands {
    use super::*;

    #[test]
    fn test_progress_show_single_habit() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["log", "done", "Exercise"]).assert().success();

        env.cmd()
            .args(["progress", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Exercise:"))
            .stdout(predicate::str::contains("Total completions: 1"));
    }

    #[test]
    fn test_progress_show_all_habits() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["habits", "add", "Read"]).assert().success();

        env.cmd()
            .args(["progress", "show"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Exercise:"))
            .stdout(predicate::str::contains("Read:"));
    }

    #[test]
    fn test_progress_streaks() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["log", "done", "Exercise"]).assert().success();

        env.cmd()
            .args(["progress", "streaks"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Exercise:"))
            .stdout(predicate::str::contains("day(s) current"));
    }

    #[test]
    fn test_progress_history() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["log", "done", "Exercise"]).assert().success();

        env.cmd()
            .args(["progress", "history", "Exercise"])
            .assert()
            .success();
    }
}

mod test_habit_metadata {
    use super::*;

    #[test]
    fn test_add_habit_with_description() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "Exercise", "--description", "Daily workout"])
            .assert()
            .success();

        env.cmd()
            .args(["habits", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Daily workout"));
    }

    #[test]
    fn test_add_habit_with_frequency() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "Exercise", "--frequency", "daily"])
            .assert()
            .success();

        env.cmd()
            .args(["habits", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("daily"));
    }

    #[test]
    fn test_add_habit_with_all_metadata() {
        let env = setup_test_env();
        env.cmd()
            .args([
                "habits", "add", "Exercise",
                "--description", "Morning run",
                "--frequency", "weekdays"
            ])
            .assert()
            .success();

        env.cmd()
            .args(["habits", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Morning run"))
            .stdout(predicate::str::contains("weekdays"));
    }

    #[test]
    fn test_add_habit_invalid_frequency() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "Exercise", "--frequency", "biweekly"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("Invalid frequency"))
            .stderr(predicate::str::contains("biweekly"));
    }

    #[test]
    fn test_frequency_case_insensitive() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "Exercise", "--frequency", "DAILY"])
            .assert()
            .success();

        env.cmd()
            .args(["habits", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("daily"));
    }

    #[test]
    fn test_update_habit_description() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--description", "New description"])
            .assert()
            .success()
            .stdout(predicate::str::contains("description"));

        env.cmd()
            .args(["habits", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("New description"));
    }

    #[test]
    fn test_update_habit_frequency() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--frequency", "weekends"])
            .assert()
            .success()
            .stdout(predicate::str::contains("frequency"));

        env.cmd()
            .args(["habits", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("weekends"));
    }

    #[test]
    fn test_update_habit_clear_description() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "Exercise", "--description", "Old desc"])
            .assert()
            .success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--description", ""])
            .assert()
            .success()
            .stdout(predicate::str::contains("cleared"));

        env.cmd()
            .args(["habits", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("(none)"));
    }

    #[test]
    fn test_update_habit_clear_frequency() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "Exercise", "--frequency", "daily"])
            .assert()
            .success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--frequency", ""])
            .assert()
            .success()
            .stdout(predicate::str::contains("cleared"));
    }

    #[test]
    fn test_update_habit_invalid_frequency() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--frequency", "never"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("Invalid frequency"));
    }

    #[test]
    fn test_update_habit_name() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--name", "Workout"])
            .assert()
            .success()
            .stdout(predicate::str::contains("name"))
            .stdout(predicate::str::contains("Exercise"))
            .stdout(predicate::str::contains("Workout"));
    }

    #[test]
    fn test_update_habit_name_preserves_completions() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--name", "Workout"])
            .assert()
            .success();

        env.cmd()
            .args(["progress", "show", "Workout"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Total completions: 1"));
    }

    #[test]
    fn test_update_habit_name_empty_fails() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--name", "   "])
            .assert()
            .failure()
            .stderr(predicate::str::contains("cannot be empty"));
    }

    #[test]
    fn test_update_habit_name_duplicate_fails() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["habits", "add", "Workout"]).assert().success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--name", "Workout"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("already exists"));
    }

    #[test]
    fn test_update_habit_name_case_insensitive_duplicate() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["habits", "add", "Workout"]).assert().success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--name", "WORKOUT"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("already exists"));
    }

    #[test]
    fn test_update_habit_name_same_case_change() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "exercise"]).assert().success();
        env.cmd()
            .args(["habits", "update", "exercise", "--name", "Exercise"])
            .assert()
            .success();
    }

    #[test]
    fn test_update_habit_no_options() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["habits", "update", "Exercise"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("Provide at least one option"));
    }

    #[test]
    fn test_update_nonexistent_habit() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "update", "NoHabit", "--description", "Test"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("not found"));
    }

    #[test]
    fn test_show_habit_with_metadata() {
        let env = setup_test_env();
        env.cmd()
            .args([
                "habits", "add", "Exercise",
                "--description", "Morning workout",
                "--frequency", "daily"
            ])
            .assert()
            .success();
        env.cmd()
            .args(["habits", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Exercise"))
            .stdout(predicate::str::contains("Morning workout"))
            .stdout(predicate::str::contains("daily"));
    }

    #[test]
    fn test_show_habit_without_metadata() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["habits", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Exercise"))
            .stdout(predicate::str::contains("(none)"));
    }

    #[test]
    fn test_show_nonexistent_habit() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "show", "NoHabit"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("not found"));
    }

    #[test]
    fn test_list_habits_shows_frequency() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "Exercise", "--frequency", "daily"])
            .assert()
            .success();
        env.cmd().args(["habits", "add", "Read"]).assert().success();

        env.cmd()
            .args(["habits", "list"])
            .assert()
            .success()
            .stdout(predicate::str::contains("(daily)"))
            .stdout(predicate::str::contains("Exercise"))
            .stdout(predicate::str::contains("Read"));
    }

    #[test]
    fn test_list_habits_verbose() {
        let env = setup_test_env();
        env.cmd()
            .args([
                "habits", "add", "Exercise",
                "--description", "Morning workout",
                "--frequency", "weekdays"
            ])
            .assert()
            .success();

        env.cmd()
            .args(["habits", "list", "--verbose"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Morning workout"))
            .stdout(predicate::str::contains("weekdays"));
    }

    #[test]
    fn test_all_valid_frequencies() {
        let env = setup_test_env();
        let valid = ["daily", "weekdays", "weekends", "weekly", "monthly"];
        for (i, freq) in valid.iter().enumerate() {
            env.cmd()
                .args(["habits", "add", &format!("Habit{}", i), "--frequency", freq])
                .assert()
                .success();
        }
    }
}

mod test_edge_cases {
    use super::*;

    #[test]
    fn test_find_habit_by_id() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "1"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Logged 'Exercise' as done"));
    }

    #[test]
    fn test_find_habit_by_name_case_insensitive() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Logged 'Exercise' as done"));
    }
}

mod test_data_export {
    use super::*;

    #[test]
    fn test_export_empty_data() {
        let env = setup_test_env();
        let export_file = env.path().join("export.json");

        env.cmd()
            .args(["data", "export", export_file.to_str().unwrap()])
            .assert()
            .success()
            .stdout(predicate::str::contains("Exported 0 habit(s) and 0 completion(s)"));

        let contents = fs::read_to_string(&export_file).unwrap();
        assert!(contents.contains("\"habits\""));
        assert!(contents.contains("\"completions\""));
    }

    #[test]
    fn test_export_with_data() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "Exercise", "--frequency", "daily"])
            .assert()
            .success();
        env.cmd()
            .args(["habits", "add", "Read", "--description", "Read books"])
            .assert()
            .success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-16"])
            .assert()
            .success();
        env.cmd()
            .args(["log", "done", "Read", "--date", "2024-06-15"])
            .assert()
            .success();

        let export_file = env.path().join("export.json");
        env.cmd()
            .args(["data", "export", export_file.to_str().unwrap()])
            .assert()
            .success()
            .stdout(predicate::str::contains("Exported 2 habit(s) and 3 completion(s)"));

        let contents = fs::read_to_string(&export_file).unwrap();
        assert!(contents.contains("Exercise"));
        assert!(contents.contains("daily"));
        assert!(contents.contains("Read"));
        assert!(contents.contains("Read books"));
        assert!(contents.contains("2024-06-15"));
        assert!(contents.contains("2024-06-16"));
    }

    #[test]
    fn test_export_refuses_overwrite() {
        let env = setup_test_env();
        let export_file = env.path().join("export.json");
        fs::write(&export_file, "{}").unwrap();

        env.cmd()
            .args(["data", "export", export_file.to_str().unwrap()])
            .assert()
            .failure()
            .stderr(predicate::str::contains("already exists"))
            .stderr(predicate::str::contains("--force"));
    }

    #[test]
    fn test_export_force_overwrites() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();

        let export_file = env.path().join("export.json");
        fs::write(&export_file, r#"{"old": "data"}"#).unwrap();

        env.cmd()
            .args(["data", "export", export_file.to_str().unwrap(), "--force"])
            .assert()
            .success();

        let contents = fs::read_to_string(&export_file).unwrap();
        assert!(contents.contains("habits"));
        assert!(!contents.contains("old"));
    }

    #[test]
    fn test_export_creates_parent_directories() {
        let env = setup_test_env();
        let export_file = env.path().join("subdir").join("nested").join("export.json");

        env.cmd()
            .args(["data", "export", export_file.to_str().unwrap()])
            .assert()
            .success();

        assert!(export_file.exists());
    }
}

mod test_data_import {
    use super::*;

    #[test]
    fn test_import_valid_data() {
        let env = setup_test_env();
        let import_data = r#"{
            "habits": {
                "1": {"name": "Meditate", "frequency": "daily"},
                "2": {"name": "Journal", "description": "Write daily thoughts"}
            },
            "completions": {
                "1": ["2024-06-15", "2024-06-16"],
                "2": ["2024-06-15"]
            }
        }"#;

        let import_file = env.path().join("import.json");
        fs::write(&import_file, import_data).unwrap();

        env.cmd()
            .args(["data", "import", import_file.to_str().unwrap()])
            .assert()
            .success()
            .stdout(predicate::str::contains("Imported 2 habit(s) and 3 completion(s)"));

        env.cmd()
            .args(["habits", "list"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Meditate"))
            .stdout(predicate::str::contains("Journal"));
    }

    #[test]
    fn test_import_empty_data() {
        let env = setup_test_env();
        let import_data = r#"{"habits": {}, "completions": {}}"#;
        let import_file = env.path().join("import.json");
        fs::write(&import_file, import_data).unwrap();

        env.cmd()
            .args(["data", "import", import_file.to_str().unwrap()])
            .assert()
            .success()
            .stdout(predicate::str::contains("Imported 0 habit(s) and 0 completion(s)"));
    }

    #[test]
    fn test_import_refuses_without_force() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();

        let import_data = r#"{"habits": {"1": {"name": "New"}}, "completions": {}}"#;
        let import_file = env.path().join("import.json");
        fs::write(&import_file, import_data).unwrap();

        env.cmd()
            .args(["data", "import", import_file.to_str().unwrap()])
            .assert()
            .failure()
            .stderr(predicate::str::contains("Current data exists"))
            .stderr(predicate::str::contains("--force"));

        env.cmd()
            .args(["habits", "list"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Exercise"));
    }

    #[test]
    fn test_import_force_replaces_data() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();

        let import_data = r#"{"habits": {"5": {"name": "Yoga"}}, "completions": {}}"#;
        let import_file = env.path().join("import.json");
        fs::write(&import_file, import_data).unwrap();

        env.cmd()
            .args(["data", "import", import_file.to_str().unwrap(), "--force"])
            .assert()
            .success();

        env.cmd()
            .args(["habits", "list"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Yoga"))
            .stdout(predicate::str::is_match("Exercise").unwrap().not());
    }

    #[test]
    fn test_import_invalid_json() {
        let env = setup_test_env();
        let import_file = env.path().join("bad.json");
        fs::write(&import_file, "not valid json {").unwrap();

        env.cmd()
            .args(["data", "import", import_file.to_str().unwrap()])
            .assert()
            .failure()
            .stderr(predicate::str::contains("Invalid JSON"));
    }

    #[test]
    fn test_import_missing_habits_field() {
        let env = setup_test_env();
        let import_file = env.path().join("import.json");
        fs::write(&import_file, r#"{"completions": {}}"#).unwrap();

        env.cmd()
            .args(["data", "import", import_file.to_str().unwrap()])
            .assert()
            .failure()
            .stderr(predicate::str::contains("missing"));
    }

    #[test]
    fn test_import_missing_completions_field() {
        let env = setup_test_env();
        let import_file = env.path().join("import.json");
        fs::write(&import_file, r#"{"habits": {}}"#).unwrap();

        env.cmd()
            .args(["data", "import", import_file.to_str().unwrap()])
            .assert()
            .failure()
            .stderr(predicate::str::contains("missing"));
    }

    #[test]
    fn test_import_invalid_habit_structure() {
        let env = setup_test_env();
        let import_data = r#"{
            "habits": {"1": {"description": "No name field"}},
            "completions": {}
        }"#;
        let import_file = env.path().join("import.json");
        fs::write(&import_file, import_data).unwrap();

        env.cmd()
            .args(["data", "import", import_file.to_str().unwrap()])
            .assert()
            .failure()
            .stderr(predicate::str::contains("missing 'name'"));
    }

    #[test]
    fn test_import_invalid_frequency() {
        let env = setup_test_env();
        let import_data = r#"{
            "habits": {"1": {"name": "Test", "frequency": "biweekly"}},
            "completions": {}
        }"#;
        let import_file = env.path().join("import.json");
        fs::write(&import_file, import_data).unwrap();

        env.cmd()
            .args(["data", "import", import_file.to_str().unwrap()])
            .assert()
            .failure()
            .stderr(predicate::str::contains("frequency"));
    }

    #[test]
    fn test_import_invalid_date_format() {
        let env = setup_test_env();
        let import_data = r#"{
            "habits": {"1": {"name": "Test"}},
            "completions": {"1": ["06-15-2024"]}
        }"#;
        let import_file = env.path().join("import.json");
        fs::write(&import_file, import_data).unwrap();

        env.cmd()
            .args(["data", "import", import_file.to_str().unwrap()])
            .assert()
            .failure()
            .stderr(predicate::str::contains("Invalid"));
    }

    #[test]
    fn test_import_nonexistent_file() {
        let env = setup_test_env();
        let import_file = env.path().join("missing.json");

        env.cmd()
            .args(["data", "import", import_file.to_str().unwrap()])
            .assert()
            .failure();
    }
}

mod test_editing_and_corrections {
    use super::*;
    use chrono::{Duration, Local};

    #[test]
    fn test_undo_removes_completion() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-16"])
            .assert()
            .success();

        env.cmd()
            .args(["log", "undo", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Removed completion"));
    }

    #[test]
    fn test_undo_nonexistent_completion() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();

        env.cmd()
            .args(["log", "undo", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success()
            .stdout(predicate::str::contains("No completion record"));
    }

    #[test]
    fn test_undo_updates_streak_immediately() {
        let env = setup_test_env();
        let today = Local::now().date_naive();
        let yesterday = (today - Duration::days(1)).format("%Y-%m-%d").to_string();
        let day_before = (today - Duration::days(2)).format("%Y-%m-%d").to_string();

        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", &day_before])
            .assert()
            .success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", &yesterday])
            .assert()
            .success();
        env.cmd().args(["log", "done", "Exercise"]).assert().success();

        env.cmd()
            .args(["progress", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Current streak:    3 day(s)"));

        env.cmd()
            .args(["log", "undo", "Exercise", "--date", &yesterday])
            .assert()
            .success();

        env.cmd()
            .args(["progress", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Current streak:    1 day(s)"));
    }

    #[test]
    fn test_rename_updates_show_output() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "Exercise", "--description", "Morning workout"])
            .assert()
            .success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--name", "Workout"])
            .assert()
            .success();

        env.cmd()
            .args(["habits", "show", "Workout"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Workout"))
            .stdout(predicate::str::contains("Morning workout"));
    }

    #[test]
    fn test_rename_updates_list_output() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--name", "Daily Workout"])
            .assert()
            .success();

        env.cmd()
            .args(["habits", "list"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Daily Workout"))
            .stdout(predicate::str::is_match("Exercise").unwrap().not());
    }

    #[test]
    fn test_rename_updates_progress_output() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["log", "done", "Exercise"]).assert().success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--name", "Workout"])
            .assert()
            .success();

        env.cmd()
            .args(["progress", "show", "Workout"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Workout:"))
            .stdout(predicate::str::contains("Total completions: 1"));
    }

    #[test]
    fn test_update_description_reflects_in_show() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "Exercise", "--description", "Old description"])
            .assert()
            .success();
        env.cmd()
            .args(["habits", "update", "Exercise", "--description", "New description"])
            .assert()
            .success();

        env.cmd()
            .args(["habits", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("New description"))
            .stdout(predicate::str::is_match("Old description").unwrap().not());
    }

    #[test]
    fn test_combined_edit_name_and_description() {
        let env = setup_test_env();
        env.cmd()
            .args(["habits", "add", "Exercise", "--description", "Old"])
            .assert()
            .success();
        env.cmd()
            .args([
                "habits", "update", "Exercise",
                "--name", "Workout",
                "--description", "New description"
            ])
            .assert()
            .success();

        env.cmd()
            .args(["habits", "show", "Workout"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Workout"))
            .stdout(predicate::str::contains("New description"));
    }
}

mod test_weekly_command {
    use super::*;

    #[test]
    fn test_weekly_shows_summary() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["log", "done", "Exercise"]).assert().success();

        env.cmd()
            .args(["progress", "weekly"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Weekly Summary"))
            .stdout(predicate::str::contains("Exercise"))
            .stdout(predicate::str::contains("Completed:"))
            .stdout(predicate::str::contains("Streak:"));
    }

    #[test]
    fn test_weekly_with_offset() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();

        env.cmd()
            .args(["progress", "weekly", "--week-offset", "1"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Weekly Summary"));
    }

    #[test]
    fn test_weekly_no_habits() {
        let env = setup_test_env();
        env.cmd()
            .args(["progress", "weekly"])
            .assert()
            .success()
            .stdout(predicate::str::contains("No habits tracked yet"));
    }
}

mod test_at_risk_command {
    use super::*;
    use chrono::{Duration, Local};

    #[test]
    fn test_at_risk_shows_at_risk_habits() {
        let env = setup_test_env();
        let today = Local::now().date_naive();
        let yesterday = (today - Duration::days(1)).format("%Y-%m-%d").to_string();
        let day_before = (today - Duration::days(2)).format("%Y-%m-%d").to_string();

        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", &day_before])
            .assert()
            .success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", &yesterday])
            .assert()
            .success();

        env.cmd()
            .args(["progress", "at-risk"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Exercise"))
            .stdout(predicate::str::contains("streak"));
    }

    #[test]
    fn test_at_risk_no_habits_at_risk() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["log", "done", "Exercise"]).assert().success();

        env.cmd()
            .args(["progress", "at-risk"])
            .assert()
            .success()
            .stdout(predicate::str::contains("No habits at risk"));
    }

    #[test]
    fn test_at_risk_no_habits() {
        let env = setup_test_env();
        env.cmd()
            .args(["progress", "at-risk"])
            .assert()
            .success()
            .stdout(predicate::str::contains("No habits tracked yet"));
    }
}

mod test_rate_command {
    use super::*;
    use chrono::Local;

    #[test]
    fn test_rate_shows_completion_rate() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-16"])
            .assert()
            .success();

        env.cmd()
            .args(["progress", "rate", "--start", "2024-06-15", "--end", "2024-06-21"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Completion Rate"))
            .stdout(predicate::str::contains("2/7"));
    }

    #[test]
    fn test_rate_single_habit() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["habits", "add", "Read"]).assert().success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success();

        env.cmd()
            .args(["progress", "rate", "--start", "2024-06-15", "--end", "2024-06-21", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Exercise"))
            .stdout(predicate::str::is_match("Read").unwrap().not());
    }

    #[test]
    fn test_rate_defaults_end_to_today() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();

        let today = Local::now().date_naive().format("%Y-%m-%d").to_string();

        env.cmd()
            .args(["progress", "rate", "--start", "2024-06-01"])
            .assert()
            .success()
            .stdout(predicate::str::contains(&today));
    }

    #[test]
    fn test_rate_invalid_date_range() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();

        env.cmd()
            .args(["progress", "rate", "--start", "2024-06-20", "--end", "2024-06-15"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("Start date must be before"));
    }

    #[test]
    fn test_rate_invalid_start_date() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();

        env.cmd()
            .args(["progress", "rate", "--start", "bad-date"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("Invalid date format"));
    }

    #[test]
    fn test_rate_nonexistent_habit() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();

        env.cmd()
            .args(["progress", "rate", "--start", "2024-06-01", "NoHabit"])
            .assert()
            .failure()
            .stderr(predicate::str::contains("not found"));
    }
}

mod test_report_command {
    use super::*;
    use chrono::{Duration, Local};

    #[test]
    fn test_report_shows_overview() {
        let env = setup_test_env();
        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd().args(["log", "done", "Exercise"]).assert().success();

        env.cmd()
            .args(["progress", "report"])
            .assert()
            .success()
            .stdout(predicate::str::contains("HABIT TRACKER REPORT"))
            .stdout(predicate::str::contains("THIS WEEK"))
            .stdout(predicate::str::contains("Exercise"));
    }

    #[test]
    fn test_report_shows_at_risk() {
        let env = setup_test_env();
        let today = Local::now().date_naive();
        let yesterday = (today - Duration::days(1)).format("%Y-%m-%d").to_string();
        let day_before = (today - Duration::days(2)).format("%Y-%m-%d").to_string();

        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", &day_before])
            .assert()
            .success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", &yesterday])
            .assert()
            .success();

        env.cmd()
            .args(["progress", "report"])
            .assert()
            .success()
            .stdout(predicate::str::contains("STREAKS AT RISK"))
            .stdout(predicate::str::contains("Exercise"));
    }

    #[test]
    fn test_report_shows_trends() {
        let env = setup_test_env();
        let today = Local::now().date_naive();

        env.cmd().args(["habits", "add", "Exercise"]).assert().success();
        for i in (0..14).step_by(2) {
            if i < 7 {
                let d = (today - Duration::days(i)).format("%Y-%m-%d").to_string();
                env.cmd()
                    .args(["log", "done", "Exercise", "--date", &d])
                    .assert()
                    .success();
            }
        }

        env.cmd()
            .args(["progress", "report"])
            .assert()
            .success()
            .stdout(predicate::str::contains("This week overall"));
    }

    #[test]
    fn test_report_no_habits() {
        let env = setup_test_env();
        env.cmd()
            .args(["progress", "report"])
            .assert()
            .success()
            .stdout(predicate::str::contains("No habits tracked yet"));
    }
}

mod test_export_import_round_trip {
    use super::*;

    #[test]
    fn test_round_trip_preserves_data() {
        let env = setup_test_env();

        env.cmd()
            .args(["habits", "add", "Exercise", "--frequency", "daily", "--description", "Daily workout"])
            .assert()
            .success();
        env.cmd()
            .args(["habits", "add", "Read", "--frequency", "weekends"])
            .assert()
            .success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-15"])
            .assert()
            .success();
        env.cmd()
            .args(["log", "done", "Exercise", "--date", "2024-06-16"])
            .assert()
            .success();
        env.cmd()
            .args(["log", "done", "Read", "--date", "2024-06-15"])
            .assert()
            .success();

        let export_file = env.path().join("backup.json");
        env.cmd()
            .args(["data", "export", export_file.to_str().unwrap()])
            .assert()
            .success();

        env.cmd().args(["habits", "remove", "Exercise"]).assert().success();
        env.cmd().args(["habits", "remove", "Read"]).assert().success();

        env.cmd()
            .args(["data", "import", export_file.to_str().unwrap()])
            .assert()
            .success();

        env.cmd()
            .args(["habits", "list"])
            .assert()
            .success()
            .stdout(predicate::str::contains("Exercise"))
            .stdout(predicate::str::contains("Read"));

        env.cmd()
            .args(["habits", "show", "Exercise"])
            .assert()
            .success()
            .stdout(predicate::str::contains("daily"))
            .stdout(predicate::str::contains("Daily workout"));
    }
}
