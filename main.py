import sys, os, re, asyncio, uuid, urllib.parse, urllib.request
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
from pydub import AudioSegment

try:
    import audioop_lts
    sys.modules['audioop'] = audioop_lts
    sys.modules['pyaudioop'] = audioop_lts
except: pass

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg")
if os.path.exists(ffmpeg_path):
    AudioSegment.converter = ffmpeg_path

CMD_PATTERN = re.compile(r'(/voice=[^ \n\r]+|/pause=\d+|\.\.\.|[.?!]|[,,;]|\n\n)')

def translate_text(text, target_lang):
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            res = response.read().decode('utf-8')
            return res.split('"')[1]
    except:
        return text

@app.get("/voices")
async def get_voices():
    voices = await edge_tts.VoicesManager.create()
    processed = []
    for v in voices.voices:
        is_multi = "Multilingual" in v.get("VoiceTag", {}).get("VoicePersonalities", [])
        processed.append({
            "ShortName": v["ShortName"],
            "FriendlyName": v["FriendlyName"],
            "Language": v["Locale"].split("-")[0],
            "Locale": v["Locale"],
            "IsMultilingual": is_multi
        })
    return processed

async def process_text_to_audio(text: str, short_p: int, long_p: int):
    tokens = re.split(CMD_PATTERN, text)
    combined = AudioSegment.empty()
    current_voice = "en-US-AndrewNeural"
    
    for token in tokens:
        if not token: continue
        
        if token.startswith("/voice="):
            current_voice = token.split("=")[1].strip()
        elif token.startswith("/pause="):
            try:
                ms = int(token.split("=")[1])
                combined += AudioSegment.silent(duration=ms)
            except: pass
        elif token == '\n\n':
            combined += AudioSegment.silent(duration=long_p)
        elif token in ['.', '!', '?', '...']:
            # Long Stop
            temp_name = f"/tmp/{uuid.uuid4()}.mp3"
            await edge_tts.Communicate(token, current_voice).save(temp_name)
            combined += AudioSegment.from_mp3(temp_name)
            combined += AudioSegment.silent(duration=long_p)
            os.remove(temp_name)
        elif token in [',', ';']:
            # Short Stop
            temp_name = f"/tmp/{uuid.uuid4()}.mp3"
            await edge_tts.Communicate(token, current_voice).save(temp_name)
            combined += AudioSegment.from_mp3(temp_name)
            combined += AudioSegment.silent(duration=short_p)
            os.remove(temp_name)
        else:
            clean_token = token.strip()
            if not clean_token: continue
            temp_name = f"/tmp/{uuid.uuid4()}.mp3"
            await edge_tts.Communicate(clean_token, current_voice).save(temp_name)
            combined += AudioSegment.from_mp3(temp_name)
            os.remove(temp_name)
            
    return combined

@app.get("/generate")
async def generate(text: str = Query(...), short_p: int = 300, long_p: int = 800):
    final_path = f"/tmp/final_{uuid.uuid4()}.mp3"
    audio_data = await process_text_to_audio(text, short_p, long_p)
    audio_data.export(final_path, format="mp3")
    return FileResponse(final_path, media_type="audio/mpeg")

@app.get("/preview")
async def preview(voice: str, lang: str):
    msg = translate_text("This is a preview of the selected voice.", lang)
    out = f"/tmp/preview_{uuid.uuid4()}.mp3"
    await edge_tts.Communicate(msg, voice).save(out)
    return FileResponse(out, media_type="audio/mpeg")