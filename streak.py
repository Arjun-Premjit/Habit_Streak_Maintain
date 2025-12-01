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
  """Authenticate and connect to Google Sheets."""
  try:
    creds_dict = {
        "type": st.secrets["google"]["type"],
        "project_id": st.secrets["google"]["project_id"],
        "private_key_id": st.secrets["google"]["private_key_id"],
        "private_key": st.secrets["google"]["private_key"],
        "client_email": st.secrets["google"]["client_email"],
        "client_id": st.secrets["google"]["client_id"],
        "auth_uri": st.secrets["google"]["auth_uri"],
        "token_uri": st.secrets["google"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["google"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["google"]["client_x509_cert_url"],
        "universe_domain": st.secrets["google"]["universe_domain"]
    }
    creds = Credentials.from_service_account_info(creds_dict, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(creds)
    sheet_id = st.secrets["google"]["sheet_id"]
    sheet = client.open_by_key(sheet_id).sheet1  # Access the first sheet
    return sheet
  except Exception as e:
    st.error(f"Connection error: {e}. Verify your Google service account and sheet permissions.")
    return None
def initialize_sheet(sheet):
    """Initialize sheet with headers if empty."""
    try:
        records = sheet.get_all_records()
        if not records:
            sheet.append_row(["Date", "Habit", "Completed"])
    except:
        sheet.append_row(["Date", "Habit", "Completed"])

def load_data_db(sheet):
    """Load all habit data from Google Sheet."""
    try:
        initialize_sheet(sheet)
        records = sheet.get_all_records()
        habits = {}
        for record in records:
            habit = record.get("Habit", "")
            if not habit:
                continue
            date_obj = datetime.strptime(record["Date"], '%d/%m/%Y').date()
            completed = record.get("Completed", "False") == 'True'
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
    return calendar.monthrange(year, month_num)[1]

def display_calendar(habits, habit_name, month_num, year):
    """Display interactive calendar for the month."""
    days = get_days_in_month(month_num, year)
    records = habits.get(habit_name, [])
    data_dict = {d: False for d in range(1, days + 1)}
    for dt, completed in records:
        if dt.month == month_num and dt.year == year:
            data_dict[dt.day] = completed
    
    # Calendar layout
    st.subheader(f"📅 {calendar.month_name[month_num]} {year} - {habit_name}")
    
    # Weekday headers
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    cols = st.columns(7)
    for i, wd in enumerate(weekdays):
        cols[i].markdown(f"**{wd}**")
    
    # First day of month
    first_day = date(year, month_num, 1)
    start_weekday = first_day.weekday()  # 0=Monday
    
    # Buttons for days
    day = 1
    for week in range(6):  # Max 6 weeks
        cols = st.columns(7)
        for wd in range(7):
            if week == 0 and wd < start_weekday:
                cols[wd].write("")  # Empty
            elif day > days:
                cols[wd].write("")  # Empty
            else:
                completed = data_dict[day]
                emoji = DONE_EMOJI if completed else MISS_EMOJI
                color = "green" if completed else "red"
                if cols[wd].button(f"{day} {emoji}", key=f"{habit_name}_{month_num}_{year}_{day}"):
                    # Toggle completion
                    data_dict[day] = not completed
                    # Update habits
                    dt = date(year, month_num, day)
                    habits[habit_name] = [(d, c) for d, c in habits[habit_name] if d != dt]
                    habits[habit_name].append((dt, data_dict[day]))
                    st.rerun()  # Refresh to update display
                day += 1
        if day > days:
            break
    
    # Progress bar
    completed_days = sum(data_dict.values())
    progress = completed_days / days
    st.progress(progress)
    st.write(f"**Progress: {completed_days}/{days} days completed ({progress*100:.1f}%)**")

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
    st.sidebar.header("➕ Add New Habit")
    new_habit = st.sidebar.text_input("Habit Name")
    if st.sidebar.button("Add Habit"):
        if new_habit and new_habit not in habits:
            habits[new_habit] = []
            st.sidebar.success(f"Added habit: {new_habit}")
        elif new_habit in habits:
            st.sidebar.warning("Habit already exists!")
        else:
            st.sidebar.error("Please enter a habit name.")
    
    # Month/Year selection
    now = datetime.now()
    current_month_num = now.month
    current_year = now.year
    
    month_names = [calendar.month_name[i] for i in range(1, 13)]
    selected_month_name = st.selectbox(
        "Select Month:",
        options=month_names,
        index=current_month_num - 1
    )
    selected_month_num = month_names.index(selected_month_name) + 1
    
    selected_year = st.number_input(
        "Select Year:",
        min_value=2000,
        max_value=2100,
        value=current_year,
        step=1
    )
    
    # Main content
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.header("📝 Today's Check-In")
        today = date.today()
        for habit in habits:
            st.subheader(f"🏃 {habit}")
            completed = st.checkbox(f"Mark as done {DONE_EMOJI}", key=habit)
            if completed:
                records = habits[habit]
                if not any(dt == today for dt, _ in records):
                    records.append((today, True))
                st.success(f"Great job! {STREAK_EMOJI} Streak: {calculate_streak(records)}")
            else:
                records = habits[habit]
                if not any(dt == today for dt, _ in records):
                    records.append((today, False))
                streak = calculate_streak(records)
                if streak > 0:
                    st.info(f"Keep it up! {STREAK_EMOJI} Streak: {streak}")
                else:
                    st.warning(f"No streak yet. {MISS_EMOJI}")
    
    with col2:
        st.header("🗓️ Edit Past Completions")
        if habits:
            selected_habit = st.selectbox("Select Habit", list(habits.keys()))
            display_calendar(habits, selected_habit, selected_month_num, selected_year)
        else:
            st.write("No habits added yet.")
    
    # Save data
    if st.button("💾 Save All Progress"):
        save_data_db(sheet, habits)
        st.success("All data saved to Google Sheets!")

if __name__ == "__main__":
    app()



