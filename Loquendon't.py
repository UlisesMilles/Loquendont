import pyttsx3
import edge_tts
import asyncio
import re
import os
import sys
import threading
import time
from pydub import AudioSegment

# --- Configuration & Colors ---
TEMP_DIR = "tts_temp_segments"
VOICE_CMD_PATTERN = re.compile(r'(/voice=\d+)')
PAUSE_CMD_PATTERN = re.compile(r'(/pause=\d+)')
SPLIT_PATTERN = re.compile(r'(/voice=\d+|/pause=\d+|\n+)')

# ANSI Color Codes
CLR_FATAL = "\033[38;5;88m"    # Dark Red
CLR_CRITICAL = "\033[91m"      # Bright Red
CLR_WARNING = "\033[93m"       # Yellow
CLR_RESET = "\033[0m"

def log_error(level, message):
    """Prints colored error messages without breaking the progress bar line."""
    colors = {"FATAL": CLR_FATAL, "CRITICAL": CLR_CRITICAL, "WARNING": CLR_WARNING}
    color = colors.get(level, CLR_RESET)
    # Clear the current line before printing error to avoid overlap
    sys.stdout.write(f"\r\033[K{color}[{level}] {message}{CLR_RESET}\n")
    sys.stdout.flush()

# --- Async Helper ---
async def _run_edge_tts_segment_save(text, voice_id, output_path):
    try:
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(output_path)
    except Exception as e:
        raise e

class UnifiedTTSEngine:
    def __init__(self):
        self.unified_voices = [] 
        self.pyttsx3_available = False
        self._map_pyttsx3_voices()
        self._map_edge_tts_voices()

        if not self.unified_voices:
            log_error("FATAL", "No TTS voices found. Engine cannot start.")
            sys.exit(1)

    def _map_pyttsx3_voices(self):
        temp_engine = None
        try:
            temp_engine = pyttsx3.init()
            pyttsx3_voices = temp_engine.getProperty('voices')
            for voice in pyttsx3_voices:
                self.unified_voices.append({
                    'index': len(self.unified_voices),
                    'engine': 'pyttsx3',
                    'name': voice.name,
                    'id': voice.id,
                    'lang': voice.languages[0] if voice.languages else 'N/A'
                })
            self.pyttsx3_available = True
        except Exception as e:
            log_error("WARNING", f"pyttsx3 offline engine failed: {e}")
            self.pyttsx3_available = False
        finally:
            if temp_engine: temp_engine.stop()

    def _map_edge_tts_voices(self):
        async def _fetch_edge_voices(): return await edge_tts.list_voices()
        try:
            voices_list_raw = asyncio.run(_fetch_edge_voices())
            for voice in voices_list_raw:
                self.unified_voices.append({
                    'index': len(self.unified_voices),
                    'engine': 'edge-tts',
                    'name': voice['Name'],
                    'id': voice['ShortName'],
                    'lang': voice['Locale']
                })
        except Exception as e:
            log_error("WARNING", f"edge-tts online engine failed: {e}")

    def synthesize_segment(self, text, voice_index, base_output_path):
        voice = self.unified_voices[voice_index]
        ext = '.wav' if voice['engine'] == 'pyttsx3' else '.mp3'
        output_filepath = base_output_path + ext

        if voice['engine'] == 'pyttsx3':
            temp_engine = pyttsx3.init()
            try:
                temp_engine.setProperty('voice', voice['id'])
                temp_engine.save_to_file(text, output_filepath)
                temp_engine.runAndWait()
                return output_filepath
            finally:
                temp_engine.stop()
        else:
            asyncio.run(_run_edge_tts_segment_save(text, voice['id'], output_filepath))
            return output_filepath

# --- Smooth UI Manager ---
class ProgressManager:
    def __init__(self, total_segments):
        self.total = total_segments
        self.current = 0
        self.running = True
        self.spinners = ['|', '/', '-', '\\']
        self.spinner_idx = 0

    def draw(self):
        """The actual drawing logic for the progress bar."""
        width = 40
        # Force float division for percentage
        percent = (float(self.current) / self.total) * 100 if self.total > 0 else 0
        filled = int(width * self.current // self.total) if self.total > 0 else 0
        bar = '█' * filled + '-' * (width - filled)
        
        sys.stdout.write(f"\rProcessing: [{bar}] {self.spinners[self.spinner_idx % 4]} {percent:.2f}%")
        sys.stdout.flush()

    def animate(self):
        """Threaded function to keep the spinner moving smoothly."""
        while self.running:
            self.draw()
            self.spinner_idx += 1
            time.sleep(0.1)

    def update(self, val):
        self.current = val

    def stop(self):
        self.running = False
        # Small sleep to let the thread finish its last cycle
        time.sleep(0.1)
        # Ensure the final 100.00% state is drawn
        self.current = self.total
        self.draw()
        sys.stdout.write("\n")
        sys.stdout.flush()

# --- Logic ---

def parse_input_file(input_filepath, default_voice_index):
    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        log_error("CRITICAL", f"Could not read file: {e}")
        return []

    tokens = re.split(SPLIT_PATTERN, content)
    segments = []
    current_voice_index = default_voice_index

    for token in tokens:
        if not token: continue
        if token.startswith('/voice='):
            try: current_voice_index = int(token.split('=')[1])
            except: pass
        elif token.startswith('/pause='):
            try: segments.append({'type': 'pause', 'duration': int(token.split('=')[1])})
            except: pass
        elif '\n' in token:
            segments.append({'type': 'pause', 'duration': 800 if token.count('\n') >= 2 else 300})
        else:
            sub_parts = re.split(r'([.!?;]+|,)', token)
            for part in sub_parts:
                if not part.strip(): continue
                segments.append({'type': 'text', 'text': part, 'voice_index': current_voice_index})
                if part in ['.', '!', '?', ';']: segments.append({'type': 'pause', 'duration': 500})
                elif part == ',': segments.append({'type': 'pause', 'duration': 250})
    return segments

def process_and_concatenate(engine, input_file, output_file):
    segments = parse_input_file(input_file, 0)
    if not segments: return

    os.makedirs(TEMP_DIR, exist_ok=True)
    combined_audio = AudioSegment.empty()
    
    ui = ProgressManager(len(segments))
    spinner_thread = threading.Thread(target=ui.animate, daemon=True)
    spinner_thread.start()

    try:
        for i, seg in enumerate(segments):
            if seg['type'] == 'pause':
                combined_audio += AudioSegment.silent(duration=seg['duration'])
            else:
                try:
                    path = engine.synthesize_segment(seg['text'], seg['voice_index'], os.path.join(TEMP_DIR, f"seg_{i}"))
                    if path:
                        combined_audio += AudioSegment.from_file(path)
                        os.remove(path)
                except Exception as e:
                    log_error("CRITICAL", f"Segment {i} failed: {e}")
            
            ui.update(i + 1)

        # Ensure the progress bar reflects 100% while exporting the final file
        ui.update(len(segments))
        extension = os.path.splitext(output_file)[1].lower().strip('.') or "wav"
        combined_audio.export(output_file, format=extension)
        
    except Exception as e:
        log_error("FATAL", f"Conversion failed: {e}")
    finally:
        ui.stop()
        if os.path.exists(TEMP_DIR):
            try: 
                for f in os.listdir(TEMP_DIR):
                    os.remove(os.path.join(TEMP_DIR, f))
                os.rmdir(TEMP_DIR)
            except: pass

def main_menu(engine):
    while True:
        print("\n--- Loquendon't ---")
        print("1. List Voices\n2. Process File\n3. Exit")
        choice = input("Choice: ")
        if choice == '1': engine.list_voices()
        elif choice == '2':
            inf = input("Input path: ").strip().strip('"')
            outf = input("Output path (.wav): ").strip().strip('"')
            if os.path.exists(inf): 
                process_and_concatenate(engine, inf, outf)
                print(f"SUCCESS! Audio saved as: {outf}")
            else: log_error("CRITICAL", "Input file not found.")
        elif choice == '3': break

if __name__ == "__main__":
    try:
        tts_engine = UnifiedTTSEngine()
        main_menu(tts_engine)
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(0)
    except Exception as e:
        log_error("FATAL", f"Unexpected crash: {e}")
