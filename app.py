import os
import json
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import date

import db
import time

app = Flask(__name__)
app.secret_key = "change_this_to_something_secret"

# ---- uploads for profile pictures ----
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER  


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """Serve uploaded images (pets, profile, etc.)."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

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
# ---------- DASHBOARD ----------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    user = db.get_user_by_id(user_id)

    # avatar for header
    if user and user["avatar_filename"]:
        avatar_url = url_for("static", filename=f"uploads/{user['avatar_filename']}")
    else:
        avatar_url = url_for("static", filename="images/profile-avatar.jpg")

    user_email = user["email"] if user else ""

    # -------- Pets for the "My Pets" section --------
    raw_pets = db.get_pets_for_user(user_id)
    pets = []
    for row in raw_pets:
        pet = dict(row)
        if pet.get("avatar_filename"):
            pet["avatar_url"] = url_for(
                "static", filename=f"uploads/{pet['avatar_filename']}"
            )
        else:
            pet["avatar_url"] = url_for("static", filename="images/default-pet.png")
        pets.append(pet)

    # -------- Upcoming reminders for dashboard cards --------
    # use helper already in db.py: get_upcoming_tasks_for_user
    upcoming_tasks = db.get_upcoming_tasks_for_user(user_id, limit=3)
    upcoming_count = len(upcoming_tasks)

    next_due_date = None
    next_task_title = None
    if upcoming_tasks:
        next_task = upcoming_tasks[0]  # soonest due (already ordered in db.py)
        next_due_date = next_task["due_date"]
        next_task_title = next_task["title"]

    return render_template(
        "dashboard.html",
        avatar_url=avatar_url,
        user_email=user_email,
        pets=pets,
        upcoming_tasks=upcoming_tasks,
        upcoming_count=upcoming_count,
        next_due_date=next_due_date,
        next_task_title=next_task_title,
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


@app.route("/my-pets", methods=["GET", "POST"])
@login_required
def my_pets():
    user_id = session["user_id"]
    user = db.get_user_by_id(user_id)

    # avatar for header
    if user and user["avatar_filename"]:
        avatar_url = url_for("static", filename=f"uploads/{user['avatar_filename']}")
    else:
        avatar_url = url_for("static", filename="images/profile-avatar.jpg")

    user_email = user["email"] if user else ""

    message = None
    error = None

    if request.method == "POST":
        # Read form values from the Add Pet form
        name = request.form.get("name", "").strip()
        species = request.form.get("species", "").strip()
        breed = request.form.get("breed", "").strip()
        birthdate = request.form.get("birthdate", "").strip()  # YYYY-MM-DD or empty
        weight = request.form.get("weight", "").strip()
        vet_name = request.form.get("vet_name", "").strip()
        notes = request.form.get("notes", "").strip()

        # ---------- NEW: handle pet photo upload ----------
        avatar_filename = None
        photo_file = request.files.get("pet_photo")  # field name in the form

        if photo_file and photo_file.filename and allowed_file(photo_file.filename):
            safe_name = secure_filename(photo_file.filename)
            unique_name = f"pet_{user_id}_{int(time.time())}_{safe_name}"
            photo_file.save(os.path.join(UPLOAD_FOLDER, unique_name))
            avatar_filename = unique_name
        # ---------------------------------------------------

        # Basic validation: name + species are required
        if not name or not species:
            error = "Pet name and species are required."
        else:
            # Create the pet in the DB (now with avatar_filename)
            db.create_pet(
                user_id=user_id,
                name=name,
                species=species,
                breed=breed or None,
                birthdate=birthdate or None,
                weight=weight or None,
                vet_name=vet_name or None,
                notes=notes or None,
                avatar_filename=avatar_filename,
            )
            message = f"Pet '{name}' added successfully."

    # Always load pets after possible insert
    raw_pets = db.get_pets_for_user(user_id)
    pets = []
    for row in raw_pets:
        pet = dict(row)
        if pet.get("avatar_filename"):
            pet["avatar_url"] = url_for(
                "static", filename=f"uploads/{pet['avatar_filename']}"
            )
        else:
            pet["avatar_url"] = url_for("static", filename="images/default-pet.png")
        pets.append(pet)

    return render_template(
        "my_pets.html",
        avatar_url=avatar_url,
        user_email=user_email,
        pets=pets,
        message=message,
        error=error,
    )

@app.route("/my-pets/<int:pet_id>/delete", methods=["POST"])
@login_required
def delete_pet(pet_id):
    user_id = session["user_id"]

    # Only delete if the pet belongs to this user
    db.delete_pet_for_user(user_id, pet_id)

    return redirect(url_for("my_pets"))


@app.route("/reminders", methods=["GET", "POST"])
@login_required
def reminders():
    import json
    user_id = session["user_id"]

    # Load user row
    user = db.get_user_by_id(user_id)

    # ---------- FIXED AVATAR HANDLING ----------
    avatar_url = url_for("static", filename="images/profile-avatar.jpg")
    if user and "avatar_filename" in user.keys() and user["avatar_filename"]:
        avatar_url = url_for("static", filename=f"uploads/{user['avatar_filename']}")

    user_email = user["email"] if user else ""

    # ---------- CREATE REMINDER ----------
    message = None
    error = None

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        due_date = request.form.get("due_date", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        pet_id = request.form.get("pet_id", "").strip()
        vet_location = request.form.get("vet_location", "").strip()

        if not title or not due_date:
            error = "A title and due date are required."
        else:
            if pet_id == "":
                pet_id = None

            # Save task
            db.create_care_task(
                user_id=user_id,
                title=title,
                due_date=due_date,
                category=category,
                description=description,
                pet_id=pet_id
            )

            message = "Reminder saved successfully."

    # ---------- LOAD REMINDERS ----------
    conn = db.get_conn()
    cur = conn.execute(
        """
        SELECT ct.*, p.name AS pet_name
        FROM care_tasks ct
        LEFT JOIN pets p ON p.id = ct.pet_id
        WHERE ct.user_id = ?
        ORDER BY ct.due_date ASC
        """,
        (user_id,),
    )
    tasks = cur.fetchall()
    conn.close()

    # ---------- CALENDAR HIGHLIGHTED DATES ----------
    dates_with_tasks = sorted({row["due_date"] for row in tasks})
    reminder_dates_json = json.dumps(dates_with_tasks)

    # ---------- GROUP TASKS BY DATE FOR POPUP ----------
    tasks_by_date = {}
    for t in tasks:
        d = t["due_date"]
        tasks_by_date.setdefault(d, []).append(dict(t))

    tasks_json = json.dumps(tasks_by_date)

    # ---------- LOAD PETS FOR DROPDOWN ----------
    pets = db.get_pets_for_user(user_id)

    return render_template(
        "reminders.html",
        avatar_url=avatar_url,
        user_email=user_email,
        tasks=tasks,
        pets=pets,
        message=message,
        error=error,
        reminder_dates_json=reminder_dates_json,
        tasks_json=tasks_json
    )



@app.route("/reminders/<int:task_id>/complete", methods=["POST"])
@login_required
def complete_task(task_id):
    user_id = session["user_id"]
    db.mark_task_completed(user_id, task_id)
    return redirect(url_for("reminders"))


@app.route("/reminders/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    user_id = session["user_id"]
    db.delete_task_for_user(user_id, task_id)
    return redirect(url_for("reminders"))


@app.route("/analytics")
@login_required
def analytics():
    user_id = session["user_id"]

    # user + avatar for header
    user = db.get_user_by_id(user_id)
    if user and user["avatar_filename"]:
        avatar_url = url_for("static", filename=f"uploads/{user['avatar_filename']}")
    else:
        avatar_url = url_for("static", filename="images/profile-avatar.jpg")
    user_email = user["email"] if user else ""

    # --- Analytics data from db.py ---
    species_rows = db.get_pet_species_counts(user_id)
    status_rows  = db.get_task_status_counts(user_id)
    due_counts   = db.get_task_counts_by_due(user_id)

    pet_species = [dict(r) for r in species_rows]
    total_pets = sum(s["count"] for s in pet_species)

    status_counts = {r["status"]: r["count"] for r in status_rows}
    total_tasks = due_counts["total"] or 0

    completed = status_counts.get("completed", 0)
    pending   = status_counts.get("pending", 0)
    overdue   = due_counts["overdue"] or 0
    upcoming  = due_counts["upcoming"] or 0

    completion_rate = round((completed / total_tasks) * 100) if total_tasks else 0

    # For bar widths on the pet species chart
    max_species = max((s["count"] for s in pet_species), default=0)
    for s in pet_species:
        s["percent"] = int((s["count"] / max_species) * 100) if max_species else 0

    return render_template(
        "analytics.html",
        avatar_url=avatar_url,
        user_email=user_email,
        pet_species=pet_species,
        total_pets=total_pets,
        total_tasks=total_tasks,
        completed=completed,
        pending=pending,
        overdue=overdue,
        upcoming=upcoming,
        completion_rate=completion_rate,
    )



if __name__ == "__main__":
    app.run(debug=True)
