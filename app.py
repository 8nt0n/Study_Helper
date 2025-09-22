from flask import Flask, render_template, render_template_string, request, redirect, url_for, session, g, abort, flash, send_file, send_from_directory, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from markdown2 import markdown

import json
import os
from functools import wraps

import re

import lib_ai_utilities as ai
import lib_video_utilities as video

# setup
import tomllib
# Read the TOML file
with open("config.toml", "rb") as f:   # Must be opened in binary mode
    config = tomllib.load(f)

# Access variables
print(config["Api_keys"]["Gemini"])   # your Gemini API KEY
print(config["Api_keys"]["OpenAi"])   # your Open Ai API KEY


# --- Flask setup ---
app = Flask(__name__)
app.secret_key = "d8c7f84a6b2146d8aebbc35a5e48c1a918f54b34f5e9d6c76a2a1cce2c9e7a92"  # change this in production
google_ai_studio_key = config["Api_keys"]["Gemini"]

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Database helper --- #
DATABASE = "users.db"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)"
        )
        db.commit()

# ===============================================================================
#                                     Index      
# ===============================================================================

# no @login_required bc we need 1 for each case
@app.route("/")
def home():
    # if were logged in
    if "user_id" in session:
        # get all of the project from this user
        db = get_db()
        user_id = session["user_id"]
        projects = db.execute("SELECT * FROM projects WHERE user_id=?", (user_id,)).fetchall()
        # render the dashboard
        return render_template("index.html", Username=session['username'], projects=projects)
    #TODO: else render a generic site
    return "<a href='/login'>Login</a> | <a href='/register'>Register</a>"




# ===============================================================================
#                                User Authentication       
# ===============================================================================


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        try:
            db = get_db()
            db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            db.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "Username already exists!"
        
    else:
        return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    # check if user exists
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect(url_for("home"))
        return "Invalid credentials!"
    # Render the page
    else:
        return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/forgot_password")
def forgot_password():
    return render_template("forgot_password.html")



# ===============================================================================
#                                       Projects    
# ===============================================================================

# just for debugging purposes, not for normal users
@app.route("/projects")
@login_required
def projects():
    db = get_db()
    user_id = session["user_id"]
    projects = db.execute("SELECT * FROM projects WHERE user_id=?", (user_id,)).fetchall()
    print(projects)
    return render_template("projects.html", projects=projects)


@app.route("/projects/create", methods=["GET", "POST"])
@login_required
def create_project():
    if request.method == "POST":
        name = request.form["name"]
        description = request.form["Description"]
        user_id = session["user_id"]
        db = get_db()
        
        # DB Schema
        #
        # CREATE TABLE projects (
        #     id INTEGER PRIMARY KEY AUTOINCREMENT,
        #     name TEXT NOT NULL,
        #     user_id INTEGER NOT NULL,
        #     FOREIGN KEY(user_id) REFERENCES users(id)
        # );

        db.execute("INSERT INTO projects (name, user_id, description, progress) VALUES (?, ?, ?, ?)", (name, user_id, description, 0))
        db.commit()
        return redirect("/")
    return render_template("create_project.html")




# ===============================================================================
#                            Project Details & Uploads
# ===============================================================================


@app.route("/projects/<int:project_id>")
@login_required
def view_project(project_id):
    # if we already extracted the information from the uploaded files
    file_path = os.path.join(
        "uploads",
        f"user_{session['user_id']}",
        f"project_{project_id}",
        "extracted",
        "analysis.txt"
    )


    if os.path.exists(file_path):
        db = get_db()
        user_id = str(session["user_id"])
        # get info abt our project
        project = db.execute(
            "SELECT * FROM projects WHERE id=? AND user_id=?",
            (project_id, user_id)
        ).fetchone()
        if not project:
            abort(403)
        
        content_folder = os.path.join(
            app.config["UPLOAD_FOLDER"],
            f"user_{user_id}",
            f"project_{project_id}",
            "content"
        )

        plan_file = os.path.join(content_folder, "plan.json")
        # get the learning plan
        with open(plan_file, "r") as f:
            plan_data = json.load(f)


        #TODO: Create videos for each subtopic of the plan

        print(project)
        # load everything into the plan
        return render_template("learning_plan.html", project=project, plan=plan_data, User_id = session["user_id"])

    # else render the upload page
    else:
        db = get_db()
        user_id = session["user_id"]
        project = db.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user_id)).fetchone()
        print(project)
        if not project:
            abort(403)
        documents = db.execute("SELECT * FROM documents WHERE project_id=?", (project_id,)).fetchall()
        print(documents)
        return render_template("project.html", project=project, documents=documents, User_id=session["user_id"])

@app.route("/projects/<int:project_id>/upload", methods=["POST"])
@login_required
def upload_file(project_id):
    db = get_db()
    user_id = session["user_id"]
    project = db.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user_id)).fetchone()
    if not project:
        abort(403)

    if "file" not in request.files:
        flash("No file part")
        return redirect(request.url)
    file = request.files["file"]
    if file.filename == "":
        flash("No selected file")
        return redirect(request.url)

    filename = secure_filename(file.filename)
    # Create directories
    user_folder = os.path.join(app.config["UPLOAD_FOLDER"], f"user_{user_id}")
    project_folder = os.path.join(user_folder, f"project_{project_id}")
    os.makedirs(project_folder, exist_ok=True)
    file_path = os.path.join(project_folder, filename)
    file.save(file_path)

    # Save to database
    db.execute("INSERT INTO documents (filename, project_id) VALUES (?, ?)", (filename, project_id))
    db.commit()
    return redirect(url_for("view_project", project_id=project_id))


@app.route("/projects/<int:project_id>/extract")
@login_required
def extract(project_id):
    db = get_db()
    user_id = session["user_id"]

    #--------------- Write a analysis for all the documents with gemini (thx for the free api key guys) ---------------#

    # Make sure project belongs to the logged-in user
    project = db.execute(
        "SELECT * FROM projects WHERE id=? AND user_id=?",
        (project_id, user_id)
    ).fetchone()
    if not project:
        abort(403)



    # Get all document records for this project
    docs = db.execute(
        "SELECT * FROM documents WHERE project_id=?",
        (project_id,)
    ).fetchall()

    # Build absolute file paths for the project’s files
    project_folder = os.path.join(app.config["UPLOAD_FOLDER"], f"user_{user_id}", f"project_{project_id}")
    file_list = [os.path.join(project_folder, doc[1]) for doc in docs]

    # Only include files that exist
    existing_files = [f for f in file_list if os.path.exists(f)]

    text_prompt = "Analyze the provided documents and images in the highest detaill possible. Answer in the language that the media is in"

    gemini_text = None
    if existing_files:
        # Send multimodal request to Gemini
        response = ai.prompt_gemini_multimodal(text_prompt, files=existing_files)

        if response and "candidates" in response:
            gemini_text = response["candidates"][0]["content"]["parts"][0]["text"]

            # Create "extracted" folder
            extracted_folder = os.path.join(project_folder, "extracted")
            os.makedirs(extracted_folder, exist_ok=True)

            # Save Gemini response to a file
            output_file = os.path.join(extracted_folder, "analysis.txt")
            with open(output_file, "w") as f:
                f.write(gemini_text)
        else:
            gemini_text = "No response received from Gemini API. Please check your API key and file paths."
    else:
        gemini_text = "No valid files found to process."


    #--------------- make chapters based of of the extracted content ---------------#
    Prompt = 'You are an AI tutor. I will give you extracted notes from a collection of documents and images. Your job is to design a structured learning plan that teaches everything step by step. Requirements for your output: Return ONLY valid JSON (no explanations, no markdown, no extra text). The JSON must follow this structure: { "chapters": [ { "title": "Chapter Title", "summary": "A short explanation of the key ideas in this chapter, no sentences, just keywords.", "subtopics": [ { "title": "Subtopic 1 Title", "description": "A brief explanation of the subtopic." }, { "title": "Subtopic 2 Title", "description": "A brief explanation of the subtopic." }, { "title": "Subtopic 3 Title", "description": "A brief explanation of the subtopic." } ] } ] } Guidelines: Break the material into 3–6 logical chapters. Each chapter should cover a coherent theme or concept. Each chapter must contain exactly 3 subtopics, with titles and brief descriptions. Titles should be short, clear, and student-friendly. Summaries should be clear enough that a beginner can understand the flow. Answer in the language the analysis is in. Here is the extracted analysis to structure into chapters: <<<ANALYSIS>>>'
    
    # find the file
    file_path = os.path.join(
        "uploads",
        f"user_{session['user_id']}",
        f"project_{project_id}",
        "extracted",
        "analysis.txt"
    )

    content_folder = os.path.join(
        app.config["UPLOAD_FOLDER"],
        f"user_{user_id}",
        f"project_{project_id}",
        "content"
    )

    # if we already have a plan just redirect
    if os.path.isfile(os.path.join(content_folder, "plan.json")):
        return redirect(url_for('view_project', project_id=project_id))

    with open(file_path, 'r') as file:
        # Read the entire content of the file into a string
        content = file.read()

    # append the file to our prompt
    Prompt += content

    Answer =  ai.prompt_gemini(google_ai_studio_key, Prompt)

    print(Answer)

    os.makedirs(content_folder, exist_ok=True)

    plan_file = os.path.join(content_folder, "plan.json")

    clean_answer = Answer.strip()
    clean_answer = re.sub(r"^```json\s*", "", clean_answer)
    clean_answer = re.sub(r"```$", "", clean_answer)

    try:
        plan_data = json.loads(clean_answer)
    except json.JSONDecodeError as e:
        print("Failed to parse cleaned Gemini output:", clean_answer)
        return f"Failed to parse JSON from Gemini: {e}", 500

    with open(plan_file, "w") as f:
        json.dump(plan_data, f, indent=2)  # Save properly as plan.json

    # Render the learning site
    with open(plan_file, "r") as f:
        plan_data = json.load(f)

    return redirect(url_for('view_project', project_id=project_id))


# ===============================================================================
#                            File Handling
# ===============================================================================
@app.route('/view/<path:filepath>')
@login_required
def view_file(filepath):
    db = get_db()

    # Normalize and prevent traversal
    safe_path = os.path.normpath(filepath)
    if ".." in safe_path.split(os.path.sep):
        abort(403)

    # Must start with "uploads/"
    if not safe_path.startswith("uploads" + os.path.sep):
        abort(403)

    parts = safe_path.split(os.path.sep)

    # We expect at least uploads/user_<id>/project_<id>/...
    if len(parts) < 4:
        abort(403)

    try:
        user_folder = parts[1]                # user_<id>
        project_folder = parts[2]             # project_<id>
        project_id = int(project_folder.replace("project_", ""))
    except (ValueError, IndexError):
        abort(403)

    # Check project ownership
    owner = db.execute(
        "SELECT user_id FROM projects WHERE id=?",
        (project_id,)
    ).fetchone()
    if not owner or owner[0] != session["user_id"]:
        abort(403)

    # Build absolute path inside the uploads directory
    absolute_path = os.path.join(app.root_path, safe_path)

    if not os.path.isfile(absolute_path):
        abort(404)

    return send_file(absolute_path)

@app.route("/delete_file/<int:file_id>", methods=["POST"])
@login_required
def delete_file(file_id):
    db = get_db()
    user_id = session["user_id"]

    # Get the document info and project owner
    doc = db.execute(
        """
        SELECT d.filename, d.project_id, p.user_id
        FROM documents d
        JOIN projects p ON d.project_id = p.id
        WHERE d.id = ?
        """,
        (file_id,)
    ).fetchone()

    if not doc or doc[2] != user_id:
        abort(403)  # user doesn’t own this file/project

    # Build the file path
    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        f"user_{user_id}",
        f"project_{doc[1]}",
        doc[0]
    )

    # Delete the file from disk if it exists
    if os.path.exists(file_path):
        os.remove(file_path)

    # Delete the database record
    db.execute("DELETE FROM documents WHERE id=?", (file_id,))
    db.commit()

    flash("File deleted successfully!")
    return redirect(url_for("view_project", project_id=doc[1]))

@app.route('/view_md/<path:filepath>')
@login_required
def view_markdown(filepath):

    db = get_db()

    safe_path = os.path.normpath(filepath)
    if ".." in safe_path.split(os.path.sep):
        abort(403)

    # All markdown files live inside uploads/
    uploads_root = os.path.join(app.root_path, "uploads")
    absolute_path = os.path.join(uploads_root, safe_path)

    parts = safe_path.split(os.path.sep)
    if len(parts) < 2:
        abort(403)

    # Check project ownership
    try:
        project_folder = next(p for p in parts if p.startswith("project_"))
        project_id = int(project_folder.replace("project_", ""))
    except (StopIteration, ValueError):
        abort(403)

    owner = db.execute("SELECT user_id FROM projects WHERE id=?", (project_id,)).fetchone()
    if not owner or owner[0] != session["user_id"]:
        abort(403)

    if not os.path.isfile(absolute_path):
        abort(404)

    # Read and convert markdown to HTML
    with open(absolute_path, "r") as f:
        md_text = f.read()
    html_content = markdown(md_text, extras=["fenced-code-blocks", "tables"])

    # HAHA dear future anton please change this shit before you git commit you cant ship this shit to production ever, no ones gonna hire you you brick
    template = """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Notes</title>
      <style>
        body { font-family: sans-serif; margin: 20px; }
        pre, code { background: #f0f0f0; padding: 4px; border-radius: 4px; }
        h1, h2, h3 { margin-top: 1.2em; }
      </style>
    </head>
    <body>
      {{ content|safe }}
    </body>
    </html>
    """
    return render_template_string(template, content=html_content)


@app.route("/quiz/<path:filepath>")
@login_required
def view_quiz(filepath):
    db = get_db()

    safe_path = os.path.normpath(filepath)
    if ".." in safe_path.split(os.path.sep):
        abort(403)

    uploads_root = os.path.join(app.root_path, "uploads")
    absolute_path = os.path.join(uploads_root, safe_path)

    # Ownership check (same pattern as before)
    parts = safe_path.split(os.path.sep)
    try:
        project_folder = next(p for p in parts if p.startswith("project_"))
        project_id = int(project_folder.replace("project_", ""))
    except (StopIteration, ValueError):
        abort(403)

    owner = db.execute("SELECT user_id FROM projects WHERE id=?", (project_id,)).fetchone()
    if not owner or owner[0] != session["user_id"]:
        abort(403)

    if not os.path.isfile(absolute_path):
        abort(404)

    with open(absolute_path) as f:
        quiz_data = json.load(f)

    # ✅ Normalize here too
    if "quiz" in quiz_data and "questions" not in quiz_data:
        quiz_data["questions"] = quiz_data.pop("quiz")


    return render_template("quiz.html", quiz=quiz_data)

#=================================================================================
#                             Content creation
#=================================================================================

def extract_json(text: str) -> str:
    # Look for ```json ... ``` or plain ``` ... ```
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
        print("Removed JSON fences, cleaned output:\n", cleaned)
        return cleaned

    # No fences detected → just return the text trimmed
    print("No fences detected, returning as-is.")
    return text.strip()


# ---------- helpers (place near top / before routes) ----------
def create_video_for_subtopic(user_id, project_id, chapter_idx, sub_idx, title, description):
    """Create video MP4 and return the viewer URL (url_for view_file)."""
    uploads_root = app.config['UPLOAD_FOLDER']
    # Read analysis
    analysis_path = os.path.join(uploads_root, f"user_{user_id}", f"project_{project_id}", "extracted", "analysis.txt")
    analysis_text = ""
    if os.path.isfile(analysis_path):
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis_text = f.read()

    videos_folder = os.path.join(uploads_root, f"user_{user_id}", f"project_{project_id}", "videos")
    os.makedirs(videos_folder, exist_ok=True)
    output_abs = os.path.join(videos_folder, f"{chapter_idx}_{sub_idx}.mp4")

    # call your existing video creation function
    video.make_video(title, description, analysis_text, output_abs)

    # viewer path expected by view_file (starts with 'uploads/...')
    video_relpath = f"uploads/user_{user_id}/project_{project_id}/videos/{chapter_idx}_{sub_idx}.mp4"
    return url_for('view_file', filepath=video_relpath)

def create_notes_for_subtopic(user_id, project_id, chapter_idx, sub_idx, title, description):
    """Create markdown notes and return viewer url (url_for view_markdown)."""
    uploads_root = app.config['UPLOAD_FOLDER']
    analysis_path = os.path.join(uploads_root, f"user_{user_id}", f"project_{project_id}", "extracted", "analysis.txt")
    analysis_text = ""
    if os.path.isfile(analysis_path):
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis_text = f.read()

    notes_folder = os.path.join(uploads_root, f"user_{user_id}", f"project_{project_id}", "notes")
    os.makedirs(notes_folder, exist_ok=True)
    output_abs = os.path.join(notes_folder, f"{chapter_idx}_{sub_idx}.md")

    prompt = f"""
Create a concise study cheat sheet in Markdown for the subtopic:
"{title}"

Use the following analysis as background:
{analysis_text}

Follow this exact Markdown structure:
# {title}
A short 1–2 sentence overview of the subtopic.

---

## 💡 Key Concepts
- Bullet point 1
- Bullet point 2
- Bullet point 3

---

## 🏷️ Important Terms
- **Term 1**: Short definition
- **Term 2**: Short definition
- **Term 3**: Short definition

---

## ⚡ Quick Facts
- Fact 1
- Fact 2
- Fact 3

---

Guidelines:
- Keep language clear and beginner-friendly.
- Use proper Markdown headings (#, ##) exactly as shown.
- Output ONLY valid Markdown (no extra commentary).
"""
    notes_response = ai.prompt_gemini(google_ai_studio_key, prompt)
    # write response (you already have extract_json for JSON; not needed for md)
    with open(output_abs, "w", encoding="utf-8") as f:
        f.write(notes_response if isinstance(notes_response, str) else str(notes_response))

    notes_relpath = f"user_{user_id}/project_{project_id}/notes/{chapter_idx}_{sub_idx}.md"
    return url_for('view_markdown', filepath=notes_relpath)

def create_quiz_for_subtopic(user_id, project_id, chapter_idx, sub_idx, title, description):
    """Create quiz JSON file and return viewer url (url_for view_quiz)."""
    uploads_root = app.config['UPLOAD_FOLDER']
    analysis_path = os.path.join(uploads_root, f"user_{user_id}", f"project_{project_id}", "extracted", "analysis.txt")
    analysis_text = ""
    if os.path.isfile(analysis_path):
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis_text = f.read()

    quizzes_folder = os.path.join(uploads_root, f"user_{user_id}", f"project_{project_id}", "quizzes")
    os.makedirs(quizzes_folder, exist_ok=True)
    output_abs = os.path.join(quizzes_folder, f"{chapter_idx}_{sub_idx}.json")

    prompt = f"""
    Create a 5-question multiple-choice quiz in valid JSON for the subtopic:
    "{title}"

    Use the following analysis as background:
    {analysis_text}

    Rules:
    - Output ONLY valid JSON.
    - Each question must have:
    - "question": string
    - "options": array of exactly 4 strings
    - "answer": string (must match one of the options)
    """
    resp = ai.prompt_gemini(google_ai_studio_key, prompt)
    cleaned = extract_json(resp)
    try:
        quiz_data = json.loads(cleaned)
    except Exception as e:
        # fallback: try to save raw as error for debugging
        raise RuntimeError(f"Invalid JSON from model: {e}\nRaw response start: {cleaned[:300]}")

    # normalize
    if "quiz" in quiz_data and "questions" not in quiz_data:
        quiz_data = {"questions": quiz_data["quiz"]}

    with open(output_abs, "w", encoding="utf-8") as f:
        json.dump(quiz_data, f, ensure_ascii=False, indent=2)

    quiz_relpath = f"user_{user_id}/project_{project_id}/quizzes/{chapter_idx}_{sub_idx}.json"
    return url_for('view_quiz', filepath=quiz_relpath)


# ---------- update existing form routes to use helpers (keeps backward compatibility) ----------
@app.route("/projects/<int:project_id>/make_video", methods=["POST"])
@login_required
def make_subtopic_video(project_id):
    db = get_db()
    user_id = str(session["user_id"])
    project = db.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user_id)).fetchone()
    if not project:
        abort(403)

    chapter_idx = request.form.get("chapter_idx")
    sub_idx     = request.form.get("sub_idx")
    title       = request.form.get("title")
    description = request.form.get("description")

    # call helper (this may take some time)
    create_video_for_subtopic(user_id, project_id, chapter_idx, sub_idx, title, description)
    flash("Video created successfully!", "success")
    return redirect(url_for("view_project", project_id=project_id))


@app.route("/projects/<int:project_id>/make_notes", methods=["POST"])
@login_required
def make_subtopic_notes(project_id):
    db = get_db()
    user_id = str(session["user_id"])
    project = db.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user_id)).fetchone()
    if not project:
        abort(403)

    chapter_idx = request.form["chapter_idx"]
    sub_idx     = request.form["sub_idx"]
    title       = request.form["title"]
    description = request.form["description"]

    create_notes_for_subtopic(user_id, project_id, chapter_idx, sub_idx, title, description)
    flash("Notes created successfully!", "success")
    return redirect(url_for("view_project", project_id=project_id))


@app.route("/projects/<int:project_id>/make_quiz", methods=["POST"])
@login_required
def make_subtopic_quiz(project_id):
    db = get_db()
    user_id = str(session["user_id"])
    project = db.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user_id)).fetchone()
    if not project:
        abort(403)

    chapter_idx = request.form["chapter_idx"]
    sub_idx     = request.form["sub_idx"]
    title       = request.form["title"]

    create_quiz_for_subtopic(user_id, project_id, chapter_idx, sub_idx, title, "")
    flash("Quiz created successfully!", "success")
    return redirect(url_for("view_project", project_id=project_id))


# ---------- updated api_resource_create (delegates to helpers) ----------
@app.route("/api/projects/<int:project_id>/resource/create", methods=["POST"])
@login_required
def api_resource_create(project_id):
    db = get_db()
    user_id = str(session["user_id"])
    data = request.get_json() or {}
    typ = data.get("type")
    chapter_idx = data.get("chapter_idx")
    sub_idx = data.get("sub_idx")
    title = data.get("title", "")
    description = data.get("description", "")

    # basic validation
    if typ not in ("video", "notes", "quiz"):
        return jsonify({"error": "invalid type"}), 400
    if chapter_idx is None or sub_idx is None:
        return jsonify({"error": "missing indices"}), 400

    # ownership check
    project = db.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user_id)).fetchone()
    if not project:
        return jsonify({"error": "forbidden"}), 403

    try:
        if typ == "video":
            url = create_video_for_subtopic(user_id, project_id, str(chapter_idx), str(sub_idx), title, description)
        elif typ == "notes":
            url = create_notes_for_subtopic(user_id, project_id, str(chapter_idx), str(sub_idx), title, description)
        else:  # quiz
            url = create_quiz_for_subtopic(user_id, project_id, str(chapter_idx), str(sub_idx), title, description)

        return jsonify({"ok": True, "url": url})
    except Exception as e:
        # return message for debugging; in production log and send friendly error
        return jsonify({"error": str(e)}), 500


#==================================================================================
#                                 API
#==================================================================================

def _resource_relpaths(user_id, project_id, chapter_idx, sub_idx):
    """
    Return the three relative paths we use for each resource.
    - video_relpath (used with view_file): starts with 'uploads/...'
    - notes_relpath (used with view_markdown): starts with 'user_...'
    - quiz_relpath (used with view_quiz): starts with 'user_...'
    """
    video_relpath = f"uploads/user_{user_id}/project_{project_id}/videos/{chapter_idx}_{sub_idx}.mp4"
    notes_relpath = f"user_{user_id}/project_{project_id}/notes/{chapter_idx}_{sub_idx}.md"
    quiz_relpath  = f"user_{user_id}/project_{project_id}/quizzes/{chapter_idx}_{sub_idx}.json"
    return video_relpath, notes_relpath, quiz_relpath

@app.route("/api/projects/<int:project_id>/resource/status")
@login_required
def api_resource_status(project_id):
    """
    Query params: type=video|notes|quiz, chapter_idx, sub_idx
    Returns JSON: {exists: bool, url: "..." }
    """
    db = get_db()
    user_id = str(session["user_id"])
    typ = request.args.get("type")
    chapter_idx = request.args.get("chapter_idx")
    sub_idx = request.args.get("sub_idx")

    if typ not in ("video", "notes", "quiz"):
        return jsonify({"error": "invalid type"}), 400
    if chapter_idx is None or sub_idx is None:
        return jsonify({"error": "missing indices"}), 400

    # confirm project ownership
    owner = db.execute("SELECT user_id FROM projects WHERE id=?", (project_id,)).fetchone()
    if not owner or str(owner[0]) != user_id:
        return jsonify({"error": "forbidden"}), 403

    video_relpath, notes_relpath, quiz_relpath = _resource_relpaths(user_id, project_id, chapter_idx, sub_idx)

    uploads_root = os.path.join(app.root_path)
    if typ == "video":
        abs_path = os.path.join(uploads_root, video_relpath)
        exists = os.path.isfile(abs_path)
        url = url_for('view_file', filepath=video_relpath)  # expects uploads/... path
    elif typ == "notes":
        # view_markdown expects path like 'user_x/project_y/notes/..'
        abs_path = os.path.join(app.root_path, "uploads", notes_relpath)  # note: view_markdown adds uploads_root
        exists = os.path.isfile(abs_path)
        url = url_for('view_markdown', filepath=notes_relpath)
    else: # quiz
        abs_path = os.path.join(app.root_path, "uploads", quiz_relpath)
        exists = os.path.isfile(abs_path)
        url = url_for('view_quiz', filepath=quiz_relpath)

    return jsonify({"exists": bool(exists), "url": url})




# --- Main ---
if __name__ == "__main__":
    init_db()
    app.run(debug=True)


