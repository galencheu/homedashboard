# Home Dashboard 🏡

A unified home dashboard combining Google Calendar with real-time Caltrain departure information in a single Streamlit application.

## Features

- **Google Calendar Integration**: View today's events in a clean, compact format
- **Caltrain Real-time Data**: Live departure information from the 511 API
- **Scheduled Fallback**: Automatically switches to scheduled data if live API is unavailable
- **Single-page Layout**: Calendar on the left, Caltrain on the right
- **Configurable Settings**: Choose origin/destination stations and toggle between live/scheduled modes

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure Google Calendar (optional):
   - Follow the instructions in `SETUP.md` to set up Google Calendar OAuth
   - Place `credentials.json` in the project directory

3. Configure Caltrain API:
   - Add your 511 API key to `.streamlit/secrets.toml`:
     ```toml
     511_key = "your_api_key_here"
     ```

4. Run the app:
   ```bash
   streamlit run app.py
   ```

5. Open `http://localhost:8501` in your browser

## Documentation

See `SETUP.md` for detailed setup instructions.

## Architecture

This unified application combines:
- The calendar functionality from the original home-dashboard prototype
- The Caltrain monitoring logic from caltrainmonitor (now integrated natively, no iframe)

Both features now run in a single Streamlit process with shared state and caching.
