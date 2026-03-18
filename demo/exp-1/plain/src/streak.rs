use chrono::{Datelike, Duration, NaiveDate};

pub fn calculate_streaks(completion_dates: &[String], reference_date: Option<NaiveDate>) -> (u32, u32) {
    if completion_dates.is_empty() {
        return (0, 0);
    }

    let reference = reference_date.unwrap_or_else(|| chrono::Local::now().date_naive());

    let mut dates: Vec<NaiveDate> = completion_dates
        .iter()
        .filter_map(|d| NaiveDate::parse_from_str(d, "%Y-%m-%d").ok())
        .collect();

    dates.sort();

    let mut longest_streak = 1u32;
    let mut current_run = 1u32;

    for i in 1..dates.len() {
        let diff = (dates[i] - dates[i - 1]).num_days();
        if diff == 1 {
            current_run += 1;
            longest_streak = longest_streak.max(current_run);
        } else {
            current_run = 1;
        }
    }

    let mut current_streak = 0u32;
    let mut check_date = reference;

    if !dates.contains(&check_date) {
        check_date = reference - Duration::days(1);
    }

    if dates.contains(&check_date) {
        current_streak = 1;
        let mut prev_date = check_date - Duration::days(1);
        while dates.contains(&prev_date) {
            current_streak += 1;
            prev_date = prev_date - Duration::days(1);
        }
    }

    (current_streak, longest_streak)
}

pub fn get_week_boundaries(reference_date: Option<NaiveDate>) -> (NaiveDate, NaiveDate) {
    let reference = reference_date.unwrap_or_else(|| chrono::Local::now().date_naive());
    let weekday = reference.weekday().num_days_from_monday();
    let week_start = reference - Duration::days(weekday as i64);
    let week_end = week_start + Duration::days(6);
    (week_start, week_end)
}

pub fn calculate_completion_rate(
    completion_dates: &[String],
    start_date: NaiveDate,
    end_date: NaiveDate,
) -> (u32, u32, f64) {
    let total_days = (end_date - start_date).num_days() + 1;
    if total_days <= 0 {
        return (0, 0, 0.0);
    }

    let completed_count = completion_dates
        .iter()
        .filter_map(|d| NaiveDate::parse_from_str(d, "%Y-%m-%d").ok())
        .filter(|d| *d >= start_date && *d <= end_date)
        .count() as u32;

    let rate = (completed_count as f64 / total_days as f64) * 100.0;
    (completed_count, total_days as u32, rate)
}

pub fn identify_at_risk_habits(
    habits: &std::collections::HashMap<String, crate::data::Habit>,
    completions: &std::collections::HashMap<String, Vec<String>>,
) -> Vec<(String, String, u32)> {
    let today = chrono::Local::now().date_naive();
    let today_str = today.format("%Y-%m-%d").to_string();

    let mut at_risk: Vec<(String, String, u32)> = Vec::new();

    for (habit_id, habit_info) in habits.iter() {
        let habit_completions = completions.get(habit_id).cloned().unwrap_or_default();
        let (current, _) = calculate_streaks(&habit_completions, None);

        if current >= 2 && !habit_completions.contains(&today_str) {
            at_risk.push((habit_id.clone(), habit_info.name.clone(), current));
        }
    }

    at_risk.sort_by(|a, b| b.2.cmp(&a.2));
    at_risk
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;

    #[test]
    fn test_empty_completions() {
        let (current, longest) = calculate_streaks(&[], None);
        assert_eq!(current, 0);
        assert_eq!(longest, 0);
    }

    #[test]
    fn test_single_completion_today() {
        let today = chrono::Local::now().date_naive();
        let dates = vec![today.format("%Y-%m-%d").to_string()];
        let (current, longest) = calculate_streaks(&dates, None);
        assert_eq!(current, 1);
        assert_eq!(longest, 1);
    }

    #[test]
    fn test_single_completion_yesterday() {
        let yesterday = chrono::Local::now().date_naive() - Duration::days(1);
        let dates = vec![yesterday.format("%Y-%m-%d").to_string()];
        let (current, longest) = calculate_streaks(&dates, None);
        assert_eq!(current, 1);
        assert_eq!(longest, 1);
    }

    #[test]
    fn test_consecutive_days_streak() {
        let today = chrono::Local::now().date_naive();
        let dates: Vec<String> = (0..5)
            .map(|i| (today - Duration::days(i)).format("%Y-%m-%d").to_string())
            .collect();
        let (current, longest) = calculate_streaks(&dates, None);
        assert_eq!(current, 5);
        assert_eq!(longest, 5);
    }

    #[test]
    fn test_broken_streak() {
        let today = chrono::Local::now().date_naive();
        let dates = vec![
            today.format("%Y-%m-%d").to_string(),
            (today - Duration::days(1)).format("%Y-%m-%d").to_string(),
            (today - Duration::days(3)).format("%Y-%m-%d").to_string(),
            (today - Duration::days(4)).format("%Y-%m-%d").to_string(),
        ];
        let (current, longest) = calculate_streaks(&dates, None);
        assert_eq!(current, 2);
        assert_eq!(longest, 2);
    }

    #[test]
    fn test_longest_streak_in_past() {
        let today = chrono::Local::now().date_naive();
        let dates = vec![
            today.format("%Y-%m-%d").to_string(),
            (today - Duration::days(10)).format("%Y-%m-%d").to_string(),
            (today - Duration::days(11)).format("%Y-%m-%d").to_string(),
            (today - Duration::days(12)).format("%Y-%m-%d").to_string(),
            (today - Duration::days(13)).format("%Y-%m-%d").to_string(),
            (today - Duration::days(14)).format("%Y-%m-%d").to_string(),
        ];
        let (current, longest) = calculate_streaks(&dates, None);
        assert_eq!(current, 1);
        assert_eq!(longest, 5);
    }

    #[test]
    fn test_streak_with_reference_date() {
        let ref_date = NaiveDate::from_ymd_opt(2024, 6, 15).unwrap();
        let dates = vec![
            "2024-06-15".to_string(),
            "2024-06-14".to_string(),
            "2024-06-13".to_string(),
        ];
        let (current, longest) = calculate_streaks(&dates, Some(ref_date));
        assert_eq!(current, 3);
        assert_eq!(longest, 3);
    }

    #[test]
    fn test_no_current_streak_if_gap_from_today() {
        let today = chrono::Local::now().date_naive();
        let old_date = (today - Duration::days(5)).format("%Y-%m-%d").to_string();
        let (current, longest) = calculate_streaks(&[old_date], None);
        assert_eq!(current, 0);
        assert_eq!(longest, 1);
    }

    #[test]
    fn test_week_boundaries_monday() {
        let monday = NaiveDate::from_ymd_opt(2024, 6, 17).unwrap();
        let (start, end) = get_week_boundaries(Some(monday));
        assert_eq!(start, NaiveDate::from_ymd_opt(2024, 6, 17).unwrap());
        assert_eq!(end, NaiveDate::from_ymd_opt(2024, 6, 23).unwrap());
    }

    #[test]
    fn test_week_boundaries_sunday() {
        let sunday = NaiveDate::from_ymd_opt(2024, 6, 23).unwrap();
        let (start, end) = get_week_boundaries(Some(sunday));
        assert_eq!(start, NaiveDate::from_ymd_opt(2024, 6, 17).unwrap());
        assert_eq!(end, NaiveDate::from_ymd_opt(2024, 6, 23).unwrap());
    }

    #[test]
    fn test_week_boundaries_wednesday() {
        let wednesday = NaiveDate::from_ymd_opt(2024, 6, 19).unwrap();
        let (start, end) = get_week_boundaries(Some(wednesday));
        assert_eq!(start, NaiveDate::from_ymd_opt(2024, 6, 17).unwrap());
        assert_eq!(end, NaiveDate::from_ymd_opt(2024, 6, 23).unwrap());
    }

    #[test]
    fn test_completion_rate_empty() {
        let (completed, total, rate) = calculate_completion_rate(
            &[],
            NaiveDate::from_ymd_opt(2024, 6, 10).unwrap(),
            NaiveDate::from_ymd_opt(2024, 6, 16).unwrap(),
        );
        assert_eq!(completed, 0);
        assert_eq!(total, 7);
        assert!((rate - 0.0).abs() < 0.01);
    }

    #[test]
    fn test_completion_rate_full() {
        let dates = vec![
            "2024-06-10".to_string(),
            "2024-06-11".to_string(),
            "2024-06-12".to_string(),
            "2024-06-13".to_string(),
            "2024-06-14".to_string(),
            "2024-06-15".to_string(),
            "2024-06-16".to_string(),
        ];
        let (completed, total, rate) = calculate_completion_rate(
            &dates,
            NaiveDate::from_ymd_opt(2024, 6, 10).unwrap(),
            NaiveDate::from_ymd_opt(2024, 6, 16).unwrap(),
        );
        assert_eq!(completed, 7);
        assert_eq!(total, 7);
        assert!((rate - 100.0).abs() < 0.01);
    }

    #[test]
    fn test_completion_rate_partial() {
        let dates = vec![
            "2024-06-10".to_string(),
            "2024-06-12".to_string(),
            "2024-06-14".to_string(),
        ];
        let (completed, total, rate) = calculate_completion_rate(
            &dates,
            NaiveDate::from_ymd_opt(2024, 6, 10).unwrap(),
            NaiveDate::from_ymd_opt(2024, 6, 16).unwrap(),
        );
        assert_eq!(completed, 3);
        assert_eq!(total, 7);
        assert!((rate - 42.857).abs() < 0.01);
    }

    #[test]
    fn test_completion_rate_excludes_outside_dates() {
        let dates = vec![
            "2024-06-08".to_string(),
            "2024-06-10".to_string(),
            "2024-06-12".to_string(),
            "2024-06-18".to_string(),
        ];
        let (completed, total, _) = calculate_completion_rate(
            &dates,
            NaiveDate::from_ymd_opt(2024, 6, 10).unwrap(),
            NaiveDate::from_ymd_opt(2024, 6, 16).unwrap(),
        );
        assert_eq!(completed, 2);
        assert_eq!(total, 7);
    }

    #[test]
    fn test_completion_rate_single_day() {
        let dates = vec!["2024-06-15".to_string()];
        let (completed, total, rate) = calculate_completion_rate(
            &dates,
            NaiveDate::from_ymd_opt(2024, 6, 15).unwrap(),
            NaiveDate::from_ymd_opt(2024, 6, 15).unwrap(),
        );
        assert_eq!(completed, 1);
        assert_eq!(total, 1);
        assert!((rate - 100.0).abs() < 0.01);
    }
}
