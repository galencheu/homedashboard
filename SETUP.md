# Unified Home Dashboard

This unified dashboard combines a custom-rendered Google Calendar agenda with Caltrain real-time and scheduled departure information in a landscape two-column interface.

## 1. Install

Use a fresh virtual environment:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 2. Google Calendar API setup

1. Open the Google Cloud Console: https://console.cloud.google.com/
2. Create or select a project and enable **Google Calendar API**.
3. Configure the OAuth consent screen for your account. For personal use, add your Google account as a test user if the app is in testing mode.
3.1. Then go to https://console.cloud.google.com/auth/audience and add the users to the Testers list as this is not a Google Verified app.
4. You need to enable to Google Calendar API for your Cloud Instance here: https://console.cloud.google.com/apis/library/calendar-json.googleapis.com
5. Create an OAuth client ID of type **Desktop app** and download its JSON file.
6. Save that file in this project folder as `credentials.json`.
7. Start the dashboard. The first calendar load will open a Google sign-in/consent flow and create `token.json` locally.
8. Keep `credentials.json` and `token.json` private. They are excluded from Git by `.gitignore`.

The app requests read-only access to your primary calendar and fetches today's events in the America/Los_Angeles time zone.

## 3. Configure Caltrain API

The app requires a 511 API key for live Caltrain data. Add it to `.streamlit/secrets.toml`:

```toml
511_key = "your_511_api_key_here"
```

The `secrets.toml` file is excluded from Git by `.gitignore`. Do not commit your API key.

## 4. Start the dashboard

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser. Avoid exposing the app to the public internet.

## 5. Using the app

- **Calendar panel (left)**: Shows today's events from your Google Calendar. Events are read-only; manage them in Google Calendar.
- **Caltrain panel (right)**: Shows live and scheduled train departures. Use the settings expander to choose your origin station, destination, and switch between live and scheduled modes.
- **Settings**: Click "⚙️ Caltrain Settings" to configure station preferences and display mode.

## Notes

- The app automatically switches between live 511 API data and scheduled Caltrain data if the API is unavailable.
- Live data refreshes every 60 seconds (cached).
- Calendar data refreshes when the page reruns.
- Keep `credentials.json` and `token.json` private. They are excluded from Git by `.gitignore`.
