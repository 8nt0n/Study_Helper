import asyncio
import edge_tts
import os
from pydub import AudioSegment
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip
import whisper
import lib_ai_utilities as ai
import random
import shutil
import os

# setup
import tomllib
# Read the TOML file
with open("config.toml", "rb") as f:   # Must be opened in binary mode
    config = tomllib.load(f)

# Access variables
print(config["Api_keys"]["Gemini"])   # your Gemini API KEY
print(config["Api_keys"]["OpenAi"])   # your Open Ai API KEY

google_ai_studio_key = config["Api_keys"]["Gemini"]


def make_video(title, description, analysis, output_path):
    print("generating video...")
    # get the script for a video
    Video_types = ["podcast"]
    Video_type = random.choice(Video_types)
    print("Chose: " + Video_type)
    
    # yeah i tried to keep it multilingual but ig this doesnt work for videos (at least for now) so fuck yall were doing german since its the best language anyways 🇩🇪🇩🇪🦅🦅
    match Video_type:
        case "podcast":
            Prompt = f"""Schreibe mir einen 500 Wörter langen „AI-Podcast“ zum Thema {title} und erkläre {description} in einer einzigen, 500 Wörter langen Antwort.
                        Die Länge des Podcasts ist sehr wichtig, stelle also sicher, dass er mindestens 500 Wörter umfasst.

                        Achte darauf, den Inhalt gut auf 3 Kapitel zu verteilen und die Informationsdichte über das gesamte Skript gleichmäßig zu halten. Beachte, dass deine Antwort später mit Text-to-Speech in Audio umgewandelt wird. Optimiere daher den Text für ein TTS-Programm, zum Beispiel indem du Formeln wie „f(x) = x * c^2“ schreibst als „f von x ist gleich x mal c hoch zwei“ oder Emotionen wie *lacht* durch „haha“ ersetzt.

                        Präsentiere alle Informationen auf eine einfache und gesprächige Weise, ohne dabei wichtige Informationen aus den ursprünglichen Notizen zu verlieren.

                        Behandle alle Inhalte aus dem Dokument, und auch wenn beide Sprecher gerne Witze machen oder humorvolle Bemerkungen einfügen, achte darauf, beim Hauptthema zu bleiben.

                        Beginne den Podcast mit einer kurzen Einführung von Sprecher 1 und strukturiere den Inhalt dann sinnvoll, sodass jedes Thema gut abgedeckt wird.

                        Bitte schreibe nur fortlaufenden Text, ohne zusätzliche Formatierungen wie Aufzählungen oder Tabellen.

                        Schreibe keine Kapitelüberschriften / Markdown oder Ähnliches. Die Sprecher sollen ausschließlich in Dialogform auftreten.

                        Die beiden Sprecher im Podcast sind Tom und Lisa. Schreibe den Podcast im folgenden Format:

                        Tom: Text

                        Lisa: Text

                        Zum Beispiel:

                        Tom: Hallo Lisa, wie geht es dir?

                        Lisa: Gut, und dir?

                        Schreibe nur über: {description}. Der restliche Teil der notizen wird später seperat behandelt.

                        Notizen:

                        {analysis}
                        
                        """



            # prompt gemini for podcast
            Script = ai.prompt_chat_gpt("gpt-3.5-turbo", Prompt)
            print("\n\n\n Script: \n" + Script + "\n\n\n")

            # generate the podcast
            generate_podcast_video(Script, output_path, "mc")
    

def generate_podcast_video(Script, output_path, background_video):
    #------------------------- Ask the user to upload a file ---------------#

    TEXT = Script
    

    tempscript = TEXT.split("\n")
    SCRIPT = [element for element in tempscript if element != '']

    #----------------------- TTS Setup -----------------------#
    VOICES = ['de-DE-AmalaNeural', 'de-DE-ConradNeural']
    OUTPUT_PATH = "audios/"
    # delete previous audios
    shutil.rmtree(OUTPUT_PATH)
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    async def tts(text, output_filename, VOICE):
        communicate = edge_tts.Communicate(text, voice=VOICES[VOICE])
        await communicate.save(output_filename)

    async def process_script(SCRIPT, OUTPUT_PATH):
        for i, line in enumerate(SCRIPT):
            audio_name = f"{i}.mp3"
            if line.startswith('Tom:'):
                line = line[len('Tom: '):]
                await tts(line, os.path.join(OUTPUT_PATH, audio_name), 1)
            elif line.startswith('Lisa:'):
                line = line[len('Lisa: '):]
                await tts(line, os.path.join(OUTPUT_PATH, audio_name), 0)
            
            print(f"Generated audio for line {i}: {line[:30]}...")
            await asyncio.sleep(1.5)  # small delay between requests

    asyncio.run(process_script(SCRIPT, OUTPUT_PATH))

    #----------------- Combine audio files -----------------#
    audio_files = sorted([os.path.join(OUTPUT_PATH, f) for f in os.listdir(OUTPUT_PATH) if f.endswith(".mp3")],
                        key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))

    combined = AudioSegment.from_mp3(audio_files[0])
    for file in audio_files[1:]:
        combined += AudioSegment.from_mp3(file)

    combined_audio_path = "audios/full_audio.wav"
    combined.export(combined_audio_path, format="wav")
    print("✅ Audio combined:", combined_audio_path)

    #----------------- Video background -----------------#
    Background = background_video

    video = VideoFileClip(f'stock_videos/{Background}.mp4')
    audio = AudioFileClip(combined_audio_path)
    video = video.set_audio(audio).subclip(0, audio.duration)

    #----------------- Whisper transcription -----------------#
    print("Transcribing audio with Whisper...")
    model = whisper.load_model("medium")
    result = model.transcribe(combined_audio_path)

    #----------------- Generate SRT and subtitle segments -----------------#
    def format_time(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    subtitles = []
    subtitle_segments = []

    def split_text(text, max_words=5):
        words = text.split()
        return [" ".join(words[i:i+max_words]) for i in range(0, len(words), max_words)]

    for i, segment in enumerate(result["segments"]):
        start = segment["start"]
        end = segment["end"]
        text = segment["text"].strip()
        
        chunks = split_text(text, max_words=5)
        duration_per_chunk = (end - start) / len(chunks) if len(chunks) > 0 else end - start
        
        for j, chunk in enumerate(chunks):
            chunk_start = start + j * duration_per_chunk
            chunk_end = chunk_start + duration_per_chunk
            subtitle_segments.append((chunk_start, chunk_end, chunk))
            
            start_str = format_time(chunk_start)
            end_str = format_time(chunk_end)
            subtitles.append(f"{len(subtitles)+1}\n{start_str} --> {end_str}\n{chunk}\n")

    srt_path = "subtitles.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        f.writelines(subtitles)
    print("✅ Subtitles saved:", srt_path)

    #----------------- Overlay subtitles on video -----------------#
    def create_subtitle_clips(srt_file, video_width):
        clips = []
        for start_time, end_time, txt in subtitle_segments:
            clip = (
                TextClip(
                    txt,
                    fontsize=80,
                    color='white',
                    font='Arial-Bold',
                    stroke_color='red',
                    stroke_width=4,
                    size=(video_width * 0.8, None),  # wrap text to 80% of video width
                    method='caption'                # pygame
                )
                .set_position(('center', 'center'))
                .set_start(start_time)
                .set_end(end_time)
            )
            clips.append(clip)
        return clips

    subtitle_clips = create_subtitle_clips(srt_path, video.w)
    final_video = CompositeVideoClip([video, *subtitle_clips])
    final_video.write_videofile(output_path, codec="libx264")
    print(f"✅ Video with subtitles saved to {output_path}")


