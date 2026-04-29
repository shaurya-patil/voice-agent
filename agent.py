import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pytz
import re
import uvicorn

TASKS_FILE = "tasks.json"

load_dotenv()

client = ElevenLabs(api_key=os.getenv("ELVLABS_API_KEY"))
AGENT_ID = os.getenv("AGENT_ID")

SERVICE_ACCOUNT_FILE = "service_account.json"
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
SCOPES = ["https://www.googleapis.com/auth/calendar"]

app = FastAPI()


# ── Google Calendar service ───────────────────────────────────────────────────
def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds)


# ── Parse natural language time ───────────────────────────────────────────────
def parse_time(requested_time: str, timezone: str) -> datetime:
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    requested_time = requested_time.lower().strip()

    try:
        dt = datetime.fromisoformat(requested_time)
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        return dt
    except ValueError:
        pass

    if "tomorrow" in requested_time:
        base_date = now + timedelta(days=1)
    elif "today" in requested_time:
        base_date = now
    else:
        base_date = now + timedelta(days=1)

    time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', requested_time)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        meridiem = time_match.group(3)

        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

        return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

    raise ValueError(f"Could not parse time: {requested_time}")


# ── Task logging ──────────────────────────────────────────────────────────────
def log_task(task: str):
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r") as f:
            tasks = json.load(f)
    else:
        tasks = []

    tasks.append({
        "task": task,
        "logged_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
    })

    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

    print(f"[logged] {task}")


# ── Schedule call on Google Calendar ─────────────────────────────────────────
def schedule_call(name: str, email: str, requested_time: str, timezone: str, duration_minutes: int = 30):
    start_dt = parse_time(requested_time, timezone)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    service = get_calendar_service()

    event = {
        "summary": f"Call with {name}",
        "description": f"Rescheduled call via AI agent.\nUser: {name}\nEmail: {email}",
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": timezone,
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 30},
                {"method": "popup", "minutes": 10},
            ],
        },
    }

    created_event = service.events().insert(
        calendarId=CALENDAR_ID,
        body=event,
        sendUpdates="none"
    ).execute()

    return {
        "scheduled_time": start_dt.strftime("%B %d at %I:%M %p"),
        "timezone": timezone,
        "event_link": created_event.get("htmlLink")
    }


# ── Called by your frontend to start a session ────────────────────────────────
@app.get("/session")
def get_signed_url(timezone: str = "Asia/Kolkata"):
    tz = pytz.timezone(timezone)
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z")  # e.g. "2026-04-29 18:45 IST"

    response = client.conversational_ai.create_conversation_token(
        agent_id=AGENT_ID,
        dynamic_variables={"current_time": current_time, "timezone": timezone},
    )
    return {"signed_url": response.signed_url}


# ── Log Task tool endpoint ────────────────────────────────────────────────────
@app.post("/tool/log_task")
async def on_log_task(request: Request):
    body = await request.json()
    parameters = body.get("parameters", {})
    task = parameters.get("task", "").strip()
    if task:
        log_task(task)
    return JSONResponse({"result": f"Task logged: {task}"})


# ── Schedule Call tool endpoint ───────────────────────────────────────────────
@app.post("/tool/schedule_call")
async def on_schedule_call(request: Request):
    body = await request.json()
    print(f"[schedule_call raw body] {json.dumps(body, indent=2)}")  # ADD THIS

    parameters = body.get("parameters", {})
    
    # also try reading directly from body if parameters is empty
    if not parameters:
        parameters = body

    name           = parameters.get("name", "User")
    email          = parameters.get("email", "")
    requested_time = parameters.get("requested_time", "")
    timezone       = parameters.get("timezone", "Asia/Kolkata")
    duration       = int(parameters.get("duration_minutes", 30))

    if not email or not requested_time:
        return JSONResponse({"result": "Missing email or requested time"})

    try:
        result = schedule_call(name, email, requested_time, timezone, duration)
        return JSONResponse({
            "result": f"Call scheduled for {result['scheduled_time']} {result['timezone']}. "
                      f"Calendar invite sent to {email}."
        })
    except Exception as e:
        return JSONResponse({"result": f"Failed to schedule call: {str(e)}"})

# ── Post call webhook ─────────────────────────────────────────────────────────
@app.post("/post-call")
async def on_post_call(request: Request):
    body = await request.json()
    conversation_id = body.get("conversation_id")

    transcript = client.conversational_ai.get_conversation(conversation_id)

    # your logic here

    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    uvicorn.run("agent:app", host="0.0.0.0", port=8000, reload=True)