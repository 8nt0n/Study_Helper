import os
import json
import asyncio
import base64
import httpx
from moviepy import *
import wave
from dotenv import load_dotenv
from pathlib import Path
import google.generativeai as genai
import whisper
import textwrap
import random
import sys
import time

# Load the environment configurations
load_dotenv()

# Delete all .wav files from previous runs
for wav_file in Path.cwd().glob("*.wav"):
    wav_file.unlink()

# =========================================
# CONFIG
# =========================================

JSON_FILE = "script.json"
GAMEPLAY_FOLDER = "../gameplay/"
FULL_AUDIO_FILE = "full_audio.wav"
AVATAR_IMAGE = "avatar.png"

WIDTH = 1080
HEIGHT = 1920

VOICE_NARRATOR = "Puck"   

# Parse multiple project keys
API_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
if not API_KEYS and os.getenv("GEMINI_API_KEY"):
    API_KEYS = [os.getenv("GEMINI_API_KEY")]

current_key_index = 0

# Prüfen, ob eine Outline als Argument übergeben wurde
if len(sys.argv) > 1:
    OUTLINE = sys.argv[1]
    print(f"📥 Outline erfolgreich via Argument empfangen!")
else:
    print("FEHLER: Kein argument übergeben")
    sys.exit(-1)


# =========================================
# ROBUSTE TEXT-GENERIERUNG (MIT KEY-ROTATION)
# =========================================

def generate_text_robust(prompt, model_name="gemini-3.5-flash", temperature=0.8):
    global current_key_index
    
    while True:
        if not API_KEYS:
            raise ValueError("❌ Keine API-Keys in den Umgebungsvariablen gefunden!")
            
        active_key = API_KEYS[current_key_index]
        # Das SDK für diesen Versuch mit dem aktuellen Key neu konfigurieren
        genai.configure(api_key=active_key)
        model = genai.GenerativeModel(model_name)
        
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json", 
                    temperature=temperature, 
                )
            )
            return response.text
            
        except Exception as e:
            error_text = str(e)
            if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text or "Quota" in error_text:
                if len(API_KEYS) > 1:
                    current_key_index = (current_key_index + 1) % len(API_KEYS)
                    print(f"🔄 Text-Gen Quota erschöpft. Wechsle zu Key #{current_key_index + 1}...")
                    time.sleep(1)
                else:
                    print("❌ Quota erschöpft und keine weiteren Backup-Keys vorhanden!")
                    raise e
            elif "400" in error_text or "401" in error_text or "403" in error_text:
                if len(API_KEYS) > 1:
                    current_key_index = (current_key_index + 1) % len(API_KEYS)
                    print(f"🔄 Key-Fehler festgestellt. Probiere Backup-Key #{current_key_index + 1}...")
                else:
                    raise e
            else:
                raise e


# =========================================
# GENERATE SCRIPT (REDDIT STORY MODE)
# =========================================

with open("../project_text.txt", "r", encoding="utf-8") as user_text_file:
    USERTEXT = user_text_file.read()

PROMPT = """
Systemrolle:
Du bist ein Experte für virale TikTok- und YouTube-Shorts-Skripte im Bereich "Reddit Stories".
Verwandle den folgenden Text in eine packende, flüssige Geschichte für EINEN Sprecher.
Die ersten 3 Sekunden (der Hook) müssen extrem fesselnd sein (z.B. "Ich (25M) habe herausgefunden, dass..."). Die Themen aus dem Text sollten dann mit einem alltagsbeispiel / erlebniss verknüpft werden das eine person so erlebt haben könnte: z.B. "letztens war ich im supermarkt und da habe ich gemerkt das..."
Der Text muss absolut für Text-to-Speech (TTS) optimiert sein: Keine Abkürzungen, keine Emojis, Zahlen als Wörter ausschreiben.

Ausgabe:
Nur valides JSON. Keine Einleitung, keine Erklärungen.

Vorlage für die Nutzereingabe:
Text: [USERTEXT]

Aufgabe:
Erstelle ein Skript im JSON-Format. Die gesamte Geschichte muss in einem einzigen Textblock ("story_text") stehen, damit wir nur EINEN API-Call für das TTS machen müssen.
WICHTIG: ERKLÄRE NICHT ALLES AUS DEM NUTZER TEXT. halte dich strikt an die themen dieser Outline:
[OUTLINE]

JSON-Schema:
{
  "video_title": "Kurzer reisserischer Titel",
  "story_text": "Der komplette Text der Geschichte hier als ein einziger, langer String. Ohne Zeilenumbrüche."
}
"""

PROMPT = PROMPT.replace("[USERTEXT]", USERTEXT)
PROMPT = PROMPT.replace("[OUTLINE]", OUTLINE)
print("📝 Generiere Reddit-Skript (ausfallsicher)...")

ai_response = generate_text_robust(PROMPT, model_name="gemini-3.5-flash", temperature=0.8)

with open(JSON_FILE, "w", encoding="utf-8") as out_file:
    out_file.write(ai_response)


# =========================================
# GENERATE QUIZ
# =========================================

print("🧠 Generiere Quiz zum Text (ausfallsicher)...")

QUIZ_PROMPT = """
Systemrolle:
Du bist ein Experte für interaktive und spannende Quizze für Social Media (TikTok/Shorts).
Erstelle basierend auf dem folgenden Text ein kurzes Quiz mit 3 Fragen.

Ausgabe:
Nur valides JSON. Keine Einleitung, keine Erklärungen.

Vorlage für die Nutzereingabe:
Text: [USERTEXT]

Aufgabe:
Erstelle ein Quiz im JSON-Format. Jede Frage soll 4 Antwortmöglichkeiten haben, von denen genau eine richtig ist.

JSON-Schema:
{
  "quiz_title": "Spannender Titel für das Quiz",
  "questions": [
    {
      "question": "Fragetext hier...",
      "options": ["Antwort 1", "Antwort 2", "Antwort 3", "Antwort 4"],
      "correct_answer_index": 0
    }
  ]
}
"""

QUIZ_PROMPT = QUIZ_PROMPT.replace("[USERTEXT]", ai_response)

quiz_ai_response = generate_text_robust(QUIZ_PROMPT, model_name="gemini-3.5-flash", temperature=0.7)

output_dir = "../FLASK/videos/"
os.makedirs(output_dir, exist_ok=True)

with open(JSON_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

quizz_title = "Reddit - " + data.get("video_title", "Reddit_Story") + ".json"
quiz_file_path = os.path.join(output_dir, quizz_title)

with open(quiz_file_path, "w", encoding="utf-8") as quiz_out_file:
    quiz_out_file.write(quiz_ai_response)

print(f"✅ Skript und Quiz erfolgreich generiert! Quiz gespeichert unter: {quiz_file_path}")


# =========================================
# TTS ENGINE (DIRECT REST API)
# =========================================

async def generate_gemini_tts(text, voice_name, output_filename):
    global current_key_index
    
    while True:
        if not API_KEYS:
            raise ValueError("❌ No API keys found! Please set GEMINI_API_KEYS in your .env file.")
            
        active_key = API_KEYS[current_key_index]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={active_key}"
        
        payload = {
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}}
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status() 
                
                data = response.json()
                audio_b64 = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                audio_bytes = base64.b64decode(audio_b64)
                
                with wave.open(output_filename, "wb") as wf:
                    wf.setnchannels(1)       
                    wf.setsampwidth(2)       
                    wf.setframerate(24000)   
                    wf.writeframes(audio_bytes)
            break 
            
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            error_text = e.response.text
            if status == 429 or "RESOURCE_EXHAUSTED" in error_text:
                if len(API_KEYS) > 1:
                    current_key_index = (current_key_index + 1) % len(API_KEYS)
                    print(f"🔄 TTS Quota Exhausted. Hot-swapping to API Key #{current_key_index + 1}...")
                    await asyncio.sleep(1)  
                else:
                    raise ValueError("❌ Ultimate daily limit reached.")
            elif status in [400, 401, 403]:
                if len(API_KEYS) > 1:
                    current_key_index = (current_key_index + 1) % len(API_KEYS)
                else:
                    raise ValueError(f"❌ Key failed: {error_text}")
            else:
                raise e

# =========================================
# GAMEPLAY LOOP
# =========================================

def get_random_gameplay(duration):
    gameplay_dir = Path(GAMEPLAY_FOLDER)
    video_files = list(gameplay_dir.glob("*.mp4"))
    if not video_files:
        raise ValueError(f"❌ Keine .mp4 Videos im Ordner '{GAMEPLAY_FOLDER}' gefunden!")
        
    random_video_path = random.choice(video_files)
    print(f"🎮 Nutze zufälliges Hintergrundvideo: {random_video_path.name}")
    
    gameplay = VideoFileClip(str(random_video_path))
    
    if gameplay.duration < duration:
        print("⚠️ Video ist kürzer als Audio. Loope das Video zur Sicherheit...")
        loops_needed = int(duration // gameplay.duration) + 1
        gameplay = concatenate_videoclips([gameplay] * loops_needed)
        
    max_start_time = max(0, gameplay.duration - duration)
    start_time = random.uniform(0, max_start_time)
    end_time = start_time + duration
    
    print(f"⏱️ Schneide Video von {start_time:.2f}s bis {end_time:.2f}s")
    
    gameplay = gameplay.subclipped(start_time, end_time)
    gameplay = gameplay.resized(height=HEIGHT)
    gameplay = gameplay.cropped(x_center=gameplay.w / 2, width=WIDTH)
    gameplay = gameplay.with_position(("center", "center"))
    return gameplay

# =========================================
# REDDIT UI & WHISPER SUBTITLES
# =========================================

def create_reddit_overlay(text, start_time, duration):
    box_width = 900
    wrapped_text = textwrap.fill(text, width=40)
    
    txt_clip = TextClip(
        text=wrapped_text,
        font_size=40,
        color="black",
        font="DejaVuSans", 
        text_align="left"
    )
    
    try:
        avatar = ImageClip(AVATAR_IMAGE).resized(width=70).with_position((40, 30))
    except Exception:
        avatar = ColorClip(size=(70, 70), color=(150, 150, 150)).with_position((40, 30))

    user_txt = TextClip(
        text="r/AskReddit • u/StoryTeller",
        font_size=28,
        color="#787C7E", 
        font="DejaVuSans-Bold"
    ).with_position((130, 50)) 

    box_height = 30 + 70 + 20 + txt_clip.h + 40
    bg_box = ColorClip(size=(box_width, int(box_height)), color=(255, 255, 255))
    
    txt_clip = txt_clip.with_position((40, 120))

    reddit_group = CompositeVideoClip(
        [bg_box, avatar, user_txt, txt_clip], 
        size=(box_width, int(box_height))
    )
    
    reddit_group = reddit_group.with_start(start_time).with_duration(duration)
    reddit_group = reddit_group.with_position(("center", "center"))
    
    return reddit_group

def generate_whisper_subtitles(audio_file, script_text):
    print("🎙️ Transcribing audio with Whisper ('small' model + prompt injection)...")
    model = whisper.load_model("small") 
    
    result = model.transcribe(
        audio_file, 
        language="de", 
        initial_prompt=script_text
    )
    
    subtitle_clips = []
    for segment in result['segments']:
        start = segment['start']
        end = segment['end']
        text = segment['text'].strip()
        
        reddit_clip = create_reddit_overlay(text, start, end - start)
        subtitle_clips.append(reddit_clip)
        
    return subtitle_clips

# =========================================
# MAIN PIPELINE
# =========================================

async def main():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    video_title = data.get("video_title", "Reddit_Story")
    full_text = data.get("story_text", "")
    
    output_video_path = f"../FLASK/videos/Reddit - {video_title}.mp4"
    os.makedirs("../videos_mixed", exist_ok=True)

    # 1. ONE SINGLE TTS API REQUEST
    print("🔊 Erstelle Voiceover in EINEM API-Call...")
    await generate_gemini_tts(full_text, VOICE_NARRATOR, FULL_AUDIO_FILE)
    
    final_audio = AudioFileClip(FULL_AUDIO_FILE)

    # 2. Transcribe and generate Reddit Box Subtitles
    subtitle_clips = generate_whisper_subtitles(FULL_AUDIO_FILE, full_text)

    # 3. Assemble Video
    print("🎬 Rendere finales Video...")
    gameplay_bg = get_random_gameplay(final_audio.duration)
    
    final_video = CompositeVideoClip(
        [gameplay_bg] + subtitle_clips,
        size=(WIDTH, HEIGHT)
    ).with_audio(final_audio)

    # 4. Render
    final_video.write_videofile(
        output_video_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="fast"
    )
    print(f"✅ Video erfolgreich gespeichert: {output_video_path}")

if __name__ == "__main__":
    asyncio.run(main())