import sys
import os
import re
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
from pydub import AudioSegment

try:
    import audioop_lts
    sys.modules['audioop'] = audioop_lts
    sys.modules['pyaudioop'] = audioop_lts
except ImportError:
    pass

app = FastAPI()

# Allow your GitHub Pages to talk to Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# FFMPEG Setup
ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg")
if os.path.exists(ffmpeg_path):
    AudioSegment.converter = ffmpeg_path

@app.get("/")
async def root():
    return JSONResponse({
        "message": "LOQUENDONT API IS LIVE",
        "usage": "/generate?text=YOUR_TEXT",
        "docs": "/docs"
    })

@app.get("/generate")
async def generate_audio(text: str = Query(...)):
    # Use /tmp as it is the only writable directory on many cloud hosts
    out = "/tmp/output.mp3"
    
    # Simple single-segment generation for testing stability first
    # We strip your custom tags just to ensure the core TTS works
    clean_text = re.sub(r'(/voice=[^ \n]+|/pause=\d+)', '', text)
    
    communicate = edge_tts.Communicate(clean_text, "en-US-AndrewNeural")
    await communicate.save(out)
    
    return FileResponse(out, media_type="audio/mpeg", filename="audio.mp3")