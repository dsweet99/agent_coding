use crate::data::{find_habit, get_next_id, load_data, save_data, validate_frequency, Habit};
use std::io;

pub fn add(name: &str, description: Option<&str>, frequency: Option<&str>) -> io::Result<()> {
    let name = name.trim();
    if name.is_empty() {
        eprintln!("Error: Habit name cannot be empty.");
        std::process::exit(1);
    }

    let freq = match validate_frequency(frequency) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("Error: {}", e);
            std::process::exit(1);
        }
    };

    let mut data = load_data()?;

    for habit_data in data.habits.values() {
        if habit_data.name.to_lowercase() == name.to_lowercase() {
            eprintln!("Error: Habit '{}' already exists.", name);
            std::process::exit(1);
        }
    }

    let habit_id = get_next_id(&data.habits).to_string();
    let habit_entry = Habit {
        name: name.to_string(),
        description: description.map(|d| d.trim().to_string()).filter(|d| !d.is_empty()),
        frequency: freq,
    };

    data.habits.insert(habit_id.clone(), habit_entry);
    save_data(&data)?;

    println!("Added habit '{}' (id: {})", name, habit_id);
    Ok(())
}

pub fn list(verbose: bool) -> io::Result<()> {
    let data = load_data()?;

    if data.habits.is_empty() {
        println!("No habits tracked yet. Use 'habits add <name>' to add one.");
        return Ok(());
    }

    println!("Habits:");

    let mut habits: Vec<_> = data.habits.iter().collect();
    habits.sort_by(|a, b| {
        let id_a: u32 = a.0.parse().unwrap_or(0);
        let id_b: u32 = b.0.parse().unwrap_or(0);
        id_a.cmp(&id_b)
    });

    for (habit_id, habit_data) in habits {
        let line = format!("  [{}] {}", habit_id, habit_data.name);

        if verbose {
            println!("{}", line);
            if let Some(ref desc) = habit_data.description {
                println!("        Description: {}", desc);
            }
            if let Some(ref freq) = habit_data.frequency {
                println!("        Frequency:   {}", freq);
            }
        } else {
            let mut meta_parts = Vec::new();
            if let Some(ref freq) = habit_data.frequency {
                meta_parts.push(freq.clone());
            }
            if meta_parts.is_empty() {
                println!("{}", line);
            } else {
                println!("{} ({})", line, meta_parts.join(", "));
            }
        }
    }

    Ok(())
}

pub fn remove(identifier: &str) -> io::Result<()> {
    let mut data = load_data()?;

    let (habit_id, habit_name) = match find_habit(&data.habits, identifier) {
        Some((id, habit)) => (id.to_string(), habit.name.clone()),
        None => {
            eprintln!("Error: Habit '{}' not found.", identifier);
            std::process::exit(1);
        }
    };

    data.habits.remove(&habit_id);
    data.completions.remove(&habit_id);

    save_data(&data)?;
    println!("Removed habit '{}' (id: {})", habit_name, habit_id);
    Ok(())
}

pub fn update(
    identifier: &str,
    name: Option<&str>,
    description: Option<&str>,
    frequency: Option<&str>,
) -> io::Result<()> {
    if name.is_none() && description.is_none() && frequency.is_none() {
        eprintln!("Error: Provide at least one option to update (--name, --description, or --frequency).");
        std::process::exit(1);
    }

    let mut data = load_data()?;

    let (habit_id, original_name) = match find_habit(&data.habits, identifier) {
        Some((id, habit)) => (id.to_string(), habit.name.clone()),
        None => {
            eprintln!("Error: Habit '{}' not found.", identifier);
            std::process::exit(1);
        }
    };

    let mut updates = Vec::new();

    if let Some(new_name) = name {
        let name_stripped = new_name.trim();
        if name_stripped.is_empty() {
            eprintln!("Error: Habit name cannot be empty.");
            std::process::exit(1);
        }

        if name_stripped.to_lowercase() != original_name.to_lowercase() {
            for (other_id, other_data) in data.habits.iter() {
                if *other_id != habit_id
                    && other_data.name.to_lowercase() == name_stripped.to_lowercase()
                {
                    eprintln!("Error: Habit '{}' already exists.", name_stripped);
                    std::process::exit(1);
                }
            }
        }

        data.habits.get_mut(&habit_id).unwrap().name = name_stripped.to_string();
        updates.push(format!("name ('{}' -> '{}')", original_name, name_stripped));
    }

    if let Some(desc) = description {
        let desc_stripped = desc.trim();
        if desc_stripped.is_empty() {
            data.habits.get_mut(&habit_id).unwrap().description = None;
            updates.push("description (cleared)".to_string());
        } else {
            data.habits.get_mut(&habit_id).unwrap().description = Some(desc_stripped.to_string());
            updates.push("description".to_string());
        }
    }

    if let Some(freq) = frequency {
        let freq_stripped = freq.trim();
        if freq_stripped.is_empty() {
            data.habits.get_mut(&habit_id).unwrap().frequency = None;
            updates.push("frequency (cleared)".to_string());
        } else {
            match validate_frequency(Some(freq_stripped)) {
                Ok(Some(f)) => {
                    data.habits.get_mut(&habit_id).unwrap().frequency = Some(f);
                    updates.push("frequency".to_string());
                }
                Ok(None) => {}
                Err(e) => {
                    eprintln!("Error: {}", e);
                    std::process::exit(1);
                }
            }
        }
    }

    save_data(&data)?;
    println!("Updated '{}': {}.", original_name, updates.join(", "));
    Ok(())
}

pub fn show(identifier: &str) -> io::Result<()> {
    let data = load_data()?;

    let (habit_id, habit_data) = match find_habit(&data.habits, identifier) {
        Some((id, habit)) => (id, habit),
        None => {
            eprintln!("Error: Habit '{}' not found.", identifier);
            std::process::exit(1);
        }
    };

    println!("Habit: {} (id: {})", habit_data.name, habit_id);

    match &habit_data.description {
        Some(desc) => println!("  Description: {}", desc),
        None => println!("  Description: (none)"),
    }

    match &habit_data.frequency {
        Some(freq) => println!("  Frequency:   {}", freq),
        None => println!("  Frequency:   (none)"),
    }

    Ok(())
}
