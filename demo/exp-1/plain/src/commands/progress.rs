use crate::data::{find_habit, load_data, parse_date};
use crate::streak::{calculate_completion_rate, calculate_streaks, get_week_boundaries, identify_at_risk_habits};
use chrono::{Duration, NaiveDate};
use std::io;

pub fn show(habit: Option<&str>) -> io::Result<()> {
    let data = load_data()?;

    if data.habits.is_empty() {
        println!("No habits tracked yet. Use 'habits add <name>' to add one.");
        return Ok(());
    }

    let habits_to_show: Vec<(String, String)> = if let Some(h) = habit {
        match find_habit(&data.habits, h) {
            Some((id, info)) => vec![(id.to_string(), info.name.clone())],
            None => {
                eprintln!("Error: Habit '{}' not found.", h);
                std::process::exit(1);
            }
        }
    } else {
        let mut habits: Vec<_> = data
            .habits
            .iter()
            .map(|(id, h)| (id.clone(), h.name.clone()))
            .collect();
        habits.sort_by(|a, b| {
            let id_a: u32 = a.0.parse().unwrap_or(0);
            let id_b: u32 = b.0.parse().unwrap_or(0);
            id_a.cmp(&id_b)
        });
        habits
    };

    for (habit_id, habit_name) in habits_to_show {
        let habit_completions = data.completions.get(&habit_id).cloned().unwrap_or_default();
        let total = habit_completions.len();
        let (current, longest) = calculate_streaks(&habit_completions, None);

        println!("{}:", habit_name);
        println!("  Total completions: {}", total);
        println!("  Current streak:    {} day(s)", current);
        println!("  Longest streak:    {} day(s)", longest);
    }

    Ok(())
}

pub fn streaks() -> io::Result<()> {
    let data = load_data()?;

    if data.habits.is_empty() {
        println!("No habits tracked yet. Use 'habits add <name>' to add one.");
        return Ok(());
    }

    println!("Streaks:");

    let mut habits: Vec<_> = data.habits.iter().collect();
    habits.sort_by(|a, b| {
        let id_a: u32 = a.0.parse().unwrap_or(0);
        let id_b: u32 = b.0.parse().unwrap_or(0);
        id_a.cmp(&id_b)
    });

    for (habit_id, habit_data) in habits {
        let habit_completions = data.completions.get(habit_id).cloned().unwrap_or_default();
        let (current, longest) = calculate_streaks(&habit_completions, None);
        println!(
            "  {}: {} day(s) current, {} day(s) longest",
            habit_data.name, current, longest
        );
    }

    Ok(())
}

pub fn history(habit: Option<&str>, days: u32) -> io::Result<()> {
    let data = load_data()?;

    if data.habits.is_empty() {
        println!("No habits tracked yet. Use 'habits add <name>' to add one.");
        return Ok(());
    }

    let habits_to_show: Vec<(String, String)> = if let Some(h) = habit {
        match find_habit(&data.habits, h) {
            Some((id, info)) => vec![(id.to_string(), info.name.clone())],
            None => {
                eprintln!("Error: Habit '{}' not found.", h);
                std::process::exit(1);
            }
        }
    } else {
        let mut habits: Vec<_> = data
            .habits
            .iter()
            .map(|(id, h)| (id.clone(), h.name.clone()))
            .collect();
        habits.sort_by(|a, b| {
            let id_a: u32 = a.0.parse().unwrap_or(0);
            let id_b: u32 = b.0.parse().unwrap_or(0);
            id_a.cmp(&id_b)
        });
        habits
    };

    let today = chrono::Local::now().date_naive();
    let date_range: Vec<NaiveDate> = (0..days as i64)
        .map(|i| today - Duration::days(i))
        .collect();

    for (i, (habit_id, habit_name)) in habits_to_show.iter().enumerate() {
        let habit_completions: std::collections::HashSet<String> = data
            .completions
            .get(habit_id)
            .cloned()
            .unwrap_or_default()
            .into_iter()
            .collect();

        println!("{}:", habit_name);

        for d in &date_range {
            let date_str = d.format("%Y-%m-%d").to_string();
            let status = if habit_completions.contains(&date_str) {
                "[x]"
            } else {
                "[ ]"
            };
            let day_name = d.format("%a").to_string();
            println!("  {} ({}): {}", date_str, day_name, status);
        }

        if habits_to_show.len() > 1 && i < habits_to_show.len() - 1 {
            println!();
        }
    }

    Ok(())
}

pub fn weekly(week_offset: u32) -> io::Result<()> {
    let data = load_data()?;

    if data.habits.is_empty() {
        println!("No habits tracked yet. Use 'habits add <name>' to add one.");
        return Ok(());
    }

    let reference_date = chrono::Local::now().date_naive() - Duration::weeks(week_offset as i64);
    let (week_start, week_end) = get_week_boundaries(Some(reference_date));

    println!(
        "Weekly Summary: {} to {}",
        week_start.format("%Y-%m-%d"),
        week_end.format("%Y-%m-%d")
    );
    println!("{}", "=".repeat(50));

    let mut total_completions = 0u32;
    let mut total_possible = 0u32;

    let mut habits: Vec<_> = data.habits.iter().collect();
    habits.sort_by(|a, b| {
        let id_a: u32 = a.0.parse().unwrap_or(0);
        let id_b: u32 = b.0.parse().unwrap_or(0);
        id_a.cmp(&id_b)
    });

    for (habit_id, habit_info) in habits {
        let habit_completions = data.completions.get(habit_id).cloned().unwrap_or_default();
        let (completed, days, rate) =
            calculate_completion_rate(&habit_completions, week_start, week_end);
        let (current_streak, longest_streak) = calculate_streaks(&habit_completions, None);

        total_completions += completed;
        total_possible += days;

        println!("\n{}:", habit_info.name);
        println!("  Completed: {}/{} days ({:.0}%)", completed, days, rate);
        println!(
            "  Streak:    {} day(s) current, {} day(s) best",
            current_streak, longest_streak
        );

        let mut week_grid = String::new();
        for i in 0..7 {
            let d = week_start + Duration::days(i);
            let day_abbrev = &d.format("%a").to_string()[..1];
            let date_str = d.format("%Y-%m-%d").to_string();
            if habit_completions.contains(&date_str) {
                week_grid.push_str(&format!("[{}]", day_abbrev));
            } else {
                week_grid.push_str(&format!(" {} ", day_abbrev));
            }
        }
        println!("  Week:      {}", week_grid);
    }

    println!("\n{}", "=".repeat(50));
    if total_possible > 0 {
        let overall_rate = (total_completions as f64 / total_possible as f64) * 100.0;
        println!(
            "Overall: {}/{} completions ({:.0}%)",
            total_completions, total_possible, overall_rate
        );
    } else {
        println!("Overall: No data for this period.");
    }

    Ok(())
}

pub fn at_risk() -> io::Result<()> {
    let data = load_data()?;

    if data.habits.is_empty() {
        println!("No habits tracked yet. Use 'habits add <name>' to add one.");
        return Ok(());
    }

    let at_risk_habits = identify_at_risk_habits(&data.habits, &data.completions);

    if at_risk_habits.is_empty() {
        println!("No habits at risk of losing their streak.");
        println!("(All streaks are either maintained today or are less than 2 days.)");
        return Ok(());
    }

    println!("Habits at risk of losing their streak:");
    println!("{}", "-".repeat(40));

    for (_, habit_name, current_streak) in at_risk_habits {
        println!("  {}: {} day streak (not done today!)", habit_name, current_streak);
    }

    println!("\nComplete these today to keep your streaks going!");

    Ok(())
}

pub fn rate(start_str: &str, end_str: Option<&str>, habit: Option<&str>) -> io::Result<()> {
    let start_date = match parse_date(Some(start_str)) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("Error: {}", e);
            std::process::exit(1);
        }
    };

    let end_date = if let Some(e) = end_str {
        match parse_date(Some(e)) {
            Ok(d) => d,
            Err(e) => {
                eprintln!("Error: {}", e);
                std::process::exit(1);
            }
        }
    } else {
        chrono::Local::now().date_naive()
    };

    if start_date > end_date {
        eprintln!("Error: Start date must be before or equal to end date.");
        std::process::exit(1);
    }

    let data = load_data()?;

    if data.habits.is_empty() {
        println!("No habits tracked yet. Use 'habits add <name>' to add one.");
        return Ok(());
    }

    let habits_to_show: Vec<(String, String)> = if let Some(h) = habit {
        match find_habit(&data.habits, h) {
            Some((id, info)) => vec![(id.to_string(), info.name.clone())],
            None => {
                eprintln!("Error: Habit '{}' not found.", h);
                std::process::exit(1);
            }
        }
    } else {
        let mut habits: Vec<_> = data
            .habits
            .iter()
            .map(|(id, h)| (id.clone(), h.name.clone()))
            .collect();
        habits.sort_by(|a, b| {
            let id_a: u32 = a.0.parse().unwrap_or(0);
            let id_b: u32 = b.0.parse().unwrap_or(0);
            id_a.cmp(&id_b)
        });
        habits
    };

    let total_days = (end_date - start_date).num_days() + 1;
    println!(
        "Completion Rate: {} to {} ({} days)",
        start_date.format("%Y-%m-%d"),
        end_date.format("%Y-%m-%d"),
        total_days
    );
    println!("{}", "-".repeat(50));

    let mut total_completions = 0u32;
    let mut total_possible = 0u32;

    for (habit_id, habit_name) in &habits_to_show {
        let habit_completions = data.completions.get(habit_id).cloned().unwrap_or_default();
        let (completed, days, rate) =
            calculate_completion_rate(&habit_completions, start_date, end_date);

        total_completions += completed;
        total_possible += days;

        let bar_width = 20;
        let filled = (rate / 100.0 * bar_width as f64) as usize;
        let bar = format!(
            "{}{}",
            "█".repeat(filled),
            "░".repeat(bar_width - filled)
        );

        println!(
            "  {}: {}/{} ({:.1}%) {}",
            habit_name, completed, days, rate, bar
        );
    }

    if habits_to_show.len() > 1 {
        println!("{}", "-".repeat(50));
        if total_possible > 0 {
            let overall_rate = (total_completions as f64 / total_possible as f64) * 100.0;
            println!(
                "  Total: {}/{} ({:.1}%)",
                total_completions, total_possible, overall_rate
            );
        }
    }

    Ok(())
}

pub fn report() -> io::Result<()> {
    let data = load_data()?;

    if data.habits.is_empty() {
        println!("No habits tracked yet. Use 'habits add <name>' to add one.");
        return Ok(());
    }

    let today = chrono::Local::now().date_naive();
    let (this_week_start, this_week_end) = get_week_boundaries(Some(today));
    let last_week_start = this_week_start - Duration::days(7);
    let last_week_end = this_week_start - Duration::days(1);

    println!("{}", "=".repeat(60));
    println!("                    HABIT TRACKER REPORT");
    println!("                    {}", today.format("%Y-%m-%d"));
    println!("{}", "=".repeat(60));

    let at_risk_habits = identify_at_risk_habits(&data.habits, &data.completions);
    if !at_risk_habits.is_empty() {
        println!("\n⚠ STREAKS AT RISK (complete today!):");
        for (_, habit_name, streak) in at_risk_habits.iter().take(5) {
            println!("    • {} ({} day streak)", habit_name, streak);
        }
    }

    println!(
        "\nTHIS WEEK ({} - {}):",
        this_week_start.format("%Y-%m-%d"),
        this_week_end.format("%Y-%m-%d")
    );
    println!("{}", "-".repeat(60));

    let mut this_week_total = 0u32;
    let mut this_week_possible = 0u32;
    let mut last_week_total = 0u32;
    let mut last_week_possible = 0u32;

    let mut habits: Vec<_> = data.habits.iter().collect();
    habits.sort_by(|a, b| {
        let id_a: u32 = a.0.parse().unwrap_or(0);
        let id_b: u32 = b.0.parse().unwrap_or(0);
        id_a.cmp(&id_b)
    });

    for (habit_id, habit_info) in habits {
        let habit_completions = data.completions.get(habit_id).cloned().unwrap_or_default();

        let (tw_completed, tw_days, tw_rate) =
            calculate_completion_rate(&habit_completions, this_week_start, this_week_end);
        let (lw_completed, lw_days, lw_rate) =
            calculate_completion_rate(&habit_completions, last_week_start, last_week_end);

        this_week_total += tw_completed;
        this_week_possible += tw_days;
        last_week_total += lw_completed;
        last_week_possible += lw_days;

        let (current_streak, _) = calculate_streaks(&habit_completions, None);

        let trend = if lw_rate > 0.0 {
            if tw_rate > lw_rate {
                " ↑"
            } else if tw_rate < lw_rate {
                " ↓"
            } else {
                " →"
            }
        } else {
            ""
        };

        println!(
            "  {}: {}/{} ({:.0}%){}  [streak: {}d]",
            habit_info.name, tw_completed, tw_days, tw_rate, trend, current_streak
        );
    }

    println!("\n{}", "-".repeat(60));

    if this_week_possible > 0 {
        let this_week_rate = (this_week_total as f64 / this_week_possible as f64) * 100.0;
        println!(
            "This week overall: {}/{} ({:.0}%)",
            this_week_total, this_week_possible, this_week_rate
        );
    }

    if last_week_possible > 0 {
        let last_week_rate = (last_week_total as f64 / last_week_possible as f64) * 100.0;
        println!(
            "Last week overall: {}/{} ({:.0}%)",
            last_week_total, last_week_possible, last_week_rate
        );

        if this_week_possible > 0 {
            let this_week_rate = (this_week_total as f64 / this_week_possible as f64) * 100.0;
            let diff = this_week_rate - last_week_rate;
            if diff > 0.0 {
                println!("Trend: +{:.0}% improvement from last week", diff);
            } else if diff < 0.0 {
                println!("Trend: {:.0}% from last week", diff);
            } else {
                println!("Trend: Steady from last week");
            }
        }
    }

    println!("\n{}", "=".repeat(60));

    Ok(())
}
