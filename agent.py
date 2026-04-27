import os
import json
from datetime import datetime
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

TASKS_FILE = "tasks.json"

load_dotenv()

client = ElevenLabs(api_key=os.getenv("ELVLABS_API_KEY"))
AGENT_ID = os.getenv("AGENT_ID")

app = FastAPI()


# ── Called by your frontend to start a session ────────────────────────────────
@app.get("/session")
def get_signed_url():
    response = client.conversational_ai.create_conversation_token(agent_id=AGENT_ID)
    return {"signed_url": response.signed_url}


# ── ElevenLabs calls this when the agent triggers a tool ──────────────────────
@app.post("/tool")
async def on_tool_call(request: Request):
    body = await request.json()
    tool_name  = body.get("tool_name")
    parameters = body.get("parameters", {})

    if tool_name == "log_task":
        task = parameters.get("task", "").strip()
        if task:
            log_task(task)
        return JSONResponse({"result": f"Task logged: {task}"})

    return JSONResponse({"result": "unknown tool"})


def log_task(task: str):
    # Load existing tasks
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r") as f:
            tasks = json.load(f)
    else:
        tasks = []

    tasks.append({
        "task": task,
        "logged_at": datetime.now().isoformat(),
    })

    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

    print(f"[logged] {task}")


# ── ElevenLabs calls this when a call ends ────────────────────────────────────
@app.post("/post-call")
async def on_post_call(request: Request):
    body = await request.json()
    conversation_id = body.get("conversation_id")

    transcript = client.conversational_ai.get_conversation(conversation_id)

    # your logic here

    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    uvicorn.run("agent:app", host="0.0.0.0", port=8000, reload=True)
