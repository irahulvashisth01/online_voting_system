<<<<<<< HEAD
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import sqlite3
import bcrypt
import os
from werkzeug.utils import secure_filename


# ✅ FIRST create app
app = Flask(__name__)
app.secret_key = "supersecretkey"

# ✅ THEN configure upload folder
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password BLOB NOT NULL,
        face_encoding BLOB,
        has_voted INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        party_name TEXT NOT NULL,
        photo TEXT,
        party_symbol TEXT,
        total_votes INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password BLOB NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS election (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status INTEGER DEFAULT 0
    )
    """)

    # Default admin
    cursor.execute("SELECT * FROM admin WHERE username=?", ("admin",))
    if not cursor.fetchone():
        hashed = bcrypt.hashpw("admin123".encode("utf-8"), bcrypt.gensalt())
        cursor.execute(
            "INSERT INTO admin (username, password) VALUES (?, ?)",
            ("admin", hashed)
        )

    # Default election row
    cursor.execute("SELECT * FROM election")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO election (status) VALUES (0)")

    conn.commit()
    conn.close()

# ================= ADMIN =================

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM admin WHERE username=?", (username,))
        admin = cursor.fetchone()
        conn.close()

        if admin and bcrypt.checkpw(password.encode("utf-8"), admin[1]):
            session["admin_id"] = admin[0]
            return redirect(url_for("admin_dashboard"))
        return "Invalid Admin Credentials"

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidates")
    candidates = cursor.fetchall()
    cursor.execute("SELECT status FROM election")
    status = cursor.fetchone()[0]
    conn.close()

    return render_template("admin_dashboard.html", candidates=candidates, status=status)


@app.route("/admin/add_candidate", methods=["POST"])
def add_candidate():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    name = request.form["name"]
    party = request.form["party"]

    photo_file = request.files["photo"]
    symbol_file = request.files["symbol"]

    photo_filename = None
    symbol_filename = None

    # Save candidate photo
    if photo_file and photo_file.filename != "":
        photo_filename = secure_filename(photo_file.filename)
        photo_path = os.path.join(app.config["UPLOAD_FOLDER"], photo_filename)
        photo_file.save(photo_path)

    # Save party symbol
    if symbol_file and symbol_file.filename != "":
        symbol_filename = secure_filename(symbol_file.filename)
        symbol_path = os.path.join(app.config["UPLOAD_FOLDER"], symbol_filename)
        symbol_file.save(symbol_path)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO candidates (name, party_name, photo, party_symbol)
        VALUES (?, ?, ?, ?)
    """, (name, party, photo_filename, symbol_filename))

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete/<int:id>")
def delete_candidate(id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM candidates WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/start")
def start_election():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE election SET status=1")
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/stop")
def stop_election():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE election SET status=0")
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

# ================= HOME =================

@app.route("/")
def home():
    return render_template("index.html")

# ================= REGISTER =================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]
        face_image = request.form.get("face_image")

        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        face_encoding_bytes = None

        if face_image:
            image_data = base64.b64decode(face_image.split(',')[1])
            np_arr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if img is None:
                return "Invalid image format!"

            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(img)

            if len(face_locations) == 0:
                return "No face detected!"

            encoding = face_recognition.face_encodings(img, face_locations)[0]
            face_encoding_bytes = pickle.dumps(encoding)

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO voters (name, email, phone, password, face_encoding) VALUES (?, ?, ?, ?, ?)",
                (name, email, phone, hashed_pw, face_encoding_bytes)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return "Email already exists!"

        conn.close()
        return redirect(url_for("login"))

    return render_template("register.html")

# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM voters WHERE email=?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and bcrypt.checkpw(password.encode("utf-8"), user[1]):
            session["user_id"] = user[0]
            return redirect(url_for("dashboard"))

        return "Invalid credentials"

    return render_template("login.html")



# ================= VOTE =================

@app.route("/vote/<int:candidate_id>")
def vote(candidate_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM election")
    if cursor.fetchone()[0] == 0:
        conn.close()
        return "Election is stopped!"

    cursor.execute("SELECT has_voted FROM voters WHERE id=?", (user_id,))
    if cursor.fetchone()[0] == 1:
        conn.close()
        return "You have already voted!"

    cursor.execute("UPDATE candidates SET total_votes = total_votes + 1 WHERE id=?", (candidate_id,))
    cursor.execute("UPDATE voters SET has_voted = 1 WHERE id=?", (user_id,))

    conn.commit()
    conn.close()

    return "Vote Cast Successfully!"

# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidates")
    candidates = cursor.fetchall()
    cursor.execute("SELECT has_voted FROM voters WHERE id=?", (session["user_id"],))
    has_voted = cursor.fetchone()[0]
    conn.close()

    return render_template("dashboard.html", candidates=candidates, has_voted=has_voted)

# ================= RESULTS =================

@app.route("/results")
def results():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, total_votes FROM candidates")
    candidates = cursor.fetchall()
    cursor.execute("SELECT status FROM election")
    status = cursor.fetchone()[0]
    conn.close()

    if status == 1:
        return "Results available only after election is stopped!"

    winner = max(candidates, key=lambda x: x[1]) if candidates else None

    return render_template("results.html", candidates=candidates, winner=winner)

# ================= LOGOUT =================

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ================= MAIN =================
if __name__ == "__main__":
    init_db()
=======
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import sqlite3
import bcrypt
import os
from werkzeug.utils import secure_filename


# ✅ FIRST create app
app = Flask(__name__)
app.secret_key = "supersecretkey"

# ✅ THEN configure upload folder
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password BLOB NOT NULL,
        face_encoding BLOB,
        has_voted INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        party_name TEXT NOT NULL,
        photo TEXT,
        party_symbol TEXT,
        total_votes INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password BLOB NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS election (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status INTEGER DEFAULT 0
    )
    """)

    # Default admin
    cursor.execute("SELECT * FROM admin WHERE username=?", ("admin",))
    if not cursor.fetchone():
        hashed = bcrypt.hashpw("admin123".encode("utf-8"), bcrypt.gensalt())
        cursor.execute(
            "INSERT INTO admin (username, password) VALUES (?, ?)",
            ("admin", hashed)
        )

    # Default election row
    cursor.execute("SELECT * FROM election")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO election (status) VALUES (0)")

    conn.commit()
    conn.close()

# ================= ADMIN =================

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM admin WHERE username=?", (username,))
        admin = cursor.fetchone()
        conn.close()

        if admin and bcrypt.checkpw(password.encode("utf-8"), admin[1]):
            session["admin_id"] = admin[0]
            return redirect(url_for("admin_dashboard"))
        return "Invalid Admin Credentials"

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidates")
    candidates = cursor.fetchall()
    cursor.execute("SELECT status FROM election")
    status = cursor.fetchone()[0]
    conn.close()

    return render_template("admin_dashboard.html", candidates=candidates, status=status)


@app.route("/admin/add_candidate", methods=["POST"])
def add_candidate():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    name = request.form["name"]
    party = request.form["party"]

    photo_file = request.files["photo"]
    symbol_file = request.files["symbol"]

    photo_filename = None
    symbol_filename = None

    # Save candidate photo
    if photo_file and photo_file.filename != "":
        photo_filename = secure_filename(photo_file.filename)
        photo_path = os.path.join(app.config["UPLOAD_FOLDER"], photo_filename)
        photo_file.save(photo_path)

    # Save party symbol
    if symbol_file and symbol_file.filename != "":
        symbol_filename = secure_filename(symbol_file.filename)
        symbol_path = os.path.join(app.config["UPLOAD_FOLDER"], symbol_filename)
        symbol_file.save(symbol_path)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO candidates (name, party_name, photo, party_symbol)
        VALUES (?, ?, ?, ?)
    """, (name, party, photo_filename, symbol_filename))

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete/<int:id>")
def delete_candidate(id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM candidates WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/start")
def start_election():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE election SET status=1")
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/stop")
def stop_election():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE election SET status=0")
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

# ================= HOME =================

@app.route("/")
def home():
    return render_template("index.html")

# ================= REGISTER =================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]
        face_image = request.form.get("face_image")

        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        face_encoding_bytes = None

        if face_image:
            image_data = base64.b64decode(face_image.split(',')[1])
            np_arr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if img is None:
                return "Invalid image format!"

            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(img)

            if len(face_locations) == 0:
                return "No face detected!"

            encoding = face_recognition.face_encodings(img, face_locations)[0]
            face_encoding_bytes = pickle.dumps(encoding)

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO voters (name, email, phone, password, face_encoding) VALUES (?, ?, ?, ?, ?)",
                (name, email, phone, hashed_pw, face_encoding_bytes)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return "Email already exists!"

        conn.close()
        return redirect(url_for("login"))

    return render_template("register.html")

# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM voters WHERE email=?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and bcrypt.checkpw(password.encode("utf-8"), user[1]):
            session["user_id"] = user[0]
            return redirect(url_for("dashboard"))

        return "Invalid credentials"

    return render_template("login.html")



# ================= VOTE =================

@app.route("/vote/<int:candidate_id>")
def vote(candidate_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM election")
    if cursor.fetchone()[0] == 0:
        conn.close()
        return "Election is stopped!"

    cursor.execute("SELECT has_voted FROM voters WHERE id=?", (user_id,))
    if cursor.fetchone()[0] == 1:
        conn.close()
        return "You have already voted!"

    cursor.execute("UPDATE candidates SET total_votes = total_votes + 1 WHERE id=?", (candidate_id,))
    cursor.execute("UPDATE voters SET has_voted = 1 WHERE id=?", (user_id,))

    conn.commit()
    conn.close()

    return "Vote Cast Successfully!"

# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidates")
    candidates = cursor.fetchall()
    cursor.execute("SELECT has_voted FROM voters WHERE id=?", (session["user_id"],))
    has_voted = cursor.fetchone()[0]
    conn.close()

    return render_template("dashboard.html", candidates=candidates, has_voted=has_voted)

# ================= RESULTS =================

@app.route("/results")
def results():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, total_votes FROM candidates")
    candidates = cursor.fetchall()
    cursor.execute("SELECT status FROM election")
    status = cursor.fetchone()[0]
    conn.close()

    if status == 1:
        return "Results available only after election is stopped!"

    winner = max(candidates, key=lambda x: x[1]) if candidates else None

    return render_template("results.html", candidates=candidates, winner=winner)

# ================= LOGOUT =================

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ================= MAIN =================
if __name__ == "__main__":
    init_db()
    app.run(debug=True)