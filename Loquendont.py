import pyttsx3
import edge_tts
import asyncio
import re
import os
import sys
import threading
import time
import json
import msvcrt
from pydub import AudioSegment

# --- Configuration & Colors ---
CONFIG_FILE = "settings.conf"
TEMP_DIR = "tts_temp_segments"

# Simplified pattern: only looks for /voice, /pause, and newlines
CMD_PATTERN = re.compile(r'(/voice=[^ \n]+|/pause=\d+|\n+)')
PUNCT_PATTERN = re.compile(r'(\.\.\.|[.?!,;])')

CLR_FATAL = "\033[38;5;88m"
CLR_CRITICAL = "\033[91m"
CLR_WARNING = "\033[93m"
CLR_RESET = "\033[0m"

PERSISTENT_LOGS = []

def log_error(level, message):
    colors = {"FATAL": CLR_FATAL, "CRITICAL": CLR_CRITICAL, "WARNING": CLR_WARNING}
    color = colors.get(level, CLR_RESET)
    timestamp = time.strftime("%H:%M:%S")
    formatted_msg = f"{color}[{level}] {timestamp} - {message}{CLR_RESET}"
    PERSISTENT_LOGS.append(formatted_msg)

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')
    if PERSISTENT_LOGS:
        print("--- PERSISTENT LOG HISTORY ---")
        for log in PERSISTENT_LOGS:
            print(log)
        print("-" * 30)

def ring_the_bell():
    if os.name == 'nt':
        import winsound
        winsound.MessageBeep()
    else:
        sys.stdout.write('\a')
        sys.stdout.flush()

def handle_invalid_input(user_input):
    clear_console()
    ring_the_bell()
    print(f"\nunrecognized option [{user_input}] entered")
    print("press enter to try again")
    input()

# --- Progress UI ---
class ProgressTracker:
    def __init__(self, total):
        self.total = total
        self.current = 0
        self.running = True
        self.chars = ['|', '/', '-', '\\']
        self.idx = 0

    def update(self):
        while self.running:
            pct = (self.current / self.total) * 100 if self.total > 0 else 0
            bar_len = 40
            filled = int(bar_len * self.current // self.total) if self.total > 0 else 0
            bar = '█' * filled + '-' * (bar_len - filled)
            spin = self.chars[self.idx % 4]
            sys.stdout.write(f"\rProcessing Segments: [{bar}] {spin} {pct:.1f}%")
            sys.stdout.flush()
            self.idx += 1
            time.sleep(0.1)

# --- Config Manager ---
class ConfigManager:
    def __init__(self):
        self.defaults = {
            "pauses": {".": 500, ",": 250, "?": 500, "!": 500, "...": 700, ";": 400, "newline": 300, "paragraph": 800}
        }
        data = self.load_config()
        self.pauses = data.get("pauses", self.defaults["pauses"])

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f: return json.load(f)
            except Exception as e:
                log_error("WARNING", f"Failed to load config: {e}")
        return self.defaults

    def save_config(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"pauses": self.pauses}, f, indent=4)

    def menu(self):
        while True:
            clear_console()
            print("--- CONFIGURATION SETTINGS ---")
            print("1. Punctuation and Paragraph Pause Timings")
            print("2. Clear Persistent Log History")
            print("3. Return to Main Menu")
            c = input("\nChoice: ")
            if c == '1': self.pause_submenu()
            elif c == '2': PERSISTENT_LOGS.clear()
            elif c == '3': break
            else: handle_invalid_input(c)

    def pause_submenu(self):
        while True:
            clear_console()
            print("--- PUNCTUATION AND PARAGRAPH PAUSE TIMINGS ---")
            keys = list(self.pauses.keys())
            for idx, k in enumerate(keys, 1):
                label = f"Pause for '{k}'" if len(k) < 4 else f"Pause for {k}"
                print(f"{idx}. {label:25}: {self.pauses[k]}ms")
            print(f"{len(keys)+1}. Back")
            choice = input(f"\nEdit (1-{len(keys)+1}): ")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(keys):
                    self.pauses[keys[idx]] = int(input(f"New millisecond delay for {keys[idx]}: "))
                    self.save_config()
                elif idx == len(keys): break
                else: handle_invalid_input(choice)
            except ValueError: handle_invalid_input(choice)

config = ConfigManager()

# --- TTS Engine ---
class UnifiedTTSEngine:
    def __init__(self):
        self.unified_voices = []
        asyncio.run(self._map_voices())

    async def _map_voices(self):
        try:
            eng = pyttsx3.init()
            for v in eng.getProperty('voices'):
                self.unified_voices.append({'engine': 'pyttsx3', 'name': v.name, 'id': v.id})
            eng.stop()
        except: pass
        try:
            vs = await edge_tts.list_voices()
            for v in vs:
                self.unified_voices.append({'engine': 'edge-tts', 'name': v['ShortName'], 'id': v['ShortName']})
        except: pass

    def list_voices(self):
        clear_console()
        print("--- AVAILABLE VOICES ---")
        if not self.unified_voices:
            print("No voices detected.")
        else:
            print(f"{'ID':<5} | {'Engine':<10} | {'Voice Name'}")
            print("-" * 60)
            for i, v in enumerate(self.unified_voices):
                print(f"{i:<5} | {v['engine']:<10} | {v['name']}")
        print("\nPress any key to return...")
        msvcrt.getch()

    def synthesize_segment(self, text, voice_id, base_path):
        try:
            v = self.unified_voices[voice_id]
            ext = '.wav' if v['engine'] == 'pyttsx3' else '.mp3'
            path = base_path + ext
            
            if v['engine'] == 'pyttsx3':
                eng = pyttsx3.init()
                eng.setProperty('voice', v['id'])
                eng.save_to_file(text, path)
                eng.runAndWait()
                eng.stop()
            else:
                asyncio.run(edge_tts.Communicate(text, v['id']).save(path))
            
            return path if os.path.exists(path) and os.path.getsize(path) > 0 else None
        except Exception as e:
            log_error("WARNING", f"Synthesis failed: {e}")
            return None

# --- Main Logic ---
def process(engine, inf, outf):
    clear_console()
    try:
        with open(inf, 'r', encoding='utf-8') as f: content = f.read()
    except Exception as e:
        log_error("CRITICAL", f"Cannot open input file: {e}")
        return

    tokens = re.split(CMD_PATTERN, content)
    segments = []
    curr_voice_id = 0

    for t in tokens:
        if not t: continue
        if t.startswith('/voice='):
            try:
                curr_voice_id = int(t.split('=')[1].split(',')[0])
            except: pass
        elif t.startswith('/pause='):
            try:
                segments.append({'type': 'pause', 'dur': int(t.split('=')[1])})
            except: pass
        elif '\n' in t:
            dur = config.pauses['paragraph'] if t.count('\n') >= 2 else config.pauses['newline']
            segments.append({'type': 'pause', 'dur': dur})
        else:
            parts = re.split(PUNCT_PATTERN, t)
            for p in parts:
                if not p: continue
                segments.append({'type': 'text', 'text': p, 'voice_id': curr_voice_id})
                if p in config.pauses:
                    segments.append({'type': 'pause', 'dur': config.pauses[p]})

    os.makedirs(TEMP_DIR, exist_ok=True)
    final_audio = AudioSegment.empty()
    ui = ProgressTracker(len(segments))
    threading.Thread(target=ui.update, daemon=True).start()

    for i, s in enumerate(segments):
        if s['type'] == 'pause':
            final_audio += AudioSegment.silent(duration=s['dur'])
        else:
            temp_file = engine.synthesize_segment(s['text'], s['voice_id'], os.path.join(TEMP_DIR, f"s_{i}"))
            if temp_file:
                try:
                    final_audio += AudioSegment.from_file(temp_file)
                    os.remove(temp_file)
                except: pass
        ui.current = i + 1
    
    ui.running = False
    sys.stdout.write(f"\rProcessing Segments: [████████████████████████████████████████] | 100.0%\n")

    try:
        final_audio.export(outf, format=outf.split('.')[-1])
        ring_the_bell()
        print(f"\nSUCCESS: Audio saved to {outf}")
    except Exception as e: log_error("FATAL", f"Export failed: {e}")
    
    print("Press any key to return to menu...")
    msvcrt.getch()

def main():
    eng = UnifiedTTSEngine()
    while True:
        clear_console()
        print("--- LOQUENDON'T ---")
        print("1. List Available Voices")
        print("2. Process Text File to Audio")
        print("3. Configuration Settings")
        print("4. Exit")
        c = input("\nChoice: ")
        if c == '1': eng.list_voices()
        elif c == '2':
            inf = input("Input File Path: ").strip('"')
            outf = input("Output Audio Path: ").strip('"')
            if os.path.exists(inf): process(eng, inf, outf)
            else: 
                log_error("CRITICAL", f"File '{inf}' not found.")
                print("\nFile not found. Press Enter to return...")
                input()
        elif c == '3': config.menu()
        elif c == '4': break
        else: handle_invalid_input(c)

if __name__ == "__main__":
    main()
