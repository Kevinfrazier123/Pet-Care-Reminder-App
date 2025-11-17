import os

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps

import db

app = Flask(__name__)
app.secret_key = "change_this_to_something_secret"

# ---- uploads for profile pictures ----
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------- helper: login_required decorator ----------
def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


# ---------- home route ----------
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ---------- REGISTER ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        terms = request.form.get("terms")

        if not email or not password or not confirm_password:
            error = "All fields are required."
        elif "@" not in email:
            error = "Please enter a valid email address."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif not terms:
            error = "You must accept the terms and policy."
        else:
            existing = db.get_user_by_email(email)
            if existing:
                error = "An account with this email already exists."
            else:
                password_hash = generate_password_hash(password)
                db.create_user(email, password_hash, is_admin=0)
                return redirect(url_for("login"))

    return render_template("register.html", error=error)


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = db.get_user_by_email(email)
        if user is None:
            error = "Invalid email or password."
        else:
            if not check_password_hash(user["password_hash"], password):
                error = "Invalid email or password."
            elif user["is_active"] == 0:
                error = "This account is inactive. Contact admin."
            else:
                session["user_id"] = user["id"]
                session["user_email"] = user["email"]
                session["is_admin"] = bool(user["is_admin"])
                return redirect(url_for("dashboard"))

    return render_template("login.html", error=error)


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- DASHBOARD ----------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    user = db.get_user_by_id(user_id)

    if user and user["avatar_filename"]:
        avatar_url = url_for("static", filename=f"uploads/{user['avatar_filename']}")
    else:
        avatar_url = url_for("static", filename="images/profile-avatar.jpg")

    user_email = user["email"] if user else ""

    return render_template(
        "dashboard.html",
        avatar_url=avatar_url,
        user_email=user_email,
    )


# ---------- PROFILE (view + update + change password) ----------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session["user_id"]
    user = db.get_user_by_id(user_id)

    profile_message = None
    password_message = None
    error_message = None

    if request.method == "POST":
        form_type = request.form.get("form_type")

        # --- Update profile info + avatar ---
        if form_type == "profile":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            home_address = request.form.get("home_address", "").strip()

            # Check if email already used by someone else
            existing = db.get_user_by_email(email)
            if existing and existing["id"] != user_id:
                error_message = "Another account already uses that email."
            else:
                avatar_filename = None
                file = request.files.get("avatar")
                if file and file.filename and allowed_file(file.filename):
                    raw_name = secure_filename(file.filename)
                    unique_name = f"user_{user_id}_{raw_name}"
                    file.save(os.path.join(UPLOAD_FOLDER, unique_name))
                    avatar_filename = unique_name

                db.update_user_profile(
                    user_id,
                    email=email,
                    full_name=full_name,
                    home_address=home_address,
                    avatar_filename=avatar_filename,
                )
                session["user_email"] = email
                profile_message = "Profile updated successfully."

        # --- Change password ---
        elif form_type == "password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not check_password_hash(user["password_hash"], current_password):
                error_message = "Current password is incorrect."
            elif not new_password:
                error_message = "New password cannot be empty."
            elif new_password != confirm_password:
                error_message = "New passwords do not match."
            else:
                new_hash = generate_password_hash(new_password)
                db.change_user_password(user_id, new_hash)
                password_message = "Password changed successfully."

        # reload user after any update
        user = db.get_user_by_id(user_id)

    # choose avatar URL (uploaded or default)
    if user and user["avatar_filename"]:
        avatar_url = url_for("static", filename=f"uploads/{user['avatar_filename']}")
    else:
        avatar_url = url_for("static", filename="images/profile-avatar.jpg")

    user_email = user["email"] if user else ""
    created_at = user["created_at"] if user else ""
    home_address = user["home_address"] if user else ""
    full_name = user["full_name"] if user else ""
    display_name = full_name or (user_email.split("@")[0].title() if user_email else "Pet Parent")

    return render_template(
        "profile.html",
        avatar_url=avatar_url,
        user_email=user_email,
        created_at=created_at,
        home_address=home_address,
        user_full_name=full_name,
        user_display_name=display_name,
        profile_message=profile_message,
        password_message=password_message,
        error_message=error_message,
    )


if __name__ == "__main__":
    app.run(debug=True)
