use chrono::NaiveDate;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::io;
use std::path::PathBuf;

pub const VALID_FREQUENCIES: &[&str] = &["daily", "weekdays", "weekends", "weekly", "monthly"];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Habit {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub frequency: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct TrackerData {
    pub habits: HashMap<String, Habit>,
    pub completions: HashMap<String, Vec<String>>,
}

fn get_data_dir() -> PathBuf {
    dirs::home_dir()
        .expect("Could not find home directory")
        .join(".habit_tracker")
}

fn get_data_file() -> PathBuf {
    get_data_dir().join("data.json")
}

fn ensure_data_dir() -> io::Result<()> {
    let data_dir = get_data_dir();
    if !data_dir.exists() {
        fs::create_dir_all(&data_dir)?;
    }
    Ok(())
}

pub fn load_data() -> io::Result<TrackerData> {
    ensure_data_dir()?;
    let data_file = get_data_file();

    if data_file.exists() {
        let contents = fs::read_to_string(&data_file)?;
        let data: TrackerData = serde_json::from_str(&contents)
            .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
        Ok(data)
    } else {
        Ok(TrackerData::default())
    }
}

pub fn save_data(data: &TrackerData) -> io::Result<()> {
    ensure_data_dir()?;
    let data_file = get_data_file();
    let contents = serde_json::to_string_pretty(data)
        .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
    fs::write(&data_file, contents)
}

pub fn get_next_id(habits: &HashMap<String, Habit>) -> u32 {
    if habits.is_empty() {
        1
    } else {
        habits
            .keys()
            .filter_map(|k| k.parse::<u32>().ok())
            .max()
            .unwrap_or(0)
            + 1
    }
}

pub fn find_habit<'a>(habits: &'a HashMap<String, Habit>, identifier: &'a str) -> Option<(&'a str, &'a Habit)> {
    if let Some(habit) = habits.get(identifier) {
        return Some((identifier, habit));
    }

    for (habit_id, habit_data) in habits.iter() {
        if habit_data.name.to_lowercase() == identifier.to_lowercase() {
            return Some((habit_id, habit_data));
        }
    }

    None
}


pub fn parse_date(date_str: Option<&str>) -> Result<NaiveDate, String> {
    match date_str {
        None => Ok(chrono::Local::now().date_naive()),
        Some(s) => NaiveDate::parse_from_str(s, "%Y-%m-%d")
            .map_err(|_| format!("Invalid date format: '{}'. Use YYYY-MM-DD format.", s)),
    }
}

pub fn validate_frequency(frequency: Option<&str>) -> Result<Option<String>, String> {
    match frequency {
        None => Ok(None),
        Some(f) => {
            let freq_lower = f.to_lowercase().trim().to_string();
            if VALID_FREQUENCIES.contains(&freq_lower.as_str()) {
                Ok(Some(freq_lower))
            } else {
                let valid_list = VALID_FREQUENCIES.join(", ");
                Err(format!(
                    "Invalid frequency: '{}'. Valid options: {}.",
                    f, valid_list
                ))
            }
        }
    }
}

pub fn validate_import_data(data: &serde_json::Value) -> Result<TrackerData, String> {
    let obj = data
        .as_object()
        .ok_or("Invalid format: root must be a JSON object.")?;

    if !obj.contains_key("habits") || !obj.contains_key("completions") {
        return Err("Invalid format: missing 'habits' or 'completions' field.".to_string());
    }

    let habits_val = &obj["habits"];
    let completions_val = &obj["completions"];

    let habits_obj = habits_val
        .as_object()
        .ok_or("Invalid format: 'habits' must be an object.")?;

    let completions_obj = completions_val
        .as_object()
        .ok_or("Invalid format: 'completions' must be an object.")?;

    let mut habits = HashMap::new();

    for (habit_id, habit_data) in habits_obj.iter() {
        let habit_obj = habit_data
            .as_object()
            .ok_or_else(|| format!("Invalid habit entry for id '{}': must be an object.", habit_id))?;

        let name = habit_obj
            .get("name")
            .ok_or_else(|| format!("Invalid habit entry for id '{}': missing 'name' field.", habit_id))?
            .as_str()
            .ok_or_else(|| format!("Invalid habit entry for id '{}': 'name' must be a non-empty string.", habit_id))?;

        if name.trim().is_empty() {
            return Err(format!(
                "Invalid habit entry for id '{}': 'name' must be a non-empty string.",
                habit_id
            ));
        }

        let description = if let Some(desc_val) = habit_obj.get("description") {
            Some(
                desc_val
                    .as_str()
                    .ok_or_else(|| format!("Invalid habit entry for id '{}': 'description' must be a string.", habit_id))?
                    .to_string(),
            )
        } else {
            None
        };

        let frequency = if let Some(freq_val) = habit_obj.get("frequency") {
            let freq = freq_val
                .as_str()
                .ok_or_else(|| format!("Invalid habit entry for id '{}': 'frequency' must be a string.", habit_id))?;

            if !VALID_FREQUENCIES.contains(&freq.to_lowercase().as_str()) {
                let valid_list = VALID_FREQUENCIES.join(", ");
                return Err(format!(
                    "Invalid habit entry for id '{}': 'frequency' must be one of: {}.",
                    habit_id, valid_list
                ));
            }
            Some(freq.to_lowercase())
        } else {
            None
        };

        habits.insert(
            habit_id.clone(),
            Habit {
                name: name.to_string(),
                description,
                frequency,
            },
        );
    }

    let mut completions = HashMap::new();

    for (habit_id, completion_list) in completions_obj.iter() {
        let dates = completion_list
            .as_array()
            .ok_or_else(|| format!("Invalid completions for habit id '{}': must be an array.", habit_id))?;

        let mut date_strings = Vec::new();

        for date_val in dates {
            let date_str = date_val
                .as_str()
                .ok_or_else(|| format!("Invalid completion date for habit id '{}': dates must be strings.", habit_id))?;

            parse_date(Some(date_str))
                .map_err(|e| format!("Invalid completion date for habit id '{}': {}", habit_id, e))?;

            date_strings.push(date_str.to_string());
        }

        completions.insert(habit_id.clone(), date_strings);
    }

    Ok(TrackerData { habits, completions })
}
