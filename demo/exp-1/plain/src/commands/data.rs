use crate::data::{load_data, save_data, validate_import_data};
use std::fs;
use std::io;
use std::path::Path;

pub fn export(filepath: &str, force: bool) -> io::Result<()> {
    let export_path = Path::new(filepath);

    if export_path.exists() && !force {
        eprintln!(
            "Error: File '{}' already exists. Use --force to overwrite.",
            filepath
        );
        std::process::exit(1);
    }

    let data = load_data()?;

    if let Some(parent) = export_path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)?;
        }
    }

    let contents = serde_json::to_string_pretty(&data)
        .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
    fs::write(export_path, contents)?;

    let habit_count = data.habits.len();
    let completion_count: usize = data.completions.values().map(|v| v.len()).sum();
    println!(
        "Exported {} habit(s) and {} completion(s) to '{}'.",
        habit_count, completion_count, filepath
    );

    Ok(())
}

pub fn import(filepath: &str, force: bool) -> io::Result<()> {
    let import_path = Path::new(filepath);

    if !import_path.exists() {
        eprintln!("Error: File '{}' does not exist.", filepath);
        std::process::exit(1);
    }

    let contents = fs::read_to_string(import_path)?;

    let import_json: serde_json::Value = match serde_json::from_str(&contents) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("Error: Invalid JSON in '{}': {}", filepath, e);
            std::process::exit(1);
        }
    };

    let import_data = match validate_import_data(&import_json) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("Error: {}", e);
            std::process::exit(1);
        }
    };

    let current_data = load_data()?;
    let has_existing_data = !current_data.habits.is_empty() || !current_data.completions.is_empty();

    if has_existing_data && !force {
        eprintln!("Error: Current data exists. Use --force to replace it.");
        std::process::exit(1);
    }

    save_data(&import_data)?;

    let habit_count = import_data.habits.len();
    let completion_count: usize = import_data.completions.values().map(|v| v.len()).sum();
    println!(
        "Imported {} habit(s) and {} completion(s) from '{}'.",
        habit_count, completion_count, filepath
    );

    Ok(())
}
