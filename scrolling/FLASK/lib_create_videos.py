import sys
import subprocess
from pathlib import Path

def run_script(script_path):
    # Macht aus dem relativen "../" Pfad einen absoluten Pfad 
    # (z.B. /home/ich/.../video_library_test/lib_generate_content.py)
    abs_path = script_path.resolve()

    print(f"\n{'#'*50}")
    print(f"🎬 Starte Phase: {abs_path.name}")
    print(f"{'#'*50}\n")

    if not abs_path.exists():
        print(f"❌ Skript nicht gefunden unter: {abs_path}")
        return False

    try:
        # Wir übergeben jetzt abs_path! Dadurch kann sich der Prozess nicht mehr verlaufen.
        subprocess.run(
            [sys.executable, str(abs_path)],
            cwd=str(abs_path.parent),
            check=True
        )
        print(f"\n✅ {abs_path.name} erfolgreich abgeschlossen!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n🛑 ABBRUCH! Fehler in {abs_path.name} (Exit-Code {e.returncode})")
        return False

def main():
    print("🚀 Vollautomatische Content-Fabrik wird gestartet...")

    # Pfade relativ zu dieser Datei (run_all.py) definieren
    # Wir nehmen an, run_all.py liegt im Ordner FLASK/
    base_dir = Path(__file__).resolve().parent.parent 
    
    content_script = base_dir / "lib_generate_content.py"
    video_script = base_dir / "lib_generate_videos.py"

    # --- Phase 1: Content & Outlines generieren ---
    if not run_script(content_script):
        sys.exit(1)

    # --- Phase 2: Videos rendern & Quizzes erstellen ---
    if not run_script(video_script):
        sys.exit(1)

    print("\n" + "="*50)
    print("🎉 JEDER EINZELNE BANGER IST FERTIG! DIE PIPELINE STEHT! 💸")
    print("="*50)

if __name__ == "__main__":
    main()