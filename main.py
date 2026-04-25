from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
import edge_tts
import asyncio
import os
import re
from pydub import AudioSegment

app = FastAPI()

CMD_PATTERN = re.compile(r'(/voice=[^ \n]+|/pause=\d+|\n+)')

@app.get("/generate")
async def generate_audio(text: str = Query(...)):
    output_file = "result.mp3"
    tokens = re.split(CMD_PATTERN, text)
    
    combined_audio = AudioSegment.empty()
    current_voice = "en-US-AndrewNeural"

    for t in tokens:
        if not t or t.isspace(): continue
        
        if t.startswith('/voice='):
            current_voice = t.split('=')[1]
        elif t.startswith('/pause='):
            ms = int(t.split('=')[1])
            combined_audio += AudioSegment.silent(duration=ms)
        else:
            # Generate the segment using edge-tts
            communicate = edge_tts.Communicate(t, current_voice)
            await communicate.save("temp.mp3")
            segment = AudioSegment.from_mp3("temp.mp3")
            combined_audio += segment
            
    combined_audio.export(output_file, format="mp3")
    return FileResponse(output_file, media_type="audio/mpeg", filename="loquendont.mp3")