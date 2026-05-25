"""
AI Voice Assistant 🎙️
======================
Features:
  ✅ Speech recognition  — listens to your voice commands
  ✅ Voice synthesis     — speaks back to you (text-to-speech)
  ✅ Open apps           — opens Chrome, Notepad, Calculator, VS Code, etc.
  ✅ Tell weather        — fetches live weather for any city
  ✅ Tell time & date    — current time, day, date
  ✅ Search Google       — opens browser with your query
  ✅ AI replies          — Claude answers anything you ask

Dependencies:
  pip install speechrecognition pyttsx3 requests anthropic python-dotenv pyaudio

  On Linux, also run:
    sudo apt install portaudio19-dev python3-pyaudio espeak

  On Mac:
    brew install portaudio

Usage:
  python ai_voice_assistant.py

  Then speak commands like:
    "What time is it?"
    "Open Chrome"
    "Weather in Mumbai"
    "Search Python tutorials"
    "What is machine learning?"
    "Stop" / "Exit" / "Goodbye"
"""

import os
import sys
import platform
import subprocess
import webbrowser
from datetime import datetime
from typing import Optional

import requests
import pyttsx3
import speech_recognition as sr
from dotenv import load_dotenv

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

load_dotenv()

# ─── Configuration ─────────────────────────────────────────────────────────

ASSISTANT_NAME  = "Teju"          # Change to any name you like
DEFAULT_CITY    = "Guntur"     # Default weather city
WAKE_WORD       = "aria"          # Say this to wake the assistant (optional)
AI_MODEL        = "claude-sonnet-4-20250514"
VOICE_RATE      = 175             # Speech speed (words per minute)
VOICE_VOLUME    = 1.0             # 0.0 to 1.0
LISTEN_TIMEOUT  = 5               # Seconds to wait for speech
PHRASE_LIMIT    = 10              # Max seconds per phrase

OS = platform.system()           # "Windows", "Darwin" (Mac), "Linux"

# ─── App Map (add your own apps here!) ────────────────────────────────────

APP_MAP = {
    # Keyword          Windows path / command       Mac command          Linux command
    "chrome":         ("chrome",                   "open -a 'Google Chrome'",  "google-chrome"),
    "firefox":        ("firefox",                  "open -a Firefox",          "firefox"),
    "notepad":        ("notepad",                  "open -a TextEdit",         "gedit"),
    "calculator":     ("calc",                     "open -a Calculator",       "gnome-calculator"),
    "file explorer":  ("explorer",                 "open ~",                   "nautilus"),
    "files":          ("explorer",                 "open ~",                   "nautilus"),
    "vs code":        ("code",                     "open -a 'Visual Studio Code'", "code"),
    "vscode":         ("code",                     "open -a 'Visual Studio Code'", "code"),
    "terminal":       ("cmd",                      "open -a Terminal",         "gnome-terminal"),
    "spotify":        ("spotify",                  "open -a Spotify",          "spotify"),
    "word":           ("winword",                  "open -a 'Microsoft Word'", "libreoffice --writer"),
    "excel":          ("excel",                    "open -a 'Microsoft Excel'","libreoffice --calc"),
    "youtube":        ("youtube.com",              "youtube.com",              "youtube.com"),  # opens in browser
}


# ─── Voice Engine ───────────────────────────────────────────────────────────

class VoiceEngine:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", VOICE_RATE)
        self.engine.setProperty("volume", VOICE_VOLUME)

        # Pick a good voice (prefer female on Windows)
        voices = self.engine.getProperty("voices")
        for v in voices:
            if "female" in v.name.lower() or "zira" in v.name.lower() or "hazel" in v.name.lower():
                self.engine.setProperty("voice", v.id)
                break

    def speak(self, text: str):
        print(f"\n🔊  {ASSISTANT_NAME}: {text}\n")
        self.engine.say(text)
        self.engine.runAndWait()


# ─── Speech Recognizer ──────────────────────────────────────────────────────

class SpeechListener:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

    def listen(self) -> Optional[str]:
        with sr.Microphone() as source:
            print("🎙️  Listening...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=LISTEN_TIMEOUT, phrase_time_limit=PHRASE_LIMIT)
                text = self.recognizer.recognize_google(audio)
                print(f"👤  You said: {text}")
                return text.lower()
            except sr.WaitTimeoutError:
                print("⏳  No speech detected.")
                return None
            except sr.UnknownValueError:
                print("❓  Could not understand. Please repeat.")
                return None
            except sr.RequestError as e:
                print(f"❌  Speech service error: {e}")
                return None


# ─── Weather ────────────────────────────────────────────────────────────────

def get_weather(city: str) -> str:
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=8
        ).json()
        if not geo.get("results"):
            return f"Sorry, I couldn't find weather data for {city}."

        r   = geo["results"][0]
        lat, lon = r["latitude"], r["longitude"]
        name = r["name"]

        wx = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "timezone": "auto"
            },
            timeout=8
        ).json()

        c = wx["current"]
        WMO = {0:"clear sky",1:"mainly clear",2:"partly cloudy",3:"overcast",
               45:"foggy",51:"light drizzle",61:"light rain",63:"rain",65:"heavy rain",
               71:"light snow",73:"snow",75:"heavy snow",80:"rain showers",95:"thunderstorm"}
        desc = WMO.get(c["weather_code"], "mixed conditions")

        return (
            f"In {name}, it's currently {round(c['temperature_2m'])} degrees Celsius "
            f"with {desc}. It feels like {round(c['apparent_temperature'])} degrees, "
            f"humidity is {round(c['relative_humidity_2m'])} percent, "
            f"and wind speed is {round(c['wind_speed_10m'])} kilometres per hour."
        )
    except Exception as e:
        return f"Sorry, I couldn't fetch the weather right now. {e}"


# ─── Open Apps ──────────────────────────────────────────────────────────────

def open_app(app_keyword: str) -> str:
    key = app_keyword.lower()
    for name, (win, mac, linux) in APP_MAP.items():
        if name in key or key in name:
            # Browser-based apps
            if "." in win:
                webbrowser.open(f"https://www.{win}")
                return f"Opening {name} in your browser."
            try:
                if OS == "Windows":
                    subprocess.Popen(win, shell=True)
                elif OS == "Darwin":
                    subprocess.Popen(mac, shell=True)
                else:
                    subprocess.Popen(linux, shell=True)
                return f"Opening {name} for you."
            except Exception as e:
                return f"I couldn't open {name}. {e}"
    return f"Sorry, I don't know how to open {app_keyword}. You can add it to the APP_MAP."


# ─── AI Reply ───────────────────────────────────────────────────────────────

def ask_claude(query: str, api_key: str) -> str:
    if not ANTHROPIC_AVAILABLE:
        return "The anthropic package is not installed. Run: pip install anthropic"
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=AI_MODEL,
            max_tokens=200,
            system=(
                f"You are {ASSISTANT_NAME}, a friendly and concise AI voice assistant. "
                "Keep answers short (2-3 sentences max), conversational, and clear. "
                "No markdown, no lists, no bullet points — plain spoken language only."
            ),
            messages=[{"role": "user", "content": query}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return f"I had trouble connecting to my AI brain. Error: {e}"


# ─── Command Router ─────────────────────────────────────────────────────────

def handle_command(command: str, voice: VoiceEngine, api_key: Optional[str]) -> bool:
    """
    Routes voice commands to the right handler.
    Returns False if the assistant should stop, True otherwise.
    """

    # ── STOP ────────────────────────────────────────────────────────────────
    if any(w in command for w in ["stop", "exit", "quit", "goodbye", "bye", "shut down"]):
        voice.speak("Goodbye! Have a wonderful day!")
        return False

    # ── TIME / DATE ─────────────────────────────────────────────────────────
    if any(w in command for w in ["time", "clock"]):
        now = datetime.now()
        voice.speak(f"The current time is {now.strftime('%I:%M %p')}.")
        return True

    if any(w in command for w in ["date", "today", "day"]):
        now = datetime.now()
        voice.speak(f"Today is {now.strftime('%A, %B %d, %Y')}.")
        return True

    # ── WEATHER ─────────────────────────────────────────────────────────────
    if "weather" in command:
        # Extract city: "weather in Mumbai" → "Mumbai"
        city = DEFAULT_CITY
        if " in " in command:
            city = command.split(" in ", 1)[1].strip()
        elif " for " in command:
            city = command.split(" for ", 1)[1].strip()
        voice.speak(get_weather(city))
        return True

    # ── OPEN APPS ───────────────────────────────────────────────────────────
    if "open" in command or "launch" in command or "start" in command:
        # Extract app name after the verb
        for verb in ["open", "launch", "start"]:
            if verb in command:
                app = command.split(verb, 1)[1].strip()
                voice.speak(open_app(app))
                return True

    # ── SEARCH GOOGLE ───────────────────────────────────────────────────────
    if any(w in command for w in ["search", "google", "look up", "find"]):
        for verb in ["search for", "search", "google", "look up", "find"]:
            if verb in command:
                query = command.split(verb, 1)[1].strip()
                webbrowser.open(f"https://www.google.com/search?q={query.replace(' ', '+')}")
                voice.speak(f"Searching Google for {query}.")
                return True

    # ── YOUTUBE SEARCH ──────────────────────────────────────────────────────
    if "play" in command and "youtube" in command:
        query = command.replace("play", "").replace("on youtube", "").replace("youtube", "").strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
        voice.speak(f"Opening YouTube search for {query}.")
        return True

    if "play" in command:
        query = command.replace("play", "").strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
        voice.speak(f"Searching YouTube for {query}.")
        return True

    # ── TELL A JOKE ─────────────────────────────────────────────────────────
    if "joke" in command:
        try:
            joke = requests.get("https://official-joke-api.appspot.com/random_joke", timeout=5).json()
            voice.speak(f"{joke['setup']} ... {joke['punchline']}")
        except Exception:
            voice.speak("Why do programmers prefer dark mode? Because light attracts bugs!")
        return True

    # ── WHO ARE YOU ─────────────────────────────────────────────────────────
    if any(w in command for w in ["who are you", "your name", "what are you"]):
        voice.speak(f"I'm {ASSISTANT_NAME}, your personal AI voice assistant, powered by Claude.")
        return True

    # ── AI FALLBACK ─────────────────────────────────────────────────────────
    if api_key:
        voice.speak(ask_claude(command, api_key))
    else:
        voice.speak("I'm not sure how to help with that. Try asking me the time, weather, or to open an app.")

    return True


# ─── Main Loop ──────────────────────────────────────────────────────────────

def main():
    print("\n" + "═" * 52)
    print(f"  🎙️  {ASSISTANT_NAME} — AI Voice Assistant")
    print("═" * 52)
    print("  Say 'Stop' or 'Exit' to quit.\n")

    voice    = VoiceEngine()
    listener = SpeechListener()
    api_key  = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("⚠️   ANTHROPIC_API_KEY not set. AI replies disabled.")
        print("    Add it to a .env file for full AI support.\n")

    voice.speak(f"Hello! I'm {ASSISTANT_NAME}, your AI assistant. How can I help you today?")

    running = True
    while running:
        try:
            command = listener.listen()
            if command:
                running = handle_command(command, voice, api_key)
        except KeyboardInterrupt:
            voice.speak("Shutting down. Goodbye!")
            break

    print("\n👋  Assistant stopped.\n")


# ─── Extension Ideas ────────────────────────────────────────────────────────
#
# Add these features yourself:
#
#   1. 📅 Calendar events  — integrate with Google Calendar API
#   2. 📧 Read emails      — use imaplib to read Gmail / Outlook
#   3. 💡 Smart home       — control lights with requests to Home Assistant
#   4. 🗒️  Notes           — append spoken notes to a .txt file
#   5. 🌐 Wikipedia lookup — pip install wikipedia, call wikipedia.summary(query)
#   6. 🎵 Music control    — use pycaw (Windows) or osascript (Mac) to control Spotify
#   7. 🔔 Reminders        — schedule with `schedule` library: pip install schedule
#   8. 📸 Screenshot       — import pyautogui; pyautogui.screenshot().save("snap.png")
#   9. 🌙 Wake word only   — enable WAKE_WORD detection using pvporcupine library
#  10. 📱 Mobile alerts    — send summaries via Twilio SMS
#
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌  Fatal error: {e}")
        sys.exit(1)