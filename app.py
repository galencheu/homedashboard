from __future__ import annotations

import datetime as dt
import html
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytz
import requests
import streamlit as st
from geopy.distance import geodesic
from streamlit_autorefresh import st_autorefresh

BASE_DIR = Path(__file__).resolve().parent
PACIFIC = ZoneInfo("America/Los_Angeles")

from functions.ct_functions import (
    get_schedule,
    assign_train_type,
    is_northbound,
)

st.set_page_config(page_title="Home Dashboard", page_icon="🏡", layout="wide", initial_sidebar_state="collapsed")

# ---------- Styling ----------
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: Inter, sans-serif; }
  .stApp { background: #0b1220; color: #e8eef8; }
  [data-testid="stHeader"] { background: rgba(11,18,32,0); }
  .block-container { padding-top: 1rem; padding-bottom: .5rem; max-width: 1800px; }
  .dash-header { display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:18px 22px; margin-bottom:14px; border:1px solid #25344b; border-radius:16px; background:linear-gradient(120deg,#182941,#111d30); }
  .dash-title { font-size:26px; font-weight:700; color:#f4f7fc; }
  .dash-subtitle { color:#aebbd0; font-size:13px; margin-top:3px; }
  .clock { font-size:27px; font-weight:700; text-align:right; color:#fff; }
  .clock-date { color:#aebbd0; font-size:12px; text-align:right; }
  .panel-title { font-size:20px; font-weight:700; margin:2px 0 10px 0; color:#f4f7fc; }
  .panel-subtitle { font-size:11px; font-weight:600; letter-spacing:.09em; color:#91a4c0; margin-bottom:10px; }
  .panel { background:#111d30; border:1px solid #263750; border-radius:15px; padding:17px; min-height:540px; }
  .event { display:grid; grid-template-columns:100px 5px 1fr; gap:11px; padding:12px 0; border-bottom:1px solid #24334a; }
  .event:last-child { border-bottom:none; }
  .event-time { font-size:15px; color:#9fb0c8; padding-top:2px; font-weight:500; }
  .event-bar { border-radius:5px; background:#60a5fa; }
  .event-name { font-size:14px; font-weight:600; color:#eef4ff; overflow-wrap:anywhere; }
  .event-meta { font-size:11px; color:#9fb0c8; margin-top:4px; }
  .event.next-event { padding:18px 0; background:rgba(96,165,250,0.08); border-radius:8px; margin-bottom:8px; border:1px solid rgba(96,165,250,0.3); }
  .event.next-event .event-time { font-size:18px; font-weight:600; color:#fff; }
  .event.next-event .event-name { font-size:18px; font-weight:700; }
  .event.next-event .event-meta { font-size:13px; }
  .empty { padding:18px; border:1px dashed #33445d; border-radius:10px; color:#9fb0c8; font-size:13px; }
  iframe { border:0; border-radius:10px; }
  [data-testid="stAlert"] { border-radius:10px; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource(ttl="300s")
def get_calendar_list():
    """Fetch list of available calendars using Google Calendar OAuth credentials."""
    credentials_path = BASE_DIR / "credentials.json"
    token_path = BASE_DIR / "token.json"
    if not credentials_path.exists():
        return []

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
        creds = Credentials.from_authorized_user_file(str(token_path), scopes) if token_path.exists() else None
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
            creds = flow.run_local_server(port=0, open_browser=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")

        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        result = service.calendarList().list().execute()
        return result.get("items", [])
    except Exception:
        return []


def get_calendar_events(calendar_ids=None):
    """Fetch today's events using Google Calendar OAuth credentials, if configured."""
    credentials_path = BASE_DIR / "credentials.json"
    token_path = BASE_DIR / "token.json"
    if not credentials_path.exists():
        return None, "Google Calendar is not configured yet. Follow SETUP.md to enable the Calendar API and add credentials.json."

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
        creds = Credentials.from_authorized_user_file(str(token_path), scopes) if token_path.exists() else None
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
            creds = flow.run_local_server(port=0, open_browser=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")

        now = dt.datetime.now(PACIFIC)
        start = now
        end = now + dt.timedelta(days=7)
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        
        all_events = []
        
        # Use provided calendar IDs or default to primary
        calendars_to_fetch = calendar_ids if calendar_ids else ["primary"]
        
        for calendar_id in calendars_to_fetch:
            result = service.events().list(
                calendarId=calendar_id, timeMin=start.isoformat(), timeMax=end.isoformat(),
                maxResults=50, singleEvents=True, orderBy="startTime"
            ).execute()
            all_events.extend(result.get("items", []))
        
        return all_events, None
    except Exception as exc:
        return None, f"Could not load Google Calendar: {exc}"


def event_time(event):
    start = event.get("start", {})
    end = event.get("end", {})
    if "dateTime" not in start:
        return "All day", "All day"
    start_dt = dt.datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00")).astimezone(PACIFIC)
    end_value = end.get("dateTime")
    end_dt = dt.datetime.fromisoformat(end_value.replace("Z", "+00:00")).astimezone(PACIFIC) if end_value else start_dt
    return start_dt.strftime("%-I:%M %p"), end_dt.strftime("%-I:%M %p")


# ---------- Caltrain Functions ----------
@st.cache_resource(ttl="60s")
def ping_train() -> dict:
    url = f"https://api.511.org/transit/VehicleMonitoring?api_key={st.secrets['511_key']}&agency=CT"
    response = requests.get(url)
    if response.status_code != 200:
        return False

    decoded_content = response.content.decode("utf-8-sig")
    data = json.loads(decoded_content)

    if data["Siri"]["ServiceDelivery"]["VehicleMonitoringDelivery"].get("VehicleActivity") is None:
        return False
    return data


def create_caltrain_dfs(data: dict) -> pd.DataFrame:
    trains = []

    for train in data["Siri"]["ServiceDelivery"]["VehicleMonitoringDelivery"]["VehicleActivity"]:
        train_obj = train["MonitoredVehicleJourney"]

        if train_obj.get("OnwardCalls") is None:
            continue

        next_stop_df = pd.DataFrame(
            [
                [
                    train_obj["MonitoredCall"]["StopPointName"],
                    train_obj["MonitoredCall"]["StopPointRef"],
                    train_obj["MonitoredCall"]["AimedArrivalTime"],
                    train_obj["MonitoredCall"]["ExpectedArrivalTime"],
                    train_obj["MonitoredCall"]["AimedDepartureTime"],
                ]
            ],
            columns=["stop_name", "stop_id", "aimed_arrival_time",
                     "expected_arrival_time", "AimedDepartureTime"],
        )

        destinations_df = pd.DataFrame(
            [
                [
                    stop["StopPointName"],
                    stop["StopPointRef"],
                    stop["AimedArrivalTime"],
                    stop["ExpectedArrivalTime"],
                    stop["AimedDepartureTime"]
                ]
                for stop in train_obj["OnwardCalls"]["OnwardCall"]
            ],
            columns=["stop_name", "stop_id", "aimed_arrival_time",
                     "expected_arrival_time", "AimedDepartureTime"],
        )

        destinations_df = pd.concat([next_stop_df, destinations_df])
        destinations_df["id"] = train_obj["VehicleRef"]
        destinations_df["origin"] = train_obj["OriginName"]
        destinations_df["origin_id"] = train_obj["OriginRef"]
        destinations_df["direction"] = train_obj["DirectionRef"] + "B"
        destinations_df["line_type"] = train_obj["PublishedLineName"]
        destinations_df["destination"] = train_obj["DestinationName"]
        destinations_df["train_longitude"] = train_obj["VehicleLocation"]["Longitude"]
        destinations_df["train_latitude"] = train_obj["VehicleLocation"]["Latitude"]
        destinations_df["stops_away"] = destinations_df.index

        trains.append(destinations_df)

    trains_df = pd.concat(trains)

    trains_df["aimed_arrival_time"] = pd.to_datetime(trains_df["aimed_arrival_time"])
    trains_df["expected_arrival_time"] = pd.to_datetime(trains_df["expected_arrival_time"])
    trains_df["AimedDepartureTime"] = pd.to_datetime(trains_df["AimedDepartureTime"])
    trains_df["train_longitude"] = trains_df["train_longitude"].astype(float)
    trains_df["train_latitude"] = trains_df["train_latitude"].astype(float)
    trains_df["stop_id"] = trains_df["stop_id"].astype(float)
    trains_df["origin_id"] = trains_df["origin_id"].astype(float)

    stop_ids = pd.read_csv(str(BASE_DIR / "stop_ids.csv"))

    sb_trains_df = pd.merge(trains_df, stop_ids, left_on="stop_id",
                            right_on="stop1", how="inner")
    nb_trains_df = pd.merge(trains_df, stop_ids, left_on="stop_id",
                            right_on="stop2", how="inner")
    trains_df = pd.concat([sb_trains_df, nb_trains_df])

    trains_df["distance"] = trains_df.apply(
        lambda x: geodesic((x["train_latitude"], x["train_longitude"]),
                           (x["lat"], x["lon"])).miles,
        axis=1,
    )
    trains_df["distance"] = trains_df["distance"].round(1).astype("str") + " mi"

    trains_df["Departure Time"] = trains_df["expected_arrival_time"]
    trains_df["Scheduled Time"] = trains_df["aimed_arrival_time"]
    trains_df["Current Time"] = dt.datetime.now(pytz.timezone("UTC"))
    trains_df["ETA"] = trains_df["Departure Time"] - trains_df["Current Time"]
    trains_df["ScheduledETA"] = trains_df["Scheduled Time"] - trains_df["Current Time"]
    trains_df["AimedDepartureTimeETA"] = trains_df["AimedDepartureTime"] - trains_df["Current Time"]

    trains_df["Train #"] = trains_df["id"]
    trains_df["Direction"] = trains_df["direction"]

    return trains_df


def clean_up_df(data: pd.DataFrame) -> pd.DataFrame:
    data["ETA"] = data["ETA"].apply(lambda x: int(x.total_seconds() / 60))
    data["ETA_COMPARE"] = data["ETA"]
    data["ETA"] = data["ETA"].astype(str) + " min"

    data["ScheduledETA"] = data["ScheduledETA"].apply(lambda x: int(x.total_seconds() / 60))
    data["ScheduledETA_COMPARE"] = data["ScheduledETA"]
    data["delayed"] = np.where(data["ETA_COMPARE"] > data["ScheduledETA_COMPARE"] + 1,
                               '!!!!!--  I SLOW  --!!!!!', '')
    data["ScheduledETA"] = data["ScheduledETA"].astype(str) + " min"

    data["AimedDepartureTimeETA"] = data["AimedDepartureTimeETA"].apply(
        lambda x: int(x.total_seconds() / 60))
    data["AimedDepartureTimeETA"] = data["AimedDepartureTimeETA"].astype(str) + " min"

    data["API Time"] = data.apply(
        lambda row: f"{row['Departure Time']} // Train in {row['ETA']}", axis=1)
    data["Scheduled Time"] = data.apply(
        lambda row: f"{row['Departure Time']} // Train in {row['ScheduledETA']}", axis=1)
    data["AimedDepartureTime"] = data.apply(
        lambda row: f"{row['AimedDepartureTime']} // Train in {row['AimedDepartureTimeETA']}", axis=1)

    data = data[["Train #", "API Time", "AimedDepartureTime", "delayed", "stopsaway2"]]
    data.columns = ["Train #", "API Arrival", "Scheduled Depature", "Delayed", "Stops Away"]

    data = data.T
    data.columns = data.iloc[0]
    data = data.drop(data.index[0])
    return data


now = dt.datetime.now(PACIFIC)
# Initialize session state for calendar selection
if "selected_calendars" not in st.session_state:
    st.session_state.selected_calendars = ["primary"]

if "auto_refresh_interval" not in st.session_state:
    st.session_state.auto_refresh_interval = 60  # Default 60 seconds (1 minute)

now = dt.datetime.now(PACIFIC)
time_text = now.strftime("%I:%M %p").lstrip("0")

# ---------- Settings in Modal ----------
with st.expander("⚙️ Settings", expanded=False):
    st.markdown("### Caltrain Settings")
    caltrain_stations = pd.read_csv(str(BASE_DIR / "stop_ids.csv"))
    chosen_station = st.selectbox("Choose Origin Station",
                                  caltrain_stations["stopname"], index=8)

    chosen_destination = st.selectbox("Choose Destination Station",
                                      ["--"] + caltrain_stations["stopname"].tolist(),
                                      index=0)

    display = st.radio(
        "Show trains",
        ["Live", "Scheduled"],
        horizontal=True,
        help="Live shows only trains that have already left the station",
    )
    
    st.markdown("### Calendar Settings")
    calendar_mode = st.radio(
        "Calendar source",
        ["Primary only", "Select calendars"],
        horizontal=True,
        help="Choose which calendars to display events from",
    )
    
    if calendar_mode == "Select calendars":
        with st.spinner("Loading calendars..."):
            calendars = get_calendar_list()
        if calendars:
            calendar_options = {cal["id"]: cal["summary"] for cal in calendars}
            # Filter default to only include valid calendar IDs
            valid_defaults = [cal_id for cal_id in st.session_state.selected_calendars if cal_id in calendar_options]
            if not valid_defaults:
                valid_defaults = [list(calendar_options.keys())[0]] if calendar_options else ["primary"]
            st.session_state.selected_calendars = st.multiselect(
                "Select calendars to display",
                options=list(calendar_options.keys()),
                format_func=lambda x: calendar_options.get(x, x),
                default=valid_defaults,
            )
        else:
            st.warning("Could not load calendar list. Using primary calendar.")
            st.session_state.selected_calendars = ["primary"]
    else:
        st.session_state.selected_calendars = ["primary"]
    
    st.markdown("---")
    st.markdown("### General Settings")
    st.session_state.auto_refresh_interval = st.number_input(
        "Auto-refresh interval (seconds)",
        min_value=10,
        max_value=300,
        value=st.session_state.auto_refresh_interval,
        step=10,
        help="Automatically refresh calendar and train data every N seconds"
    )
    
    if st.button("🔄 Refresh Now", use_container_width=True):
        st.rerun()

# Set up auto-refresh
st_autorefresh(interval=st.session_state.auto_refresh_interval * 1000, key="data_refresh")

left, right = st.columns([1.15, 1], gap="medium")
with left:
    st.markdown('<div class="panel-title">▦ Upcoming Events</div><div class="panel-subtitle">GOOGLE CALENDAR · LOCAL TIME</div>', unsafe_allow_html=True)
    with st.spinner("Loading calendar…"):
        events, error = get_calendar_events(st.session_state.selected_calendars)
    if error:
        st.warning(error)
        st.caption("Calendar events will appear here after setup. Your transit panel can still run independently.")
    elif not events:
        st.markdown('<div class="empty">Nothing scheduled in the next week. Enjoy the breathing room.</div>', unsafe_allow_html=True)
    else:
        # Filter to show only upcoming events in the next week
        now = dt.datetime.now(PACIFIC)
        week_later = now + dt.timedelta(days=7)
        upcoming_events = []
        all_day_events = []
        for event in events:
            start = event.get("start", {})
            if "dateTime" in start:
                event_start = dt.datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00")).astimezone(PACIFIC)
                if now <= event_start <= week_later:
                    upcoming_events.append((event_start, event))
            else:
                # All-day events - collect separately
                all_day_events.append(event)
        
        # Sort by start time
        upcoming_events.sort(key=lambda x: x[0])
        
        event_html = []
        
        # Add consolidated all-day events as a single entry
        if all_day_events:
            all_day_titles = [html.escape(e.get("summary", "Untitled")) for e in all_day_events]
            all_day_text = ", ".join(all_day_titles)
            color = "#60a5fa"
            event_html.append(f'<div class="event"><div class="event-time">All day</div><div class="event-bar" style="background:{color}"></div><div><div class="event-name">All-day events</div><div class="event-meta">{all_day_text}</div></div></div>')
        
        # Add timed events with date and time
        first_start_time = None
        for i, (event_start, event) in enumerate(upcoming_events):
            start_text, end_text = event_time(event)
            # Add date to time display
            date_str = event_start.strftime("%b %d")
            full_time_text = f"{date_str} · {start_text}"
            title = html.escape(event.get("summary", "Untitled event"))
            location = html.escape(event.get("location", ""))
            description = f"{full_time_text} – {end_text}" if start_text != "All day" else "All day event"
            if location:
                description += " · " + location
            color = ["#34d399", "#a78bfa", "#fbbf24", "#f472b6", "#60a5fa"][i % 5]
            
            # Mark all events with the same start time as next events
            if start_text != "All day":
                if first_start_time is None:
                    first_start_time = event_start
                is_next_event = event_start == first_start_time
            else:
                is_next_event = False
            
            event_class = "event next-event" if is_next_event else "event"
            
            event_html.append(f'<div class="{event_class}"><div class="event-time">{html.escape(full_time_text)}</div><div class="event-bar" style="background:{color}"></div><div><div class="event-name">{title}</div><div class="event-meta">{html.escape(description)}</div></div></div>')
        st.markdown("".join(event_html), unsafe_allow_html=True)
    st.caption("Calendar data is read-only. Manage or edit events in Google Calendar.")

with right:
    st.markdown('<div class="panel-subtitle">LIVE GTFS / 511 DATA</div>', unsafe_allow_html=True)

    # Fetch API data
    API_RESPONSE_DATA = ping_train()

    if display == "Scheduled":
        st.warning("📆 Pulling the current schedule from the Caltrain website...")

        if chosen_destination != "--" and chosen_destination != chosen_station:
            if is_northbound(chosen_station, chosen_destination):
                caltrain_data = get_schedule("northbound", chosen_station, chosen_destination)
            else:
                caltrain_data = get_schedule("southbound", chosen_station, chosen_destination)
        else:
            caltrain_data = pd.concat([
                get_schedule("northbound", chosen_station, chosen_destination),
                get_schedule("southbound", chosen_station, chosen_destination)
            ])

        caltrain_data = caltrain_data.sort_values(by=["ETA"])
        caltrain_data["Train #"] = caltrain_data["Train #"].map(
            lambda c: f"{assign_train_type(c)}-{c}")

        # NORTHBOUND
        st.subheader(f"Northbound Trains - {time_text}")
        nb_data = caltrain_data.query("Direction == 'NB'").drop("Direction", axis=1)
        nb_data = nb_data.T
        nb_data.columns = nb_data.iloc[0]
        st.dataframe(nb_data.drop(nb_data.index[0]), use_container_width=True)

        # SOUTHBOUND
        st.subheader(f"Southbound Trains - {time_text}")
        sb_data = caltrain_data.query("Direction == 'SB'").drop("Direction", axis=1)
        sb_data = sb_data.T
        sb_data.columns = sb_data.iloc[0]
        st.dataframe(sb_data.drop(sb_data.index[0]), use_container_width=True)

    else:
        if API_RESPONSE_DATA is False:
            st.error("❌ Unable to fetch live Caltrain data. API may be down.")
        else:
            api_live_responsetime = API_RESPONSE_DATA["Siri"]["ServiceDelivery"]["ResponseTimestamp"]
            api_live_responsetime_dt = dt.datetime.strptime(api_live_responsetime, '%Y-%m-%dT%H:%M:%SZ') \
                .replace(tzinfo=pytz.utc) \
                .astimezone(pytz.timezone('US/Pacific'))
            api_live_responsetime = api_live_responsetime_dt.strftime('%I:%M %p')

            current_time_dt = dt.datetime.now(pytz.timezone("US/Pacific"))
            api_hi_time = current_time_dt + dt.timedelta(seconds=90)
            api_lo_time = current_time_dt - dt.timedelta(seconds=90)

            if api_live_responsetime_dt < api_hi_time and api_live_responsetime_dt > api_lo_time:
                st.info(f"✅ Caltrain API is up 🚂 (API Time: {api_live_responsetime})")
            else:
                st.error(f"❌ Caltrain API Time is off by {api_live_responsetime_dt - current_time_dt} minutes")

            caltrain_data = create_caltrain_dfs(API_RESPONSE_DATA)
            caltrain_data["Train Type"] = caltrain_data["Train #"].apply(assign_train_type)
            caltrain_data["Train #"] = caltrain_data["Train #"].map(
                lambda c: f"{assign_train_type(c)}-{c}")

            caltrain_data["Departure Time"] = pd.to_datetime(
                caltrain_data["Departure Time"]).dt.tz_convert("US/Pacific").dt.strftime("%I:%M %p")
            caltrain_data["Scheduled Time"] = pd.to_datetime(
                caltrain_data["Scheduled Time"]).dt.tz_convert("US/Pacific").dt.strftime("%I:%M %p")
            caltrain_data["AimedDepartureTime"] = pd.to_datetime(
                caltrain_data["AimedDepartureTime"]).dt.tz_convert("US/Pacific").dt.strftime("%I:%M %p")

            caltrain_data = caltrain_data.reset_index(drop=True)

            idx = (caltrain_data
                   .sort_values(["id", "aimed_arrival_time"])
                   .groupby("id")
                   .head(1)
                   .index)

            first_stops = caltrain_data.loc[idx, ["id", "stop_name"]].drop_duplicates().set_index("id")["stop_name"]
            caltrain_data["stopsaway2"] = caltrain_data["id"].map(first_stops)
            caltrain_data["stopsaway2"] = caltrain_data["stopsaway2"].astype(str).str.replace(
                r'\s*Caltrain Station\s+(Northbound|Southbound)\s*$',
                '', regex=True
            ).str.strip()
            caltrain_data["stopsaway2"] = (
                caltrain_data["stops_away"].astype(str)
                + " // " + caltrain_data["stopsaway2"]
                + " // " + caltrain_data["distance"]
            )

            valid_destinations = ["San Francisco", "Tamien", "San Jose Diridon"]

            if chosen_destination not in ["--"] + valid_destinations:
                dest_ids = caltrain_data[caltrain_data["stopname"] == chosen_destination]["id"]
                caltrain_data = caltrain_data[caltrain_data["id"].isin(dest_ids)]

            if chosen_destination != "--" and chosen_destination != chosen_station:
                if is_northbound(chosen_station, chosen_destination):
                    caltrain_data = caltrain_data.query("direction == 'NB'")
                else:
                    caltrain_data = caltrain_data.query("direction == 'SB'")

            # NORTHBOUND
            st.subheader(f"Northbound Trains - {time_text}")
            nb_trains = caltrain_data.query("Direction == 'NB'").drop("Direction", axis=1)
            nb_trains = nb_trains[nb_trains["stopname"] == chosen_station].sort_values("ETA")

            if nb_trains.empty:
                st.info("No trains northbound.")
            else:
                st.dataframe(clean_up_df(nb_trains), use_container_width=True)

            # SOUTHBOUND
            st.subheader(f"Southbound Trains - {time_text}")
            sb_trains = caltrain_data.query("direction == 'SB'").drop("direction", axis=1)
            sb_trains = sb_trains[sb_trains["stopname"] == chosen_station].sort_values("ETA")

            if sb_trains.empty:
                st.info("No trains southbound.")
            else:
                st.dataframe(clean_up_df(sb_trains), use_container_width=True)

st.markdown("<div style='text-align:center;color:#64748b;font-size:11px;margin-top:12px'>Local dashboard · Calendar refreshes when the page reruns · Transit refresh follows your existing app</div>", unsafe_allow_html=True)
