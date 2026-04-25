import sys, os, re, asyncio, uuid
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
from pydub import AudioSegment

# Python 3.14 Compatibility
try:
    import audioop_lts
    sys.modules['audioop'] = audioop_lts
    sys.modules['pyaudioop'] = audioop_lts
except: pass

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# FFMPEG path setup for Render
ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg")
if os.path.exists(ffmpeg_path):
    AudioSegment.converter = ffmpeg_path

# This pattern finds /voice=, /pause=, or new lines
CMD_PATTERN = re.compile(r'(/voice=[^ \n\r]+|/pause=\d+|\n)')

async def process_text_to_audio(text: str):
    tokens = re.split(CMD_PATTERN, text)
    combined = AudioSegment.empty()
    current_voice = "en-US-AndrewNeural"
    
    for token in tokens:
        if not token or token == '\n': continue
        
        if token.startswith("/voice="):
            current_voice = token.split("=")[1].strip()
        elif token.startswith("/pause="):
            ms = int(token.split("=")[1])
            combined += AudioSegment.silent(duration=ms)
        else:
            # It's actual text - generate speech
            temp_name = f"/tmp/{uuid.uuid4()}.mp3"
            communicate = edge_tts.Communicate(token.strip(), current_voice)
            await communicate.save(temp_name)
            
            segment = AudioSegment.from_mp3(temp_name)
            combined += segment
            os.remove(temp_name) # Clean up
            
    return combined

@app.get("/generate")
async def generate(text: str = Query(...)):
    final_path = f"/tmp/final_{uuid.uuid4()}.mp3"
    audio_data = await process_text_to_audio(text)
    audio_data.export(final_path, format="mp3")
    return FileResponse(final_path, media_type="audio/mpeg", filename="loquendont.mp3")
