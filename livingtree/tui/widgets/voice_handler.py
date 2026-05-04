"""Voice input/output — speech recognition and TTS."""
from __future__ import annotations

import asyncio
import io
import tempfile
from pathlib import Path
from typing import Optional


async def speech_to_text(language: str = "zh-CN") -> Optional[str]:
    """Record microphone and convert to text."""
    loop = asyncio.get_event_loop()

    def _record_and_recognize() -> Optional[str]:
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=10, phrase_time_limit=30)
            return r.recognize_google(audio, language=language)
        except ImportError:
            pass
        except Exception:
            pass
        return None

    return await loop.run_in_executor(None, _record_and_recognize)


async def text_to_speech(text: str, lang: str = "zh-CN") -> bool:
    """Convert text to speech and play it. Returns True if successful."""
    loop = asyncio.get_event_loop()

    def _synthesize_and_play() -> bool:
        # Try pyttsx3 first (offline, no API key needed)
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 180)
            # Find Chinese voice if available
            voices = engine.getProperty("voices")
            for v in voices:
                if "chinese" in v.name.lower() or "zh" in v.id.lower():
                    engine.setProperty("voice", v.id)
                    break
            engine.say(text)
            engine.runAndWait()
            return True
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback: Windows SAPI
        try:
            import subprocess
            import tempfile
            import os

            # PowerShell text-to-speech
            ps_script = f'''
            Add-Type -AssemblyName System.Speech
            $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
            $synth.Rate = 0
            $synth.Speak("{text.replace('"', '""')}")
            '''
            subprocess.run(
                ["powershell", "-Command", ps_script],
                timeout=60, capture_output=True,
            )
            return True
        except Exception:
            pass

        return False

    return await loop.run_in_executor(None, _synthesize_and_play)


def open_media_player(path: str | Path) -> bool:
    """Open a media file with the system default player."""
    import subprocess
    import os

    p = str(path)
    try:
        if os.name == "nt":
            os.startfile(p)
        else:
            subprocess.run(["xdg-open", p])
        return True
    except Exception:
        return False
