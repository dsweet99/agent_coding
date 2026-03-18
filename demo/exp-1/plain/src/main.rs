mod data;
mod commands;
mod streak;

use clap::{Parser, Subcommand};
use std::process;

#[derive(Parser)]
#[command(name = "habit-tracker")]
#[command(version = "0.1.0")]
#[command(about = "Daily Habit Tracker - Track your habits and build consistency.\n\nA simple command-line tool to define habits, log daily completions,\nand view your progress over time.")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Manage your habits (add, list, remove)
    Habits {
        #[command(subcommand)]
        command: HabitsCommands,
    },
    /// Log habit completions
    Log {
        #[command(subcommand)]
        command: LogCommands,
    },
    /// View habit progress and statistics
    Progress {
        #[command(subcommand)]
        command: ProgressCommands,
    },
    /// Import and export tracking data
    Data {
        #[command(subcommand)]
        command: DataCommands,
    },
}

#[derive(Subcommand)]
enum HabitsCommands {
    /// Add a new habit to track
    Add {
        /// Name of the habit
        name: String,
        /// Optional description of the habit
        #[arg(short, long)]
        description: Option<String>,
        /// Target frequency (daily, weekdays, weekends, weekly, monthly)
        #[arg(short, long)]
        frequency: Option<String>,
    },
    /// List all habits being tracked
    List {
        /// Show metadata details
        #[arg(short, long)]
        verbose: bool,
    },
    /// Remove a habit from tracking
    Remove {
        /// Habit ID or name
        identifier: String,
    },
    /// Update a habit's name, description, or frequency
    Update {
        /// Habit ID or name
        identifier: String,
        /// New name for the habit
        #[arg(short, long)]
        name: Option<String>,
        /// New description (use empty string to clear)
        #[arg(short, long)]
        description: Option<String>,
        /// New frequency (daily, weekdays, weekends, weekly, monthly, or empty to clear)
        #[arg(short, long)]
        frequency: Option<String>,
    },
    /// Show detailed information about a habit
    Show {
        /// Habit ID or name
        identifier: String,
    },
}

#[derive(Subcommand)]
enum LogCommands {
    /// Mark a habit as completed
    Done {
        /// Habit ID or name
        habit: String,
        /// Date of completion (YYYY-MM-DD). Defaults to today
        #[arg(short, long)]
        date: Option<String>,
    },
    /// Remove a completion record for a habit
    Undo {
        /// Habit ID or name
        habit: String,
        /// Date to undo (YYYY-MM-DD). Defaults to today
        #[arg(short, long)]
        date: Option<String>,
    },
}

#[derive(Subcommand)]
enum ProgressCommands {
    /// Show progress for a habit or all habits
    Show {
        /// Habit ID or name (optional, shows all if omitted)
        habit: Option<String>,
    },
    /// Show current and longest streaks for all habits
    Streaks,
    /// Show recent completion history
    History {
        /// Habit ID or name (optional, shows all if omitted)
        habit: Option<String>,
        /// Number of days to show (default: 7)
        #[arg(short = 'n', long, default_value = "7")]
        days: u32,
    },
    /// Show weekly summary report across all habits
    Weekly {
        /// Weeks ago (0=current, 1=last week, etc.)
        #[arg(short, long, default_value = "0")]
        week_offset: u32,
    },
    /// Show habits at risk of losing their streak
    AtRisk,
    /// Show completion rate for a date range
    Rate {
        /// Start date (YYYY-MM-DD)
        #[arg(short, long)]
        start: String,
        /// End date (YYYY-MM-DD). Defaults to today
        #[arg(short, long)]
        end: Option<String>,
        /// Habit ID or name (optional, shows all if omitted)
        habit: Option<String>,
    },
    /// Show an at-a-glance report useful for planning the next week
    Report,
}

#[derive(Subcommand)]
enum DataCommands {
    /// Export all tracking data to a file
    Export {
        /// Path where the data will be saved
        filepath: String,
        /// Overwrite existing file without prompting
        #[arg(short, long)]
        force: bool,
    },
    /// Import tracking data from a file
    Import {
        /// Path to the file to import
        filepath: String,
        /// Replace existing data without prompting
        #[arg(short, long)]
        force: bool,
    },
}

fn main() {
    let cli = Cli::parse();

    let result = match cli.command {
        Commands::Habits { command } => match command {
            HabitsCommands::Add { name, description, frequency } => {
                commands::habits::add(&name, description.as_deref(), frequency.as_deref())
            }
            HabitsCommands::List { verbose } => {
                commands::habits::list(verbose)
            }
            HabitsCommands::Remove { identifier } => {
                commands::habits::remove(&identifier)
            }
            HabitsCommands::Update { identifier, name, description, frequency } => {
                commands::habits::update(&identifier, name.as_deref(), description.as_deref(), frequency.as_deref())
            }
            HabitsCommands::Show { identifier } => {
                commands::habits::show(&identifier)
            }
        },
        Commands::Log { command } => match command {
            LogCommands::Done { habit, date } => {
                commands::log::done(&habit, date.as_deref())
            }
            LogCommands::Undo { habit, date } => {
                commands::log::undo(&habit, date.as_deref())
            }
        },
        Commands::Progress { command } => match command {
            ProgressCommands::Show { habit } => {
                commands::progress::show(habit.as_deref())
            }
            ProgressCommands::Streaks => {
                commands::progress::streaks()
            }
            ProgressCommands::History { habit, days } => {
                commands::progress::history(habit.as_deref(), days)
            }
            ProgressCommands::Weekly { week_offset } => {
                commands::progress::weekly(week_offset)
            }
            ProgressCommands::AtRisk => {
                commands::progress::at_risk()
            }
            ProgressCommands::Rate { start, end, habit } => {
                commands::progress::rate(&start, end.as_deref(), habit.as_deref())
            }
            ProgressCommands::Report => {
                commands::progress::report()
            }
        },
        Commands::Data { command } => match command {
            DataCommands::Export { filepath, force } => {
                commands::data::export(&filepath, force)
            }
            DataCommands::Import { filepath, force } => {
                commands::data::import(&filepath, force)
            }
        },
    };

    if let Err(e) = result {
        eprintln!("Error: {}", e);
        process::exit(1);
    }
}
