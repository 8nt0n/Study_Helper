import os
import json
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

# Configurations laden
load_dotenv()

# =========================================
# CONFIG & KEY-MANAGEMENT
# =========================================

# Parse multiple project keys from your .env file
API_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
if not API_KEYS and os.getenv("GEMINI_API_KEY"):
    API_KEYS = [os.getenv("GEMINI_API_KEY")]

current_key_index = 0

# =========================================
# ROBUSTE TEXT-GENERIERUNG (MIT KEY-ROTATION)
# =========================================

def generate_text_robust(prompt, model_name="gemini-3.5-flash", temperature=0.7):
    """
    Generiert Text über das Google GenAI SDK und rotiert bei 429er-Fehlern 
    automatisch durch die API-Keys.
    """
    global current_key_index
    
    while True:
        if not API_KEYS:
            print("❌ Keine API-Keys in den Umgebungsvariablen gefunden!")
            sys.exit(1)
            
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
                    print(f"🔄 Content-Splitter Quota erschöpft. Wechsle zu Key #{current_key_index + 1}...")
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
# MAIN PIPELINE
# =========================================

def main():
    print("🧠 Analysiere Rohstoff-Text für die Content-Planung...")

    input_path = Path("project_text.txt")
    output_path = Path("content.json")

    if not input_path.exists():
        print(f"❌ Keine '{input_path.name}' im Hauptordner gefunden!")
        sys.exit(1) # Zwingt run_all.py zum Abbruch

    with open(input_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    PROMPT = f"""
Systemrolle:
Du bist ein Chef-Redakteur für virale Kurzvideos (TikTok, YouTube Shorts, Reels). Deine Aufgabe ist es, einen langen Lehrtext strategisch in eine Serie von packenden, logisch aufeinander aufbauenden Kurzvideos zu zerlegen.

Entscheide für jeden Abschnitt, welches Format besser passt:
1. "mentality-edit": Eignet sich perfekt für trockene Fakten, wissenschaftliche Erklärungen oder gesellschaftliche Phänomene, die man gut durch zynischen Tech-Bro-Humor kontern kann, videos sind ca. 20 sekunden lang also maximal 1 kurzes, leicht verständliches thema
2. "reddit-story": Eignet sich perfekt für emotionale Geschichten, Fallbeispiele, Metaphern oder narrative Abläufe, die wie eine packende Story vorgelesen werden können, MUSS anhand eines realen beispiels / alltagsmoment passieren und mit spannender hook starten, z.B. "letztens war ich im supermarkt einkaufen -> verknüpfung zu thema", videos sind ca. 1min lang also mehr tiefe für ca. 1 bis maximal 2 themen möglich

Aufgabe:
Erstelle aus dem Lehrtext eine Liste von Video-Elementen. Jedes Element braucht den exakten Typ ("mentality-edit" oder "reddit-story") und eine "outline", die als präziser Input für die Videoskript-Generierung dient. Die Outline muss alle relevanten Fakten für dieses eine Video knackig zusammenfassen.

Lehrtext:
{raw_text}

Ausgabe:
Gib NUR valides JSON zurück. Keine Einleitungen, kein Markdown-Inkompatibilitäten, keine Erklärungen.

JSON-Schema:
{{
  "elements": [
    {{
      "type": "mentality-edit" | "reddit-story",
      "outline": "Prägnante Zusammenfassung und Anweisung für dieses spezifische Video"
    }}
  ]
}}
"""

    print("🤖 Gemini splittet den Content auf und generiert Outlines (ausfallsicher)...")
    try:
        # Aufruf über die neue, robuste Funktion
        ai_response = generate_text_robust(PROMPT, model_name="gemini-3.5-flash", temperature=0.7)
        
        # Validieren und speichern
        json_data = json.loads(ai_response)
        
        with open(output_path, "w", encoding="utf-8") as out_f:
            json.dump(json_data, out_f, indent=2, ensure_ascii=False)
            
        print(f"✅ 'content.json' erfolgreich erstellt! ({len(json_data.get('elements', []))} Videos geplant)")

    except Exception as e:
        print(f"💥 Kritischer Fehler bei der JSON-Generierung: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()