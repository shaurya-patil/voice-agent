import queue
import threading
import numpy as np
import sounddevice as sd
from elevenlabs.conversational_ai.conversation import AudioInterface

SAMPLE_RATE    = 16000   # input (mic) sample rate expected by ElevenLabs
OUTPUT_RATE    = 24000   # output (speaker) sample rate from ElevenLabs
CHANNELS       = 1
DTYPE          = "int16"
CHUNK          = 1024    # frames per buffer


class SoundDeviceAudioInterface(AudioInterface):
    """
    Drop-in replacement for DefaultAudioInterface using sounddevice.
    No PyAudio / mpv / ffmpeg required.
    """

    def __init__(self, on_mic_start=None, on_mic_stop=None):
        self._input_queue: queue.Queue[bytes] = queue.Queue()
        self._output_queue: queue.Queue[bytes | None] = queue.Queue()
        self._input_stream  = None
        self._output_stream = None
        self._output_thread = None
        self._running       = False

        # optional status callbacks for the UI
        self.on_mic_start = on_mic_start
        self.on_mic_stop  = on_mic_stop

    # ── AudioInterface contract ───────────────────────────────────────────────

    def start(self, input_callback):
        """Called by the SDK to start audio I/O."""
        self._running = True
        self._input_callback = input_callback

        # Microphone input stream
        def mic_callback(indata, frames, time_info, status):
            if self._running:
                self._input_callback(indata.tobytes())

        self._input_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=CHUNK,
            callback=mic_callback,
        )
        self._input_stream.start()
        if self.on_mic_start:
            self.on_mic_start()

        # Speaker output thread
        self._output_stream = sd.OutputStream(
            samplerate=OUTPUT_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=CHUNK,
        )
        self._output_stream.start()
        self._output_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._output_thread.start()

    def stop(self):
        """Called by the SDK to stop audio I/O."""
        self._running = False
        self._output_queue.put(None)  # sentinel to unblock playback loop

        if self._input_stream:
            self._input_stream.stop()
            self._input_stream.close()

        if self._output_thread:
            self._output_thread.join(timeout=2)

        if self._output_stream:
            self._output_stream.stop()
            self._output_stream.close()

        if self.on_mic_stop:
            self.on_mic_stop()

    def output(self, audio: bytes):
        """Called by the SDK with raw PCM audio to play."""
        self._output_queue.put(audio)

    def interrupt(self):
        """Called by the SDK when the agent is interrupted — drain the queue."""
        while not self._output_queue.empty():
            try:
                self._output_queue.get_nowait()
            except queue.Empty:
                break

    # ── internal ──────────────────────────────────────────────────────────────

    def _playback_loop(self):
        while self._running:
            chunk = self._output_queue.get()
            if chunk is None:
                break
            audio_np = np.frombuffer(chunk, dtype=np.int16)
            try:
                self._output_stream.write(audio_np)
            except Exception:
                pass
