import os
import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, date, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Emojis
DONE_EMOJI = "✅"
STREAK_EMOJI = "🔥"
MISS_EMOJI = "❌"

def get_connection():
    # Authenticate with Google Sheets using st.secrets
    creds_dict = st.secrets["google"]["credentials"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(creds)
    sheet_id = st.secrets["google"]["sheet_id"]
    sheet = client.open_by_key(sheet_id).sheet1  # Access the first sheet
    return sheet

def load_data_db(sheet):
    """Load all habit data from Google Sheet."""
    try:
        records = sheet.get_all_records()
        habits = {}
        for record in records:
            habit = record["Habit"]
            date_obj = datetime.strptime(record["Date"], '%d/%m/%Y').date()
            completed = record["Completed"] == 'True'
            if habit not in habits:
                habits[habit] = []
            habits[habit].append((date_obj, completed))
        return habits
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return {}

def save_data_db(sheet, habits):
    """Save all habit data to Google Sheet."""
    try:
        sheet.clear()
        sheet.append_row(["Date", "Habit", "Completed"])
        for habit, records in habits.items():
            for date_obj, completed in records:
                date_str = date_obj.strftime('%d/%m/%Y')
                sheet.append_row([date_str, habit, str(completed)])
    except Exception as e:
        st.error(f"Error saving to sheet: {e}")

def get_days_in_month(month_num, year):
    """Return number of days in month."""
    return calendar.monthrange(year, month_num)[1]

def get_habit_df_for_month(habits, habit_name, month_num, year):
    """Get DataFrame for a habit's data in a specific month."""
    days = get_days_in_month(month_num, year)
    dates_list = [date(year, month_num, day) for day in range(1, days + 1)]
    
    records = habits.get(habit_name, [])
    data_dict = {d: False for d in dates_list}
    for d, completed in records:
        if d in data_dict:
            data_dict[d] = completed
    
    df_data = {
        "தேதி": [d.strftime('%d/%m/%Y') for d in dates_list],
        "நிறைவு": [DONE_EMOJI if data_dict[d] else MISS_EMOJI for d in dates_list]
    }
    return pd.DataFrame(df_data)

def update_habit_from_df(habits, habit_name, df, month_num, year):
    """Update habits dict from edited DataFrame."""
    days = get_days_in_month(month_num, year)
    dates_list = [date(year, month_num, day) for day in range(1, days + 1)]
    
    if habit_name not in habits:
        habits[habit_name] = []
    
    for i, d in enumerate(dates_list):
        completed = df.loc[i, "நிறைவு"] == DONE_EMOJI
        # Remove existing entry for this date
        habits[habit_name] = [(dt, comp) for dt, comp in habits[habit_name] if dt != d]
        # Add updated entry
        habits[habit_name].append((d, completed))

def calculate_streak(records):
    today = date.today()
    streak = 0
    sorted_records = sorted(records, key=lambda x: x[0], reverse=True)
    for dt, completed in sorted_records:
        if completed and dt == today - timedelta(days=streak):
            streak += 1
        elif not completed and dt == today - timedelta(days=streak):
            break
        else:
            break
    return streak

def app():
    st.set_page_config(page_title="Habit Streak Tracker", page_icon="🔥", layout="wide")
    st.title("🔥 Habit Streak Tracker 🔥")
    st.markdown("Track your daily habits and build streaks! Data is saved to Google Sheets.")
    
    sheet = get_connection()
    habits = load_data_db(sheet)
    
    # Sidebar for adding habits
    st.sidebar.header("Add New Habit")
    new_habit = st.sidebar.text_input("Habit Name")
    if st.sidebar.button("Add Habit"):
        if new_habit and new_habit not in habits:
            habits[new_habit] = []
            st.sidebar.success(f"Added habit: {new_habit}")
        elif new_habit in habits:
            st.sidebar.warning("Habit already exists!")
        else:
            st.sidebar.error("Please enter a habit name.")
    
    # Get current month and year
    now = datetime.now()
    current_month_num = now.month
    current_year = now.year
    
    # Month dropdown
    month_names = [calendar.month_name[i] for i in range(1, 13)]
    selected_month_name = st.selectbox(
        "Select Month for Editing:",
        options=month_names,
        index=current_month_num - 1
    )
    selected_month_num = month_names.index(selected_month_name) + 1
    
    # Year input
    selected_year = st.number_input(
        "Select Year:",
        min_value=2000,
        max_value=2100,
        value=current_year,
        step=1
    )
    
    st.write(f"**Editing data for: {selected_month_name} {selected_year}**")
    
    # Main content
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.header("Today's Check-In")
        today = date.today()
        for habit in habits:
            st.subheader(f"{habit}")
            completed = st.checkbox(f"Mark as done {DONE_EMOJI}", key=habit)
            if completed:
                # Add today's completion if not already present
                records = habits[habit]
                if not any(dt == today for dt, _ in records):
                    records.append((today, True))
                st.success(f"Great job! {STREAK_EMOJI} Streak: {calculate_streak(records)}")
            else:
                # Ensure today's record exists as not completed
                records = habits[habit]
                if not any(dt == today for dt, _ in records):
                    records.append((today, False))
                streak = calculate_streak(records)
                if streak > 0:
                    st.info(f"Keep it up! {STREAK_EMOJI} Streak: {streak}")
                else:
                    st.warning(f"No streak yet. {MISS_EMOJI}")
    
    with col2:
        st.header("Edit Past Month Completions")
        if habits:
            selected_habit = st.selectbox("Select Habit to Edit", list(habits.keys()))
            df = get_habit_df_for_month(habits, selected_habit, selected_month_num, selected_year)
            
            if 'editor_key' not in st.session_state:
                st.session_state.editor_key = 0
            
            edited_df = st.data_editor(
                df,
                column_config={
                    "தேதி": st.column_config.TextColumn("தேதி (dd/mm/yyyy)", disabled=True),
                    "நிறைவு": st.column_config.SelectboxColumn("நிறைவு", options=[DONE_EMOJI, MISS_EMOJI]),
                },
                hide_index=True,
                num_rows="fixed",
                key=f"editor_{st.session_state.editor_key}"
            )
            
            if st.button("Update Past Data"):
                update_habit_from_df(habits, selected_habit, edited_df, selected_month_num, selected_year)
                st.success("Past data updated!")
                st.session_state.editor_key += 1  # Refresh editor
        else:
            st.write("No habits added yet.")
    
    # Save data
    if st.button("Save All Progress"):
        save_data_db(sheet, habits)
        st.success("All data saved to Google Sheets!")

if __name__ == "__main__":
    app()
