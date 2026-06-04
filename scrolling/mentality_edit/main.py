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

# Load the environment configurations
load_dotenv()

# Delete all .wav files
for wav_file in Path.cwd().glob("*.wav"):
    wav_file.unlink()

# =========================================
# CONFIG
# =========================================

JSON_FILE = "script.json"
MODERATOR_IMAGE = "moderator.png"
GAST_IMAGE = "gast.png"
BASS_SOUND = "bass.mp3"
GAMEPLAY_FOLDER = "../gameplay/"

# portrait
WIDTH = 1080
HEIGHT = 1920

VOICE_MODERATOR = "Puck"   
VOICE_GAST = "Charon"      

BASS_EVERY = 2
FONT_SIZE = 75


API_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
if not API_KEYS and os.getenv("GEMINI_API_KEY"):
    API_KEYS = [os.getenv("GEMINI_API_KEY")]

current_key_index = 0

print("🤖 Lade Whisper Modell (Small)...")
whisper_model = whisper.load_model("small")

if len(sys.argv) > 1:
    OUTLINE = sys.argv[1]
    print(f"📥 Outline erfolgreich via Argument empfangen!")
else:
    print("FEHLER: Kein argument übergeben")
    sys.exit(-1)


# =========================================
# TEXT-GENERIERUNG (MIT KEY-ROTATION, ist so semi gegen die AGBS)
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
            # Prüfen auf Rate-Limits oder Erschöpfung der Quota
            if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text or "Quota" in error_text:
                if len(API_KEYS) > 1:
                    current_key_index = (current_key_index + 1) % len(API_KEYS)
                    print(f"🔄 Text-Gen Quota erschöpft. Wechsle zu Key #{current_key_index + 1}...")
                    time.sleep(1)
                else:
                    print("❌ Quota erschöpft und keine weiteren Backup-Keys vorhanden!")
                    raise e
            elif "400" in error_text or "401" in error_text or "403" in error_text:
                # Bei Key-Fehlern ebenfalls versuchen zu rotieren
                if len(API_KEYS) > 1:
                    current_key_index = (current_key_index + 1) % len(API_KEYS)
                    print(f"🔄 Key-Fehler festgestellt. Probiere Backup-Key #{current_key_index + 1}...")
                else:
                    raise e
            else:
                raise e


# =========================================
# Generate Script
# =========================================

with open("../project_text.txt", "r", encoding="utf-8") as user_text_file:
    USERTEXT = user_text_file.read()

PROMPT = """
Systemrolle:
Du bist ein Experte für virale, zynische Podcast-Edits im Stil von "Lost, relatable Genz Tiktoker" und Tech-Bro-Satire. Du verwandelst lehrreiche Inhalte in extrem kontrastreiche, absurde Dialoge voller Tech-Bro gelaber und schwarzem Humor, Beginne direkt mit den themen aus der outline: KEINE EINLEITUNG IN DAS THEMA, NUR REINE FAKTEN UND TROLLING DURCH DEN GAST

Die Charaktere:

Der Host:
Aufrichtig, ruhig und absolut sachlich. Er erklärt komplexe wissenschaftliche oder gesellschaftliche Dinge in zwei klaren, leicht verständlichen Sätzen. Er ist der klassische „Straight Man“.

Der Gast:
Ein witziger absolut überzogener Tech-Bro. Er ist chronisch online, und hat manchmal einen (witzig übertriebenen) Gottkomplex. Seine Antworten sind kurz (ca. 5 bis 12 Wörter). Fluchen und vulgäre Beleidigungen sind für den Comedy-Effekt ausdrücklich erwünscht. Achte darauf das die Antworten von ihm immer witzig und absurd sind, Humor zielgruppe sind jugendliche social media nutzer also greife da aktuelle themen auf.
Wörter die er benutzten könnte: "Sigma-Grindset", "Low Performer", "NPC", "Steuerhinterziehung", "Moggen", "Let him cook", "W-Rizz", "Insiderhandel" (für ihn nicht als Verbrechen sondern als Lifehack)

Die Regel:
Die Aussagen des Gasts sollen die rationale Logik des Hosts auf eine witzige und absurd dumme weise kontern.

Ausgabe:
Nur valides JSON. Keine Einleitung, keine Erklärungen, keine LaTeX-Formeln. Der Text muss absolut für Text-to-Speech (TTS) optimiert sein: Keine Abkürzungen, keine Sonderzeichen, Zahlen und Symbole müssen als Wort ausgeschrieben werden (z.B. "CO zwei" statt "CO2", "Prozent" statt "%"). Füge immer die tts anweisung "[energetic but annoyed, very expressive, social media]" beim gast hinzu

Vorlage für die Nutzereingabe:
Lehrtext: [USERTEXT]

Aufgabe:
Erstelle einen Dialog mit 2 Gesprächswechseln im JSON-Format.
WICHTIG: ERKLÄRE NICHT ALLES AUS DEM NUTZER TEXT. halte dich strikt an die themen dieser Outline:
[OUTLINE]

JSON-Schema:
{
"video_title": "string",
"script": [
{ "speaker": "Host", "line": "string" },
{ "speaker": "Guest", "line": "string" }
]
}



Beispielausgabe (Thema: Photosynthese)

{
"video_title": "NUR NPCs BRAUCHEN SAUERSTOFF",
"script": [
{
"speaker": "Host",
"line": "Die Pflanze spaltet tatsächlich Wassermoleküle und setzt dabei Sauerstoff als Nebenprodukt frei. Deshalb haben wir überhaupt erst Luft zum Atmen."
},
{
"speaker": "Guest",
"line": "[energetic but annoyed, very expressive, social media] Atmen ist für leute ohne Sigma-Grindset"
},
{
"speaker": "Host",
"line": "In der zweiten Phase, dem Calvin-Zyklus, verwandelt die Pflanze Kohlenstoffdioxid und Energie in Glukose. Pflanzen sind somit die wichtigsten Produzenten für fast alle Nahrungsketten."
},
{
"speaker": "Guest",
"line": "[energetic but annoyed, very expressive, social media] Und ich verwandle Kaffee und puren Hass in Durchfall..."
}
]
}


Beispielausgabe 2 (Thema: Schwarze Löcher)
{
"video_title": "SCHWARZE LÖCHER SIND CRINGE",
"script": [
{
"speaker": "Host",
"line": "Schwarze Löcher sind Regionen der Raumzeit, in denen die Gravitation so stark ist, dass nichts, nicht einmal das Licht, entkommen kann, sobald es den Ereignishorizont überschreitet."
},
{
"speaker": "Guest",
"line": "[energetic but annoyed, very expressive, social media] Wie die praktikanten in meinem Keller... die werden auch NIE entkommen"
},
{
"speaker": "Host",
"line": "Der Ereignishorizont ist dabei keine physische Oberfläche, sondern eine unumkehrbare Grenze. Alles, was sie einmal überschreitet, ist für immer verloren."
},
{
"speaker": "Guest",
"line": "[energetic but annoyed, very expressive, social media] Grenzen existieren nicht in MEINEM Kopf, DODGE COIN TO THE MOON"
}
]
}
"""

PROMPT = PROMPT.replace("[USERTEXT]", USERTEXT)
PROMPT = PROMPT.replace("[OUTLINE]", OUTLINE)
print("📝 Generiere Video-Script (ausfallsicher)...")

ai_response = generate_text_robust(PROMPT, model_name="gemini-3.5-flash", temperature=0.8)

with open(JSON_FILE, "w", encoding="utf-8") as out_file:
    out_file.write(ai_response)


# =========================================
# Generate Quiz
# =========================================

with open(JSON_FILE, "r", encoding="utf-8") as f:
    script_data = json.load(f)

video_title = script_data.get("video_title", "sigma_grind")
QUIZ_FILE = f"../FLASK/videos/Mentality - {video_title}.json"

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

print("🧠 Generiere passendes Quiz (ausfallsicher)...")
quiz_response_text = generate_text_robust(QUIZ_PROMPT, model_name="gemini-3.5-flash", temperature=0.8)

with open(QUIZ_FILE, "w", encoding="utf-8") as q_file:
    q_file.write(quiz_response_text)

print(f"✅ Quiz gespeichert unter: {QUIZ_FILE}")


# =========================================
# TTS ENGINE
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
            async with httpx.AsyncClient(timeout=60.0) as client:
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
                    print(f"🔄 TTS Quota Exhausted. Hot-swapping to Key #{current_key_index + 1}...")
                    await asyncio.sleep(1)  
                else:
                    raise e
            elif status in [400, 401, 403]:
                if len(API_KEYS) > 1:
                    current_key_index = (current_key_index + 1) % len(API_KEYS)
                else:
                    raise ValueError(f"❌ Key failed: {error_text}")
            else:
                raise e

# =========================================
# ADHD SUBTITLES MIT WHISPER TIMINGS
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
                    text=w['word'],
                    font_size=FONT_SIZE,
                    color="white",
                    bg_color="red" if is_highlight else None,
                    stroke_color="black",
                    stroke_width=2, 
                    font="DejaVuSans-Bold",
                    margin=(15, 15)
                ).with_opacity(1)

                if is_highlight:
                    txt = txt.resized(1.15)

                temp_clips.append(txt)

            total_width = sum(c.w for c in temp_clips) + (25 * (len(temp_clips) - 1))
            max_allowed_width = WIDTH - 80
            scale_factor = 1.0
            
            if total_width > max_allowed_width:
                scale_factor = max_allowed_width / total_width
                temp_clips = [c.resized(scale_factor) for c in temp_clips]
                spacing = 25 * scale_factor
                total_width = sum(c.w for c in temp_clips) + (spacing * (len(temp_clips) - 1))
            else:
                spacing = 25

            x = (WIDTH - total_width) / 2

            for txt_clip in temp_clips:
                pos_y = 1050 - (txt_clip.h / 2)
                txt_clip = txt_clip.with_position((x, pos_y))
                txt_clip = txt_clip.with_start(start_time).with_duration(clip_duration)
                clips.append(txt_clip)
                x += txt_clip.w + spacing

    return clips

# =========================================
# GAMEPLAY RANDOMIZER
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
        loops_needed = int(duration // gameplay.duration) + 1
        gameplay = concatenate_videoclips([gameplay] * loops_needed)
        
    max_start_time = max(0, gameplay.duration - duration)
    start_time = random.uniform(0, max_start_time)
    end_time = start_time + duration
    
    gameplay = gameplay.subclipped(start_time, end_time)
    gameplay = gameplay.resized(height=700)
    gameplay = gameplay.cropped(x_center=gameplay.w / 2, width=WIDTH)
    gameplay = gameplay.with_position(("center", 1220))
    
    return gameplay

# =========================================
# SPEAKER CLIP
# =========================================

def create_speaker_clip(image_path, audio, whisper_words):
    bg = ColorClip(size=(WIDTH, HEIGHT), color=(255, 255, 255), duration=audio.duration)
    img = ImageClip(str(image_path)).without_mask()
    img = img.resized(height=1300)

    if img.w > 1080:
        img = img.resized(width=1080)

    img = img.with_position(("center", 0))
    img = img.with_duration(audio.duration)
    img = img.resized(lambda t: 1 + 0.01 * t)

    gameplay = get_random_gameplay(audio.duration)
    subtitles = create_adhd_subtitles_whisper(whisper_words, audio.duration)

    final = CompositeVideoClip(
        [bg, img, gameplay] + subtitles,
        size=(WIDTH, HEIGHT)
    ).with_audio(audio)

    return final

# =========================================
# MENTALITY SCREEN
# =========================================

def create_mentality_clip(audio):
    bg = ColorClip(size=(WIDTH, HEIGHT), color=(0, 0, 0), duration=audio.duration)
    txt = TextClip(
        text="MENTALITY",
        font_size=140,
        color="white",
        font="DejaVuSans-Bold",
        stroke_color="white",
        stroke_width=2,
        margin=(30, 30)
    ).without_mask()

    txt = txt.with_position("center").with_duration(audio.duration)
    final = CompositeVideoClip([bg, txt], size=(WIDTH, HEIGHT)).with_audio(audio)
    return final

# =========================================
# MAIN
# =========================================

async def main():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    clips = []
    counter = 0

    video_title = data.get("video_title", "sigma_grind")
    OUTPUT_VIDEO = f"../FLASK/videos/Mentality - {video_title}.mp4"

    for i, entry in enumerate(data["script"]):
        speaker = entry["speaker"]
        line = entry["line"]

        clean_line = line.replace("[energetic but annoyed, very expressive, social media]", "").strip()

        tts_file = f"tts_{i}.wav"
        voice = VOICE_MODERATOR if speaker == "Host" else VOICE_GAST

        print(f"\n🔊 Generating TTS {i} for {speaker}...")
        await generate_gemini_tts(line, voice, tts_file)
        audio = AudioFileClip(tts_file)

        print(f"🎙️ Transcribing Audio {i} mit Whisper...")
        result = whisper_model.transcribe(
            tts_file, 
            language="de", 
            initial_prompt=clean_line,
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
        
        if not whisper_words:
            print("⚠️ Whisper hat nichts erkannt. Nutze leeren Subtitle-Fallback.")
            whisper_words = [{"word": "...", "start": 0, "end": audio.duration}]

        image_path = MODERATOR_IMAGE if speaker == "Host" else GAST_IMAGE

        clip = create_speaker_clip(image_path, audio, whisper_words)
        clips.append(clip)
        counter += 1

        if counter % BASS_EVERY == 0:
            bass_audio = AudioFileClip(BASS_SOUND)
            mentality_clip = create_mentality_clip(bass_audio)
            clips.append(mentality_clip)

    print("\n🎬 Rendere finales Video. Das kann dauern...")
    final_video = concatenate_videoclips(clips, method="compose")

    final_video.write_videofile(
        OUTPUT_VIDEO,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="fast"
    )
    print(f"✅ Banger fertig: {OUTPUT_VIDEO}")

if __name__ == "__main__":
    asyncio.run(main())