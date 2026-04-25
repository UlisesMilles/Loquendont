import sys
import os
import re
import asyncio
import shutil
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
from pydub import AudioSegment

# --- PYTHON 3.14 COMPATIBILITY PATCH ---
try:
    import audioop_lts
    sys.modules['audioop'] = audioop_lts
    sys.modules['pyaudioop'] = audioop_lts
except ImportError:
    pass

app = FastAPI()

# Enable CORS so your GitHub Pages can talk to Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tell pydub where ffmpeg is
ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg")
if os.path.exists(ffmpeg_path):
    AudioSegment.converter = ffmpeg_path

CMD_PATTERN = re.compile(r'(/voice=[^ \n]+|/pause=\d+|\n+)')

@app.get("/")
async def root():
    return {"status": "online", "endpoint": "/generate"}

@app.get("/generate")
async def generate_audio(text: str = Query(...)):
    output_file = "/tmp/result.mp3"
    tokens = re.split(CMD_PATTERN, text)
    
    combined_audio = AudioSegment.empty()
    current_voice = "en-US-AndrewNeural"

    for t in tokens:
        if not t or t.strip() == "" and t != "\n": continue
        
        if t.startswith('/voice='):
            current_voice = t.split('=')[1]
        elif t.startswith('/pause='):
            try:
                ms = int(t.split('=')[1])
                combined_audio += AudioSegment.silent(duration=ms)
            except: pass
        else:
            communicate = edge_tts.Communicate(t.strip(), current_voice)
            temp_file = f"/tmp/temp_{hash(t)}.mp3"
            await communicate.save(temp_file)
            segment = AudioSegment.from_mp3(temp_file)
            combined_audio += segment
            os.remove(temp_file)
            
    combined_audio.export(output_file, format="mp3")
    return FileResponse(output_file, media_type="audio/mpeg", filename="loquendont.mp3")
