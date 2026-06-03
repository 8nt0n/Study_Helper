import os
import sys
import json
import subprocess
from pathlib import Path


def run_pipeline(folder_name, outline_text):
    """
    Wechselt in den Ordner, sucht das venv und führt die main.py 
    mit der Outline als Command-Line-Argument aus.
    """
    current_dir = Path.cwd()
    project_path = current_dir / folder_name

    print(f"\n=========================================")
    print(f"🚀 Starte Pipeline für: {folder_name}")
    print(f"📋 Outline: \"{outline_text[:50]}...\"")
    print(f"=========================================")

    if not project_path.exists():
        print(f"❌ Ordner '{folder_name}' existiert nicht unter: {project_path}")
        return False

    # Pfad zum Python-Interpreter im venv bestimmen (Cross-Platform)
    if os.name == "nt":  # Windows
        python_executable = project_path / "venv" / "Scripts" / "python.exe"
    else:  # Mac / Linux
        python_executable = project_path / "venv" / "bin" / "python"

    main_script = project_path / "main.py"

    # Validierung
    if not python_executable.exists():
        print(f"❌ Kein venv gefunden in: {python_executable}")
        return False
    
    if not main_script.exists():
        print(f"❌ Keine main.py gefunden in: {main_script}")
        return False

    try:
        # Wir übergeben outline_text als zusätzliches Element in der Liste.
        # Das landet in der main.py als sys.argv[1]
        subprocess.run(
            [str(python_executable), str(main_script), outline_text],
            cwd=str(project_path),
            check=True
        )
        print(f"✅ {folder_name} erfolgreich beendet!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"💥 Fehler beim Ausführen von {folder_name}: {e}")
        return False
    
async def main():
    json_path = Path("content.json")
    if not json_path.exists():
        print(f"❌ 'content.json' wurde nicht im Hauptverzeichnis gefunden!")
        import sys
        sys.exit(1) # <--- Auch hier harter Abbruch

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Schleife durch alle Elemente in der JSON
    for item in data.get("elements", []):
        video_type = item.get("type")
        outline = item.get("outline", "")

        # Ordnernamen-Mapping (falls dein Typ Bindestriche hat, die Ordner aber Unterstriche nutzen)
        folder_name = video_type.replace("-", "_")

        # Ausführen
        run_pipeline(folder_name, outline)

    print("\n🎉 Alle Videos aus der content.json wurden stur durchgeballert!")

if __name__ == "__main__":
    import asyncio  # <--- Sicherstellen, dass asyncio importiert ist
    asyncio.run(main())  # <--- Das startet die async main() korrekt!