use crate::data::{find_habit, load_data, parse_date, save_data};
use std::io;

pub fn done(habit: &str, date_str: Option<&str>) -> io::Result<()> {
    let completion_date = match parse_date(date_str) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("Error: {}", e);
            std::process::exit(1);
        }
    };

    let mut data = load_data()?;

    let (habit_id, habit_name) = match find_habit(&data.habits, habit) {
        Some((id, h)) => (id.to_string(), h.name.clone()),
        None => {
            eprintln!("Error: Habit '{}' not found.", habit);
            std::process::exit(1);
        }
    };

    let date_key = completion_date.format("%Y-%m-%d").to_string();

    let completions = data.completions.entry(habit_id).or_insert_with(Vec::new);

    if completions.contains(&date_key) {
        println!("'{}' already marked done for {}.", habit_name, date_key);
        return Ok(());
    }

    completions.push(date_key.clone());
    completions.sort();
    save_data(&data)?;

    println!("Logged '{}' as done for {}.", habit_name, date_key);
    Ok(())
}

pub fn undo(habit: &str, date_str: Option<&str>) -> io::Result<()> {
    let completion_date = match parse_date(date_str) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("Error: {}", e);
            std::process::exit(1);
        }
    };

    let mut data = load_data()?;

    let (habit_id, habit_name) = match find_habit(&data.habits, habit) {
        Some((id, h)) => (id.to_string(), h.name.clone()),
        None => {
            eprintln!("Error: Habit '{}' not found.", habit);
            std::process::exit(1);
        }
    };

    let date_key = completion_date.format("%Y-%m-%d").to_string();

    let completions = data.completions.get_mut(&habit_id);

    match completions {
        Some(dates) if dates.contains(&date_key) => {
            dates.retain(|d| d != &date_key);
            save_data(&data)?;
            println!("Removed completion for '{}' on {}.", habit_name, date_key);
        }
        _ => {
            println!("No completion record for '{}' on {}.", habit_name, date_key);
        }
    }

    Ok(())
}
