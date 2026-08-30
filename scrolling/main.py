import os
import json
import asyncio
import base64
import httpx
from moviepy import *
import wave
import random
from dotenv import load_dotenv
from pathlib import Path
import google.generativeai as genai
import whisper 
import sys
import time

load_dotenv()

for wav_file in Path.cwd().glob("*.wav"):
    wav_file.unlink()

# =========================================
# CONFIG
# =========================================

JSON_FILE = "script.json"
FULL_AUDIO_FILE = "full_audio.wav"

BEATS_FOLDER = "beats"
VIDEO_CLIPS_FOLDER = "video-clip"

# TikTok portrait
WIDTH = 1080
HEIGHT = 1920

VOICE_NARRATOR = "Charon"      
FONT_SIZE = 85

API_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
if not API_KEYS and os.getenv("GEMINI_API_KEY"):
    API_KEYS = [os.getenv("GEMINI_API_KEY")]

current_key_index = 0

print("Lade Whisper Modell (Small)...")
whisper_model = whisper.load_model("small")

if len(sys.argv) > 1:
    OUTLINE = sys.argv[1]
    print(f"Outline erfolgreich via Argument empfangen!")
else:
    print("FEHLER: Kein argument übergeben")
    sys.exit(-1)


def generate_text_robust(prompt, model_name="gemini-3.5-flash", temperature=0.85):
    global current_key_index
    
    while True:
        if not API_KEYS:
            raise ValueError("❌ Keine API-Keys in den Umgebungsvariablen gefunden!")
            
        active_key = API_KEYS[current_key_index]
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
                    print(f"Text-Gen Quota erschöpft. Wechsle zu Key #{current_key_index + 1}...")
                    time.sleep(1)
                else:
                    print("Quota erschöpft und keine weiteren Backup-Keys vorhanden!")
                    raise e
            elif "400" in error_text or "401" in error_text or "403" in error_text:
                if len(API_KEYS) > 1:
                    current_key_index = (current_key_index + 1) % len(API_KEYS)
                    print(f"Key-Fehler festgestellt. Probiere Backup-Key #{current_key_index + 1}...")
                else:
                    raise e
            else:
                raise e


# =========================================
# GENERATE SCRIPT
# =========================================

with open("../project_text.txt", "r", encoding="utf-8") as user_text_file:
    USERTEXT = user_text_file.read()

PROMPT = """
Systemrolle:
Du bist ein genialer Songwriter für absolut unangenehme, maximal cringe Deutschrap-Tracks von einem "Gangster-Rap-Opa", der versucht, in der Hood zu flexen. 
Du nimmst die harten wissenschaftlichen Fakten aus dem Lehrtext und verwandelst sie in gereimte, peinliche Rap-Bars. 

Stil-Elemente:
- Benutze exzessiv peinlichen Gen-Z-Slang (Digga, Bro, Rizz, Sigma, Skibidi, Gyatt, Wallah, Macher, Goofy)
- Kombiniere das mit klassischen Rentner-Themen (Rheuma, Heizdecke, Gebiss, Rente, Stützstrümpfe, Dr. Müller-Wohlfahrt)
- Jede Zeile muss sich reimen (AABB oder ABAB)! Es muss wie ein schlechter, rhythmischer Rap-Song klingen.
- Keine Einleitungen, der Text startet sofort mit dem ersten Verse!

Text-To-Speech Optimierung:
Das Skript wird vorgelesen! Keine Abkürzungen, keine Emojis, Symbole und Zahlen MÜSSEN komplett als Wort ausgeschrieben werden (z.B. "Prozent" statt "%", "Zweiundzwanzig" statt "22").

Ausgabe:
Nur valides JSON. Keine Erklärungen.

Vorlage für die Nutzereingabe:
Lehrtext: [USERTEXT]

Aufgabe:
Erstelle das Rap-Skript im JSON-Format. Bringe die Rap-Bars in einem einzigen durchgehenden Textblock ("lyrics_text") unter. Halte dich strikt an diese Outline:
[OUTLINE]

JSON-Schema:
{
  "video_title": "string (z.B. SIGMA_OPA_FLEX)",
  "lyrics_text": "Yo, check das aus, der Opa flext im Heizdecke-Modus... (Der komplette Rap-Song ohne Zeilenumbrüche)"
}
"""

PROMPT = PROMPT.replace("[USERTEXT]", USERTEXT).replace("[OUTLINE]", OUTLINE)
print("Generiere Cringe-Opa Rap-Lyrics...")

ai_response = generate_text_robust(PROMPT, model_name="gemini-3.5-flash", temperature=0.85)

with open(JSON_FILE, "w", encoding="utf-8") as out_file:
    out_file.write(ai_response)


# =========================================
# GENERATE QUIZ
# =========================================

print("Generiere Rap-Quiz (ausfallsicher)...")
QUIZ_PROMPT = """
Systemrolle:
Erstelle basierend auf dem folgendem Text ein kurzes Social-Media-Quiz mit 3 Fragen im JSON-Format. 
Ausgabe NUR valides JSON.

JSON-Schema:
{
  "quiz_title": "Opa Rap Quiz",
  "questions": [
    {
      "question": "Fragetext...",
      "options": ["A", "B", "C", "D"],
      "correct_answer_index": 0
    }
  ]
}
"""
QUIZ_PROMPT = QUIZ_PROMPT.replace("[USERTEXT]", ai_response)
quiz_response_text = generate_text_robust(QUIZ_PROMPT, model_name="gemini-3.5-flash", temperature=0.7)

with open(JSON_FILE, "r", encoding="utf-8") as f:
    script_data = json.load(f)
video_title = script_data.get("video_title", "Opa_Rap_Banger")

QUIZ_FILE = f"../FLASK/videos/Rap - {video_title}.json"
with open(QUIZ_FILE, "w", encoding="utf-8") as q_file:
    q_file.write(quiz_response_text)


# =========================================
# TTS ENGINE (REST API)
# =========================================

async def generate_gemini_tts(text, voice_name, output_filename):
    global current_key_index
    
    while True:
        if not API_KEYS:
            raise ValueError("❌ Keine API Keys gefunden!")
            
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
                audio_bytes = base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
                
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
                    print(f"TTS Quota erschöpft. Swappe zu Key #{current_key_index + 1}...")
                    await asyncio.sleep(1)  
                else:
                    raise e
            elif status in [400, 401, 403]:
                if len(API_KEYS) > 1:
                    current_key_index = (current_key_index + 1) % len(API_KEYS)
                else:
                    raise ValueError(f"Key defekt: {error_text}")
            else:
                raise e


# =========================================
# VIDEO CLIPS BACKGROUND
# =========================================

def get_video_clips_background(duration):

    clips_dir = Path(VIDEO_CLIPS_FOLDER)
    video_files = list(clips_dir.glob("*.mp4")) + list(clips_dir.glob("*.mov"))
    
    if not video_files:
        raise ValueError(f"❌ Keine .mp4 oder .mov Videos im Ordner '{VIDEO_CLIPS_FOLDER}' gefunden!")
        
    selected_clips = []
    current_duration = 0.0

    pool = video_files.copy()
    random.shuffle(pool)
    last_clip_path = None
    
    while current_duration < duration:
        if not pool:
            print("🔄 Alle Video-Clips wurden einmal gespielt. Starte neue Runde...")
            pool = video_files.copy()
            random.shuffle(pool)
            
            if len(pool) > 1 and pool[0] == last_clip_path:
                swap_idx = random.randint(1, len(pool) - 1)
                pool[0], pool[swap_idx] = pool[swap_idx], pool[0]
        
        random_clip_path = pool.pop(0)
        last_clip_path = random_clip_path
        
        clip = VideoFileClip(str(random_clip_path))
        clip = clip.without_audio()

        if (clip.w / clip.h) < (WIDTH / HEIGHT):
            clip = clip.resized(width=WIDTH)
        else:
            clip = clip.resized(height=HEIGHT)
            
        clip = clip.cropped(x_center=clip.w / 2, y_center=clip.h / 2, width=WIDTH, height=HEIGHT)
        
        selected_clips.append(clip)
        current_duration += clip.duration
        
    final_bg = concatenate_videoclips(selected_clips)
    final_bg = final_bg.subclipped(0, duration)
    
    return final_bg


# =========================================
# RANDOM BEAT
# =========================================

def get_random_beat(duration):
    beats_dir = Path(BEATS_FOLDER)
    beat_files = list(beats_dir.glob("*.mp3")) + list(beats_dir.glob("*.wav"))
    
    if not beat_files:
        print(f"⚠️ Keine Beats im Ordner '{BEATS_FOLDER}' gefunden! Video wird ohne Beat erstellt.")
        return None
        
    random_beat_path = random.choice(beat_files)
    print(f"🎵 Gewählter Beat: {random_beat_path.name}")
    beat = AudioFileClip(str(random_beat_path))

    if beat.duration < duration:
        loops_needed = int(duration // beat.duration) + 1
        beat = concatenate_audioclips([beat] * loops_needed)
        
    beat = beat.subclipped(0, duration)
    return beat.with_volume_scaled(0.2)


# =========================================
# ADHD SUBTITLES
# =========================================

def create_adhd_subtitles_whisper(whisper_words, audio_duration):
    clips = []
    chunks = [whisper_words[i:i+2] for i in range(0, len(whisper_words), 2)]
    
    for chunk in chunks:
        if not chunk: continue
        chunk_end = chunk[-1]['end']
        
        for i, target_word in enumerate(chunk):
            start_time = target_word['start']
            
            if i + 1 < len(chunk):
                end_time = chunk[i+1]['start']
            else:
                end_time = chunk_end
                
            if end_time <= start_time:
                end_time = start_time + 0.1
                
            clip_duration = end_time - start_time
            temp_clips = []
            
            for j, w in enumerate(chunk):
                is_highlight = (i == j)

                txt = TextClip(
                    text=w['word'].upper(),
                    font_size=FONT_SIZE,
                    color="white",
                    bg_color="red" if is_highlight else None,
                    stroke_color="black",
                    stroke_width=3, 
                    font="DejaVuSans-Bold",
                    margin=(15, 15)
                ).with_opacity(1)

                if is_highlight:
                    txt = txt.resized(1.2)

                temp_clips.append(txt)

            total_width = sum(c.w for c in temp_clips) + (25 * (len(temp_clips) - 1))
            max_allowed_width = WIDTH - 80
            
            if total_width > max_allowed_width:
                scale_factor = max_allowed_width / total_width
                temp_clips = [c.resized(scale_factor) for c in temp_clips]
                spacing = 25 * scale_factor
                total_width = sum(c.w for c in temp_clips) + (spacing * (len(temp_clips) - 1))
            else:
                spacing = 25

            x = (WIDTH - total_width) / 2

            for txt_clip in temp_clips:
                pos_y = 960 - (txt_clip.h / 2)
                txt_clip = txt_clip.with_position((x, pos_y))
                txt_clip = txt_clip.with_start(start_time).with_duration(clip_duration)
                clips.append(txt_clip)
                x += txt_clip.w + spacing

    return clips


# =========================================
# MAIN PIPELINE
# =========================================

async def main():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    lyrics_text = data.get("lyrics_text", "")
    OUTPUT_VIDEO = f"../FLASK/videos/Rap - {video_title}.mp4"

    # 1. Voice Track generieren
    print("\n🔊 Generiere Opa-Rap-Stimme via Gemini...")
    await generate_gemini_tts(lyrics_text, VOICE_NARRATOR, FULL_AUDIO_FILE)
    audio = AudioFileClip(FULL_AUDIO_FILE)

    # 2. Whisper Timings holen
    print("🎙️ Transkribiere Rap-Spur für ADHD-Subtitles...")
    result = whisper_model.transcribe(
        FULL_AUDIO_FILE, 
        language="de", 
        initial_prompt=lyrics_text,
        word_timestamps=True
    )
    
    whisper_words = []
    for segment in result.get('segments', []):
        for w in segment.get('words', []):
            whisper_words.append({
                "word": w["word"].strip(),
                "start": w["start"],
                "end": min(w["end"], audio.duration) 
            })

    # 3. Video-Hintergrund erstellen (Clips statt Bilder/Gameplay)
    print("🎬 Generiere Video-Hintergrund aus Clips...")
    video_bg = get_video_clips_background(audio.duration)
    
    # 4. Audio-Spuren mischen (Stimme + Beat)
    beat_audio = get_random_beat(audio.duration)
    if beat_audio:
        print("🎵 Mixe Hintergrund-Beat mit dem Sprach-Audio...")
        final_audio = CompositeAudioClip([audio, beat_audio])
    else:
        final_audio = audio

    # 5. Subtitles generieren
    subtitles = create_adhd_subtitles_whisper(whisper_words, audio.duration)

    # 6. Komposition & Rendering
    print("\n🎬 Mixe den Rap-Banger zusammen...")
    final_video = CompositeVideoClip(
        [video_bg] + subtitles,
        size=(WIDTH, HEIGHT)
    ).with_audio(final_audio)

    final_video.write_videofile(
        OUTPUT_VIDEO,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="fast"
    )
    print(f"\n🎉 DER TRACK DES JAHRES IST FERTIG: {OUTPUT_VIDEO}")

if __name__ == "__main__":
    asyncio.run(main())