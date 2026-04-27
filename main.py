import os
import subprocess
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ELVLABS_API_KEY")
client = ElevenLabs(api_key=API_KEY)

def tts(text: str, voice_id: str = "WuePGPKIAIKI8COZpzce"):
    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128"
    )
    return audio

def main():
    audio = tts("Aww hell nawhh, this neega tripping")
    # Save audio bytes to file
    with open("output.mp3", "wb") as f:
        for chunk in audio:
            f.write(chunk)
    # Open with default Windows media player
    os.startfile("output.mp3")

if __name__ == "__main__":
    main()
