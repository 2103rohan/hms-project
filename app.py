import os
import sqlite3
from datetime import date, datetime
from functools import wraps
from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "dev-hospital-management-system-secret-key"
)

DATABASE_NAME = "hospital.db"
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), DATABASE_NAME)

DEMO_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
DEMO_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def get_database_connection():
    if "database" not in g:
        g.database = sqlite3.connect(DATABASE_PATH)
        g.database.row_factory = sqlite3.Row
        g.database.execute("PRAGMA foreign_keys = ON")
    return g.database


@app.teardown_appcontext
def close_database_connection(exception=None):
    database = g.pop("database", None)
    if database is not None:
        database.close()


def initialize_database():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS doctors (
            doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT NOT NULL,
            phone TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (patient_id),
            FOREIGN KEY (doctor_id) REFERENCES doctors (doctor_id)
        );

        CREATE TABLE IF NOT EXISTS bills (
            bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            consultation_fee REAL NOT NULL,
            medicine_fee REAL NOT NULL,
            other_charges REAL NOT NULL,
            total_amount REAL NOT NULL,
            bill_date TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
        );
        """)
    connection.commit()
    connection.close()


initialize_database()


@app.cli.command("init-db")
def initialize_database_command():
    initialize_database()
    print("Database tables initialized successfully.")


def login_required(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)

    return decorated_function


@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == DEMO_ADMIN_USERNAME and password == DEMO_ADMIN_PASSWORD:
            session["user"] = username
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    database = get_database_connection()

    patient_record = database.execute(
        "SELECT COUNT(patient_id) AS total FROM patients"
    ).fetchone()
    doctor_record = database.execute(
        "SELECT COUNT(doctor_id) AS total FROM doctors"
    ).fetchone()
    appointment_record = database.execute(
        "SELECT COUNT(appointment_id) AS total FROM appointments"
    ).fetchone()
    bill_record = database.execute(
        "SELECT COUNT(bill_id) AS total FROM bills"
    ).fetchone()

    statistics = {
        "total_patients": patient_record["total"] if patient_record else 0,
        "total_doctors": doctor_record["total"] if doctor_record else 0,
        "total_appointments": appointment_record["total"] if appointment_record else 0,
        "total_bills": bill_record["total"] if bill_record else 0,
    }

    recent_appointments = database.execute("""
        SELECT
            appointments.appointment_id,
            appointments.appointment_date,
            appointments.appointment_time,
            appointments.status,
            patients.name AS patient_name,
            doctors.name AS doctor_name,
            doctors.specialization AS doctor_specialization
        FROM appointments
        INNER JOIN patients ON appointments.patient_id = patients.patient_id
        INNER JOIN doctors ON appointments.doctor_id = doctors.doctor_id
        ORDER BY appointments.appointment_id DESC
        LIMIT 5
        """).fetchall()

    return render_template(
        "dashboard.html",
        statistics=statistics,
        recent_appointments=recent_appointments,
    )


def validate_patient_data(name, age_raw, gender, phone, address):
    if not name or len(name) < 2:
        return (
            False,
            "Patient name is required and must be at least 2 characters.",
            None,
        )

    if not age_raw:
        return False, "Patient age is required.", None

    try:
        age = int(age_raw)
        if age < 1 or age > 150:
            return False, "Age must be a positive integer between 1 and 150.", None
    except ValueError:
        return False, "Age must be a valid whole number.", None

    if not gender or gender not in ["Male", "Female", "Other"]:
        return False, "Please select a valid gender.", None

    if not phone:
        return False, "Contact phone number is required.", None

    phone_digits = "".join(character for character in phone if character.isdigit())
    if len(phone_digits) < 7 or len(phone_digits) > 15:
        return False, "Phone number must contain between 7 and 15 digits.", None

    if not address or len(address) < 3:
        return (
            False,
            "Residential address is required and must be at least 3 characters.",
            None,
        )

    cleaned_data = {
        "name": name,
        "age": age,
        "gender": gender,
        "phone": phone,
        "address": address,
    }
    return True, None, cleaned_data


def escape_like_wildcards(search_text):
    return search_text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_like_pattern(search_text):
    return f"%{escape_like_wildcards(search_text)}%"


def normalize_search_date(search_text):
    cleaned = search_text.strip()
    for date_format in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            parsed_date = datetime.strptime(cleaned, date_format)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


@app.route("/patients")
@login_required
def patients():
    search_query = request.args.get("search", "").strip()
    database = get_database_connection()

    if search_query:
        search_pattern = build_like_pattern(search_query)
        patient_records = database.execute(
            """
            SELECT patient_id, name, age, gender, phone, address
            FROM patients
            WHERE name LIKE ? ESCAPE '\\'
               OR phone LIKE ? ESCAPE '\\'
            ORDER BY patient_id DESC
            """,
            (search_pattern, search_pattern),
        ).fetchall()
    else:
        patient_records = database.execute("""
            SELECT patient_id, name, age, gender, phone, address
            FROM patients
            ORDER BY patient_id DESC
            """).fetchall()

    return render_template(
        "patients.html",
        patients=patient_records,
        search_query=search_query,
    )


@app.route("/patients/add", methods=["GET", "POST"])
@login_required
def add_patient():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        age_raw = request.form.get("age", "").strip()
        gender = request.form.get("gender", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        form_data = {
            "name": name,
            "age": age_raw,
            "gender": gender,
            "phone": phone,
            "address": address,
        }

        is_valid, error_message, cleaned_data = validate_patient_data(
            name, age_raw, gender, phone, address
        )

        if not is_valid:
            flash(error_message, "error")
            return render_template(
                "patient_form.html",
                form_title="Register New Patient",
                form_subtitle="Add a new patient record to the hospital database",
                form_action=url_for("add_patient"),
                submit_button_text="Register Patient",
                form_data=form_data,
            )

        database = get_database_connection()
        database.execute(
            """
            INSERT INTO patients (name, age, gender, phone, address)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cleaned_data["name"],
                cleaned_data["age"],
                cleaned_data["gender"],
                cleaned_data["phone"],
                cleaned_data["address"],
            ),
        )
        database.commit()
        flash("Patient registered successfully.", "success")
        return redirect(url_for("patients"))

    return render_template(
        "patient_form.html",
        form_title="Register New Patient",
        form_subtitle="Add a new patient record to the hospital database",
        form_action=url_for("add_patient"),
        submit_button_text="Register Patient",
        form_data=None,
    )


@app.route("/patients/<int:patient_id>/edit", methods=["GET", "POST"])
@login_required
def edit_patient(patient_id):
    database = get_database_connection()
    patient_record = database.execute(
        """
        SELECT patient_id, name, age, gender, phone, address
        FROM patients
        WHERE patient_id = ?
        """,
        (patient_id,),
    ).fetchone()

    if patient_record is None:
        flash("Patient record not found.", "error")
        return redirect(url_for("patients"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        age_raw = request.form.get("age", "").strip()
        gender = request.form.get("gender", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        form_data = {
            "name": name,
            "age": age_raw,
            "gender": gender,
            "phone": phone,
            "address": address,
        }

        is_valid, error_message, cleaned_data = validate_patient_data(
            name, age_raw, gender, phone, address
        )

        if not is_valid:
            flash(error_message, "error")
            return render_template(
                "patient_form.html",
                form_title="Edit Patient Details",
                form_subtitle="Update registered patient details",
                form_action=url_for("edit_patient", patient_id=patient_id),
                submit_button_text="Save Changes",
                form_data=form_data,
            )

        database.execute(
            """
            UPDATE patients
            SET name = ?, age = ?, gender = ?, phone = ?, address = ?
            WHERE patient_id = ?
            """,
            (
                cleaned_data["name"],
                cleaned_data["age"],
                cleaned_data["gender"],
                cleaned_data["phone"],
                cleaned_data["address"],
                patient_id,
            ),
        )
        database.commit()
        flash("Patient record updated successfully.", "success")
        return redirect(url_for("patients"))

    return render_template(
        "patient_form.html",
        form_title="Edit Patient Details",
        form_subtitle="Update registered patient details",
        form_action=url_for("edit_patient", patient_id=patient_id),
        submit_button_text="Save Changes",
        form_data=dict(patient_record),
    )


@app.route("/patients/<int:patient_id>/delete", methods=["GET", "POST"])
@login_required
def delete_patient(patient_id):
    database = get_database_connection()
    patient_record = database.execute(
        """
        SELECT patient_id, name, age, gender, phone, address
        FROM patients
        WHERE patient_id = ?
        """,
        (patient_id,),
    ).fetchone()

    if patient_record is None:
        flash("Patient record not found.", "error")
        return redirect(url_for("patients"))

    if request.method == "POST":
        database.execute(
            "DELETE FROM patients WHERE patient_id = ?",
            (patient_id,),
        )
        database.commit()
        flash("Patient record deleted successfully.", "success")
        return redirect(url_for("patients"))

    return render_template("patient_delete.html", patient=patient_record)


def validate_doctor_data(name, specialization, phone):
    if not name or len(name) < 2:
        return False, "Doctor name is required and must be at least 2 characters.", None

    if not specialization or len(specialization) < 2:
        return (
            False,
            "Medical specialization is required and must be at least 2 characters.",
            None,
        )

    if not phone:
        return False, "Contact phone number is required.", None

    phone_digits = "".join(character for character in phone if character.isdigit())
    if len(phone_digits) < 7 or len(phone_digits) > 15:
        return False, "Phone number must contain between 7 and 15 digits.", None

    cleaned_data = {
        "name": name,
        "specialization": specialization,
        "phone": phone,
    }
    return True, None, cleaned_data


@app.route("/doctors")
@login_required
def doctors():
    search_query = request.args.get("search", "").strip()
    database = get_database_connection()

    if search_query:
        search_pattern = build_like_pattern(search_query)
        doctor_records = database.execute(
            """
            SELECT doctor_id, name, specialization, phone
            FROM doctors
            WHERE name LIKE ? ESCAPE '\\'
               OR specialization LIKE ? ESCAPE '\\'
               OR phone LIKE ? ESCAPE '\\'
            ORDER BY doctor_id DESC
            """,
            (
                search_pattern,
                search_pattern,
                search_pattern,
            ),
        ).fetchall()
    else:
        doctor_records = database.execute("""
            SELECT doctor_id, name, specialization, phone
            FROM doctors
            ORDER BY doctor_id DESC
            """).fetchall()

    return render_template(
        "doctors.html",
        doctors=doctor_records,
        search_query=search_query,
    )


@app.route("/doctors/add", methods=["GET", "POST"])
@login_required
def add_doctor():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        specialization = request.form.get("specialization", "").strip()
        phone = request.form.get("phone", "").strip()

        form_data = {
            "name": name,
            "specialization": specialization,
            "phone": phone,
        }

        is_valid, error_message, cleaned_data = validate_doctor_data(
            name, specialization, phone
        )

        if not is_valid:
            flash(error_message, "error")
            return render_template(
                "doctor_form.html",
                form_title="Add New Doctor",
                form_subtitle="Register a new medical practitioner",
                form_action=url_for("add_doctor"),
                submit_button_text="Register Doctor",
                form_data=form_data,
            )

        database = get_database_connection()
        database.execute(
            """
            INSERT INTO doctors (name, specialization, phone)
            VALUES (?, ?, ?)
            """,
            (
                cleaned_data["name"],
                cleaned_data["specialization"],
                cleaned_data["phone"],
            ),
        )
        database.commit()
        flash("Doctor registered successfully.", "success")
        return redirect(url_for("doctors"))

    return render_template(
        "doctor_form.html",
        form_title="Add New Doctor",
        form_subtitle="Register a new medical practitioner",
        form_action=url_for("add_doctor"),
        submit_button_text="Register Doctor",
        form_data=None,
    )


@app.route("/doctors/<int:doctor_id>/edit", methods=["GET", "POST"])
@login_required
def edit_doctor(doctor_id):
    database = get_database_connection()
    doctor_record = database.execute(
        """
        SELECT doctor_id, name, specialization, phone
        FROM doctors
        WHERE doctor_id = ?
        """,
        (doctor_id,),
    ).fetchone()

    if doctor_record is None:
        flash("Doctor record not found.", "error")
        return redirect(url_for("doctors"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        specialization = request.form.get("specialization", "").strip()
        phone = request.form.get("phone", "").strip()

        form_data = {
            "name": name,
            "specialization": specialization,
            "phone": phone,
        }

        is_valid, error_message, cleaned_data = validate_doctor_data(
            name, specialization, phone
        )

        if not is_valid:
            flash(error_message, "error")
            return render_template(
                "doctor_form.html",
                form_title="Edit Doctor Details",
                form_subtitle="Update medical practitioner profile",
                form_action=url_for("edit_doctor", doctor_id=doctor_id),
                submit_button_text="Save Changes",
                form_data=form_data,
            )

        database.execute(
            """
            UPDATE doctors
            SET name = ?, specialization = ?, phone = ?
            WHERE doctor_id = ?
            """,
            (
                cleaned_data["name"],
                cleaned_data["specialization"],
                cleaned_data["phone"],
                doctor_id,
            ),
        )
        database.commit()
        flash("Doctor record updated successfully.", "success")
        return redirect(url_for("doctors"))

    return render_template(
        "doctor_form.html",
        form_title="Edit Doctor Details",
        form_subtitle="Update medical practitioner profile",
        form_action=url_for("edit_doctor", doctor_id=doctor_id),
        submit_button_text="Save Changes",
        form_data=dict(doctor_record),
    )


@app.route("/doctors/<int:doctor_id>/delete", methods=["GET", "POST"])
@login_required
def delete_doctor(doctor_id):
    database = get_database_connection()
    doctor_record = database.execute(
        """
        SELECT doctor_id, name, specialization, phone
        FROM doctors
        WHERE doctor_id = ?
        """,
        (doctor_id,),
    ).fetchone()

    if doctor_record is None:
        flash("Doctor record not found.", "error")
        return redirect(url_for("doctors"))

    if request.method == "POST":
        database.execute(
            "DELETE FROM doctors WHERE doctor_id = ?",
            (doctor_id,),
        )
        database.commit()
        flash("Doctor record deleted successfully.", "success")
        return redirect(url_for("doctors"))

    return render_template("doctor_delete.html", doctor=doctor_record)


def get_appointment_form_choices(database):
    patients_list = database.execute("""
        SELECT patient_id, name
        FROM patients
        ORDER BY name
        """).fetchall()
    doctors_list = database.execute("""
        SELECT doctor_id, name, specialization
        FROM doctors
        ORDER BY name
        """).fetchall()
    return patients_list, doctors_list


def validate_appointment_data(
    database,
    patient_id_raw,
    doctor_id_raw,
    appointment_date,
    appointment_time,
    status,
):
    valid_statuses = ("Scheduled", "Completed", "Cancelled")

    if not patient_id_raw:
        return False, "Please select a registered patient.", None

    try:
        patient_id = int(patient_id_raw)
    except (ValueError, TypeError):
        return False, "Invalid patient selected.", None

    patient_record = database.execute(
        """
        SELECT patient_id
        FROM patients
        WHERE patient_id = ?
        """,
        (patient_id,),
    ).fetchone()
    if patient_record is None:
        return False, "Selected patient does not exist.", None

    if not doctor_id_raw:
        return False, "Please select a registered doctor.", None

    try:
        doctor_id = int(doctor_id_raw)
    except (ValueError, TypeError):
        return False, "Invalid doctor selected.", None

    doctor_record = database.execute(
        """
        SELECT doctor_id
        FROM doctors
        WHERE doctor_id = ?
        """,
        (doctor_id,),
    ).fetchone()
    if doctor_record is None:
        return False, "Selected doctor does not exist.", None

    if not appointment_date:
        return False, "Appointment date is required.", None

    if not appointment_time:
        return False, "Appointment time is required.", None

    if status not in valid_statuses:
        return False, "Status must be Scheduled, Completed, or Cancelled.", None

    cleaned_data = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "status": status,
    }
    return True, None, cleaned_data


@app.route("/appointments")
@login_required
def appointments():
    search_query = request.args.get("search", "").strip()
    database = get_database_connection()

    if search_query:
        search_pattern = build_like_pattern(search_query)
        normalized_date = normalize_search_date(search_query)

        if normalized_date is not None:
            appointment_records = database.execute(
                """
                SELECT
                    appointments.appointment_id,
                    patients.name AS patient_name,
                    doctors.name AS doctor_name,
                    appointments.appointment_date,
                    appointments.appointment_time,
                    appointments.status
                FROM appointments
                JOIN patients
                    ON appointments.patient_id = patients.patient_id
                JOIN doctors
                    ON appointments.doctor_id = doctors.doctor_id
                WHERE patients.name LIKE ? ESCAPE '\\'
                   OR doctors.name LIKE ? ESCAPE '\\'
                   OR appointments.appointment_date = ?
                   OR appointments.status LIKE ? ESCAPE '\\'
                ORDER BY appointments.appointment_date DESC,
                         appointments.appointment_time DESC
                """,
                (
                    search_pattern,
                    search_pattern,
                    normalized_date,
                    search_pattern,
                ),
            ).fetchall()
        else:
            appointment_records = database.execute(
                """
                SELECT
                    appointments.appointment_id,
                    patients.name AS patient_name,
                    doctors.name AS doctor_name,
                    appointments.appointment_date,
                    appointments.appointment_time,
                    appointments.status
                FROM appointments
                JOIN patients
                    ON appointments.patient_id = patients.patient_id
                JOIN doctors
                    ON appointments.doctor_id = doctors.doctor_id
                WHERE patients.name LIKE ? ESCAPE '\\'
                   OR doctors.name LIKE ? ESCAPE '\\'
                   OR appointments.status LIKE ? ESCAPE '\\'
                ORDER BY appointments.appointment_date DESC,
                         appointments.appointment_time DESC
                """,
                (
                    search_pattern,
                    search_pattern,
                    search_pattern,
                ),
            ).fetchall()
    else:
        appointment_records = database.execute("""
            SELECT
                appointments.appointment_id,
                patients.name AS patient_name,
                doctors.name AS doctor_name,
                appointments.appointment_date,
                appointments.appointment_time,
                appointments.status
            FROM appointments
            JOIN patients
                ON appointments.patient_id = patients.patient_id
            JOIN doctors
                ON appointments.doctor_id = doctors.doctor_id
            ORDER BY appointments.appointment_date DESC,
                     appointments.appointment_time DESC
            """).fetchall()

    return render_template(
        "appointments.html",
        appointments=appointment_records,
        search_query=search_query,
    )


@app.route("/appointments/add", methods=["GET", "POST"])
@login_required
def add_appointment():
    database = get_database_connection()
    patients_list, doctors_list = get_appointment_form_choices(database)

    if request.method == "POST":
        patient_id_raw = request.form.get("patient_id", "").strip()
        doctor_id_raw = request.form.get("doctor_id", "").strip()
        appointment_date = request.form.get("appointment_date", "").strip()
        appointment_time = request.form.get("appointment_time", "").strip()
        status = request.form.get("status", "Scheduled").strip()

        form_data = {
            "patient_id": patient_id_raw,
            "doctor_id": doctor_id_raw,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "status": status,
        }

        is_valid, error_message, cleaned_data = validate_appointment_data(
            database,
            patient_id_raw,
            doctor_id_raw,
            appointment_date,
            appointment_time,
            status,
        )

        if not is_valid:
            flash(error_message, "error")
            return render_template(
                "appointment_form.html",
                form_title="Book Appointment",
                form_subtitle="Schedule a new patient consultation",
                form_action=url_for("add_appointment"),
                submit_button_text="Book Appointment",
                form_data=form_data,
                patients=patients_list,
                doctors=doctors_list,
            )

        database.execute(
            """
            INSERT INTO appointments (
                patient_id,
                doctor_id,
                appointment_date,
                appointment_time,
                status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cleaned_data["patient_id"],
                cleaned_data["doctor_id"],
                cleaned_data["appointment_date"],
                cleaned_data["appointment_time"],
                cleaned_data["status"],
            ),
        )
        database.commit()
        flash("Appointment booked successfully.", "success")
        return redirect(url_for("appointments"))

    return render_template(
        "appointment_form.html",
        form_title="Book Appointment",
        form_subtitle="Schedule a new patient consultation",
        form_action=url_for("add_appointment"),
        submit_button_text="Book Appointment",
        form_data={"status": "Scheduled"},
        patients=patients_list,
        doctors=doctors_list,
    )


@app.route("/appointments/<int:appointment_id>/edit", methods=["GET", "POST"])
@login_required
def edit_appointment(appointment_id):
    database = get_database_connection()
    appointment_record = database.execute(
        """
        SELECT appointment_id, patient_id, doctor_id, appointment_date, appointment_time, status
        FROM appointments
        WHERE appointment_id = ?
        """,
        (appointment_id,),
    ).fetchone()

    if appointment_record is None:
        flash("Appointment record not found.", "error")
        return redirect(url_for("appointments"))

    patients_list, doctors_list = get_appointment_form_choices(database)

    if request.method == "POST":
        patient_id_raw = request.form.get("patient_id", "").strip()
        doctor_id_raw = request.form.get("doctor_id", "").strip()
        appointment_date = request.form.get("appointment_date", "").strip()
        appointment_time = request.form.get("appointment_time", "").strip()
        status = request.form.get("status", "").strip()

        form_data = {
            "appointment_id": appointment_id,
            "patient_id": patient_id_raw,
            "doctor_id": doctor_id_raw,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "status": status,
        }

        is_valid, error_message, cleaned_data = validate_appointment_data(
            database,
            patient_id_raw,
            doctor_id_raw,
            appointment_date,
            appointment_time,
            status,
        )

        if not is_valid:
            flash(error_message, "error")
            return render_template(
                "appointment_form.html",
                form_title="Edit Appointment",
                form_subtitle="Update patient consultation details",
                form_action=url_for("edit_appointment", appointment_id=appointment_id),
                submit_button_text="Save Changes",
                form_data=form_data,
                patients=patients_list,
                doctors=doctors_list,
            )

        database.execute(
            """
            UPDATE appointments
            SET patient_id = ?, doctor_id = ?, appointment_date = ?, appointment_time = ?, status = ?
            WHERE appointment_id = ?
            """,
            (
                cleaned_data["patient_id"],
                cleaned_data["doctor_id"],
                cleaned_data["appointment_date"],
                cleaned_data["appointment_time"],
                cleaned_data["status"],
                appointment_id,
            ),
        )
        database.commit()
        flash("Appointment updated successfully.", "success")
        return redirect(url_for("appointments"))

    return render_template(
        "appointment_form.html",
        form_title="Edit Appointment",
        form_subtitle="Update patient consultation details",
        form_action=url_for("edit_appointment", appointment_id=appointment_id),
        submit_button_text="Save Changes",
        form_data=dict(appointment_record),
        patients=patients_list,
        doctors=doctors_list,
    )


@app.route("/appointments/<int:appointment_id>/delete", methods=["GET", "POST"])
@login_required
def delete_appointment(appointment_id):
    database = get_database_connection()
    appointment_record = database.execute(
        """
        SELECT
            appointments.appointment_id,
            appointments.patient_id,
            patients.name AS patient_name,
            appointments.doctor_id,
            doctors.name AS doctor_name,
            doctors.specialization AS doctor_specialization,
            appointments.appointment_date,
            appointments.appointment_time,
            appointments.status
        FROM appointments
        JOIN patients
            ON appointments.patient_id = patients.patient_id
        JOIN doctors
            ON appointments.doctor_id = doctors.doctor_id
        WHERE appointments.appointment_id = ?
        """,
        (appointment_id,),
    ).fetchone()

    if appointment_record is None:
        flash("Appointment record not found.", "error")
        return redirect(url_for("appointments"))

    if request.method == "POST":
        database.execute(
            "DELETE FROM appointments WHERE appointment_id = ?",
            (appointment_id,),
        )
        database.commit()
        flash("Appointment deleted successfully.", "success")
        return redirect(url_for("appointments"))

    return render_template(
        "appointment_delete.html",
        appointment=appointment_record,
    )


def validate_bill_data(
    database,
    patient_id_raw,
    consultation_fee_raw,
    medicine_fee_raw,
    other_charges_raw,
):
    if not patient_id_raw:
        return False, "Please select a registered patient.", None

    try:
        patient_id = int(patient_id_raw)
    except (ValueError, TypeError):
        return False, "Invalid patient selected.", None

    patient_record = database.execute(
        """
        SELECT patient_id
        FROM patients
        WHERE patient_id = ?
        """,
        (patient_id,),
    ).fetchone()
    if patient_record is None:
        return False, "Selected patient does not exist.", None

    def parse_monetary_amount(raw_value, field_name):
        if raw_value is None or str(raw_value).strip() == "":
            return False, f"{field_name} is required.", 0.0
        try:
            amount = float(raw_value)
            if amount < 0:
                return False, f"{field_name} cannot be negative.", 0.0
            return True, None, round(amount, 2)
        except (ValueError, TypeError):
            return False, f"{field_name} must be a valid number.", 0.0

    is_valid, error_message, consultation_fee = parse_monetary_amount(
        consultation_fee_raw, "Consultation fee"
    )
    if not is_valid:
        return False, error_message, None

    is_valid, error_message, medicine_fee = parse_monetary_amount(
        medicine_fee_raw, "Medicine fee"
    )
    if not is_valid:
        return False, error_message, None

    is_valid, error_message, other_charges = parse_monetary_amount(
        other_charges_raw, "Other charges"
    )
    if not is_valid:
        return False, error_message, None

    total_amount = round(consultation_fee + medicine_fee + other_charges, 2)

    cleaned_data = {
        "patient_id": patient_id,
        "consultation_fee": consultation_fee,
        "medicine_fee": medicine_fee,
        "other_charges": other_charges,
        "total_amount": total_amount,
    }
    return True, None, cleaned_data


@app.route("/billing")
@login_required
def billing():
    search_query = request.args.get("search", "").strip()
    database = get_database_connection()

    if search_query:
        search_pattern = build_like_pattern(search_query)
        normalized_date = normalize_search_date(search_query)

        if normalized_date is not None:
            bill_records = database.execute(
                """
                SELECT
                    bills.bill_id,
                    patients.name AS patient_name,
                    bills.consultation_fee,
                    bills.medicine_fee,
                    bills.other_charges,
                    bills.total_amount,
                    bills.bill_date
                FROM bills
                JOIN patients
                    ON bills.patient_id = patients.patient_id
                WHERE patients.name LIKE ? ESCAPE '\\'
                   OR bills.bill_date = ?
                ORDER BY bills.bill_id DESC
                """,
                (
                    search_pattern,
                    normalized_date,
                ),
            ).fetchall()
        else:
            bill_records = database.execute(
                """
                SELECT
                    bills.bill_id,
                    patients.name AS patient_name,
                    bills.consultation_fee,
                    bills.medicine_fee,
                    bills.other_charges,
                    bills.total_amount,
                    bills.bill_date
                FROM bills
                JOIN patients
                    ON bills.patient_id = patients.patient_id
                WHERE patients.name LIKE ? ESCAPE '\\'
                ORDER BY bills.bill_id DESC
                """,
                (search_pattern,),
            ).fetchall()
    else:
        bill_records = database.execute("""
            SELECT
                bills.bill_id,
                patients.name AS patient_name,
                bills.consultation_fee,
                bills.medicine_fee,
                bills.other_charges,
                bills.total_amount,
                bills.bill_date
            FROM bills
            JOIN patients
                ON bills.patient_id = patients.patient_id
            ORDER BY bills.bill_id DESC
            """).fetchall()

    return render_template(
        "billing.html",
        bills=bill_records,
        search_query=search_query,
    )


@app.route("/billing/add", methods=["GET", "POST"])
@login_required
def add_bill():
    database = get_database_connection()
    patients_list = database.execute("""
        SELECT patient_id, name
        FROM patients
        ORDER BY name
        """).fetchall()

    if request.method == "POST":
        patient_id_raw = request.form.get("patient_id", "").strip()
        consultation_fee_raw = request.form.get("consultation_fee", "0").strip()
        medicine_fee_raw = request.form.get("medicine_fee", "0").strip()
        other_charges_raw = request.form.get("other_charges", "0").strip()

        form_data = {
            "patient_id": patient_id_raw,
            "consultation_fee": consultation_fee_raw,
            "medicine_fee": medicine_fee_raw,
            "other_charges": other_charges_raw,
        }

        is_valid, error_message, cleaned_data = validate_bill_data(
            database,
            patient_id_raw,
            consultation_fee_raw,
            medicine_fee_raw,
            other_charges_raw,
        )

        if not is_valid:
            flash(error_message, "error")
            return render_template(
                "billing_form.html",
                form_action=url_for("add_bill"),
                form_data=form_data,
                patients=patients_list,
            )

        bill_date = date.today().strftime("%Y-%m-%d")

        cursor = database.execute(
            """
            INSERT INTO bills (
                patient_id,
                consultation_fee,
                medicine_fee,
                other_charges,
                total_amount,
                bill_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cleaned_data["patient_id"],
                cleaned_data["consultation_fee"],
                cleaned_data["medicine_fee"],
                cleaned_data["other_charges"],
                cleaned_data["total_amount"],
                bill_date,
            ),
        )
        database.commit()
        new_bill_id = cursor.lastrowid
        flash("Bill generated successfully.", "success")
        return redirect(url_for("view_bill", bill_id=new_bill_id))

    return render_template(
        "billing_form.html",
        form_action=url_for("add_bill"),
        form_data={"consultation_fee": "0", "medicine_fee": "0", "other_charges": "0"},
        patients=patients_list,
    )


@app.route("/billing/<int:bill_id>")
@login_required
def view_bill(bill_id):
    database = get_database_connection()
    bill_record = database.execute(
        """
        SELECT
            bills.bill_id,
            bills.patient_id,
            patients.name AS patient_name,
            patients.phone AS patient_phone,
            patients.address AS patient_address,
            bills.consultation_fee,
            bills.medicine_fee,
            bills.other_charges,
            bills.total_amount,
            bills.bill_date
        FROM bills
        JOIN patients
            ON bills.patient_id = patients.patient_id
        WHERE bills.bill_id = ?
        """,
        (bill_id,),
    ).fetchone()

    if bill_record is None:
        flash("Bill record not found.", "error")
        return redirect(url_for("billing"))

    return render_template("bill.html", bill=bill_record)


@app.route("/billing/<int:bill_id>/delete", methods=["GET", "POST"])
@login_required
def delete_bill(bill_id):
    database = get_database_connection()
    bill_record = database.execute(
        """
        SELECT
            bills.bill_id,
            bills.patient_id,
            patients.name AS patient_name,
            bills.total_amount,
            bills.bill_date
        FROM bills
        JOIN patients
            ON bills.patient_id = patients.patient_id
        WHERE bills.bill_id = ?
        """,
        (bill_id,),
    ).fetchone()

    if bill_record is None:
        flash("Bill record not found.", "error")
        return redirect(url_for("billing"))

    if request.method == "POST":
        database.execute(
            "DELETE FROM bills WHERE bill_id = ?",
            (bill_id,),
        )
        database.commit()
        flash("Bill deleted successfully.", "success")
        return redirect(url_for("billing"))

    return render_template("bill_delete.html", bill=bill_record)


if __name__ == "__main__":
    app.run(debug=True)
