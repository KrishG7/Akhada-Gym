from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client, Client
import os
from datetime import datetime, timedelta
import random
import json
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional outside local development
    pass

import hmac
from werkzeug.security import check_password_hash, generate_password_hash

# Credentials come from the environment (see README "Configuration"), never from source.
# SUPABASE_KEY must be the server-side service_role key once database/lock_down.sql is applied.
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Set SUPABASE_URL and SUPABASE_KEY (see README, Configuration).")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__, static_url_path='/static')

# A random key per process logs everyone out on restart and breaks sessions across gunicorn
# workers, so a fixed key is required except when running locally with FLASK_DEBUG=1.
_secret_key = os.environ.get("FLASK_SECRET_KEY")
if not _secret_key:
    if os.environ.get("FLASK_DEBUG") != "1":
        raise RuntimeError("Set FLASK_SECRET_KEY (or FLASK_DEBUG=1 for local development).")
    _secret_key = os.urandom(24)
app.secret_key = _secret_key
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

# Plans a person may pick for themselves. "Admin" is deliberately not here: it grants the admin
# role at login, so it can only exist on rows an operator creates in the database.
ALLOWED_PLANS = {"Basic", "Premium", "VIP"}
RESERVED_EMAILS = {"admin@gym.com"}


def hash_password(password):
    return generate_password_hash(password)


def is_hashed(stored):
    return isinstance(stored, str) and stored.startswith(("pbkdf2:", "scrypt:"))


def password_matches(stored, supplied):
    """Hashed rows use werkzeug; rows created before hashing was added are plain text and are
    compared in constant time (and upgraded to a hash on the next successful login)."""
    if not stored or supplied is None:
        return False
    if is_hashed(stored):
        return check_password_hash(stored, supplied)
    return hmac.compare_digest(str(stored), str(supplied))

exercise_database = {
    'push': {
        'beginner': [
            {'name': 'Push-ups', 'sets': '3', 'reps': '8-10', 'rest': '60s'},
            {'name': 'Dumbbell Bench Press', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Overhead Press', 'sets': '3', 'reps': '8-10', 'rest': '60s'},
            {'name': 'Tricep Dips', 'sets': '3', 'reps': '8-10', 'rest': '60s'},
            {'name': 'Lateral Raises', 'sets': '3', 'reps': '12-15', 'rest': '45s'},
        ],
        'intermediate': [
            {'name': 'Barbell Bench Press', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
            {'name': 'Incline Dumbbell Press', 'sets': '4', 'reps': '10-12', 'rest': '75s'},
            {'name': 'Military Press', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
            {'name': 'Cable Flyes', 'sets': '3', 'reps': '12-15', 'rest': '60s'},
            {'name': 'Tricep Pushdowns', 'sets': '3', 'reps': '12-15', 'rest': '60s'},
            {'name': 'Front Raises', 'sets': '3', 'reps': '12-15', 'rest': '45s'},
        ],
        'advanced': [
            {'name': 'Bench Press (Heavy)', 'sets': '5', 'reps': '5-6', 'rest': '120s'},
            {'name': 'Incline Barbell Press', 'sets': '4', 'reps': '6-8', 'rest': '90s'},
            {'name': 'Weighted Dips', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
            {'name': 'Overhead Press', 'sets': '4', 'reps': '6-8', 'rest': '90s'},
            {'name': 'Cable Crossovers', 'sets': '4', 'reps': '12-15', 'rest': '60s'},
            {'name': 'Skull Crushers', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
        ],
    },
    'pull': {
        'beginner': [
            {'name': 'Lat Pulldowns', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Seated Cable Rows', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Dumbbell Rows', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Face Pulls', 'sets': '3', 'reps': '12-15', 'rest': '45s'},
            {'name': 'Bicep Curls', 'sets': '3', 'reps': '10-12', 'rest': '45s'},
        ],
        'intermediate': [
            {'name': 'Pull-ups', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
            {'name': 'Barbell Rows', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
            {'name': 'T-Bar Rows', 'sets': '4', 'reps': '10-12', 'rest': '75s'},
            {'name': 'Cable Rows', 'sets': '3', 'reps': '12-15', 'rest': '60s'},
            {'name': 'Hammer Curls', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Reverse Flyes', 'sets': '3', 'reps': '12-15', 'rest': '45s'},
        ],
        'advanced': [
            {'name': 'Weighted Pull-ups', 'sets': '5', 'reps': '6-8', 'rest': '120s'},
            {'name': 'Deadlifts', 'sets': '5', 'reps': '5-6', 'rest': '120s'},
            {'name': 'Pendlay Rows', 'sets': '4', 'reps': '6-8', 'rest': '90s'},
            {'name': 'Chest Supported Rows', 'sets': '4', 'reps': '10-12', 'rest': '75s'},
            {'name': 'Preacher Curls', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Shrugs', 'sets': '4', 'reps': '12-15', 'rest': '60s'},
        ],
    },
    'legs': {
        'beginner': [
            {'name': 'Goblet Squats', 'sets': '3', 'reps': '10-12', 'rest': '90s'},
            {'name': 'Leg Press', 'sets': '3', 'reps': '12-15', 'rest': '75s'},
            {'name': 'Leg Curls', 'sets': '3', 'reps': '12-15', 'rest': '60s'},
            {'name': 'Leg Extensions', 'sets': '3', 'reps': '12-15', 'rest': '60s'},
            {'name': 'Calf Raises', 'sets': '3', 'reps': '15-20', 'rest': '45s'},
        ],
        'intermediate': [
            {'name': 'Barbell Squats', 'sets': '4', 'reps': '8-10', 'rest': '120s'},
            {'name': 'Romanian Deadlifts', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
            {'name': 'Walking Lunges', 'sets': '3', 'reps': '12-15', 'rest': '75s'},
            {'name': 'Leg Press', 'sets': '4', 'reps': '12-15', 'rest': '75s'},
            {'name': 'Hamstring Curls', 'sets': '3', 'reps': '12-15', 'rest': '60s'},
            {'name': 'Standing Calf Raises', 'sets': '4', 'reps': '15-20', 'rest': '45s'},
        ],
        'advanced': [
            {'name': 'Barbell Squats (Heavy)', 'sets': '5', 'reps': '5-6', 'rest': '150s'},
            {'name': 'Front Squats', 'sets': '4', 'reps': '6-8', 'rest': '120s'},
            {'name': 'Bulgarian Split Squats', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
            {'name': 'Stiff-Leg Deadlifts', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
            {'name': 'Leg Press (Heavy)', 'sets': '4', 'reps': '10-12', 'rest': '90s'},
            {'name': 'Seated Calf Raises', 'sets': '4', 'reps': '15-20', 'rest': '60s'},
        ],
    },
    'arms': {
        'beginner': [
            {'name': 'Barbell Curls', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Tricep Pushdowns', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Hammer Curls', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Overhead Tricep Extension', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Wrist Curls', 'sets': '2', 'reps': '15-20', 'rest': '45s'},
        ],
        'intermediate': [
            {'name': 'EZ Bar Curls', 'sets': '4', 'reps': '8-10', 'rest': '75s'},
            {'name': 'Close Grip Bench Press', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
            {'name': 'Incline Dumbbell Curls', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Skull Crushers', 'sets': '3', 'reps': '10-12', 'rest': '75s'},
            {'name': 'Cable Curls', 'sets': '3', 'reps': '12-15', 'rest': '60s'},
            {'name': 'Tricep Dips', 'sets': '3', 'reps': '10-12', 'rest': '75s'},
        ],
        'advanced': [
            {'name': 'Barbell Curls (Heavy)', 'sets': '5', 'reps': '6-8', 'rest': '90s'},
            {'name': 'Weighted Dips', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
            {'name': 'Preacher Curls', 'sets': '4', 'reps': '8-10', 'rest': '75s'},
            {'name': 'Close Grip Bench', 'sets': '4', 'reps': '6-8', 'rest': '90s'},
            {'name': 'Concentration Curls', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Overhead Cable Extensions', 'sets': '3', 'reps': '12-15', 'rest': '60s'},
        ],
    },
    'fullbody': {
        'beginner': [
            {'name': 'Squats', 'sets': '3', 'reps': '10-12', 'rest': '90s'},
            {'name': 'Push-ups', 'sets': '3', 'reps': '8-10', 'rest': '60s'},
            {'name': 'Dumbbell Rows', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
            {'name': 'Overhead Press', 'sets': '3', 'reps': '8-10', 'rest': '60s'},
            {'name': 'Plank', 'sets': '3', 'reps': '30-45s', 'rest': '60s'},
        ],
        'intermediate': [
            {'name': 'Deadlifts', 'sets': '4', 'reps': '6-8', 'rest': '120s'},
            {'name': 'Bench Press', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
            {'name': 'Pull-ups', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
            {'name': 'Lunges', 'sets': '3', 'reps': '12-15', 'rest': '75s'},
            {'name': 'Military Press', 'sets': '3', 'reps': '8-10', 'rest': '75s'},
            {'name': 'Hanging Leg Raises', 'sets': '3', 'reps': '10-12', 'rest': '60s'},
        ],
        'advanced': [
            {'name': 'Squats (Heavy)', 'sets': '5', 'reps': '5-6', 'rest': '150s'},
            {'name': 'Deadlifts (Heavy)', 'sets': '5', 'reps': '5-6', 'rest': '150s'},
            {'name': 'Bench Press', 'sets': '5', 'reps': '5-6', 'rest': '120s'},
            {'name': 'Weighted Pull-ups', 'sets': '4', 'reps': '6-8', 'rest': '120s'},
            {'name': 'Front Squats', 'sets': '4', 'reps': '8-10', 'rest': '120s'},
            {'name': 'Barbell Rows', 'sets': '4', 'reps': '8-10', 'rest': '90s'},
        ],
    },
}

# --- Template Filters ---
@app.template_filter('currency')
def currency_filter(value):
    """Formats a number as Indian Rupees."""
    if value is None:
        value = 0
    return f"₹{value:,.2f}"

@app.template_filter('format_isodate')
def format_isodate_filter(value, format_str="%b %d, %Y"):
    if not value:
        return "N/A"
    try:
        # datetime.fromisoformat() is built to handle Supabase's format
        # (e.g., 2025-11-15T17:18:37.123456+00:00)
        dt = datetime.fromisoformat(value)
        return dt.strftime(format_str)
    except (ValueError, TypeError):
        # Fallback for any other weird date formats
        return value
        
# --- Helper Function ---
def get_user_from_session():
    return session.get("user")

# --- Routes ---

@app.route("/")
def index():
    user = get_user_from_session()
    if user:
        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        elif user["role"] == "trainer":
            return redirect(url_for("trainer_dashboard"))
        elif user["role"] == "member":
            return redirect(url_for("member_dashboard"))
    return render_template("guest_portal.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")
        table_to_query = "members" if role in ["admin", "member"] else "trainers"
        
        try:
            response = supabase.from_(table_to_query).select("*").eq("email", email).execute()
            if not response.data:
                flash("Invalid email or password.", "error")
                return redirect(url_for("login"))

            user_data = response.data[0]
            
            if password_matches(user_data["password"], password):
                if not is_hashed(user_data["password"]):
                    try:  # upgrade a legacy plain-text row; a failure must not block the login
                        supabase.from_(table_to_query).update({"password": hash_password(password)}).eq("id", user_data["id"]).execute()
                    except Exception:
                        app.logger.exception("could not upgrade legacy password hash")
                final_role = role
                if role == "member" and (user_data.get("plan") == "Admin" or user_data.get("email") == "admin@gym.com"):
                     final_role = "admin"

                session["user"] = {
                    "email": user_data["email"],
                    "name": user_data["name"],
                    "id": user_data["id"],
                    "role": final_role
                }
                return redirect(url_for("index"))
            else:
                flash("Invalid email or password.", "error")
                return redirect(url_for("login"))
        
        except Exception as e:
            app.logger.exception("login failed")
            flash("Something went wrong. Please try again.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        plan = request.form.get("plan")
        
        if not name or not email or not password or not plan:
            flash("Name, Email, Password, and Plan are required.", "error")
            return redirect(url_for("signup"))
        if plan not in ALLOWED_PLANS or email.strip().lower() in RESERVED_EMAILS:
            flash("Invalid plan or email.", "error")
            return redirect(url_for("signup"))

        try:
            joined_date = datetime.now()
            expiry_date = joined_date + timedelta(days=30)
            
            payload = {
                "name": name,
                "email": email,
                "password": hash_password(password),
                "phone": request.form.get("phone"),
                "gender": request.form.get("gender"),
                "age": int(request.form.get("age")) if request.form.get("age", '').isdigit() else None,
                "address": request.form.get("address"),
                "plan": plan,
                "status": "Active",
                "joined_date": joined_date.strftime("%Y-%m-%d"),
                "expiry_date": expiry_date.strftime("%Y-%m-%d"),
            }

            response = supabase.from_("members").insert(payload).execute()
            
            if response.data:
                flash("Account created successfully! Please log in.", "success")
                return redirect(url_for("login"))
            else:
                if response.error and "duplicate key" in response.error.message:
                     flash("An account with this email already exists.", "error")
                else:
                    flash(f"Error creating account: {response.error.message if response.error else 'Unknown error'}", "error")
                return redirect(url_for("signup"))

        except Exception as e:
            app.logger.exception("signup failed")
            flash("Something went wrong. Please try again.", "error")
            return redirect(url_for("signup"))

    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))

# --- Admin Dashboard Routes ---

@app.route("/dashboard/admin")
def admin_dashboard():
    """
    This is the ADMIN OVERVIEW page.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))

    try:
        members = supabase.from_("members").select("*").execute().data
        trainers = supabase.from_("trainers").select("*").execute().data
        payments = supabase.from_("payments").select("*").execute().data
        checkins = supabase.from_("checkins").select("*").execute().data
        passes = supabase.from_("one_day_passes").select("*").execute().data
    except Exception as e:
        flash(f"Error fetching data: {e}", "error")
        members, trainers, payments, checkins, passes = [], [], [], [], []

    total_revenue = sum(p.get("amount", 0) for p in payments)
    active_members = len([m for m in members if m.get("status") == "Active"])
    sessions_count = len(checkins)
    trainer_count = len(trainers)

    revenue_last_7_days = []
    today = datetime.now()
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        day_total = sum(
            p.get("amount", 0) for p in payments 
            if p.get("timestamp") and p["timestamp"].startswith(day_str)
        )
        revenue_last_7_days.append({
            "label": day.strftime("%b %d"),
            "amount": day_total
        })

    return render_template(
        "admin_overview.html",
        user=user,
        active_page="overview",
        members_list=members,
        trainers_list=trainers,
        payments_list=payments,
        checkins_list=checkins,
        passes_list=passes,
        total_revenue=total_revenue,
        active_members=active_members,
        sessions_count=sessions_count,
        trainer_count=trainer_count,
        revenue_last_7_days=revenue_last_7_days
    )

#
# --- THIS IS THE ***CORRECT*** ADMIN_MEMBERS FUNCTION ---
#
@app.route("/admin/members")
def admin_members():
    """
    This is the "Manage Members" page.
    It fetches all members and displays them in a table.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    try:
        members = supabase.from_("members").select("*").order("id", desc=True).execute().data
    except Exception as e:
        flash(f"Error fetching members: {e}", "error")
        members = []

    return render_template(
        "admin_members.html", 
        user=user,
        active_page="members",
        members_list=members
    )


@app.route("/admin/members/add", methods=["GET", "POST"])
def admin_add_member():
    """
    Handles the "Add Member" page.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        plan = request.form.get("plan")
        
        if not name or not email or not password or not plan:
            flash("Name, Email, Password, and Plan are required fields.", "error")
            return redirect(url_for("admin_add_member"))
        if plan not in ALLOWED_PLANS:
            flash("Invalid plan.", "error")
            return redirect(url_for("admin_add_member"))

        try:
            joined_date = datetime.now()
            expiry_date = joined_date + timedelta(days=30)
            
            payload = {
                "name": name,
                "email": email,
                "password": hash_password(password),
                "phone": request.form.get("phone"),
                "gender": request.form.get("gender"),
                "age": int(request.form.get("age")) if request.form.get("age", '').isdigit() else None,
                "address": request.form.get("address"),
                "plan": plan,
                "status": "Active",
                "joined_date": joined_date.strftime("%Y-%m-%d"),
                "expiry_date": expiry_date.strftime("%Y-%m-%d"),
            }

            response = supabase.from_("members").insert(payload).execute()
            
            if response.data:
                flash(f"Member '{name}' created successfully!", "success")
                return redirect(url_for("admin_members"))
            else:
                if response.error and "duplicate key" in response.error.message:
                     flash("An account with this email already exists.", "error")
                else:
                    flash(f"Error creating member: {response.error.message if response.error else 'Unknown error'}", "error")
                return redirect(url_for("admin_add_member"))

        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "error")
            return redirect(url_for("admin_add_member"))

    return render_template(
        "admin_add_member.html", 
        user=user,
        active_page="members"
    )

@app.route("/admin/members/delete/<int:member_id>", methods=["POST"])
def admin_delete_member(member_id):
    """
    Handles the deletion of a member.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to perform this action.", "error")
        return redirect(url_for("admin_members"))

    try:
        response = supabase.from_("members").delete().eq("id", member_id).execute()
        
        if response.data:
            flash(f"Member (ID: {member_id}) has been deleted successfully.", "success")
        else:
            flash(f"Error deleting member: {response.error.message if response.error else 'Member not found.'}", "error")

    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "error")
    
    return redirect(url_for("admin_members"))

@app.route("/admin/members/edit/<int:member_id>", methods=["GET", "POST"])
def admin_edit_member(member_id):
    """
    Handles the "Edit Member" page.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("admin_members"))

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        plan = request.form.get("plan")
        status = request.form.get("status")
        
        if not name or not email or not plan:
            flash("Name, Email, and Plan are required fields.", "error")
            return redirect(url_for("admin_edit_member", member_id=member_id))

        try:
            payload = {
                "name": name,
                "email": email,
                "phone": request.form.get("phone"),
                "gender": request.form.get("gender"),
                "age": int(request.form.get("age")) if request.form.get("age", '').isdigit() else None,
                "address": request.form.get("address"),
                "plan": plan,
                "status": status,
                "expiry_date": request.form.get("expiry_date")
            }

            response = supabase.from_("members").update(payload).eq("id", member_id).execute()
            
            if response.data:
                flash(f"Member '{name}' (ID: {member_id}) updated successfully!", "success")
                return redirect(url_for("admin_members"))
            else:
                flash(f"Error updating member: {response.error.message if response.error else 'Unknown error'}", "error")
        
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "error")
        
        return redirect(url_for("admin_edit_member", member_id=member_id))

    try:
        response = supabase.from_("members").select("*").eq("id", member_id).single().execute()
        
        if not response.data:
            flash(f"No member found with ID {member_id}.", "error")
            return redirect(url_for("admin_members"))
            
        member_data = response.data
        
        return render_template(
            "admin_edit_member.html", 
            user=user,
            active_page="members",
            member=member_data
        )

    except Exception as e:
        flash(f"Error fetching member data: {e}", "error")
        return redirect(url_for("admin_members"))

@app.route("/admin/trainers")
def admin_trainers():
    """
    This is the "Manage Trainers" page.
    It fetches all trainers and displays them in a table.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    try:
        # 1. Fetch all trainers from Supabase
        trainers = supabase.from_("trainers").select("*").order("id", desc=True).execute().data
    except Exception as e:
        flash(f"Error fetching trainers: {e}", "error")
        trainers = []

    # 2. Render the new trainers template, passing in the data
    return render_template(
        "admin_trainers.html", 
        user=user,
        active_page="trainers",  # This tells the sidebar to highlight the 'Trainers' link
        trainers_list=trainers
    )

@app.route("/admin/trainers/add", methods=["GET", "POST"])
def admin_add_trainer():
    """
    Handles the "Add Trainer" page.
    GET: Shows the form.
    POST: Processes the form data and creates a new trainer.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))

    # Handle the form submission
    if request.method == "POST":
        # 1. Get all data from the form
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        
        if not name or not email or not password:
            flash("Name, Email, and Password are required fields.", "error")
            return redirect(url_for("admin_add_trainer"))

        try:
            # 2. Calculate join date
            joined_date = datetime.now().strftime("%Y-%m-%d")
            
            # 3. Create the payload for Supabase
            payload = {
                "name": name,
                "email": email,
                "password": hash_password(password),
                "phone": request.form.get("phone"),
                "specialization": request.form.get("specialization"),
                "experience": request.form.get("experience"),
                "certification": request.form.get("certification"),
                "salary": request.form.get("salary"),
                "joined_date": joined_date,
            }

            # 4. Insert into Supabase
            response = supabase.from_("trainers").insert(payload).execute()
            
            if response.data:
                flash(f"Trainer '{name}' created successfully!", "success")
                return redirect(url_for("admin_trainers")) # Send back to the trainers list
            else:
                if response.error and "duplicate key" in response.error.message:
                     flash("A trainer with this email already exists.", "error")
                else:
                    flash(f"Error creating trainer: {response.error.message if response.error else 'Unknown error'}", "error")
                return redirect(url_for("admin_add_trainer"))

        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "error")
            return redirect(url_for("admin_add_trainer"))

    # Show the "Add Trainer" form (GET request)
    return render_template(
        "admin_add_trainer.html", 
        user=user,
        active_page="trainers"  # Keep the 'Trainers' link highlighted
    )

# --- ADD THIS NEW FUNCTION to app.py ---

@app.route("/admin/trainers/delete/<int:trainer_id>", methods=["POST"])
def admin_delete_trainer(trainer_id):
    """
    Handles the deletion of a trainer.
    This route ONLY accepts POST requests for security.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to perform this action.", "error")
        return redirect(url_for("admin_trainers"))

    try:
        # 1. Attempt to delete the trainer from Supabase using their ID
        response = supabase.from_("trainers").delete().eq("id", trainer_id).execute()
        
        if response.data:
            flash(f"Trainer (ID: {trainer_id}) has been deleted successfully.", "success")
        else:
            flash(f"Error deleting trainer: {response.error.message if response.error else 'Trainer not found.'}", "error")

    except Exception as e:
        # This might fail if the trainer is linked to classes, etc.
        flash(f"An unexpected error occurred: {e}", "error")
    
    # 2. Always redirect back to the trainers list
    return redirect(url_for("admin_trainers"))



@app.route("/admin/trainers/edit/<int:trainer_id>", methods=["GET", "POST"])
def admin_edit_trainer(trainer_id):
    """
    Handles the "Edit Trainer" page.
    GET: Shows the form pre-filled with the trainer's data.
    POST: Processes the form data and updates the trainer.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("admin_trainers"))

    # --- Handle POST request (saving changes) ---
    if request.method == "POST":
        # 1. Get all data from the form
        name = request.form.get("name")
        email = request.form.get("email")
        
        if not name or not email:
            flash("Name and Email are required fields.", "error")
            return redirect(url_for("admin_edit_trainer", trainer_id=trainer_id))

        try:
            # 2. Create the payload for Supabase
            payload = {
                "name": name,
                "email": email,
                "phone": request.form.get("phone"),
                "specialization": request.form.get("specialization"),
                "experience": request.form.get("experience"),
                "certification": request.form.get("certification"),
                "salary": request.form.get("salary"),
                "clients": int(request.form.get("clients")) if request.form.get("clients", '').isdigit() else 0,
                "rating": float(request.form.get("rating")) if request.form.get("rating", '').replace('.', '', 1).isdigit() else 0.0
            }

            # 3. Update the trainer in Supabase
            response = supabase.from_("trainers").update(payload).eq("id", trainer_id).execute()
            
            if response.data:
                flash(f"Trainer '{name}' (ID: {trainer_id}) updated successfully!", "success")
                return redirect(url_for("admin_trainers"))
            else:
                flash(f"Error updating trainer: {response.error.message if response.error else 'Unknown error'}", "error")
        
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "error")
        
        return redirect(url_for("admin_edit_trainer", trainer_id=trainer_id))

    # --- Handle GET request (showing the form) ---
    try:
        # 1. Fetch the existing trainer's data
        response = supabase.from_("trainers").select("*").eq("id", trainer_id).single().execute()
        
        if not response.data:
            flash(f"No trainer found with ID {trainer_id}.", "error")
            return redirect(url_for("admin_trainers"))
            
        trainer_data = response.data
        
        # 2. Render the edit form, passing in the trainer's data
        return render_template(
            "admin_edit_trainer.html", 
            user=user,
            active_page="trainers",  # Keep the 'Trainers' link highlighted
            trainer=trainer_data     # Pass the data to pre-fill the form
        )

    except Exception as e:
        flash(f"Error fetching trainer data: {e}", "error")
        return redirect(url_for("admin_trainers"))

# --- ADD THIS NEW FUNCTION to app.py ---

@app.route("/admin/payments")
def admin_payments():
    """
    This is the "Manage Payments" page.
    It fetches all payments and displays them in a table.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    try:
        # 1. Fetch all payments from Supabase, newest first.
        # We also "join" the members table to get the member's name.
        payments = supabase.from_("payments") \
            .select("*, members(name)") \
            .order("timestamp", desc=True) \
            .execute().data
            
    except Exception as e:
        flash(f"Error fetching payments: {e}", "error")
        payments = []

    # 2. Render the new payments template, passing in the data
    return render_template(
        "admin_payments.html", 
        user=user,
        active_page="payments",  # This tells the sidebar to highlight the 'Payments' link
        payments_list=payments
    )

@app.route("/admin/checkins")
def admin_checkins():
    """
    This is the "Check-ins" page.
    It fetches all check-in records.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    try:
        # 1. Fetch all checkins from Supabase, newest first.
        # We also "join" the members table to get the member's name.
        checkins = supabase.from_("checkins") \
            .select("*, members(name)") \
            .order("timestamp", desc=True) \
            .execute().data
            
    except Exception as e:
        flash(f"Error fetching check-ins: {e}", "error")
        checkins = []

    # 2. Render the new checkins template
    return render_template(
        "admin_checkins.html", 
        user=user,
        active_page="checkins",  # This tells the sidebar to highlight the 'Check-ins' link
        checkins_list=checkins
    )

@app.route("/admin/passes")
def admin_passes():
    """
    This is the "One-Day Passes" page.
    It fetches all pass booking records.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    try:
        # 1. Fetch all passes from Supabase, newest first.
        passes = supabase.from_("one_day_passes") \
            .select("*") \
            .order("booking_date", desc=True) \
            .execute().data
            
    except Exception as e:
        flash(f"Error fetching one-day passes: {e}", "error")
        passes = []

    # 2. Render the new passes template
    return render_template(
        "admin_passes.html", 
        user=user,
        active_page="passes",  # This tells the sidebar to highlight the 'Passes' link
        passes_list=passes
    )

# --- Trainer Dashboard Routes ---

@app.route("/dashboard/trainer")
def trainer_dashboard():
    """
    This is the TRAINER OVERVIEW page.
    """
    user = get_user_from_session()
    if not user or user["role"] != "trainer":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))

    trainer_id = user["id"]
    client_count = 0
    class_count = 0
    sessions_today = []
    
    try:
        client_sessions = supabase.from_("trainer_sessions").select("member_id").eq("trainer_id", trainer_id).execute().data
        unique_client_ids = {session['member_id'] for session in client_sessions}
        client_count = len(unique_client_ids)

        class_response = supabase.from_("classes").select("*", count='exact').eq("trainer_id", trainer_id).execute()
        class_count = class_response.count or 0

        today = datetime.now().date()
        today_start = str(today)
        tomorrow = today + timedelta(days=1)
        today_end = str(tomorrow)

        sessions_today = supabase.from_("trainer_sessions") \
            .select("*, members(name)") \
            .eq("trainer_id", trainer_id) \
            .gte("timestamp", today_start) \
            .lt("timestamp", today_end) \
            .execute().data
            
    except Exception as e:
        flash(f"Error fetching trainer data: {e}", "error")

    return render_template(
        "trainer_overview.html",
        user=user,
        trainer_active_page="overview",
        client_count=client_count,
        class_count=class_count,
        sessions_today=sessions_today
    )

@app.route("/dashboard/trainer/clients")
def trainer_clients():
    """
    This is the "My Clients" page for trainers.
    It finds all members assigned to this trainer.
    """
    user = get_user_from_session()
    if not user or user["role"] != "trainer":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    trainer_id = user["id"]
    clients = []

    try:
        # 1. Get all unique member IDs from 'trainer_sessions' for this trainer
        session_rows = supabase.from_("trainer_sessions") \
            .select("member_id") \
            .eq("trainer_id", trainer_id) \
            .execute().data
        
        # Get a unique set of IDs
        client_ids = list({row['member_id'] for row in session_rows})

        # 2. Fetch the member details for those IDs
        if client_ids:
            clients = supabase.from_("members") \
                .select("*") \
                .in_("id", client_ids) \
                .execute().data
            
    except Exception as e:
        flash(f"Error fetching your clients: {e}", "error")
        clients = []

    # 3. Render the new 'my clients' template
    return render_template(
        "trainer_clients.html", 
        user=user,
        trainer_active_page="clients",  # This tells the sidebar to highlight the link
        clients_list=clients
    )

@app.route("/dashboard/trainer/schedule")
def trainer_schedule():
    """
    This is the "My Schedule" page for trainers.
    It fetches all upcoming classes and personal sessions.
    """
    user = get_user_from_session()
    if not user or user["role"] != "trainer":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    trainer_id = user["id"]
    sorted_events = []
    
    try:
        now = datetime.now().isoformat()

        # 1. Get all upcoming personal training sessions
        sessions = supabase.from_("trainer_sessions") \
            .select("*, members(name)") \
            .eq("trainer_id", trainer_id) \
            .gte("timestamp", now) \
            .order("timestamp") \
            .execute().data
        
        # 2. Get all upcoming group classes
        classes = supabase.from_("classes") \
            .select("*") \
            .eq("trainer_id", trainer_id) \
            .gte("starts_at", now) \
            .order("starts_at") \
            .execute().data

        # 3. Combine them into one list
        all_events = []
        for session in sessions:
            all_events.append({
                "type": "Personal Training",
                "title": session.get('members', {}).get('name') or 'Personal Session',
                "date_time": session.get('timestamp')
            })
        
        for a_class in classes:
            all_events.append({
                "type": "Group Class",
                "title": a_class.get('title'),
                "date_time": a_class.get('starts_at')
            })

        # 4. Sort the combined list by date
        # We use a helper function to handle None dates just in case
        def get_date(event):
            dt_str = event.get("date_time")
            if not dt_str:
                return datetime.max.replace(tzinfo=None) # Put events with no date at the end
            return datetime.fromisoformat(dt_str).replace(tzinfo=None)

        sorted_events = sorted(all_events, key=get_date)

    except Exception as e:
        flash(f"Error fetching your schedule: {e}", "error")
        sorted_events = []

    # 5. Render the new 'my schedule' template
    return render_template(
        "trainer_schedule.html", 
        user=user,
        trainer_active_page="schedule",  # This tells the sidebar to highlight the link
        events_list=sorted_events
    )

@app.route("/dashboard/trainer/tools", methods=["GET", "POST"])
def trainer_tools():
    """
    This is the "Tools" page for trainers.
    It provides standalone calculators.
    GET: Shows the blank forms.
    POST: Processes a form and re-renders the page with results.
    """
    user = get_user_from_session()
    if not user or user["role"] != "trainer":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    # These will hold the results after a POST
    bmi_results = None
    workout_results = None

    if request.method == "POST":
        form_type = request.form.get("form_type")
        
        # --- Handle the BMI Calculator Form ---
        if form_type == "bmi":
            try:
                height_cm = float(request.form.get("height"))
                weight_kg = float(request.form.get("weight"))
                height_m = height_cm / 100
                bmi = round(weight_kg / (height_m * height_m), 1)
                
                if bmi < 18.5: category = 'Underweight'
                elif bmi < 25: category = 'Normal'
                elif bmi < 30: category = 'Overweight'
                else: category = 'Obese'
                
                bmi_results = {"bmi": bmi, "category": category}
            except Exception as e:
                flash(f"Error in BMI calculation: {e}", "error")
        
        # --- Handle the Workout Generator Form ---
        elif form_type == "workout":
            try:
                split = request.form.get("split")
                level = request.form.get("level")
                goal = request.form.get("goal")
                num_exercises = int(request.form.get("num_exercises"))
                
                exercise_pool = exercise_database.get(split, {}).get(level, [])
                random.shuffle(exercise_pool)
                selected_exercises = exercise_pool[:num_exercises]
                
                final_workout = []
                for exercise in selected_exercises:
                    new_exercise = exercise.copy()
                    sets, reps = new_exercise['sets'], new_exercise['reps']
                    if goal == 'strength':
                        new_exercise['sets'] = str(int(sets) + 1); new_exercise['reps'] = '4-6'
                    elif goal == 'endurance':
                        new_exercise['reps'] = '15-20'
                    final_workout.append(new_exercise)
                
                workout_results = final_workout
            except Exception as e:
                flash(f"Error generating workout: {e}", "error")

    # This 'render_template' is used for both GET and POST
    return render_template(
        "trainer_tools.html", 
        user=user,
        trainer_active_page="tools",  # This tells the sidebar to highlight the link
        bmi_results=bmi_results,
        workout_results=workout_results
    )


# --- Member Dashboard Routes ---

@app.route("/dashboard/member")
def member_dashboard():
    """
    This is the MEMBER OVERVIEW page.
    It fetches all data for the logged-in member.
    """
    user = get_user_from_session()
    if not user or user["role"] != "member":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))

    member_id = user["id"]
    member, checkins, sessions = None, [], []

    try:
        # 1. Get member's full details
        member_response = supabase.from_("members").select("*").eq("id", member_id).single().execute()
        member = member_response.data if member_response.data else None
        
        # 2. Parallel fetches for activity
        checkin_response = supabase.from_("checkins").select("*").eq("member_id", member_id).order("timestamp", desc=True).limit(200).execute()
        checkins = checkin_response.data if checkin_response.data else []
        
        session_response = supabase.from_("trainer_sessions").select("*, trainers(name,email)").eq("member_id", member_id).order("timestamp", desc=True).limit(200).execute()
        sessions = session_response.data if session_response.data else []
        
        # 3. Auto-checkin logic
        if member and member.get("status") == "Active":
            
            # Helper function to parse ISO date strings safely
            def safe_fromiso(date_str):
                if not date_str: return None
                # Handle full ISO format (with timezone and microseconds)
                try: return datetime.fromisoformat(date_str)
                except ValueError:
                    # Handle date-only or time-zone missing formats
                    return datetime.strptime(date_str.split('.')[0], '%Y-%m-%dT%H:%M:%S')

            last_checkin = checkins[0].get("timestamp") if checkins else None
            needs_checkin = True
            
            if last_checkin:
                last_checkin_time = safe_fromiso(last_checkin)
                
                # Check only if parsing was successful
                if last_checkin_time:
                    # If it's been less than 6 hours, do not check in
                    if (datetime.now() - last_checkin_time).total_seconds() < 6 * 3600:
                        needs_checkin = False
                
            if needs_checkin:
                # Insert check-in and re-fetch list
                supabase.from_("checkins").insert({"member_id": member_id}).execute()
                checkin_response = supabase.from_("checkins").select("*").eq("member_id", member_id).order("timestamp", ascending=False).limit(200).execute()
                checkins = checkin_response.data if checkin_response.data else []

    except Exception as e:
        flash(f"Error fetching your data: {e}", "error")
        # Ensure 'member' is defined even on failure
        member = member if member else {}

    # 4. Calculate stats
    total_checkins = len(checkins)
    total_sessions = len(sessions)
    
    # Calculate current streak
    current_streak = 0
    if checkins:
        day_set = {
            # Use split to handle the complex ISO format correctly for date comparison
            c.get("timestamp").split('T')[0] 
            for c in checkins if c.get("timestamp")
        }
        today = datetime.now().strftime('%Y-%m-%d')
        
        for i in range(len(day_set)):
            d = datetime.now().date() - timedelta(days=i)
            d_str = d.strftime('%Y-%m-%d')
            
            if d_str == today and d_str in day_set:
                current_streak += 1
            elif d_str < today and d_str in day_set:
                current_streak += 1
            else:
                break

    return render_template(
        "member_overview.html",
        user=user,
        member=member,
        member_active_page="overview",
        total_checkins=total_checkins,
        total_sessions=total_sessions,
        current_streak=current_streak,
        recent_sessions=sessions[:5]
    )

@app.route("/dashboard/member/health", methods=["GET", "POST"])
def member_health():
    """
    This is the "Health" page (BMI Calculator).
    GET: Shows the calculator and BMI history.
    POST: Calculates, saves BMI/Nutrition data, and shows the results.
    """
    user = get_user_from_session()
    if not user or user["role"] != "member":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))

    member_id = user["id"]
    calculation_results = None
    
    # Handle the form submission
    if request.method == "POST":
        try:
            # 1. Get all data from form (Including NEW fields)
            height_cm = float(request.form.get("height"))
            weight_kg = float(request.form.get("weight"))
            age = int(request.form.get("age"))
            gender = request.form.get("gender")
            activity_level = request.form.get("activity_level")
            goal = request.form.get("goal")

            # NEW INPUTS
            target_weight = float(request.form.get("target_weight"))
            duration_weeks = int(request.form.get("duration_weeks"))
            
            # 2. BMI Calculation
            height_m = height_cm / 100
            bmi = round(weight_kg / (height_m * height_m), 1)
            
            if bmi < 18.5: category = 'Underweight'
            elif bmi < 25: category = 'Normal'
            elif bmi < 30: category = 'Overweight'
            else: category = 'Obese'

            # 3. BMR (Basal Metabolic Rate) - Mifflin-St Jeor Equation
            if gender == 'male':
                bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
            else:
                bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
            
            bmr = round(bmr)

            # 4. TDEE (Total Daily Energy Expenditure)
            activity_multipliers = {
                'sedentary': 1.2,
                'light': 1.375,
                'moderate': 1.55,
                'active': 1.725,
                'veryActive': 1.9
            }
            tdee = round(bmr * activity_multipliers.get(activity_level, 1.55))

            # 5. Goal-based calorie adjustment (Calculated Adjustment)
            
            # Note: We must ensure duration_weeks is positive to avoid DivisionByZero
            if duration_weeks <= 0:
                daily_adjustment = 0
            elif goal == 'maintain':
                daily_adjustment = 0
            else:
                weight_difference_kg = target_weight - weight_kg # Positive if gaining, negative if losing
                # A common estimate: 1 kg of mass change requires ~7700 kcal adjustment
                total_calorie_adjustment = weight_difference_kg * 7700
                duration_days = duration_weeks * 7
                
                # The daily adjustment needed to hit the goal
                daily_adjustment = round(total_calorie_adjustment / duration_days)
            
            target_calories = tdee + daily_adjustment
            
            # Safety checks for extremely low targets
            target_calories = max(1200, target_calories)
            
            # 6. Macronutrient Breakdown (40% carbs, 30% protein, 30% fat)
            protein = round((target_calories * 0.30) / 4)
            carbs = round((target_calories * 0.40) / 4)
            fats = round((target_calories * 0.30) / 9)

            # 7. Save BMI to database 
            supabase.from_("bmi_history").insert({
                "member_id": member_id,
                "weight_kg": weight_kg,
                "height_cm": height_cm,
                "bmi": bmi,
                "category": category
            }).execute()
            
            # 8. Store results to display
            calculation_results = {
                "bmi": bmi,
                "category": category,
                "bmr": bmr,
                "tdee": tdee,
                "target_calories": target_calories,
                "protein": protein,
                "carbs": carbs,
                "fats": fats,
                "goal": goal,
                "target_weight": target_weight,
                "duration_weeks": duration_weeks,
                "daily_adjustment": daily_adjustment
            }
            flash("Health metrics calculated and saved!", "success")

        except Exception as e:
            flash(f"Error processing calculation: Please check your input fields. Error: {e}", "error")

    # --- Handle the GET request (and the end of the POST) ---
    try:
        # Fetch all past BMI history for this member
        history = supabase.from_("bmi_history") \
            .select("*") \
            .eq("member_id", member_id) \
            .order("recorded_at", desc=True) \
            .limit(10) \
            .execute().data
            
    except Exception as e:
        flash(f"Error fetching BMI history: {e}", "error")
        history = []

    # Render the health page
    return render_template(
        "member_health.html",
        user=user,
        member_active_page="health",
        results=calculation_results,
        history=history
    )

@app.route("/dashboard/member/workout", methods=["GET", "POST"])
def member_workout():
    """
    This is the "Workout Generator" page.
    """
    user = get_user_from_session()
    if not user or user["role"] != "member":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))

    member_id = user["id"]
    generated_workout = None
    
    if request.method == "POST":
        try:
            split = request.form.get("split")
            level = request.form.get("level")
            goal = request.form.get("goal")
            num_exercises = int(request.form.get("num_exercises"))
            
            exercise_pool = exercise_database.get(split, {}).get(level, [])
            
            random.shuffle(exercise_pool)
            selected_exercises = exercise_pool[:num_exercises]
            
            final_workout = []
            for exercise in selected_exercises:
                new_exercise = exercise.copy()
                sets, reps = new_exercise['sets'], new_exercise['reps']
                
                if goal == 'strength':
                    new_exercise['sets'] = str(int(sets) + 1)
                    new_exercise['reps'] = '4-6'
                elif goal == 'endurance':
                    new_exercise['reps'] = '15-20'
                
                final_workout.append(new_exercise)
            
            generated_workout = final_workout
            
            supabase.from_("workout_logs").insert({
                "member_id": member_id,
                "workout": json.dumps(final_workout)
            }).execute()
            
            flash("Your new workout has been generated and saved!", "success")

        except Exception as e:
            flash(f"Error generating workout: {e}", "error")

    try:
        logs = supabase.from_("workout_logs") \
            .select("*") \
            .eq("member_id", member_id) \
            .order("created_at", desc=True) \
            .limit(10) \
            .execute().data
        
        # *** FIX: PARSE THE JSON WORKOUT STRING IN PYTHON ***
        for log in logs:
            if isinstance(log.get("workout"), str):
                log["workout"] = json.loads(log["workout"])
            # If it's already a dict/list (which newer Supabase versions do), leave it alone.
            
    except Exception as e:
        flash(f"Error fetching workout history: {e}", "error")
        logs = []

    # Render the workout page
    return render_template(
        "member_workout.html",
        user=user,
        member_active_page="workout",
        generated_workout=generated_workout,
        past_workouts=logs
    )

@app.route("/dashboard/member/personal_training", methods=["GET", "POST"])
def member_personal_training():
    """
    Handles booking personal training sessions based on member's plan limit (VIP: 8, Premium: 2).
    """
    user = get_user_from_session()
    if not user or user["role"] != "member":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    member_id = user["id"]
    trainers_list = []
    
    try:
        # Fetch member data for limit check
        member_response = supabase.from_("members").select("id, plan").eq("id", member_id).single().execute().data
        member_data = member_response if member_response else {}
        
        # Calculate sessions used this month
        now = datetime.now() # *** FIX 1: Define 'now' here ***
        start_of_month = datetime(now.year, now.month, 1).isoformat()
        
        sessions_used_response = supabase.from_("trainer_sessions") \
            .select("id") \
            .eq("member_id", member_id) \
            .eq("session_type", "Personal Training") \
            .gte("timestamp", start_of_month) \
            .execute().data
            
        sessions_used = len(sessions_used_response)
        
        # Define limits based on your logic (8 for VIP, 2 for Premium)
        if member_data.get('plan') == 'VIP':
            limit = 8
        elif member_data.get('plan') == 'Premium':
            limit = 2
        else:
            limit = 0 

        sessions_remaining = max(0, limit - sessions_used)
        
        # Fetch trainers for dropdown
        trainers_list = (
    supabase
    .from_("trainers")
    .select("id, name")
    .order("name", desc=False)   # Ascending order
    .execute()
    .data
)


    except Exception as e:
        # If this initial fetch fails, still allow access to the page with a warning
        flash(f"Error fetching session limits: {e}", "error")
        sessions_remaining = 0
        limit = 0
        now = datetime.now() # Ensure 'now' is defined even if fetch fails


    if request.method == "POST":
        if sessions_remaining <= 0:
            flash("You have used all your allotted personal training sessions for this month.", "error")
            return redirect(url_for("member_personal_training"))
            
        try:
            # 1. Get form data
            trainer_id_booked = int(request.form.get("trainer_id"))
            session_time_local = request.form.get("session_time")
            
            # 2. Insert new session
            supabase.from_("trainer_sessions").insert({
                "trainer_id": trainer_id_booked,
                "member_id": member_id,
                "session_type": "Personal Training",
                "timestamp": f"{session_time_local}:00+00:00" # Add timezone info for Supabase
            }).execute()
            
            flash("Personal Training session booked successfully!", "success")
            return redirect(url_for("member_dashboard"))

        except Exception as e:
            flash(f"Error booking session: {e}", "error")
            return redirect(url_for("member_personal_training"))


    return render_template(
        "member_personal_training.html",
        user=user,
        member_active_page="pt",
        trainers_list=trainers_list,
        sessions_used=sessions_used,
        sessions_limit=limit,
        sessions_remaining=sessions_remaining,
        now=now # *** FIX 2: Pass 'now' to the template ***
    )

@app.route("/dashboard/member/classes", methods=["GET", "POST"])
def member_classes():
    user = get_user_from_session()
    if not user or user["role"] != "member":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))

    member_id = user["id"]

    # ---------------- POST: BOOK CLASS ----------------
    if request.method == "POST":
        try:
            class_id_to_book = int(request.form.get("class_id"))

            existing = supabase.from_("enrollments") \
                .select("id") \
                .eq("member_id", member_id) \
                .eq("class_id", class_id_to_book) \
                .execute().data or []

            if existing:
                flash("You are already enrolled in this class.", "error")
                return redirect(url_for("member_classes"))

            class_data = supabase.from_("classes") \
                .select("capacity") \
                .eq("id", class_id_to_book) \
                .single().execute().data

            enrollments = supabase.from_("enrollments") \
                .select("id", count='exact') \
                .eq("class_id", class_id_to_book) \
                .execute()

            if class_data and enrollments.count is not None and enrollments.count >= class_data["capacity"]:
                flash("This class is full.", "error")
                return redirect(url_for("member_classes"))

            supabase.from_("enrollments").insert({
                "member_id": member_id,
                "class_id": class_id_to_book
            }).execute()

            flash("Class booked successfully!", "success")
        except Exception as e:
            flash(f"Error booking class: {e}", "error")

        return redirect(url_for("member_classes"))


    # ---------------- GET: FETCH DATA ----------------
    try:
        # 1. Group class enrollments
        raw_group = supabase.from_("enrollments") \
            .select("id, class_id, classes(title, starts_at, trainers(name))") \
            .eq("member_id", member_id) \
            .execute().data or []

        # Remove None entries
        my_group_enrollments = [item for item in raw_group if item]

        # 2. PT sessions
        raw_pt = supabase.from_("trainer_sessions") \
            .select("id, session_type, timestamp, trainers(name)") \
            .eq("member_id", member_id) \
            .execute().data or []

        my_pt_sessions = [item for item in raw_pt if item]

        combined_bookings = []
        my_enrolled_class_ids = set()

        # ---------- A) Add GROUP CLASSES safely -----------
        for enrollment in my_group_enrollments:

            # enrollment itself is safe now, but nested keys may be None
            class_data = enrollment.get("classes") or {}

            # if class_data is empty, skip (class deleted)
            if not class_data:
                continue

            trainer_data = class_data.get("trainers") or {}

            combined_bookings.append({
                "type": "Group",
                "title": class_data.get("title", "Untitled Class"),
                "starts_at": class_data.get("starts_at"),
                "trainer_name": trainer_data.get("name", "N/A"),
                "enrollment_id": enrollment.get("id"),
            })

            my_enrolled_class_ids.add(class_data.get("id"))

        # ---------- B) Add PT SESSIONS safely -----------
        for session in my_pt_sessions:
            trainer_data = session.get("trainers") or {}

            combined_bookings.append({
                "type": "PT",
                "title": session.get("session_type", "Personal Training"),
                "starts_at": session.get("timestamp"),
                "trainer_name": trainer_data.get("name", "N/A"),
                "enrollment_id": session.get("id"),
            })

        # Sorting
        combined_bookings.sort(key=lambda x: x.get("starts_at") or "")

        # ---------- C) Available classes ----------
        now = datetime.now().isoformat()

        all_available_classes = supabase.from_("classes") \
            .select("*, trainers(name)") \
            .gte("starts_at", now) \
            .order("starts_at") \
            .execute().data or []

    except Exception as e:
        flash(f"Error fetching class schedule: {e}", "error")
        combined_bookings = []
        my_enrolled_class_ids = set()
        all_available_classes = []

    return render_template(
        "member_classes.html",
        user=user,
        member_active_page="classes",
        combined_bookings=combined_bookings,
        available_classes=all_available_classes,
        my_enrolled_class_ids=my_enrolled_class_ids
    )



@app.route("/dashboard/member/classes/cancel", methods=["POST"])
def member_cancel_class():
    """
    Handles the cancellation of an enrollment.
    """
    user = get_user_from_session()
    if not user or user["role"] != "member":
        flash("You do not have permission to perform this action.", "error")
        return redirect(url_for("login"))

    try:
        enrollment_id_to_cancel = int(request.form.get("enrollment_id"))
        
        enrollment = supabase.from_("enrollments") \
            .select("id, member_id") \
            .eq("id", enrollment_id_to_cancel) \
            .single().execute().data
            
        if not enrollment or enrollment["member_id"] != user["id"]:
            flash("Invalid enrollment ID.", "error")
            return redirect(url_for("member_classes"))
        
        supabase.from_("enrollments").delete().eq("id", enrollment_id_to_cancel).execute()
        flash("Booking cancelled successfully.", "success")

    except Exception as e:
        flash(f"Error cancelling booking: {e}", "error")

    return redirect(url_for("member_classes"))

@app.route("/dashboard/member/profile", methods=["GET", "POST"])
def member_profile():
    """
    This is the "My Profile" page.
    """
    user = get_user_from_session()
    if not user or user["role"] != "member":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    member_id = user["id"]

    if request.method == "POST":
        try:
            name = request.form.get("name")
            phone = request.form.get("phone")
            age = request.form.get("age")
            gender = request.form.get("gender")
            address = request.form.get("address")
            
            payload = {
                "name": name,
                "phone": phone,
                "age": int(age) if age and age.isdigit() else None,
                "gender": gender,
                "address": address,
            }

            response = supabase.from_("members").update(payload).eq("id", member_id).execute()
            
            if response.data:
                flash("Your profile has been updated successfully!", "success")
                session["user"]["name"] = name
                session.modified = True
            else:
                flash(f"Error updating profile: {response.error.message if response.error else 'Unknown error'}", "error")
        
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "error")
        
        return redirect(url_for("member_profile"))

    try:
        member_data = supabase.from_("members").select("*").eq("id", member_id).single().execute().data
        
        if not member_data:
            flash("Could not retrieve your member data.", "error")
            return redirect(url_for("member_dashboard"))
            
        return render_template(
            "member_profile.html", 
            user=user,
            active_page="profile",
            member=member_data
        )

    except Exception as e:
        flash(f"Error fetching your profile: {e}", "error")
        return redirect(url_for("member_dashboard"))

# --- Helper Functions (from your supabase.ts) ---

def generate_otp():
    """Generates a 6-digit OTP string."""
    return str(random.randint(100000, 999999))

def generate_booking_id():
    """Generates a unique booking ID."""
    timestamp = int(datetime.now().timestamp() * 1000)
    rand = random.randint(100, 999)
    return f"AKHADA{timestamp}{rand}"


@app.route("/api/book_pass", methods=["POST"])
def api_book_pass():
    """
    Handles the One-Day Pass booking from JavaScript.
    Receives JSON, creates a pass, and returns JSON.
    """
    import json
    from flask import jsonify, request
    from datetime import datetime
    
    try:
        data = request.json
        name = data.get("name")
        phone = data.get("phone")
        email = data.get("email")
        booking_type = data.get("bookingType")
        
        if not name or not phone or not email or not booking_type:
            return jsonify({"success": False, "error": "Missing required fields."}), 400

        otp = generate_otp()
        booking_id = generate_booking_id()
        amount = 500 if booking_type == 'one_day_pass' else 200

        qr_data = json.dumps({
            "bookingId": booking_id,
            "name": name,
            "type": booking_type,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "amount": amount
        })

        # --- CRITICAL FIX: Checking for Supabase Errors in the response object ---
        response = supabase.from_("one_day_passes").insert({
            "name": name,
            "phone": phone,
            "email": email,
            "booking_type": booking_type,
            "otp": otp,
            "payment_status": "completed", 
            "amount": amount,
            "booking_date": datetime.now().isoformat(),
            "qr_code": qr_data
        }).execute()
        
        # Check if the response itself indicates an error (especially helpful for older libraries)
        if hasattr(response, 'error') and response.error:
            raise Exception(response.error.message)
        
        if not response.data or not isinstance(response.data, list):
            # This handles cases where data structure is unexpectedly empty or not a list
            raise Exception("Supabase returned an invalid or empty response.")
        
        # End of CRITICAL FIX ---
        
        # Send back the new data to our JavaScript
        return jsonify({
            "success": True,
            "bookingId": booking_id,
            "qrData": qr_data,
            "amount": amount,
            "date": datetime.now().strftime("%B %d, %Y")
        })

    except Exception as e:
        # Catch and send a clean error response to the client
        return jsonify({"success": False, "error": f"Booking API Error: {str(e)}"}), 500

@app.route("/admin/classes")
def admin_classes():
    """
    Shows a list of all classes for supervision. Admin can only Delete.
    """
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    try:
        # Fetch all classes, joining the trainers table to show who teaches it
        classes = supabase.from_("classes") \
            .select("*, trainers(name)") \
            .order("starts_at", desc=False) \
            .execute().data
        
    except Exception as e:
        flash(f"Error fetching classes: {e}", "error")
        classes = []

    # Note: Renders the *new* supervisory template
    return render_template(
        "admin_classes_supervisor.html", 
        user=user,
        active_page="classes",
        classes_list=classes
    )

@app.route("/admin/classes/delete/<int:class_id>", methods=["POST"])
def admin_delete_class(class_id):
    """Admin is the only one who can delete a class (supervisor role)."""
    user = get_user_from_session()
    if not user or user["role"] != "admin":
        flash("You do not have permission to perform this action.", "error")
        return redirect(url_for("admin_classes"))
    
    try:
        # NOTE: This will fail if there are existing enrollments (due to FK constraint)
        supabase.from_("classes").delete().eq("id", class_id).execute()
        flash("Class deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting class: Cannot delete class with existing enrollments.", "error")

    return redirect(url_for("admin_classes"))


# --- Trainer Dashboard Class Management Routes (Trainer CRUD) ---

@app.route("/dashboard/trainer/classes", methods=["GET"])
def trainer_classes():
    """
    Shows a list of all classes taught by this trainer.
    """
    user = get_user_from_session()
    if not user or user["role"] != "trainer":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    trainer_id = user["id"]
    
    try:
        # Fetch all classes, showing enrollment count
        classes = supabase.from_("classes") \
            .select("*, trainers(name), enrollments(count)") \
            .eq("trainer_id", trainer_id) \
            .order("starts_at") \
            .execute().data
        
        # NOTE: If needed, you would group and count enrollments here
        
    except Exception as e:
        flash(f"Error fetching your classes: {e}", "error")
        classes = []

    return render_template(
        "trainer_classes.html", 
        user=user,
        trainer_active_page="classes",
        classes_list=classes
    )

@app.route("/dashboard/trainer/classes/form", methods=["GET", "POST"])
def trainer_class_form():
    """Handles adding or editing a class by the trainer."""
    user = get_user_from_session()
    if not user or user["role"] != "trainer":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))
    
    class_id = request.args.get('class_id', type=int)
    trainer_id = user["id"]
    class_data = None
    
    # Check if editing existing class
    if class_id:
        try:
            class_data = supabase.from_("classes").select("*").eq("id", class_id).single().execute().data
            # Security check: Trainer must be the owner of the class
            if not class_data or class_data.get('trainer_id') != trainer_id:
                 flash("You are not authorized to edit this class.", "error")
                 return redirect(url_for("trainer_classes"))
            
            # Pre-process dates for HTML form display
            if class_data.get('starts_at'):
                dt = datetime.fromisoformat(class_data['starts_at'].replace('Z', '+00:00'))
                class_data['start_date'] = dt.strftime('%Y-%m-%d')
                class_data['start_time'] = dt.strftime('%H:%M')
            
        except Exception as e:
            flash(f"Error fetching class data: {e}", "error")
            return redirect(url_for("trainer_classes"))

    if request.method == "POST":
        try:
            payload = {
                "title": request.form.get("title"),
                "description": request.form.get("description"),
                "trainer_id": trainer_id, # Must be the logged-in trainer
                "capacity": int(request.form.get("capacity")),
                "price": float(request.form.get("price")),
                "starts_at": f"{request.form.get('start_date')}T{request.form.get('start_time')}:00+00:00" 
            }
            
            if class_id:
                supabase.from_("classes").update(payload).eq("id", class_id).execute()
                flash(f"Class '{payload['title']}' updated successfully!", "success")
            else:
                supabase.from_("classes").insert(payload).execute()
                flash(f"Class '{payload['title']}' scheduled successfully!", "success")

            return redirect(url_for("trainer_classes"))

        except Exception as e:
            flash(f"Error saving class: {e}", "error")
            return redirect(request.url)

    return render_template(
        "trainer_class_form.html", 
        user=user,
        trainer_active_page="classes",
        class_data=class_data,
        is_edit=class_id is not None
    )

@app.route("/dashboard/trainer/classes/delete/<int:class_id>", methods=["POST"])
def trainer_delete_class(class_id):
    """Handles the deletion of a class by the trainer."""
    user = get_user_from_session()
    if not user or user["role"] != "trainer":
        flash("You do not have permission to perform this action.", "error")
        return redirect(url_for("trainer_classes"))
    
    try:
        class_check = supabase.from_("classes").select("trainer_id").eq("id", class_id).single().execute().data
        if class_check and class_check.get('trainer_id') != user["id"]:
             flash("You are not authorized to delete this class.", "error")
             return redirect(url_for("trainer_classes"))
             
        supabase.from_("classes").delete().eq("id", class_id).execute()
        flash("Class deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting class: Cannot delete class with existing enrollments.", "error")

    return redirect(url_for("trainer_classes"))

# --- Main execution ---
if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")