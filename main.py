import sys, os, re, asyncio, uuid, urllib.parse, urllib.request
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
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

CMD_PATTERN = re.compile(r'(/voice=[^ \n\r]+|/pause=\d+|\n)')

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
    voice_list = voices.voices
    processed = []
    for v in voice_list:
        is_multi = "Multilingual" in v.get("VoiceTag", {}).get("VoicePersonalities", [])
        
        raw_name = v["FriendlyName"].split("-")[-1].strip().replace("Neural", "")
        
        country = v["FriendlyName"].split("(")[1].split(",")[0] if "(" in v["FriendlyName"] else "Unknown"
        
        processed.append({
            "ShortName": v["ShortName"],
            "Name": raw_name,
            "Country": country,
            "Language": v["Locale"].split("-")[0],
            "IsMultilingual": is_multi
        })
    return processed

async def process_text_to_audio(text: str):
    tokens = re.split(CMD_PATTERN, text)
    combined = AudioSegment.empty()
    current_voice = "en-US-AndrewNeural"
    
    for token in tokens:
        if not token or token == '\n': continue
        if token.startswith("/voice="):
            current_voice = token.split("=")[1].strip()
        elif token.startswith("/pause="):
            try:
                ms = int(token.split("=")[1])
                combined += AudioSegment.silent(duration=ms)
            except: pass
        else:
            temp_name = f"/tmp/{uuid.uuid4()}.mp3"
            communicate = edge_tts.Communicate(token.strip(), current_voice)
            await communicate.save(temp_name)
            segment = AudioSegment.from_mp3(temp_name)
            combined += segment
            os.remove(temp_name)
    return combined

@app.get("/generate")
async def generate(text: str = Query(...)):
    final_path = f"/tmp/final_{uuid.uuid4()}.mp3"
    audio_data = await process_text_to_audio(text)
    audio_data.export(final_path, format="mp3")
    return FileResponse(final_path, media_type="audio/mpeg", filename="loquendont.mp3")

@app.get("/preview")
async def preview(voice: str, lang: str):
    original_msg = "This is a preview of the selected voice."
    translated_msg = translate_text(original_msg, lang)
    out = f"/tmp/preview_{uuid.uuid4()}.mp3"
    communicate = edge_tts.Communicate(translated_msg, voice)
    await communicate.save(out)
    return FileResponse(out, media_type="audio/mpeg")