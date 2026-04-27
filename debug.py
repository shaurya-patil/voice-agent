import os
import traceback
from dotenv import load_dotenv

load_dotenv()

AGENT_ID = os.getenv("AGENT_ID")
API_KEY  = os.getenv("ELVLABS_API_KEY")

print(f"AGENT_ID: {AGENT_ID}")
print(f"API_KEY set: {bool(API_KEY)}")

try:
    print("Importing ElevenLabs...")
    from elevenlabs.client import ElevenLabs
    print("OK")

    print("Importing Conversation...")
    from elevenlabs.conversational_ai.conversation import Conversation
    print("OK")

    print("Importing SoundDeviceAudioInterface...")
    from audio_interface import SoundDeviceAudioInterface
    print("OK")

    print("Creating ElevenLabs client...")
    client = ElevenLabs(api_key=API_KEY)
    print("OK")

    print("Creating audio interface...")
    audio = SoundDeviceAudioInterface()
    print("OK")

    print("Creating Conversation...")
    conversation = Conversation(
        client,
        AGENT_ID,
        requires_auth=bool(API_KEY),
        audio_interface=audio,
        callback_agent_response=lambda r: print(f"Agent: {r}"),
        callback_user_transcript=lambda t: print(f"User: {t}"),
        callback_latency_measurement=lambda l: print(f"Latency: {l}ms"),
    )
    print("OK")

    print("\nAll good — starting session. Speak into your mic. Ctrl+C to stop.\n")
    conversation.start_session()
    session_id = conversation.wait_for_session_end()
    print(f"Session ended. ID: {session_id}")

except Exception as e:
    print(f"\n--- ERROR ---")
    traceback.print_exc()

input("\nPress Enter to exit...")
