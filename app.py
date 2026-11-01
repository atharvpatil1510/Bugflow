from functools import wraps
from flask import Flask, request, jsonify, render_template_string, session
from flask import Flask, render_template, request, redirect, url_for, flash, session
from db import get_connection
import pickle
import os
from flask import send_from_directory
from werkzeug.utils import secure_filename
import uuid
from flask import send_from_directory
import pandas as pd
import csv
from flask import request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from io import StringIO
from flask import Response
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
# File upload configuration
UPLOAD_FOLDER = os.path.join(app.root_path, "uploads")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB maximum

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Day 4: Permitted issue status transitions

WORKFLOW_TRANSITIONS = {
    "Open": ["In Progress"],
    "In Progress": ["Resolved"],
    "Resolved": ["In Progress"]
}

def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)
    return wrapped_view

app.secret_key = "bugflow-dev-secret-key"


@app.route("/assign-bug/<int:bug_id>", methods=["POST"])
@login_required
def assign_bug(bug_id):
    # Allow only Admin and Project Manager
    role = session.get("user_role", "").strip().lower()

    if role not in ["admin", "project manager"]:
        return (
            "Access denied. Only Admin or Project Manager can assign bugs.",
            403
        )

    # Validate the selected Developer
    assigned_to = request.form.get(
        "assigned_to_user_id", ""
    ).strip()

    if not assigned_to.isdigit():
        return "Please select a valid Developer.", 400

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Confirm that the selected user is a Developer
        cur.execute(
            """
            SELECT user_id
            FROM public.users
            WHERE user_id = %s
              AND LOWER(TRIM(role)) = 'developer'
            """,
            (int(assigned_to),)
        )

        if cur.fetchone() is None:
            return "The selected user is not a valid Developer.", 400

        # Confirm that the bug exists
        cur.execute(
            """
            SELECT id
            FROM public.bug_reports
            WHERE id = %s
            """,
            (bug_id,)
        )

        if cur.fetchone() is None:
            return "Bug not found.", 404

        # Assign the bug to the selected Developer
        cur.execute(
            """
            UPDATE public.bug_reports
            SET assigned_to_user_id = %s
            WHERE id = %s
            """,
            (int(assigned_to), bug_id)
        )

        conn.commit()
        return redirect(url_for("reports"))

    except Exception:
        conn.rollback()
        app.logger.exception("Bug assignment failed")
        return "Could not assign the bug. Check the application logs.", 500

    finally:
        cur.close()
        conn.close()

@app.route("/view-attachment/<int:attachment_id>")
@login_required
def view_attachment(attachment_id):

    # Only Admin and Project Manager can view attachments
    user_role = session.get("user_role", "").strip().lower()

    if user_role not in ["admin", "project manager"]:
        flash("You are not authorized to view attachments.", "error")
        return redirect(url_for("reports"))

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT original_filename, stored_filename
            FROM public.bug_attachments
            WHERE attachment_id = %s
        """, (attachment_id,))

        attachment = cur.fetchone()

        if attachment is None:
            flash("Attachment not found.", "error")
            return redirect(url_for("reports"))

        original_filename = attachment[0]
        stored_filename = attachment[1]

        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            stored_filename,
            as_attachment=False,
            download_name=original_filename
        )

    except Exception as e:
        print("VIEW ATTACHMENT ERROR:", repr(e))
        flash("Unable to open attachment.", "error")
        return redirect(url_for("reports"))

    finally:
        cur.close()
        conn.close()

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip()

        # Public registration can create only Developer or Tester accounts
        allowed_roles = ["Developer", "Tester"]

        if not name or not email or not password or not role:
            return render_template_string(
                REGISTER_PAGE,
                error="Please fill in all fields."
            ), 400

        if len(password) < 8:
            return render_template_string(
                REGISTER_PAGE,
                error="Password must contain at least 8 characters."
            ), 400

        if role not in allowed_roles:
            return render_template_string(
                REGISTER_PAGE,
                error="Please select a valid role."
            ), 400

        password_hash = generate_password_hash(password)
        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                INSERT INTO public.users (name, role, email, password_hash)
                VALUES (%s, %s, %s, %s)
                """,
                (name, role, email, password_hash)
            )
            conn.commit()

            return render_template_string(SUCCESS_PAGE)

        except Exception as e:
            conn.rollback()

            if getattr(e, "pgcode", None) == "23505":
                return render_template_string(
                    REGISTER_PAGE,
                    error="This email is already registered."
                ), 409

            app.logger.exception("Registration failed")
            return render_template_string(
                REGISTER_PAGE,
                error="Registration failed. Please try again."
            ), 500

        finally:
            cur.close()
            conn.close()

    return render_template_string(REGISTER_PAGE, error=None)


REGISTER_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Join BugFlow</title>
<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    min-height: 100vh;
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #080d1b;
    color: #f8fafc;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 30px 16px;
    overflow-x: hidden;
}

body::before, body::after {
    content: "";
    position: fixed;
    width: 330px;
    height: 330px;
    border-radius: 50%;
    filter: blur(100px);
    opacity: .24;
    pointer-events: none;
}

body::before {
    background: #4f46e5;
    top: -100px;
    left: -90px;
}

body::after {
    background: #0891b2;
    right: -100px;
    bottom: -100px;
}

.layout {
    position: relative;
    z-index: 1;
    width: 100%;
    max-width: 1000px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 48px;
    align-items: center;
}

.brand { padding: 20px; }

.logo {
    display: inline-flex;
    align-items: center;
    gap: 12px;
    font-size: 25px;
    font-weight: 800;
    letter-spacing: -.7px;
}

.logo-icon {
    width: 48px;
    height: 48px;
    display: grid;
    place-items: center;
    border-radius: 15px;
    background: linear-gradient(135deg, #6366f1, #06b6d4);
    box-shadow: 0 8px 28px #4f46e155;
    font-size: 24px;
}

.brand h1 {
    font-size: clamp(32px, 4vw, 48px);
    line-height: 1.12;
    letter-spacing: -1.8px;
    margin: 38px 0 18px;
}

.gradient {
    background: linear-gradient(90deg, #818cf8, #67e8f9);
    color: #a5f3fc;
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}

.brand p {
    color: #a6b2c8;
    line-height: 1.8;
    font-size: 15px;
    max-width: 390px;
}

.feature {
    margin-top: 28px;
    color: #dbeafe;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.check {
    width: 30px;
    height: 30px;
    display: grid;
    place-items: center;
    border-radius: 9px;
    background: #172743;
    color: #67e8f9;
}

.card {
    background: rgba(17, 25, 46, .94);
    border: 1px solid #283550;
    border-radius: 24px;
    padding: 34px;
    box-shadow: 0 28px 80px #0006;
}

.card h2 {
    font-size: 28px;
    margin: 0 0 8px;
    letter-spacing: -.7px;
}

.subtitle {
    color: #9ba9c0;
    font-size: 14px;
    margin-bottom: 25px;
}

.field { margin-bottom: 17px; }

label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 8px;
    color: #dce5f5;
}

input, select {
    width: 100%;
    padding: 13px 14px;
    border: 1px solid #34425d;
    border-radius: 11px;
    outline: none;
    background: #0b1326;
    color: #f8fafc;
    font-size: 14px;
    transition: border .2s, box-shadow .2s;
}

input:focus, select:focus {
    border-color: #818cf8;
    box-shadow: 0 0 0 3px #6366f125;
}

input::placeholder { color: #687892; }

button {
    width: 100%;
    margin-top: 8px;
    padding: 14px;
    border: 0;
    border-radius: 11px;
    background: linear-gradient(100deg, #6366f1, #4f46e5 55%, #0891b2);
    color: white;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    transition: transform .2s, filter .2s;
}

button:hover {
    transform: translateY(-2px);
    filter: brightness(1.12);
}

.error {
    padding: 12px;
    border: 1px solid #7f1d1d;
    border-radius: 10px;
    background: #451a1a;
    color: #fecaca;
    font-size: 13px;
    margin-bottom: 18px;
}

.footer {
    margin-top: 22px;
    text-align: center;
    color: #9ba9c0;
    font-size: 13px;
}

a { color: #a5b4fc; text-decoration: none; font-weight: 600; }
a:hover { color: #67e8f9; }

@media (max-width: 720px) {
    .layout { grid-template-columns: 1fr; gap: 24px; max-width: 470px; }
    .brand { padding: 8px 5px; }
    .brand h1 { font-size: 34px; margin-top: 25px; }
    .brand p, .feature { display: none; }
    .card { padding: 25px 20px; }
}
</style>
</head>
<body>
<div class="layout">
    <section class="brand">
        <div class="logo">
            <div class="logo-icon">🐞</div>
            <span>Bug<span class="gradient">Flow</span></span>
        </div>
        <h1>Build better software.<br><span class="gradient">Together.</span></h1>
        <p>Create your account and join a collaborative workspace for tracking bugs, managing issues, and improving software quality.</p>
        <div class="feature"><span class="check">✓</span> Organized defect tracking</div>
        <div class="feature"><span class="check">✓</span> Team collaboration</div>
        <div class="feature"><span class="check">✓</span> A clearer development workflow</div>
    </section>

    <section class="card">
        <h2>Create account</h2>
        <div class="subtitle">Get started with your BugFlow workspace.</div>

        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}

        <form method="POST" action="{{ url_for('register') }}">
            <div class="field">
                <label for="name">Full name</label>
                <input id="name" type="text" name="name"
                       placeholder="Enter your full name"
                       autocomplete="name" maxlength="100" required>
            </div>

            <div class="field">
                <label for="email">Email address</label>
                <input id="email" type="email" name="email"
                       placeholder="you@example.com"
                       autocomplete="email" maxlength="254" required>
            </div>

            <div class="field">
                <label for="password">Password</label>
                <input id="password" type="password" name="password"
                       placeholder="At least 8 characters"
                       minlength="8" autocomplete="new-password" required>
            </div>

            <div class="field">
                <label for="role">Choose your role</label>
                <select id="role" name="role" required>
                    <option value="">Select a role</option>
                    <option value="Developer">Developer</option>
                    <option value="Tester">Tester</option>
                </select>
            </div>

            <button type="submit">Create My Account →</button>
        </form>

        <div class="footer">
            Already have an account? <a href="{{ url_for('login') }}">Sign in</a>
        </div>
    </section>
</div>
</body>
</html>
"""


SUCCESS_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Registration Successful | BugFlow</title>
<style>
* { box-sizing: border-box; }
body {
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    padding: 20px; font-family: 'Segoe UI', Arial, sans-serif;
    background: #080d1b; color: #f8fafc;
}
.card {
    max-width: 460px; width: 100%; padding: 42px 30px;
    border: 1px solid #283550; border-radius: 24px;
    background: #11192e; text-align: center;
    box-shadow: 0 25px 80px #0006;
}
.icon { font-size: 56px; }
h1 { color: #6ee7b7; font-size: 27px; }
p { color: #a6b2c8; line-height: 1.7; }
a {
    display: inline-block; margin-top: 16px; padding: 13px 28px;
    border-radius: 11px; color: white; text-decoration: none;
    font-weight: 700;
    background: linear-gradient(100deg, #6366f1, #0891b2);
}
</style>
</head>
<body>
<div class="card">
    <div class="icon">🎉</div>
    <h1>Registration Successful!</h1>
    <p>Your BugFlow account has been created successfully.</p>
    <p>You can now sign in to continue.</p>
    <a href="{{ url_for('login') }}">Go to Login →</a>
</div>
</body>
</html>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                SELECT user_id, name, role, password_hash
                FROM public.users
                WHERE LOWER(email) = %s
                """,
                (email,)
            )
            user = cur.fetchone()

            if user and check_password_hash(user[3], password):
                role = user[2].strip().lower()

                allowed_roles = [
                    "admin",
                    "project manager",
                    "developer",
                    "tester"
                ]

                if role not in allowed_roles:
                    error = "Your account has an unrecognized role."
                else:
                    session["user_id"] = user[0]
                    session["user_name"] = user[1]
                    session["user_role"] = user[2]

                    return redirect(url_for("dashboard"))

            else:
                error = "Invalid email or password."

        except Exception:
            app.logger.exception("Login failed")
            error = "Login failed. Please try again."

        finally:
            cur.close()
            conn.close()

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">

        <title>Login | BugFlow</title>

        <style>
            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }

            body {
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 25px;
                font-family: "Segoe UI", Arial, sans-serif;
                background: linear-gradient(
                    135deg, #080d20, #1e3a8a, #6d28d9
                );
                background-size: 200% 200%;
                animation: backgroundMove 10s ease infinite;
            }

            @keyframes backgroundMove {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }

            .login-container {
                display: grid;
                grid-template-columns: 1fr 1fr;
                width: 100%;
                max-width: 1000px;
                min-height: 570px;
                overflow: hidden;
                border-radius: 24px;
                background: white;
                box-shadow: 0 25px 70px rgba(0, 0, 0, 0.35);
                animation: appear 0.7s ease;
            }

            @keyframes appear {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            .welcome-panel {
                position: relative;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                justify-content: center;
                padding: 45px;
                color: white;
                background: linear-gradient(
                    145deg, #2563eb, #4f46e5, #7c3aed
                );
            }

            .welcome-panel::before,
            .welcome-panel::after {
                content: "";
                position: absolute;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.09);
            }

            .welcome-panel::before {
                width: 280px;
                height: 280px;
                right: -120px;
                top: -100px;
            }

            .welcome-panel::after {
                width: 230px;
                height: 230px;
                left: -100px;
                bottom: -90px;
            }

            .brand {
                position: relative;
                z-index: 1;
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 65px;
            }

            .brand-icon {
                width: 52px;
                height: 52px;
                display: grid;
                place-items: center;
                border-radius: 15px;
                font-size: 27px;
                background: rgba(255, 255, 255, 0.18);
            }

            .brand h2 {
                font-size: 28px;
                letter-spacing: 0.5px;
            }

            .welcome-content {
                position: relative;
                z-index: 1;
            }

            .welcome-content h1 {
                font-size: clamp(32px, 4vw, 43px);
                line-height: 1.2;
                margin-bottom: 20px;
            }

            .welcome-content p {
                color: #e0e7ff;
                font-size: 15px;
                line-height: 1.8;
            }

            .features {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 27px;
            }

            .feature {
                padding: 10px 12px;
                border-radius: 10px;
                font-size: 12px;
                background: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.18);
            }

            .form-panel {
                display: flex;
                flex-direction: column;
                justify-content: center;
                padding: 50px 42px;
                background: #ffffff;
            }

            .form-panel h2 {
                color: #111827;
                font-size: 30px;
                margin-bottom: 10px;
            }

            .subtitle {
                color: #64748b;
                font-size: 14px;
                line-height: 1.7;
                margin-bottom: 30px;
            }

            .error-message {
                padding: 12px 14px;
                margin-bottom: 20px;
                border-radius: 10px;
                color: #b91c1c;
                background: #fee2e2;
                border: 1px solid #fecaca;
                font-size: 13px;
            }

            .input-group {
                margin-bottom: 22px;
            }

            .input-group label {
                display: block;
                margin-bottom: 9px;
                color: #374151;
                font-size: 13px;
                font-weight: 600;
            }

            .input-group input {
                width: 100%;
                padding: 14px 15px;
                border: 1px solid #dbe2ef;
                border-radius: 11px;
                background: #f8fafc;
                font-size: 14px;
                outline: none;
                transition: 0.25s ease;
            }

            .input-group input:focus {
                border-color: #6366f1;
                background: white;
                box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.12);
            }

            .login-button {
                width: 100%;
                padding: 15px;
                margin-top: 5px;
                border: none;
                border-radius: 11px;
                color: white;
                background: linear-gradient(100deg, #2563eb, #7c3aed);
                box-shadow: 0 7px 18px rgba(79, 70, 229, 0.25);
                font-size: 15px;
                font-weight: 700;
                cursor: pointer;
                transition: transform 0.25s, box-shadow 0.25s;
            }

            .login-button:hover {
                transform: translateY(-2px);
                box-shadow: 0 12px 25px rgba(79, 70, 229, 0.35);
            }

            .register-link {
                margin-top: 26px;
                text-align: center;
                color: #64748b;
                font-size: 13px;
            }

            .register-link a {
                color: #4f46e5;
                font-weight: 700;
                text-decoration: none;
            }

            .register-link a:hover {
                text-decoration: underline;
            }

            @media (max-width: 720px) {
                body {
                    padding: 14px;
                }

                .login-container {
                    grid-template-columns: 1fr;
                    max-width: 460px;
                }

                .welcome-panel {
                    padding: 28px;
                }

                .brand {
                    margin-bottom: 28px;
                }

                .welcome-content h1 {
                    font-size: 31px;
                }

                .form-panel {
                    padding: 35px 27px;
                }
            }

           
        </style>
    </head>

    <body>
        <div class="login-container">

            <section class="welcome-panel">
                <div class="brand">
                    <div class="brand-icon">🐞</div>
                    <h2>BugFlow</h2>
                </div>

                <div class="welcome-content">
                    <h1>Find it.<br>Track it.<br>Fix it.</h1>

                    <p>
                        Welcome to your intelligent software defect
                        tracking workspace. Manage issues, monitor
                        progress, and improve software quality.
                    </p>

                    
                </div>
            </section>

            <section class="form-panel">
                <h2>Welcome Back!</h2>

                <p class="subtitle">
                    Sign in to your BugFlow account to continue.
                </p>

                {% if error %}
                    <div class="error-message">{{ error }}</div>
                {% endif %}

                <form method="POST"
                      action="{{ url_for('login') }}">

                    <div class="input-group">
                        <label for="email">Email Address</label>
                        <input
                            id="email"
                            type="email"
                            name="email"
                            placeholder="Enter your email"
                            autocomplete="email"
                            required>
                    </div>

                    <div class="input-group">
                        <label for="password">Password</label>
                        <input
                            id="password"
                            type="password"
                            name="password"
                            placeholder="Enter your password"
                            autocomplete="current-password"
                            required>
                    </div>

                    <button class="login-button" type="submit">
                        Login to BugFlow →
                    </button>
                </form>

                <div class="register-link">
                    Don't have an account?
                    <a href="{{ url_for('register') }}">
                        Create Account
                    </a>
                </div>
            </section>

        </div>
    </body>
    </html>
    """, error=error)


# Load the trained ML model
with open("models/severity_model.pkl", "rb") as file:
    model = pickle.load(file)


# Load historical bug reports for resolution assistance
historical_bugs = pd.read_csv("data/bug_reports_clean.csv")

resolution_vectorizer = TfidfVectorizer(
    lowercase=True,
    stop_words="english",
    max_features=20000
)

historical_tfidf = resolution_vectorizer.fit_transform(
    historical_bugs["Short Description"]
)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def find_similar_bugs(description, top_n=5):
    query_vector = resolution_vectorizer.transform([description])

    similarities = cosine_similarity(
        query_vector,
        historical_tfidf
    ).flatten()

    top_indices = similarities.argsort()[::-1]
    results = []

    for index in top_indices:
        if similarities[index] <= 0:
            break

        bug = historical_bugs.iloc[index]

        results.append({
            "project": bug.get("Project", "Unknown"),
            "bug_id": bug.get("Bug ID", "N/A"),
            "description": bug.get("Short Description", ""),
            "severity": bug.get("Severity Label", "Unknown"),
            "status": bug.get("Resolution Status", "Unknown"),
            "similarity": round(
                float(similarities[index]) * 100, 2
            )
        })

        if len(results) >= top_n:
            break

    return results





@app.route("/")
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>BugFlow | Defect Tracking</title>

        <style>
            * {
                box-sizing: border-box;
            }

            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #f1f5fb;
                color: #1e293b;
            }

            .navbar {
                background: #111c3a;
                color: white;
                padding: 18px 5%;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 12px;
            }

            .brand {
                font-size: 25px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }

            .brand span {
                color: #60a5fa;
            }

            .nav-label {
                font-size: 13px;
                color: #cbd5e1;
            }

            .hero {
                background: linear-gradient(135deg, #172554, #1d4ed8);
                color: white;
                padding: 42px 5%;
            }

            .hero-content {
                max-width: 1200px;
                margin: auto;
            }

            .hero h1 {
                font-size: 34px;
                margin: 0 0 12px;
            }

            .hero p {
                color: #dbeafe;
                line-height: 1.7;
                max-width: 650px;
                margin: 0;
            }

            .main {
                max-width: 1200px;
                margin: 30px auto;
                padding: 0 22px;
            }

            .welcome {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 15px;
                margin-bottom: 24px;
            }

            .welcome h2 {
                margin: 0 0 7px;
                color: #172554;
            }

            .muted {
                color: #64748b;
                font-size: 14px;
                line-height: 1.6;
            }

            .role-badge {
                display: inline-block;
                padding: 8px 14px;
                background: #dbeafe;
                color: #1d4ed8;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
            }

            .layout {
                display: grid;
                grid-template-columns: minmax(0, 1.5fr) minmax(260px, 1fr);
                gap: 22px;
                align-items: start;
            }

            .card {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 15px;
                padding: 25px;
                box-shadow: 0 6px 20px #0f172a08;
                min-width: 0;
            }

            .card h3 {
                margin: 0 0 8px;
                font-size: 20px;
                color: #172554;
            }

            .card-description {
                color: #64748b;
                font-size: 13px;
                line-height: 1.6;
                margin: 0 0 22px;
            }

            label {
                display: block;
                margin: 15px 0 7px;
                font-size: 13px;
                font-weight: bold;
                color: #334155;
            }

            input, textarea {
                width: 100%;
                padding: 12px 13px;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background: #fbfdff;
                font-family: inherit;
                font-size: 14px;
                outline: none;
                transition: border-color 0.2s, box-shadow 0.2s;
            }

            input:focus, textarea:focus {
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px #3b82f61c;
            }

            textarea {
                resize: vertical;
                min-height: 120px;
            }

            button, .button {
                display: inline-block;
                border: none;
                border-radius: 8px;
                padding: 12px 17px;
                background: #2563eb;
                color: white;
                font-weight: bold;
                font-size: 13px;
                text-decoration: none;
                text-align: center;
                cursor: pointer;
                transition: background 0.2s, transform 0.2s;
            }

            button:hover, .button:hover {
                background: #1d4ed8;
                transform: translateY(-1px);
            }

            .submit-button {
                width: 100%;
                margin-top: 20px;
                padding: 14px;
            }

            .quick-links {
                display: grid;
                gap: 12px;
                margin-top: 22px;
            }

            .quick-link {
                display: flex;
                align-items: center;
                gap: 13px;
                padding: 15px;
                background: #f8faff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                color: #1e40af;
                text-decoration: none;
                transition: background 0.2s, border-color 0.2s;
            }

            .quick-link:hover {
                background: #eff6ff;
                border-color: #93c5fd;
            }

            .link-icon {
                width: 40px;
                height: 40px;
                display: flex;
                justify-content: center;
                align-items: center;
                flex-shrink: 0;
                background: #dbeafe;
                border-radius: 10px;
                font-size: 19px;
            }

            .link-text strong {
                display: block;
                font-size: 13px;
                margin-bottom: 5px;
            }

            .link-text small {
                display: block;
                color: #64748b;
                font-size: 11px;
            }

            .logout-link {
                color: #dc2626;
            }

            .logout-link .link-icon {
                background: #fee2e2;
            }

            .login-actions {
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                margin-top: 20px;
            }

            .secondary-button {
                background: white;
                color: #1d4ed8;
                border: 1px solid #bfdbfe;
            }

            .secondary-button:hover {
                background: #eff6ff;
            }

            .footer {
                text-align: center;
                color: #64748b;
                padding: 25px 15px;
                font-size: 12px;
            }

            @media (max-width: 800px) {
                .layout {
                    grid-template-columns: 1fr;
                }

                .hero h1 {
                    font-size: 27px;
                }
            }

            @media (max-width: 480px) {
                .hero {
                    padding: 30px 20px;
                }

                .main {
                    padding: 0 14px;
                    margin: 20px auto;
                }

                .card {
                    padding: 19px;
                }

                .navbar {
                    padding: 16px 20px;
                }
            }
        </style>
    </head>

    <body>
        <header class="navbar">
            <div class="brand">🐞 Bug<span>Flow</span></div>
            <div class="nav-label">
                INTELLIGENT DEFECT TRACKING SYSTEM
            </div>
        </header>

        <section class="hero">
            <div class="hero-content">
                <h1>Track Bugs. Build Better Software.</h1>
                <p>
                    Report software defects, manage assignments, monitor
                    progress, and help your team deliver more reliable software
                    with BugFlow.
                </p>
            </div>
        </section>

        <main class="main">
            {% if session.get("user_id") %}

                <div class="welcome">
                    <div>
                        <h2>Welcome back, {{ session.get("user_name") }}! 👋</h2>
                        <div class="muted">
                            Manage your bug reports and keep your projects moving.
                        </div>
                    </div>
                    <span class="role-badge">
                        {{ session.get("user_role", "User") }}
                    </span>
                </div>

                <div class="layout">
                    <section class="card">
                        <h3>🐛 Submit a Bug Report</h3>
                        <p class="card-description">
                            Found a problem? Enter the project details and
                            describe the issue so your team can investigate it.
                        </p>

                       
<form action="/report" method="post">
    <label for="project">Project Name</label>
    <input
        id="project"
        name="project"
        placeholder="e.g. Online Shopping Application"
        required
    >

    <label for="title">Bug Title</label>
    <input
        id="title"
        name="title"
        placeholder="Briefly describe the issue"
        required
    >

    <label for="description">Bug Description</label>
    <textarea
        id="description"
        name="description"
        rows="5"
        placeholder="Explain what happened and how to reproduce the issue..."
        required
    ></textarea>

    <!-- Issue Type -->
    <label for="issue_type">Issue Type</label>
    <select id="issue_type" name="issue_type" required>
        <option value="">Select Issue Type</option>
        <option value="Bug">Bug</option>
        <option value="Feature Request">Feature Request</option>
        <option value="Enhancement">Enhancement</option>
        <option value="Technical Debt">Technical Debt</option>
    </select>

    <!-- Severity -->
    <label for="severity">Severity</label>
    <select id="severity" name="severity" required>
        <option value="">Select Severity</option>
        <option value="Critical">Critical</option>
        <option value="High">High</option>
        <option value="Medium">Medium</option>
        <option value="Low">Low</option>
    </select>

    <!-- Priority -->
    <label for="priority">Priority</label>
    <select id="priority" name="priority" required>
        <option value="">Select Priority</option>
        <option value="P1">P1 - Urgent</option>
        <option value="P2">P2 - High</option>
        <option value="P3">P3 - Medium</option>
        <option value="P4">P4 - Low</option>
    </select>

    <!-- Affected Module -->
    <label for="affected_module">Affected Module</label>
    <input
        id="affected_module"
        name="affected_module"
        placeholder="e.g. Login, Payment, Dashboard"
        required
    >

    <!-- Business Impact -->
    <label for="business_impact">Business Impact</label>
    <textarea
        id="business_impact"
        name="business_impact"
        rows="3"
        placeholder="Explain how this issue affects users or business operations..."
        required
    ></textarea>

    <button class="submit-button" type="submit">
        + Submit Bug Report
    </button>
</form>

                    </section>

                    <aside class="card">
                        <h3>Quick Navigation</h3>
                        <p class="card-description">
                            Open a BugFlow feature to continue your work.
                        </p>

                        <div class="quick-links">
                            <a class="quick-link" href="/reports">
                                <span class="link-icon">📋</span>
                                <span class="link-text">
                                    <strong>Bug Reports</strong>
                                    <small>View and manage submitted issues</small>
                                </span>
                            </a>

                            <a class="quick-link" href="/dashboard">
                                <span class="link-icon">📊</span>
                                <span class="link-text">
                                    <strong>Dashboard</strong>
                                    <small>View your project overview</small>
                                </span>
                            </a>

                            <a class="quick-link" href="/similar-bugs">
                                <span class="link-icon">🤖</span>
                                <span class="link-text">
                                    <strong>Resolution Assistance</strong>
                                    <small>Explore similar bug reports</small>
                                </span>
                            </a>

                            <a class="quick-link logout-link" href="/logout">
                                <span class="link-icon">↪</span>
                                <span class="link-text">
                                    <strong>Logout</strong>
                                    <small>End your current session</small>
                                </span>
                            </a>
                        </div>
                    </aside>
                </div>

            {% else %}

                <section class="card">
                    <h2>Welcome to BugFlow</h2>
                    <p class="muted">
                        Please log in or create an account to submit bug
                        reports, track defects, and access your dashboard.
                    </p>

                    <div class="login-actions">
                        <a class="button" href="/login">Login to BugFlow</a>
                        <a class="button secondary-button" href="/register">
                            Create an Account
                        </a>
                    </div>
                </section>

            {% endif %}
        </main>

        <footer class="footer">
            BugFlow · Intelligent Software Defect Tracking System
        </footer>
    </body>
    </html>
    """)


@app.route("/assign-to-sprint/<int:bug_id>", methods=["POST"])
@login_required
def assign_to_sprint(bug_id):

    sprint_id = request.form.get("sprint_id")

    if not sprint_id:
        flash("Please select a sprint.", "error")
        return redirect(url_for("backlog"))

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE public.bug_reports
            SET sprint_id = %s
            WHERE id = %s
              AND sprint_id IS NULL
        """, (sprint_id, bug_id))

        if cur.rowcount == 0:
            conn.rollback()
            flash("Issue not found or already assigned.", "error")
        else:
            conn.commit()
            flash("Issue assigned successfully!", "success")

    except Exception as e:
        conn.rollback()
        print("Assignment Error:", repr(e))
        flash("Unable to assign issue.", "error")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("backlog"))


@app.route("/sprint/<int:sprint_id>")
@login_required
def sprint_details(sprint_id):

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Get sprint information
        cur.execute("""
            SELECT sprint_id, sprint_name, start_date, end_date
            FROM public.sprints
            WHERE sprint_id = %s
        """, (sprint_id,))

        sprint = cur.fetchone()

        if sprint is None:
            return "Sprint not found", 404

        # Get issues assigned to this sprint
        cur.execute("""
            SELECT id, project, title, severity, status
            FROM public.bug_reports
            WHERE sprint_id = %s
            ORDER BY id DESC
        """, (sprint_id,))

        sprint_issues = cur.fetchall()

        # Count completed issues
        cur.execute("""
            SELECT COUNT(*)
            FROM public.bug_reports
            WHERE sprint_id = %s
              AND LOWER(status) IN ('resolved', 'closed')
        """, (sprint_id,))

        completed = cur.fetchone()[0]

        # Count pending issues
        cur.execute("""
            SELECT COUNT(*)
            FROM public.bug_reports
            WHERE sprint_id = %s
              AND LOWER(status) NOT IN ('resolved', 'closed')
        """, (sprint_id,))

        pending = cur.fetchone()[0]

        return render_template(
            "sprint_details.html",
            sprint=sprint,
            issues=sprint_issues,
            completed=completed,
            pending=pending
        )

    except Exception as e:
        conn.rollback()
        print("SPRINT DETAILS ERROR:", repr(e))
        return f"Sprint Details Error: {e}", 500

    finally:
        cur.close()
        conn.close()


@app.route("/sprints", methods=["GET", "POST"])
@login_required
def sprints():

    conn = get_connection()
    cur = conn.cursor()

    try:
        if request.method == "POST":

            sprint_name = request.form.get("sprint_name", "").strip()
            start_date = request.form.get("start_date")
            end_date = request.form.get("end_date")

            if not sprint_name or not start_date or not end_date:
                flash("Please fill all sprint details.", "error")

            else:
                cur.execute("""
                    INSERT INTO public.sprints
                    (sprint_name, start_date, end_date)
                    VALUES (%s, %s, %s)
                """, (sprint_name, start_date, end_date))

                conn.commit()
                flash("Sprint created successfully!", "success")

                return redirect(url_for("sprints"))

        cur.execute("""
            SELECT
                s.sprint_id,
                s.sprint_name,
                s.start_date,
                s.end_date,
                COUNT(b.id) AS total_issues,
                COUNT(b.id) FILTER (
                    WHERE LOWER(b.status) IN ('resolved', 'closed')
                ) AS completed_issues,
                COUNT(b.id) FILTER (
                    WHERE b.id IS NOT NULL
                    AND LOWER(b.status) NOT IN ('resolved', 'closed')
                ) AS pending_issues
            FROM public.sprints s
            LEFT JOIN public.bug_reports b
                ON s.sprint_id = b.sprint_id
            GROUP BY
                s.sprint_id,
                s.sprint_name,
                s.start_date,
                s.end_date
            ORDER BY s.sprint_id DESC
        """)

        sprint_list = cur.fetchall()

        return render_template(
            "sprints.html",
            sprints=sprint_list
        )

    except Exception as e:
        conn.rollback()
        print("SPRINT ERROR:", repr(e))
        return f"Sprint Error: {e}", 500

    finally:
        cur.close()
        conn.close()


@app.route("/backlog")
@login_required
def backlog():

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Fetch unassigned issues
        cur.execute("""
            SELECT id, project, title, severity, status
            FROM public.bug_reports
            WHERE sprint_id IS NULL
            ORDER BY id DESC
        """)
        backlog_issues = cur.fetchall()

        # Fetch all available sprints
        cur.execute("""
            SELECT sprint_id, sprint_name
            FROM public.sprints
            ORDER BY sprint_id DESC
        """)
        sprint_list = cur.fetchall()

        print("Available Sprints:", sprint_list)

        return render_template(
            "backlog.html",
            issues=backlog_issues,
            sprints=sprint_list
        )

    except Exception as e:
        conn.rollback()
        print("BACKLOG ERROR:", repr(e))
        return f"Backlog Error: {e}", 500

    finally:
        cur.close()
        conn.close()

@app.route("/report", methods=["POST"])
@login_required
def report():
    project = request.form.get("project", "").strip()
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()

    # Classification fields
    issue_type = request.form.get("issue_type", "").strip()
    severity = request.form.get("severity", "").strip()
    priority = request.form.get("priority", "").strip()
    affected_module = request.form.get("affected_module", "").strip()
    business_impact = request.form.get("business_impact", "").strip()

    # Allowed dropdown values
    allowed_issue_types = [
        "Bug",
        "Feature Request",
        "Enhancement",
        "Technical Debt"
    ]

    allowed_severities = [
        "Critical",
        "High",
        "Medium",
        "Low"
    ]

    allowed_priorities = ["P1", "P2", "P3", "P4"]

    # Validate required fields
    if not all([
        project, title, description,
        issue_type, severity, priority,
        affected_module, business_impact
    ]):
        return "Please fill in all fields.", 400

    if issue_type not in allowed_issue_types:
        return "Invalid issue type.", 400

    if severity not in allowed_severities:
        return "Invalid severity.", 400

    if priority not in allowed_priorities:
        return "Invalid priority.", 400

    if len(affected_module) > 100:
        return "Affected module must be 100 characters or fewer.", 400

    # Preserve ML severity prediction
    predicted_severity = str(model.predict([description])[0])

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO public.bug_reports
            (
                project,
                title,
                description,
                issue_type,
                severity,
                priority,
                affected_module,
                business_impact,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            project,
            title,
            description,
            issue_type,
            severity,
            priority,
            affected_module,
            business_impact,
            "Open"
        ))

        bug_id = cursor.fetchone()[0]
        connection.commit()

    except Exception:
        connection.rollback()
        app.logger.exception("Could not save bug report")
        return "Could not save bug report. Check application logs.", 500

    finally:
        cursor.close()
        connection.close()

    return render_template_string("""
        <h1>Bug Report Saved Successfully!</h1>

        <p><b>Bug ID:</b> {{ bug_id }}</p>
        <p><b>Project:</b> {{ project }}</p>
        <p><b>Title:</b> {{ title }}</p>
        <p><b>Issue Type:</b> {{ issue_type }}</p>
        <p><b>Selected Severity:</b> {{ severity }}</p>
        <p><b>ML Predicted Severity:</b> {{ predicted_severity }}</p>
        <p><b>Priority:</b> {{ priority }}</p>
        <p><b>Affected Module:</b> {{ affected_module }}</p>
        <p><b>Business Impact:</b> {{ business_impact }}</p>
        <p><b>Status:</b> Open</p>

        <a href="/">Submit another report</a>
        <br><br>
        <a href="/reports">View all reports</a>
    """,
        bug_id=bug_id,
        project=project,
        title=title,
        issue_type=issue_type,
        severity=severity,
        predicted_severity=predicted_severity,
        priority=priority,
        affected_module=affected_module,
        business_impact=business_impact
    )
@app.route("/upload-attachment/<int:bug_id>", methods=["POST"])
@login_required
def upload_attachment(bug_id):

    file = request.files.get("attachment")

    if not file or file.filename == "":
        flash("Please select a file.", "error")
        return redirect("/reports")

    original_filename =secure_filename(file.filename)

    if not original_filename:
        flash("Invalid filename.", "error")
        return redirect("/reports")

    # Allow common document and image formats
    allowed_extensions = {
        "pdf", "png", "jpg", "jpeg",
        "txt", "doc", "docx", "csv", "xlsx"
    }

    extension = original_filename.rsplit(".", 1)[-1].lower()

    if "." not in original_filename or extension not in allowed_extensions:
        flash("This file type is not allowed.", "error")
        return redirect("/reports")

    # Generate a unique stored filename
    stored_filename = f"{uuid.uuid4().hex}.{extension}"
    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        stored_filename
    )

    conn = get_connection()
    cur = conn.cursor()

    try:
        file.save(file_path)

        cur.execute("""
            INSERT INTO public.bug_attachments
            (bug_id, user_id, original_filename, stored_filename)
            VALUES (%s, %s, %s, %s)
        """, (
            bug_id,
            session["user_id"],
            original_filename,
            stored_filename
        ))

        conn.commit()
        flash("Attachment uploaded successfully!", "success")

    except Exception as e:
        conn.rollback()

        if os.path.exists(file_path):
            os.remove(file_path)

        print("Attachment Upload Error:", e)
        flash("Unable to upload attachment.", "error")

    finally:
        cur.close()
        conn.close()

    return redirect("/reports")
@app.route("/add-comment/<int:bug_id>", methods=["POST"])
@login_required
def add_comment(bug_id):

    comment_text = request.form.get("comment_text", "").strip()

    if not comment_text:
        flash("Comment cannot be empty.", "error")
        return redirect("/reports")

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO public.bug_comments
            (bug_id, user_id, comment_text)
            VALUES (%s, %s, %s)
        """, (
            bug_id,
            session["user_id"],
            comment_text
        ))

        conn.commit()
        flash("Comment added successfully!", "success")

    except Exception as e:
        conn.rollback()
        print("Comment Error:", e)
        flash("Unable to add comment.", "error")

    finally:
        cur.close()
        conn.close()

    return redirect("/reports")

@app.route("/reports")
@login_required
def reports():

    search = request.args.get("search", "").strip()
    issue_type_filter = request.args.get("issue_type", "").strip()
    severity_filter = request.args.get("severity", "").strip()
    priority_filter = request.args.get("priority", "").strip()
    affected_module_filter = request.args.get("affected_module", "").strip()

    page = max(request.args.get("page", 1, type=int), 1)
    page_size = 5
    offset = (page - 1) * page_size

    role = session.get("user_role", "").strip().lower()
    user_id = session.get("user_id")

    can_assign = role in ("admin", "project manager")

    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Developer access restriction
        if role == "developer":
            access_filter = "AND br.assigned_to_user_id = %s"
            access_params = (user_id,)
        else:
            access_filter = ""
            access_params = ()

        search_pattern = f"%{search}%"

        filter_conditions = []
        filter_params = []

        if search:
            filter_conditions.append("""
                (
                    br.project ILIKE %s
                    OR br.title ILIKE %s
                    OR br.severity ILIKE %s
                    OR br.status ILIKE %s
                    OR br.issue_type ILIKE %s
                    OR br.priority ILIKE %s
                    OR br.affected_module ILIKE %s
                    OR br.business_impact ILIKE %s
                )
            """)
            filter_params.extend([search_pattern] * 8)

        if issue_type_filter:
            filter_conditions.append("br.issue_type = %s")
            filter_params.append(issue_type_filter)

        if severity_filter:
            filter_conditions.append("br.severity = %s")
            filter_params.append(severity_filter)

        if priority_filter:
            filter_conditions.append("br.priority = %s")
            filter_params.append(priority_filter)

        if affected_module_filter:
            filter_conditions.append("br.affected_module ILIKE %s")
            filter_params.append(f"%{affected_module_filter}%")

        where_clause = (
            " AND ".join(filter_conditions)
            if filter_conditions else "TRUE"
        )

        # Count filtered reports
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM public.bug_reports AS br
            WHERE {where_clause}
            {access_filter}
        """, (*filter_params, *access_params))

        total_reports = cursor.fetchone()[0]

        # Pagination
        total_pages = max(
            1, (total_reports + page_size - 1) // page_size
        )

        page = min(page, total_pages)
        offset = (page - 1) * page_size

        # Fetch bug reports
        cursor.execute(f"""
            SELECT
                br.id,
                br.project,
                br.title,
                br.description,
                br.severity,
                br.status,
                br.created_at,
                br.assigned_to_user_id,
                u.name,
                br.issue_type,
                br.priority,
                br.affected_module,
                br.business_impact
            FROM public.bug_reports AS br
            LEFT JOIN public.users AS u
                ON br.assigned_to_user_id = u.user_id
            WHERE {where_clause}
            {access_filter}
            ORDER BY br.id DESC
            LIMIT %s OFFSET %s
        """, (
            *filter_params,
            *access_params,
            page_size,
            offset
        ))

        rows = cursor.fetchall()

        bug_ids = [bug[0] for bug in rows]

        # Fetch comments
        comments_by_bug = {
            bug_id: [] for bug_id in bug_ids
        }

        if bug_ids:
            cursor.execute("""
                SELECT
                    bc.bug_id,
                    bc.comment_text,
                    u.name,
                    bc.created_at
                FROM public.bug_comments AS bc
                JOIN public.users AS u
                    ON bc.user_id = u.user_id
                WHERE bc.bug_id = ANY(%s)
                ORDER BY bc.created_at DESC
            """, (bug_ids,))

            comment_rows = cursor.fetchall()

            for comment in comment_rows:
                comments_by_bug[comment[0]].append({
                    "text": comment[1],
                    "author": comment[2],
                    "created_at": comment[3]
                })

        # Fetch attachments
        attachments_by_bug = {
            bug_id: [] for bug_id in bug_ids
        }

        if bug_ids:
            cursor.execute("""
                SELECT
                    attachment_id,
                    bug_id,
                    original_filename,
                    stored_filename,
                    uploaded_at
                FROM public.bug_attachments
                WHERE bug_id = ANY(%s)
                ORDER BY uploaded_at DESC
            """, (bug_ids,))

            attachment_rows = cursor.fetchall()

            for attachment in attachment_rows:
                    attachments_by_bug[attachment[1]].append({
                        "id": attachment[0],
                        "filename": attachment[2],
                        "stored_filename": attachment[3],
                        "uploaded_at": attachment[4]
                    })

        # Fetch activity history
        activity_by_bug = {
            bug_id: [] for bug_id in bug_ids
        }

        if bug_ids:
            cursor.execute("""
                SELECT
                    ia.bug_id,
                    ia.old_status,
                    ia.new_status,
                    u.name,
                    ia.activity_message,
                    ia.created_at
                FROM public.issue_activity AS ia
                LEFT JOIN public.users AS u
                    ON ia.user_id = u.user_id
                WHERE ia.bug_id = ANY(%s)
                ORDER BY ia.created_at DESC
            """, (bug_ids,))

            activity_rows = cursor.fetchall()

            for activity in activity_rows:
                activity_by_bug[activity[0]].append({
                    "old_status": activity[1],
                    "new_status": activity[2],
                    "author": activity[3] or "Unknown user",
                    "message": activity[4],
                    "created_at": activity[5]
                })

        # Developer list for assignment
        if can_assign:
            cursor.execute("""
                SELECT user_id, name
                FROM public.users
                WHERE LOWER(TRIM(role)) = 'developer'
                ORDER BY name
            """)
            developers = cursor.fetchall()
        else:
            developers = []

    finally:
        cursor.close()
        connection.close()

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>BugFlow | Bug Reports</title>

        <style>
            * { box-sizing: border-box; }

            body {
                margin: 0;
                padding: 30px;
                font-family: Arial, sans-serif;
                background: #f3f6fc;
                color: #1e293b;
            }

            .container {
                max-width: 1500px;
                margin: auto;
            }

            .header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 15px;
                margin-bottom: 25px;
            }

            h1 {
                margin: 0 0 8px;
                color: #172554;
            }

            .subtitle {
                color: #64748b;
                margin: 0;
            }

            .summary {
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                margin-bottom: 22px;
            }

            .summary-card {
                background: white;
                padding: 17px 22px;
                border-radius: 12px;
                box-shadow: 0 3px 12px #0f172a0b;
                border: 1px solid #e2e8f0;
            }

            .summary-card span {
                display: block;
                color: #64748b;
                font-size: 13px;
                margin-bottom: 7px;
            }

            .summary-card strong {
                font-size: 23px;
                color: #1d4ed8;
            }

            .toolbar {
                display: flex;
                gap: 10px;
                align-items: center;
                flex-wrap: wrap;
                background: white;
                padding: 16px;
                border-radius: 12px 12px 0 0;
                border: 1px solid #e2e8f0;
            }

            input, select, button, .button-link {
                padding: 10px 12px;
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                font-size: 13px;
            }

            input {
                min-width: 230px;
                flex: 1;
            }

            button {
                background: #2563eb;
                color: white;
                border: none;
                cursor: pointer;
                font-weight: bold;
            }

            button:hover {
                background: #1d4ed8;
            }

            .clear-link, .nav-link {
                color: #2563eb;
                text-decoration: none;
                font-weight: bold;
                font-size: 13px;
            }

            .table-card {
                background: white;
                border: 1px solid #e2e8f0;
                border-top: none;
                border-radius: 0 0 12px 12px;
                overflow: hidden;
                box-shadow: 0 5px 20px #0f172a0a;
            }

            .table-scroll {
                width: 100%;
                overflow-x: auto;
            }

            table {
                width: 100%;
                min-width: 1600px;
                border-collapse: separate;
                border-spacing: 0;
                text-align: left;
            }

            thead th {
                background: #172554;
                color: white;
                padding: 16px 14px;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                white-space: nowrap;
            }

            tbody td {
                padding: 15px 14px;
                border-bottom: 1px solid #e9eef5;
                font-size: 13px;
                vertical-align: middle;
            }

            tbody tr:nth-child(even) {
                background: #f8faff;
            }

            tbody tr:hover {
                background: #eef4ff;
            }

            tbody tr:last-child td {
                border-bottom: none;
            }

            .bug-id {
                color: #2563eb;
                font-weight: bold;
                white-space: nowrap;
            }

            .bug-title {
                cursor: pointer;
                color: #1d4ed8;
                font-weight: bold;
                min-width: 190px;
            }

            .bug-title:hover {
                color: #1e40af;
            }

            .toggle-icon {
                margin-left: 6px;
                font-size: 12px;
            }

            .description {
                display: block;
                color: #475569;
                font-size: 12px;
                font-weight: 400;
                margin-top: 9px;
                max-width: 300px;
                line-height: 1.7;
                padding: 10px 12px;
                background: #f8fafc;
                border-left: 3px solid #60a5fa;
                border-radius: 5px;
                overflow-wrap: anywhere;
                white-space: normal;
            }

            .bug-details {
                display: none;
                margin-top: 12px;
                padding: 16px;
                background: #f8fafc;
                border: 1px solid #dbeafe;
                border-radius: 12px;
                max-width: 380px;
            }

            .bug-details.show {
                display: block;
            }

            .bug-time {
                margin-top: 10px;
                color: #64748b;
                font-size: 12px;
            }

            .comments-heading {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin: 16px 0 12px;
            }

            .comments-heading h4 {
                margin: 0;
                color: #172554;
                font-size: 15px;
            }

            .comment-count {
                background: #dbeafe;
                color: #1d4ed8;
                padding: 4px 9px;
                border-radius: 20px;
                font-size: 11px;
                font-weight: bold;
            }

            .comment-card {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 13px;
                margin-bottom: 10px;
            }

            .comment-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 6px;
            }

            .comment-author {
                color: #1d4ed8;
                font-size: 12px;
                font-weight: bold;
            }

            .comment-date {
                color: #94a3b8;
                font-size: 10px;
            }

            .comment-text {
                color: #334155;
                font-size: 12px;
                line-height: 1.6;
                margin: 10px 0 0;
                white-space: pre-wrap;
                overflow-wrap: anywhere;
            }

            .no-comments {
                text-align: center;
                padding: 16px 10px;
                color: #94a3b8;
                background: white;
                border: 1px dashed #cbd5e1;
                border-radius: 9px;
                font-size: 12px;
            }

            .comment-form {
                margin-top: 15px;
                padding: 12px;
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }

            .comment-form textarea {
                width: 100%;
                min-height: 75px;
                padding: 11px;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                resize: vertical;
                font-family: Arial, sans-serif;
                font-size: 12px;
                outline: none;
            }

            .comment-form textarea:focus {
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px #3b82f61a;
            }

            .comment-form button {
                margin-top: 9px;
                padding: 10px 15px;
                border-radius: 7px;
                background: #2563eb;
                color: white;
                font-size: 12px;
            }

            .attachment-section {
                margin-top: 16px;
                padding: 12px;
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }

            .attachment-section h4 {
                margin: 0 0 12px;
                color: #172554;
                font-size: 14px;
            }

            .attachment-item {
                padding: 9px;
                margin-bottom: 7px;
                background: #f8fafc;
                border-radius: 7px;
                overflow-wrap: anywhere;
                font-size: 12px;
            }

            .attachment-item small {
                display: block;
                margin-top: 4px;
                color: #64748b;
            }

            .attachment-form input {
                width: 100%;
                min-width: 0;
                margin-bottom: 9px;
            }

            .attachment-form button {
                padding: 9px 13px;
                font-size: 12px;
            }

            .project {
                font-weight: 600;
                color: #475569;
            }

            .badge {
                display: inline-block;
                padding: 6px 10px;
                border-radius: 20px;
                font-size: 11px;
                font-weight: bold;
                white-space: nowrap;
            }

            .critical {
                background: #fee2e2;
                color: #b91c1c;
            }

            .high {
                background: #ffedd5;
                color: #c2410c;
            }

            .medium {
                background: #dbeafe;
                color: #1d4ed8;
            }

            .low {
                background: #e2e8f0;
                color: #475569;
            }

            .open {
                background: #fef3c7;
                color: #92400e;
            }

            .in-progress {
                background: #dbeafe;
                color: #1e40af;
            }

            .resolved, .closed {
                background: #dcfce7;
                color: #166534;
            }

            .unknown {
                background: #e2e8f0;
                color: #475569;
            }

            .assignee {
                color: #334155;
                font-weight: 600;
                white-space: nowrap;
            }

            .table-form {
                display: flex;
                align-items: center;
                gap: 6px;
                min-width: 190px;
            }

            .table-form select {
                width: 130px;
                min-width: 0;
                background: white;
            }

            .table-form button {
                padding: 10px;
                white-space: nowrap;
            }

            .pagination {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
                flex-wrap: wrap;
                padding: 18px;
                background: white;
                border-top: 1px solid #e2e8f0;
            }

            .pagination-links {
                display: flex;
                gap: 8px;
            }

            .page-button {
                display: inline-block;
                padding: 9px 13px;
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                text-decoration: none;
                color: #1e40af;
                font-size: 13px;
                font-weight: bold;
            }

            .page-button:hover {
                background: #eff6ff;
            }

            .empty {
                padding: 35px;
                text-align: center;
                color: #64748b;
            }

            .footer {
                margin-top: 22px;
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
            }

            @media (max-width: 700px) {
                body {
                    padding: 14px;
                }

                .header h1 {
                    font-size: 23px;
                }

                .toolbar {
                    align-items: stretch;
                }

                input {
                    min-width: 100%;
                }
            }
        </style>
    </head>

    <body>
    <div class="container">

        <div class="header">
            <div>
                <h1>🐞 BugFlow Reports</h1>
                <p class="subtitle">
                    Manage, assign and track software defects
                </p>
            </div>
            <a class="nav-link" href="/">← Back to Dashboard</a>
        </div>

        <div class="summary">
            <div class="summary-card">
                <span>Matching Reports</span>
                <strong>{{ total_reports }}</strong>
            </div>

            <div class="summary-card">
                <span>Current Page</span>
                <strong>{{ page }} / {{ total_pages }}</strong>
            </div>
        </div>

        <form class="toolbar" action="/reports" method="get">

            <input
                type="text"
                name="search"
                placeholder="Search bug reports..."
                value="{{ search }}"
            >

            <select name="issue_type">
                <option value="">All Issue Types</option>
                {% for item in ['Bug', 'Feature Request', 'Enhancement', 'Technical Debt'] %}
                <option value="{{ item }}"
                    {% if issue_type_filter == item %}selected{% endif %}>
                    {{ item }}
                </option>
                {% endfor %}
            </select>

            <select name="severity">
                <option value="">All Severities</option>
                {% for item in ['Critical', 'High', 'Medium', 'Low'] %}
                <option value="{{ item }}"
                    {% if severity_filter == item %}selected{% endif %}>
                    {{ item }}
                </option>
                {% endfor %}
            </select>

            <select name="priority">
                <option value="">All Priorities</option>
                {% for item in ['P1', 'P2', 'P3', 'P4'] %}
                <option value="{{ item }}"
                    {% if priority_filter == item %}selected{% endif %}>
                    {{ item }}
                </option>
                {% endfor %}
            </select>

            <input
                type="text"
                name="affected_module"
                placeholder="Affected Module"
                value="{{ affected_module_filter }}"
            >

            <button type="submit">Apply Filters</button>
            <a class="clear-link" href="/reports">Clear Filters</a>

        </form>

        <div class="table-card">
            <div class="table-scroll">

                <table>
                    <thead>
                        <tr>
                            <th>Bug ID</th>
                            <th>Title / Description</th>
                            <th>Project</th>
                            <th>Issue Type</th>
                            <th>Severity</th>
                            <th>Priority</th>
                            <th>Affected Module</th>
                            <th>Business Impact</th>
                            <th>Status</th>
                            <th>Assigned To</th>

                            {% if can_assign %}
                            <th>Assign Developer</th>
                            {% endif %}

                            <th>Update Status</th>
                        </tr>
                    </thead>

                    <tbody>
                    {% for bug in bugs %}
                        <tr>
                            <td>
                                <span class="bug-id">BUG-{{ bug[0] }}</span>
                            </td>

                            <td>
                                <div class="bug-title"
                                     onclick="toggleBugDetails({{ bug[0] }})">
                                    {{ bug[2] }}
                                    <span class="toggle-icon" id="icon-{{ bug[0] }}">＋</span>
                                </div>

                                <div class="bug-details" id="details-{{ bug[0] }}">

                                    <div class="description">
                                        <strong>Description:</strong>
                                        {{ bug[3] or 'No description available' }}
                                    </div>

                                    <div class="bug-time">
                                        <strong>Created:</strong>
                                        {{ bug[6].strftime('%d %b %Y, %I:%M %p') if bug[6] else 'Not available' }}
                                    </div>

                                    <!-- ACTIVITY HISTORY -->
                                    <hr>

                                    <div class="comments-heading">
                                        <h4>📋 Activity History</h4>
                                        <span class="comment-count">
                                            {{ activity_by_bug.get(bug[0], [])|length }} Activities
                                        </span>
                                    </div>

                                    {% for activity in activity_by_bug.get(bug[0], []) %}
                                        <div class="comment-card">

                                            <div class="comment-header">
                                                <span class="comment-author">
                                                    👤 {{ activity.author }}
                                                </span>

                                                <span class="comment-date">
                                                    {{ activity.created_at.strftime('%d %b %Y · %I:%M %p') if activity.created_at else '' }}
                                                </span>
                                            </div>

                                            <p class="comment-text">
                                                <strong>{{ activity.old_status }}</strong>
                                                →
                                                <strong>{{ activity.new_status }}</strong>
                                            </p>

                                            <p class="comment-text">
                                                {{ activity.message }}
                                            </p>

                                        </div>
                                    {% else %}
                                        <div class="no-comments">
                                            No activity recorded yet.
                                        </div>
                                    {% endfor %}

                                    <!-- COMMENTS -->
                                    <div class="comments-heading">
                                        <h4>💬 Discussion</h4>
                                        <span class="comment-count">
                                            {{ comments_by_bug.get(bug[0], [])|length }} Comments
                                        </span>
                                    </div>

                                    <div class="comments-list">
                                        {% for comment in comments_by_bug.get(bug[0], []) %}
                                            <div class="comment-card">
                                                <div class="comment-header">
                                                    <span class="comment-author">
                                                        👤 {{ comment.author }}
                                                    </span>
                                                    <span class="comment-date">
                                                        {{ comment.created_at.strftime('%d %b %Y · %I:%M %p') if comment.created_at else '' }}
                                                    </span>
                                                </div>
                                                <p class="comment-text">{{ comment.text }}</p>
                                            </div>
                                        {% else %}
                                            <div class="no-comments">
                                                💬 No discussion yet. Be the first to comment!
                                            </div>
                                        {% endfor %}
                                    </div>

                                    <form
                                        class="comment-form"
                                        action="{{ url_for('add_comment', bug_id=bug[0]) }}"
                                        method="POST">

                                        <textarea
                                            name="comment_text"
                                            placeholder="Share an update or discuss this issue..."
                                            required
                                            maxlength="5000"></textarea>

                                        <button type="submit">➤ Post Comment</button>
                                    </form>

                                   
<!-- ATTACHMENTS -->
<div class="attachment-section">
    <h4>📎 Attachments</h4>

    {% for attachment in attachments_by_bug.get(bug[0], []) %}
        <div class="attachment-item">

            📄 {{ attachment.filename }}

            <a href="{{ url_for('view_attachment', attachment_id=attachment.id) }}"
               target="_blank"
               rel="noopener noreferrer"
               class="view-attachment-btn">
                👁️ View File
            </a>

            <small>
                {{ attachment.uploaded_at.strftime('%d %b %Y, %I:%M %p') if attachment.uploaded_at else '' }}
            </small>

        </div>
    {% else %}
        <p class="no-comments">No attachments uploaded yet.</p>
    {% endfor %}

    <form
        class="attachment-form"
        action="{{ url_for('upload_attachment', bug_id=bug[0]) }}"
        method="POST"
        enctype="multipart/form-data">

        <input
            type="file"
            name="attachment"
            accept=".pdf,.png,.jpg,.jpeg,.txt,.doc,.docx,.csv,.xlsx"
            required>

        <button type="submit">📤 Upload Attachment</button>
    </form>
</div>


                                </div>
                            </td>

                            <td>
                                <span class="project">
                                    {{ bug[1] or "Not specified" }}
                                </span>
                            </td>

                            <td>{{ bug[9] or "Not specified" }}</td>

                            <td>
                                {% set sev = (bug[4] or "Unknown")|lower %}
                                <span class="badge
                                    {% if sev == 'critical' %}critical
                                    {% elif sev == 'high' %}high
                                    {% elif sev == 'medium' %}medium
                                    {% elif sev == 'low' %}low
                                    {% else %}unknown{% endif %}">
                                    {{ bug[4] or "Unknown" }}
                                </span>
                            </td>

                            <td>{{ bug[10] or "Not specified" }}</td>
                            <td>{{ bug[11] or "Not specified" }}</td>
                            <td>{{ bug[12] or "Not specified" }}</td>

                            <td>
                                {% set stat = (bug[5] or "Unknown")|lower|replace(" ", "-") %}
                                <span class="badge
                                    {% if stat == 'open' %}open
                                    {% elif stat == 'in-progress' %}in-progress
                                    {% elif stat == 'resolved' %}resolved
                                    {% elif stat == 'closed' %}closed
                                    {% else %}unknown{% endif %}">
                                    {{ bug[5] or "Unknown" }}
                                </span>
                            </td>

                            <td>
                                <span class="assignee">
                                    {{ bug[8] or "Not assigned" }}
                                </span>
                            </td>

                            {% if can_assign %}
                            <td>
                                <form class="table-form"
                                      action="{{ url_for('assign_bug', bug_id=bug[0]) }}"
                                      method="post">

                                    <select name="assigned_to_user_id" required>
                                        <option value="">Choose developer</option>
                                        {% for developer in developers %}
                                        <option value="{{ developer[0] }}"
                                            {% if bug[7] == developer[0] %}selected{% endif %}>
                                            {{ developer[1] }}
                                        </option>
                                        {% endfor %}
                                    </select>

                                    <button type="submit">Assign</button>
                                </form>
                            </td>
                            {% endif %}

                            <td>
                                <form class="table-form"
                                      action="{{ url_for('update_status', bug_id=bug[0]) }}"
                                      method="post">

                                    <select name="status">
                                        <option value="Open"
                                            {% if bug[5] == "Open" %}selected{% endif %}>
                                            Open
                                        </option>

                                        <option value="In Progress"
                                            {% if bug[5] == "In Progress" %}selected{% endif %}>
                                            In Progress
                                        </option>

                                        <option value="Resolved"
                                            {% if bug[5] == "Resolved" %}selected{% endif %}>
                                            Resolved
                                        </option>

                                        <option value="Closed"
                                            {% if bug[5] == "Closed" %}selected{% endif %}>
                                            Closed
                                        </option>
                                    </select>

                                    <button type="submit">Update</button>
                                </form>
                            </td>
                        </tr>

                    {% else %}
                        <tr>
                            <td colspan="{{ 12 if can_assign else 11 }}" class="empty">
                                No matching bug reports found.
                            </td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>

            </div>

            <div class="pagination">
                <span>
                    Showing page {{ page }} of {{ total_pages }}
                </span>

                <div class="pagination-links">
                    {% if page > 1 %}
                    <a class="page-button"
                       href="{{ url_for('reports', search=search, issue_type=issue_type_filter, severity=severity_filter, priority=priority_filter, affected_module=affected_module_filter, page=page-1) }}">
                        ← Previous
                    </a>
                    {% endif %}

                    {% if page < total_pages %}
                    <a class="page-button"
                       href="{{ url_for('reports', search=search, issue_type=issue_type_filter, severity=severity_filter, priority=priority_filter, affected_module=affected_module_filter, page=page+1) }}">
                        Next →
                    </a>
                    {% endif %}
                </div>
            </div>
        </div>

        <div class="footer">
            {% if session.get('user_role', '')|lower in ['admin', 'project manager'] %}
                <a href="{{ url_for('export_csv') }}">Download CSV</a>
            {% endif %}
            <a class="nav-link" href="/">⌂ Home</a>
        </div>

    </div>

    <script>
        function toggleBugDetails(bugId) {
            const details = document.getElementById("details-" + bugId);
            const icon = document.getElementById("icon-" + bugId);

            details.classList.toggle("show");

            if (details.classList.contains("show")) {
                icon.textContent = "−";
            } else {
                icon.textContent = "＋";
            }
        }
    </script>

    </body>
    </html>
    """,
        bugs=rows,
        search=search,
        comments_by_bug=comments_by_bug,
        attachments_by_bug=attachments_by_bug,
        activity_by_bug=activity_by_bug,
        page=page,
        total_pages=total_pages,
        total_reports=total_reports,
        developers=developers,
        can_assign=can_assign,
        issue_type_filter=issue_type_filter,
        severity_filter=severity_filter,
        priority_filter=priority_filter,
        affected_module_filter=affected_module_filter
    )



@app.route("/update-status/<int:bug_id>", methods=["POST"])
@login_required
def update_status(bug_id):

    new_status = request.form.get("status", "").strip()
    user_id = session.get("user_id")

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Get current status and lock the issue during the update
        cur.execute("""
            SELECT status
            FROM public.bug_reports
            WHERE id = %s
            FOR UPDATE
        """, (bug_id,))

        issue = cur.fetchone()

        if issue is None:
            flash("Issue not found.", "error")
            return redirect(url_for("reports"))

        old_status = issue[0]

        # Check permitted transition
        allowed_statuses = WORKFLOW_TRANSITIONS.get(old_status, [])

        if new_status not in allowed_statuses:
            conn.rollback()
            flash(
                f"Invalid transition: {old_status} to {new_status}.",
                "error"
            )
            return redirect(url_for("reports"))

        # Update issue status
        cur.execute("""
            UPDATE public.bug_reports
            SET status = %s
            WHERE id = %s
        """, (new_status, bug_id))

        # Record activity history
        cur.execute("""
            INSERT INTO public.issue_activity
            (bug_id, user_id, old_status, new_status,
             activity_type, activity_message)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            bug_id,
            user_id,
            old_status,
            new_status,
            "STATUS_CHANGE",
            f"Status changed from {old_status} to {new_status}"
        ))

        conn.commit()

        flash("Issue status updated successfully!", "success")

    except Exception as e:
        conn.rollback()
        print("WORKFLOW ERROR:", repr(e))
        flash("Unable to update issue status.", "error")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("reports"))

@login_required
def update_status(bug_id):
    new_status = request.form.get("status", "").strip()

    allowed_statuses = ["Open", "In Progress", "Resolved", "Closed"]

    if new_status not in allowed_statuses:
        return "Invalid status.", 400

    role = session.get("user_role", "").strip().lower()
    user_id = session.get("user_id")

    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Find the bug and its current assignee.
        cursor.execute("""
            SELECT assigned_to_user_id
            FROM public.bug_reports
            WHERE id = %s
        """, (bug_id,))

        bug = cursor.fetchone()

        if not bug:
            return "Bug report not found.", 404

        assigned_user_id = bug[0]

        # Admin and Project Manager can update any bug.
        if role in ["admin", "project manager"]:
            pass

        # Developer can update only bugs assigned to them.
        elif role == "developer":
            if assigned_user_id is None or str(assigned_user_id) != str(user_id):
                return "Access denied. This bug is not assigned to you.", 403

        # Tester can only mark bugs as Resolved.
        elif role == "tester":
            if new_status != "Resolved":
                return "Access denied. Testers can only mark bugs as Resolved.", 403

        else:
            return "Access denied.", 403

        # Update the bug status.
        cursor.execute("""
            UPDATE public.bug_reports
            SET status = %s
            WHERE id = %s
        """, (new_status, bug_id))

        connection.commit()

    except Exception:
        connection.rollback()
        app.logger.exception("Status update failed")
        return "Could not update the bug status. Check application logs.", 500

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("reports"))

@app.route("/export-csv")
def export_csv():
    # User must be logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Only Admin and Project Manager can download CSV
    role = session.get("user_role", "").strip().lower()

    if role not in ["admin", "project manager"]:
        return "Access denied: Only Admin and Project Manager can download CSV.", 403
        

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, project, title, description, severity,
                   status, created_at, assigned_to_user_id
            FROM public.bug_reports
            ORDER BY id
        """)

        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]

        import csv
        import io
        from flask import make_response

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        writer.writerows(rows)

        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = (
            "attachment; filename=bugflow_reports.csv"
        )
        response.headers["Content-Type"] = "text/csv; charset=utf-8"

        return response

    finally:
        cur.close()
        conn.close()



@app.route("/dashboard")
@login_required
def dashboard():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Dashboard overview counts
        # Dashboard overview counts
        cursor.execute("""
            SELECT
                COUNT(*),
                COUNT(*) FILTER (WHERE status = 'Open'),
                COUNT(*) FILTER (WHERE status = 'In Progress'),
                COUNT(*) FILTER (WHERE status = 'Resolved')
            FROM public.bug_reports;
        """)
        totals = cursor.fetchone()

# Bug counts grouped by severity
        cursor.execute("""
            SELECT severity, COUNT(*)
            FROM public.bug_reports
            GROUP BY severity
            ORDER BY COUNT(*) DESC;
        """)
        severity_counts = cursor.fetchall()

        role = session.get("user_role", "").strip().lower()
        user_id = session.get("user_id")

        # Developers see only bugs assigned to them
        if role == "developer":
            cursor.execute("""
                SELECT
                    br.id,
                    br.title,
                    br.project,
                    br.severity,
                    br.status,
                    COALESCE(u.name, 'Unassigned')
                FROM public.bug_reports br
                LEFT JOIN public.users u
                    ON br.assigned_to_user_id = u.user_id
                WHERE br.assigned_to_user_id = %s
                ORDER BY br.created_at DESC
                LIMIT 10;
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT
                    br.id,
                    br.title,
                    br.project,
                    br.severity,
                    br.status,
                    COALESCE(u.name, 'Unassigned')
                FROM public.bug_reports br
                LEFT JOIN public.users u
                    ON br.assigned_to_user_id = u.user_id
                ORDER BY br.created_at DESC
                LIMIT 10;
            """)

        recent_bugs = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BugFlow | Dashboard</title>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
        :root {
            --navy: #142b4a;
            --navy-dark: #0c1e35;
            --blue: #3678f5;
            --blue-light: #eaf1ff;
            --page: #f4f7fc;
            --text: #24334b;
            --muted: #77859a;
            --line: #e4eaf2;
            --white: #ffffff;
            --green: #159b72;
            --red: #e45261;
            --amber: #e5a12b;
            --purple: #8063df;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: "Segoe UI", Arial, sans-serif;
            color: var(--text);
            background: var(--page);
        }

        a {
            text-decoration: none;
        }

        .layout {
            display: flex;
            min-height: 100vh;
        }

        /* LEFT VERTICAL SIDEBAR */
        .sidebar {
            flex: 0 0 235px;
            padding: 26px 16px;
            color: white;
            background: linear-gradient(
                180deg,
                var(--navy),
                var(--navy-dark)
            );
            box-shadow: 4px 0 20px rgba(16, 35, 65, 0.08);
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 11px;
            margin: 0 0 30px;
            padding: 0 8px;
        }

        .brand-icon {
            display: flex;
            width: 43px;
            height: 43px;
            align-items: center;
            justify-content: center;
            border-radius: 13px;
            background: var(--blue);
            font-size: 23px;
        }

        .brand h2 {
            margin: 0;
            color: white;
            font-size: 23px;
        }

        .brand small {
            display: block;
            margin-top: 3px;
            color: #b8c8df;
            font-size: 10px;
            letter-spacing: 1.3px;
        }

        .user-info {
            margin: 0 5px 24px;
            padding: 15px;
            overflow-wrap: anywhere;
            border: 1px solid rgba(255,255,255,.12);
            border-radius: 12px;
            background: rgba(255,255,255,.06);
            color: #d7e3f4;
            font-size: 13px;
            line-height: 1.7;
        }

        .menu-label {
            margin: 0 10px 10px;
            color: #91a6c3;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
        }

        .sidebar nav {
            display: flex;
            flex-direction: column;
            gap: 7px;
        }
/* Expandable bug details */
.bug-details {
    display: none;
    margin-top: 12px;
    padding: 16px;
    background: #f8fafc;
    border: 1px solid #dbeafe;
    border-radius: 12px;
    width: 380px;
    max-width: 100%;
}

.bug-details.show {
    display: block;
}

/* Description panel */
.description {
    display: block;
    color: #475569;
    font-size: 13px;
    line-height: 1.7;
    padding: 12px;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow-wrap: anywhere;
}

/* Created date */
.bug-time {
    margin: 10px 0 16px;
    color: #64748b;
    font-size: 11px;
}

/* Comments heading */
.comments-heading {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 16px 0 12px;
}

.comments-heading h4 {
    margin: 0;
    color: #172554;
    font-size: 15px;
}

.comment-count {
    background: #dbeafe;
    color: #1d4ed8;
    padding: 4px 9px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: bold;
}

/* Individual comment */
.comment-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 13px;
    margin-bottom: 10px;
}

.comment-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
}

.comment-author {
    color: #1d4ed8;
    font-size: 12px;
    font-weight: bold;
}

.comment-date {
    color: #94a3b8;
    font-size: 10px;
}

.comment-text {
    color: #334155;
    font-size: 12px;
    line-height: 1.6;
    margin: 10px 0 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}

.no-comments {
    text-align: center;
    padding: 16px 10px;
    color: #94a3b8;
    background: white;
    border: 1px dashed #cbd5e1;
    border-radius: 9px;
    font-size: 12px;
}

/* Comment input area */
.comment-form {
    margin-top: 15px;
    padding: 12px;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}

.comment-form textarea {
    width: 100%;
    min-height: 75px;
    padding: 11px;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    resize: vertical;
    font-family: Arial, sans-serif;
    font-size: 12px;
    outline: none;
}

.comment-form textarea:focus {
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px #3b82f61a;
}

.comment-form button {
    margin-top: 9px;
    padding: 10px 15px;
    border-radius: 7px;
    background: #2563eb;
    color: white;
    font-size: 12px;
}

.comment-form button:hover {
    background: #1d4ed8;
}
        .sidebar nav a {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 13px;
            border-radius: 9px;
            color: #d6e2f1;
            font-size: 14px;
            transition: .2s ease;
        }

        .sidebar nav a:hover {
            color: white;
            background: rgba(255,255,255,.10);
        }

        .sidebar nav a[href="/dashboard"] {
            color: white;
            background: var(--blue);
            font-weight: 700;
            box-shadow: 0 5px 14px rgba(54,120,245,.25);
        }

        /* MAIN CONTENT */
        .main-content {
            flex: 1;
            min-width: 0;
            padding: 30px;
        }

        .page-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 18px;
            margin-bottom: 25px;
        }

        .eyebrow {
            margin: 0 0 7px;
            color: var(--blue);
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 1.5px;
            text-transform: uppercase;
        }

        .page-header h1 {
            margin: 0;
            color: var(--navy);
            font-size: clamp(25px, 3vw, 32px);
            letter-spacing: -.7px;
        }

        .page-subtitle {
            margin: 8px 0 0;
            color: var(--muted);
            font-size: 14px;
        }

        .primary-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 12px 17px;
            border-radius: 9px;
            color: white;
            background: var(--blue);
            font-size: 13px;
            font-weight: 700;
            box-shadow: 0 5px 14px rgba(54,120,245,.2);
            transition: .2s ease;
        }

        .primary-btn:hover {
            background: #245fce;
            transform: translateY(-1px);
        }

        .section-heading {
            margin: 0 0 15px;
            color: var(--navy);
            font-size: 19px;
        }

        .section-subtitle {
            margin: -8px 0 18px;
            color: var(--muted);
            font-size: 13px;
        }

        /* FOUR HORIZONTAL OVERVIEW CARDS */
        .cards {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 17px;
            margin-bottom: 30px;
        }

        .card {
            position: relative;
            min-width: 0;
            overflow: hidden;
            padding: 21px;
            border: 1px solid var(--line);
            border-radius: 15px;
            background: white;
            box-shadow: 0 5px 20px rgba(27,51,85,.045);
            transition: transform .2s, box-shadow .2s;
        }

        .card:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 25px rgba(27,51,85,.08);
        }

        .card::before {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: var(--blue);
            content: "";
        }

        .card:nth-child(2)::before {
            background: var(--red);
        }

        .card:nth-child(3)::before {
            background: var(--amber);
        }

        .card:nth-child(4)::before {
            background: var(--green);
        }

        .card-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
            margin-bottom: 17px;
        }

        .card h3 {
            margin: 0;
            color: var(--muted);
            font-size: 13px;
            font-weight: 600;
        }

        .card-icon {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 39px;
            height: 39px;
            flex-shrink: 0;
            border-radius: 11px;
            color: var(--blue);
            background: var(--blue-light);
            font-size: 20px;
        }

        .card:nth-child(2) .card-icon {
            color: var(--red);
            background: #fff0f1;
        }

        .card:nth-child(3) .card-icon {
            color: #b77a08;
            background: #fff5df;
        }

        .card:nth-child(4) .card-icon {
            color: var(--green);
            background: #e6f8f1;
        }

        .card h2 {
            margin: 0;
            color: var(--navy);
            font-size: 32px;
            letter-spacing: -1px;
        }

        .card-note {
            margin-top: 7px;
            color: var(--muted);
            font-size: 11px;
        }

        /* CHARTS STACK VERTICALLY */
        .dashboard-sections {
            display: flex;
            flex-direction: column;
            gap: 24px;
        }

        .panel {
            min-width: 0;
            padding: 23px;
            border: 1px solid var(--line);
            border-radius: 15px;
            background: white;
            box-shadow: 0 5px 20px rgba(27,51,85,.04);
        }

        .panel-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 18px;
        }

        .panel-header h2 {
            margin: 0;
            color: var(--navy);
            font-size: 18px;
        }

        .panel-description {
            margin: 6px 0 0;
            color: var(--muted);
            font-size: 12px;
        }

        .chart-container {
            position: relative;
            width: 100%;
            height: 300px;
        }

        /* SEVERITY TABLE */
        .table-wrap {
            width: 100%;
            overflow-x: auto;
            border: 1px solid var(--line);
            border-radius: 11px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
        }

        th, td {
            padding: 14px 16px;
            border-bottom: 1px solid #edf1f7;
            text-align: left;
            vertical-align: middle;
            font-size: 13px;
        }

        th {
            color: #63758d;
            background: #f5f8fd;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: .6px;
            text-transform: uppercase;
            white-space: nowrap;
        }

        tbody tr:last-child td {
            border-bottom: none;
        }

        tbody tr:hover td {
            background: #f8faff;
        }

        .severity-name {
            font-weight: 700;
            text-transform: capitalize;
        }

        .severity-badge,
        .status-badge {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            text-transform: capitalize;
            white-space: nowrap;
        }

        .sev-critical, .sev-blocker {
            color: #b42332;
            background: #ffeaed;
        }

        .sev-major {
            color: #ad5a0a;
            background: #fff0df;
        }

        .sev-normal, .sev-medium {
            color: #245fbd;
            background: #eaf2ff;
        }

        .sev-minor, .sev-trivial, .sev-low {
            color: #147653;
            background: #e4f8ef;
        }

        .status-open {
            color: #b42332;
            background: #ffeaed;
        }

        .status-in-progress {
            color: #956008;
            background: #fff4d9;
        }

        .status-resolved {
            color: #147653;
            background: #e4f8ef;
        }

        .issue-title {
            min-width: 190px;
            max-width: 390px;
            color: var(--navy);
            font-weight: 600;
            overflow-wrap: anywhere;
        }

        .project-name {
            color: #526780;
            font-weight: 600;
        }

        .assigned-name {
            color: #526780;
        }

        /* RECENT ISSUES SEARCH */
        .issue-tools {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 17px;
        }

        .search-box {
            flex: 1;
            min-width: 220px;
            position: relative;
        }

        .search-box input {
            width: 100%;
        }

        input, select {
            min-height: 42px;
            padding: 10px 12px;
            border: 1px solid #dbe4f0;
            border-radius: 9px;
            color: var(--text);
            background: white;
            font-family: inherit;
            font-size: 13px;
            outline: none;
        }

        input:focus, select:focus {
            border-color: var(--blue);
            box-shadow: 0 0 0 3px rgba(54,120,245,.11);
        }

        .view-all {
            color: var(--blue);
            font-size: 13px;
            font-weight: 700;
        }

        .empty-state {
            padding: 25px;
            color: var(--muted);
            text-align: center;
        }

        .footer-note {
            margin-top: 23px;
            color: var(--muted);
            font-size: 11px;
            text-align: center;
        }

        /* RESPONSIVE DESIGN */
        @media (max-width: 1150px) {
            .sidebar {
                flex-basis: 205px;
            }

            .main-content {
                padding: 24px 20px;
            }

            .cards {
                gap: 11px;
            }

            .card {
                padding: 16px;
            }
        }

        @media (max-width: 850px) {
            .cards {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 650px) {
            .layout {
                flex-direction: column;
            }

            .sidebar {
                min-height: auto;
                width: 100%;
                flex-basis: auto;
                padding: 17px;
            }

            .brand {
                margin-bottom: 16px;
            }

            .user-info {
                margin-bottom: 15px;
            }

            .sidebar nav {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .main-content {
                padding: 20px 13px;
            }

            .cards {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 10px;
            }

            .card {
                padding: 14px;
            }

            .card h2 {
                font-size: 27px;
            }

            .card h3 {
                font-size: 12px;
            }

            .card-icon {
                width: 33px;
                height: 33px;
                font-size: 17px;
            }

            .panel {
                padding: 15px;
            }

            .chart-container {
                height: 260px;
            }

            th, td {
                padding: 11px;
            }
        }

        @media (max-width: 360px) {
            .cards {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>

<body>
<div class="layout">

    <aside class="sidebar">
        <div class="brand">
            <div class="brand-icon">🐞</div>
            <div>
                <h2>BugFlow</h2>
                <small>DEFECT TRACKING</small>
            </div>
        </div>

        <p class="user-info">
            <strong>Welcome back!</strong><br>
            {{ session.get('user_name', 'User') }}<br>
            {{ session.get('user_role', 'User') }}
        </p>

        <p class="menu-label">MAIN MENU</p>

        <nav>
            <a href="/dashboard">▦ &nbsp; Dashboard</a>
            <a href="/">⌂ &nbsp; Home</a>
            <a href="/reports">▤ &nbsp; Bug Reports</a>
            <a href="{{ url_for('sprints') }}">
    <i class="fas fa-calendar-alt"></i>
    <span>🏃Sprints</span>
</a>
            {% set role = session.get('user_role', '').strip().lower() %}
            {% if role in ['admin', 'project manager'] %}
                <a href="/users">♙ &nbsp; Users</a>
            {% endif %}

            <a href="/settings">⚙ &nbsp; Settings</a>
            <a href="/logout">⇥ &nbsp; Logout</a>
        </nav>
    </aside>

    <main class="main-content">

        <header class="page-header">
            <div>
                <p class="eyebrow">BUGFLOW WORKSPACE</p>
                <h1>Dashboard Overview</h1>
                <p class="page-subtitle">
                    Track issues, monitor severity and follow bug resolution progress.
                </p>
            </div>

            <a class="primary-btn" href="/">
                <span>＋</span> Create Issue
            </a>
        </header>

        <!-- HORIZONTAL OVERVIEW CARDS -->
        <section>
            <h2 class="section-heading">Overview</h2>
            <p class="section-subtitle">
                Summary of saved bug reports
            </p>

            <div class="cards">
                <div class="card">
                    <div class="card-top">
                        <h3>Total Issues</h3>
                        <span class="card-icon">▤</span>
                    </div>
                    <h2>{{ totals[0] }}</h2>
                    <div class="card-note">All recorded issues</div>
                </div>

                <div class="card">
                    <div class="card-top">
                        <h3>Open Issues</h3>
                        <span class="card-icon">◉</span>
                    </div>
                    <h2>{{ totals[1] }}</h2>
                    <div class="card-note">Awaiting action</div>
                </div>

                <div class="card">
                    <div class="card-top">
                        <h3>In Progress</h3>
                        <span class="card-icon">◷</span>
                    </div>
                    <h2>{{ totals[2] }}</h2>
                    <div class="card-note">Currently being handled</div>
                </div>

                <div class="card">
                    <div class="card-top">
                        <h3>Resolved</h3>
                        <span class="card-icon">✓</span>
                    </div>
                    <h2>{{ totals[3] }}</h2>
                    <div class="card-note">Marked as resolved</div>
                </div>
            </div>
        </section>

        <!-- ALL FOLLOWING SECTIONS STACK VERTICALLY -->
        <div class="dashboard-sections">

            <section class="panel">
                <div class="panel-header">
                    <div>
                        <h2>Severity Distribution</h2>
                        <p class="panel-description">
                            Breakdown of recorded bugs by severity
                        </p>
                    </div>
                </div>

                <div class="chart-container">
                    <canvas id="severityChart"></canvas>
                </div>
            </section>

            <section class="panel">
                <div class="panel-header">
                    <div>
                        <h2>Issue Status Overview</h2>
                        <p class="panel-description">
                            Compare open, in-progress and resolved issues
                        </p>
                    </div>
                </div>

                <div class="chart-container">
                    <canvas id="statusChart"></canvas>
                </div>
            </section>

            <section class="panel">
                <div class="panel-header">
                    <div>
                        <h2>Severity Details</h2>
                        <p class="panel-description">
                            Number of recorded bugs at each severity level
                        </p>
                    </div>
                </div>

                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Severity</th>
                                <th>Number of Bugs</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for severity, count in severity_counts %}
                            <tr>
                                <td>
                                    <span class="severity-badge sev-{{ (severity or 'unknown')|lower|replace(' ', '-') }}">
                                        {{ severity or 'Unknown' }}
                                    </span>
                                </td>
                                <td><strong>{{ count }}</strong></td>
                            </tr>
                            {% else %}
                            <tr>
                                <td colspan="2" class="empty-state">
                                    No severity data available.
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </section>

            <section class="panel">
                <div class="panel-header">
                    <div>
                        <h2>Recent Issues</h2>
                        <p class="panel-description">
                            Latest bug reports available to your account
                        </p>
                    </div>

                    <a class="view-all" href="/reports">View All Issues →</a>
                </div>

                <div class="issue-tools">
                    <div class="search-box">
                        <input
                            type="text"
                            id="issueSearch"
                            placeholder="Search title, project or developer..."
                            oninput="filterIssues()"
                            aria-label="Search recent issues"
                        >
                    </div>

                    <select
                        id="statusFilter"
                        onchange="filterIssues()"
                        aria-label="Filter by status"
                    >
                        <option value="">All Statuses</option>
                        <option value="Open">Open</option>
                        <option value="In Progress">In Progress</option>
                        <option value="Resolved">Resolved</option>
                    </select>
                </div>

                <div class="table-wrap">
                    <table id="issuesTable">
                        <thead>
                            <tr>
                                <th>Issue ID</th>
                                <th>Title</th>
                                <th>Project</th>
                                <th>Severity</th>
                                <th>Status</th>
                                <th>Assigned Developer</th>
                            </tr>
                        </thead>

                        <tbody>
                            {% for bug in recent_bugs %}
                            <tr class="issue-row">
                                <td>#{{ bug[0] }}</td>

                                <td class="issue-title">
                                    {{ bug[1] }}
                                </td>

                                <td class="project-name">
                                    {{ bug[2] or '—' }}
                                </td>

                                <td>
                                    <span class="severity-badge sev-{{ (bug[3] or 'unknown')|lower|replace(' ', '-') }}">
                                        {{ bug[3] or 'Unknown' }}
                                    </span>
                                </td>

                                <td class="issue-status">
                                    <span class="status-badge status-{{ (bug[4] or 'unknown')|lower|replace(' ', '-') }}">
                                        {{ bug[4] or 'Unknown' }}
                                    </span>
                                </td>
                                
                                <td class="assigned-name">
                                    {{ bug[5] or 'Unassigned' }}
                                </td>
                            </tr>
                            {% else %}
                            <tr>
                                <td colspan="6" class="empty-state">
                                    No issues found.
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>

                <p id="noSearchResults" class="empty-state" style="display:none;">
                    No issues match your search.
                </p>
            </section>

        </div>

        <footer class="footer-note">
            BugFlow · Intelligent Software Defect Tracking System
        </footer>

    </main>
</div>

<script>
    // Severity distribution chart
    const severityLabels = {{ severity_counts | map(attribute=0) | list | tojson }};
    const severityValues = {{ severity_counts | map(attribute=1) | list | tojson }};

    const severityColors = {
        critical: "#e45261",
        blocker: "#a92335",
        major: "#e5a12b",
        normal: "#3678f5",
        medium: "#8063df",
        minor: "#159b72",
        trivial: "#38a888",
        low: "#38a888"
    };

    const severityBackgrounds = severityLabels.map(function(label) {
        return severityColors[String(label || "").toLowerCase()] || "#94a3b8";
    });

    new Chart(document.getElementById("severityChart"), {
        type: "doughnut",
        data: {
            labels: severityLabels,
            datasets: [{
                label: "Number of Bugs",
                data: severityValues,
                backgroundColor: severityBackgrounds,
                borderColor: "#ffffff",
                borderWidth: 3,
                hoverOffset: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "58%",
            plugins: {
                legend: {
                    position: "bottom",
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                }
            }
        }
    });

    // Issue status chart
    new Chart(document.getElementById("statusChart"), {
        type: "bar",
        data: {
            labels: ["Open", "In Progress", "Resolved"],
            datasets: [{
                label: "Number of Bugs",
                data: [
                    {{ totals[1] }},
                    {{ totals[2] }},
                    {{ totals[3] }}
                ],
                backgroundColor: ["#e45261", "#e5a12b", "#159b72"],
                borderRadius: 7,
                maxBarThickness: 75
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    },
                    grid: {
                        color: "#edf1f7"
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });

    // Search and filter recent issue rows
    function filterIssues() {
        const searchText = document
            .getElementById("issueSearch")
            .value.toLowerCase()
            .trim();

        const selectedStatus = document
            .getElementById("statusFilter")
            .value.toLowerCase();

        const rows = document.querySelectorAll(
            "#issuesTable tbody .issue-row"
        );

        let visibleCount = 0;

        rows.forEach(function(row) {
            const rowText = row.innerText.toLowerCase();
            const statusElement = row.querySelector(".issue-status");
            const status = statusElement
                ? statusElement.innerText.trim().toLowerCase()
                : "";

            const matchesSearch = rowText.includes(searchText);
            const matchesStatus =
                selectedStatus === "" || status === selectedStatus;

            const visible = matchesSearch && matchesStatus;

            row.style.display = visible ? "" : "none";

            if (visible) {
                visibleCount++;
            }
        });

        const noResults = document.getElementById("noSearchResults");
        noResults.style.display =
            rows.length > 0 && visibleCount === 0 ? "block" : "none";
    }
</script>

</body>
</html>
""",
        totals=totals,
        severity_counts=severity_counts,
        recent_bugs=recent_bugs
    )



@app.route("/similar-bugs", methods=["GET", "POST"])
@login_required
def similar_bugs():
    description = ""

    if request.method == "POST":
        description = request.form.get("description", "").strip()

    results = find_similar_bugs(description) if description else []

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>BugFlow | Resolution Assistance</title>

        <style>
            * { box-sizing: border-box; }

            body {
                margin: 0;
                font-family: "Segoe UI", Arial, sans-serif;
                color: #203047;
                background: #f2f6fb;
            }

            .topbar {
                background: linear-gradient(120deg, #102d4d, #1677e8);
                color: white;
                padding: 25px 30px;
                box-shadow: 0 5px 18px #12365a20;
            }

            .brand {
                display: flex;
                align-items: center;
                gap: 13px;
            }

            .brand-icon {
                width: 48px;
                height: 48px;
                display: grid;
                place-items: center;
                border-radius: 13px;
                background: #ffffff20;
                font-size: 25px;
            }

            .brand h1 {
                margin: 0;
                font-size: 25px;
            }

            .brand p {
                margin: 5px 0 0;
                color: #dceaff;
                font-size: 13px;
            }

            .container {
                max-width: 1050px;
                margin: 30px auto;
                padding: 0 20px;
            }

            .page-heading {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 15px;
                margin-bottom: 22px;
            }

            .page-heading h2 {
                margin: 0 0 7px;
                font-size: 25px;
            }

            .page-heading p {
                margin: 0;
                color: #718096;
                font-size: 14px;
                line-height: 1.6;
            }

            .back-button {
                display: inline-block;
                padding: 11px 15px;
                background: white;
                color: #174ea6;
                border: 1px solid #dce6f2;
                border-radius: 9px;
                text-decoration: none;
                font-size: 13px;
                font-weight: 700;
            }

            .search-panel {
                position: relative;
                overflow: hidden;
                background: white;
                border: 1px solid #e0e9f4;
                border-radius: 16px;
                padding: 25px;
                margin-bottom: 28px;
                box-shadow: 0 7px 24px #2030470b;
            }

            .search-panel h3 {
                margin: 0 0 8px;
                font-size: 19px;
            }

            .search-panel .subtitle {
                color: #718096;
                font-size: 13px;
                margin: 0 0 20px;
                line-height: 1.6;
            }

            .input-label {
                display: block;
                margin-bottom: 9px;
                font-size: 13px;
                font-weight: 700;
                color: #315574;
            }

            textarea {
                width: 100%;
                min-height: 145px;
                resize: vertical;
                padding: 15px;
                border: 1px solid #d5dfeb;
                border-radius: 10px;
                background: #fbfdff;
                color: #203047;
                font: inherit;
                font-size: 14px;
                line-height: 1.7;
                outline: none;
            }

            textarea:focus {
                border-color: #1677e8;
                box-shadow: 0 0 0 3px #1677e81a;
            }

            .form-footer {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 12px;
                margin-top: 15px;
            }

            .hint {
                color: #718096;
                font-size: 12px;
            }

            .search-button {
                border: none;
                border-radius: 9px;
                padding: 13px 20px;
                color: white;
                background: linear-gradient(120deg, #1677e8, #125fc0);
                font-size: 14px;
                font-weight: 700;
                cursor: pointer;
                box-shadow: 0 5px 13px #1677e82c;
            }

            .search-button:hover {
                filter: brightness(.95);
                transform: translateY(-1px);
            }

            .section-heading {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 10px;
                margin: 28px 0 16px;
            }

            .section-heading h2 {
                margin: 0;
                font-size: 20px;
            }

            .result-count {
                background: #e2edff;
                color: #174ea6;
                padding: 7px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 700;
            }

            .result-card {
                background: white;
                border: 1px solid #e2eaf3;
                border-radius: 13px;
                padding: 21px;
                margin-bottom: 15px;
                box-shadow: 0 5px 17px #20304708;
                transition: transform .2s, box-shadow .2s;
            }

            .result-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 9px 22px #20304712;
            }

            .result-top {
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 12px;
                margin-bottom: 15px;
            }

            .result-number {
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 14px;
                font-weight: 700;
            }

            .number-icon {
                display: grid;
                place-items: center;
                width: 38px;
                height: 38px;
                background: #e8f0fe;
                border-radius: 10px;
                font-size: 18px;
            }

            .similarity-badge {
                background: #e5f5eb;
                color: #137333;
                padding: 7px 11px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 700;
            }

            .bug-description {
                margin: 0 0 17px;
                font-size: 15px;
                line-height: 1.8;
                overflow-wrap: anywhere;
                white-space: pre-wrap;
            }

            .score-label {
                display: flex;
                justify-content: space-between;
                gap: 10px;
                color: #718096;
                font-size: 12px;
                margin-bottom: 7px;
            }

            .score-track {
                width: 100%;
                height: 7px;
                background: #edf1f6;
                border-radius: 10px;
                overflow: hidden;
            }

            .score-fill {
                height: 100%;
                background: linear-gradient(90deg, #1677e8, #35b7a2);
                border-radius: 10px;
            }

            .metadata {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 18px;
            }

            .meta-item {
                background: #f4f7fb;
                border: 1px solid #e7edf5;
                border-radius: 8px;
                padding: 9px 12px;
                font-size: 12px;
                color: #536578;
            }

            .meta-item strong {
                color: #203047;
            }

            .empty-state {
                background: white;
                border: 1px solid #e2eaf3;
                border-radius: 14px;
                padding: 36px 20px;
                text-align: center;
                box-shadow: 0 5px 17px #20304708;
            }

            .empty-icon {
                font-size: 38px;
                margin-bottom: 10px;
            }

            .empty-state h3 {
                margin: 0 0 8px;
            }

            .empty-state p {
                margin: 0;
                color: #718096;
                font-size: 14px;
                line-height: 1.7;
            }

            .footer {
                text-align: center;
                margin: 28px 0 18px;
                color: #8290a3;
                font-size: 12px;
            }

            @media(max-width: 600px) {
                .topbar { padding: 20px; }
                .container { padding: 0 12px; margin-top: 20px; }
                .search-panel { padding: 18px; }
                .page-heading h2 { font-size: 22px; }
                .form-footer { align-items: stretch; }
                .search-button { width: 100%; }
                .result-card { padding: 16px; }
            }
        </style>
    </head>

    <body>
        <header class="topbar">
            <div class="brand">
                <div class="brand-icon">🧠</div>
                <div>
                    <h1>BugFlow</h1>
                    <p>Intelligent Software Defect Tracking System</p>
                </div>
            </div>
        </header>

        <main class="container">
            <div class="page-heading">
                <div>
                    <h2>✨ Resolution Assistance</h2>
                    <p>
                        Find historical bug reports with descriptions
                        similar to the issue you're investigating.
                    </p>
                </div>

                <a class="back-button" href="/dashboard">
                    ← Back to home
                </a>
            </div>

            <section class="search-panel">
                <h3>🔍 Describe Your Bug</h3>
                <p class="subtitle">
                    Enter the symptoms or error details. BugFlow will
                    search for similar historical reports.
                </p>

                <form method="post">
                    <label class="input-label" for="description">
                        Bug description
                    </label>

                    <textarea
                        id="description"
                        name="description"
                        placeholder="Example: The login button does not respond after entering valid credentials..."
                        required>{{ description }}</textarea>

                    <div class="form-footer">
                        <span class="hint">
                            Tip: Include the error message and what happened.
                        </span>
                        <button class="search-button" type="submit">
                            ✨ Find Similar Bugs
                        </button>
                    </div>
                </form>
            </section>

            {% if description %}
                <div class="section-heading">
                    <h2>📚 Historical Matches</h2>
                    {% if results %}
                        <span class="result-count">
                            {{ results|length }} result(s)
                        </span>
                    {% endif %}
                </div>

                {% if results %}
                    {% for bug in results %}
                        <article class="result-card">
                            <div class="result-top">
                                <div class="result-number">
                                    <span class="number-icon">🐞</span>
                                    <span>Historical Report #{{ loop.index }}</span>
                                </div>

                                <span class="similarity-badge">
                                    {{ bug.similarity }}% similarity
                                </span>
                            </div>

                            <p class="bug-description">
                                {{ bug.description }}
                            </p>

                            <div class="score-label">
                                <span>Text similarity score</span>
                                <strong>{{ bug.similarity }}%</strong>
                            </div>

                            <div class="score-track">
                                <div class="score-fill"
                                     style="width: {{ [[bug.similarity|float, 0]|max, 100]|min }}%;">
                                </div>
                            </div>

                            <div class="metadata">
                                <div class="meta-item">
                                    ⚠️ <strong>Severity:</strong>
                                    {{ bug.severity or 'Not specified' }}
                                </div>
                            </div>
                        </article>
                    {% endfor %}
                {% else %}
                    <section class="empty-state">
                        <div class="empty-icon">🔎</div>
                        <h3>No Similar Reports Found</h3>
                        <p>
                            Try adding more details, such as the error
                            message, affected feature, or steps to reproduce
                            the issue.
                        </p>
                    </section>
                {% endif %}
            {% else %}
                <section class="empty-state">
                    <div class="empty-icon">💡</div>
                    <h3>Ready to Investigate?</h3>
                    <p>
                        Submit a bug description above to discover
                        similar reports from your historical data.
                    </p>
                </section>
            {% endif %}

            <p class="footer">
                🐞 BugFlow · Intelligent Software Defect Tracking System
            </p>
        </main>
    </body>
    </html>
    """, description=description, results=results)





@app.route("/users", methods=["GET", "POST"])
@login_required
def users():
    role = session.get("user_role", "").strip().lower()

    # Only Admin and Project Manager can access this page
    if role not in ["admin", "project manager"]:
        return "Access denied: You are not authorized to view users.", 403

    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Update a user's role when the form is submitted
        if request.method == "POST":
            user_id = request.form.get("user_id", "").strip()
            new_role = request.form.get("role", "").strip()

            allowed_roles = [
                "Admin",
                "Project Manager",
                "Developer",
                "Tester"
            ]

            if new_role not in allowed_roles:
                return "Invalid role selected.", 400

            try:
                target_id = int(user_id)
            except (ValueError, TypeError):
                return "Invalid user ID.", 400

            # Prevent changing your own role accidentally
            if target_id == session.get("user_id"):
                return "You cannot change your own role.", 400

            cursor.execute("""
                UPDATE public.users
                SET role = %s
                WHERE user_id = %s
                RETURNING user_id;
            """, (new_role, target_id))

            updated_user = cursor.fetchone()

            if not updated_user:
                connection.rollback()
                return "User not found.", 404

            connection.commit()
            return redirect("/users")

        # Display all registered users
        cursor.execute("""
            SELECT user_id, name, email, role
            FROM public.users
            ORDER BY user_id;
        """)
        users_list = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>BugFlow - User Management</title>

        <style>
            * { box-sizing: border-box; }

            body {
                margin: 0;
                font-family: "Segoe UI", Arial, sans-serif;
                background: #f2f6fb;
                color: #203047;
            }

            .topbar {
                background: linear-gradient(120deg, #12365a, #1677e8);
                color: white;
                padding: 24px 30px;
                box-shadow: 0 4px 15px #12365a20;
            }

            .topbar h1 { margin: 0 0 6px; }
            .topbar p { margin: 0; color: #dceaff; }

            .container {
                max-width: 1250px;
                margin: 30px auto;
                padding: 0 20px;
            }

            .toolbar {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 12px;
                margin-bottom: 20px;
            }

            .toolbar h2 { margin: 0; }

            .button {
                display: inline-block;
                padding: 10px 15px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 600;
                background: #e0ebfa;
                color: #174ea6;
            }

            .panel {
                background: white;
                border: 1px solid #e2eaf3;
                border-radius: 14px;
                overflow: hidden;
                box-shadow: 0 6px 22px #2030470c;
            }

            .panel-header {
                padding: 20px;
                border-bottom: 1px solid #eaf0f6;
            }

            .panel-header h3 { margin: 0 0 5px; }
            .panel-header p { margin: 0; color: #718096; font-size: 14px; }

            .table-wrap { overflow-x: auto; }

            table {
                width: 100%;
                min-width: 780px;
                border-collapse: collapse;
            }

            th {
                background: #eaf2fb;
                color: #315574;
                text-align: left;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: .5px;
                padding: 15px;
            }

            td {
                padding: 14px 15px;
                border-bottom: 1px solid #edf1f6;
                font-size: 14px;
            }

            tbody tr:hover { background: #f6faff; }

            .user-id {
                background: #e8f0fe;
                color: #174ea6;
                padding: 5px 9px;
                border-radius: 6px;
                font-weight: 700;
            }

            .role-badge {
                display: inline-block;
                background: #e5f5eb;
                color: #137333;
                padding: 5px 10px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 700;
                margin-bottom: 7px;
            }

            select {
                display: block;
                width: 100%;
                min-width: 145px;
                padding: 9px;
                margin: 4px 0 8px;
                border: 1px solid #d5dfeb;
                border-radius: 7px;
                background: white;
            }

            button {
                background: #1677e8;
                color: white;
                border: none;
                border-radius: 7px;
                padding: 9px 13px;
                cursor: pointer;
                font-weight: 600;
            }

            button:hover { background: #125fc0; }

            .empty {
                text-align: center;
                color: #718096;
                padding: 30px;
            }

            .note {
                background: #eaf2fb;
                color: #315574;
                padding: 14px 16px;
                border-radius: 9px;
                margin-bottom: 18px;
                font-size: 14px;
                line-height: 1.5;
            }

            .footer {
                text-align: center;
                color: #718096;
                font-size: 12px;
                margin: 22px;
            }

            @media(max-width: 600px) {
                .topbar { padding: 20px; }
                .container { padding: 0 12px; }
            }
        </style>
    </head>

    <body>
        <header class="topbar">
            <h1>🐞 BugFlow | User Management</h1>
            <p>Manage registered users and assign their roles</p>
        </header>

        <main class="container">
            <div class="toolbar">
                <h2>👥 Registered Users</h2>
                <a class="button" href="/dashboard">
                    ← Back to Dashboard
                </a>
            </div>

            <div class="note">
                <strong>Role management:</strong>
                Select a role and click Save Role to update a user's
                permissions. You cannot change your own role here.
            </div>

            <section class="panel">
                <div class="panel-header">
                    <h3>User Directory</h3>
                    <p>Review registered accounts and manage access roles.</p>
                </div>

                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>User ID</th>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Current Role</th>
                                <th>Change Role</th>
                            </tr>
                        </thead>

                        <tbody>
                            {% for user in users_list %}
                            <tr>
                                <td>
                                    <span class="user-id">#{{ user[0] }}</span>
                                </td>

                                <td><strong>{{ user[1] }}</strong></td>

                                <td>{{ user[2] or 'Not provided' }}</td>

                                <td>
                                    <span class="role-badge">
                                        {{ user[3] }}
                                    </span>
                                </td>

                                <td>
                                    {% if user[0] != session.get('user_id') %}
                                    <form method="POST" action="/users">
                                        <input type="hidden"
                                               name="user_id"
                                               value="{{ user[0] }}">

                                        <select name="role" required>
                                            {% for option in [
                                                'Admin',
                                                'Project Manager',
                                                'Developer',
                                                'Tester'
                                            ] %}
                                            <option value="{{ option }}"
                                                {% if user[3]|lower == option|lower %}
                                                    selected
                                                {% endif %}>
                                                {{ option }}
                                            </option>
                                            {% endfor %}
                                        </select>

                                        <button type="submit">Save Role</button>
                                    </form>
                                    {% else %}
                                        <span>Current account</span>
                                    {% endif %}
                                </td>
                            </tr>
                            {% else %}
                            <tr>
                                <td colspan="5" class="empty">
                                    No registered users found.
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </section>

            <p class="footer">
                BugFlow · Intelligent Software Defect Tracking System
            </p>
        </main>
    </body>
    </html>
    """, users_list=users_list)


@app.route("/settings")
@login_required
def settings():
    return render_template_string("""
    <h1>BugFlow - Settings</h1>
    <p>Manage your account settings.</p>

    <p><strong>Name:</strong>
       {{ session.get('user_name', 'User') }}</p>

    <p><strong>Role:</strong>
       {{ session.get('user_role', 'User') }}</p>

    <p><a href="/dashboard">← Back to Dashboard</a></p>
    """)


@app.route("/api/predict", methods=["POST"])
@login_required
def predict():
    data = request.get_json(silent=True) or {}
    description = str(data.get("description", "")).strip()

    if not description:
        return jsonify({"error": "Description is required"}), 400

    severity = str(model.predict([description])[0])

    return jsonify({
        "description": description,
        "predicted_severity": severity
    })


if __name__ == "__main__":
    app.run(debug=True)
