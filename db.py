import sqlite3
import os
import sys

def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.

    Args:
        relative_path (str): Relative path to the resource

    Returns:
        str: Absolute path to the resource
    """
    try:
        base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_user_profile_folder():
    """
    Get the path to the user's profile folder in Windows.

    Returns:
        str: Path to the user profile folder
    """
    return os.environ.get("USERPROFILE")

def create_db():
    """
    Initialize the SQLite database and create required tables if they don't exist.
    Creates:
        - procs table: Stores patient procedure records
        - config table: Stores application configuration including version info
    """
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS procs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT UNIQUE,
        patient_name TEXT,
        images INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        uploading_percentage INTEGER DEFAULT 0
    )''')

    # Check if config table exists and add version column if necessary
    cursor.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name='config' ''')
    if not cursor.fetchone():
        cursor.execute('''CREATE TABLE config (
            id INTEGER PRIMARY KEY,
            ae_title TEXT NOT NULL,
            port INTEGER NOT NULL,
            technician_email TEXT NOT NULL,
            version TEXT DEFAULT '1.0'
        )''')
        cursor.execute('''INSERT INTO config (id, ae_title, port, technician_email, version)
            VALUES (1, 'RADIOLINK', 4008, 'technician@gmail.com', '1.0')''')

    conn.commit()
    conn.close()

create_db()

def insert_proc(patient_id, patient_name, status='pending'):
    """
    Insert or update a patient procedure record.

    Args:
        patient_id (str): Unique identifier for the patient
        patient_name (str): Name of the patient
        status (str): Initial status for new records (default: 'pending')
    """
    if not patient_id or not patient_name:
        raise ValueError("Patient ID and name are required")
        
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()

    try:
        cursor.execute('''SELECT images FROM procs WHERE patient_id = ?''', (patient_id,))
        result = cursor.fetchone()
        if result:
            cursor.execute('''UPDATE procs SET images = images + 1 WHERE patient_id = ?''', (patient_id,))
        else:
            cursor.execute('''INSERT INTO procs 
                (patient_id, patient_name, images, status, uploading_percentage)
                VALUES (?, ?, 1, ?, 0)''', (patient_id, patient_name, status))
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise
    finally:
        conn.close()

def update_proc_status(patient_id, status):
    """
    Update the status of a patient procedure record.

    Args:
        patient_id (str): Unique identifier for the patient
        status (str): New status to set
    """
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()
    try:
        cursor.execute('''UPDATE procs SET status = ? WHERE patient_id = ?''', (status, patient_id))
        conn.commit()
    finally:
        conn.close()

def update_proc_uploading_percentage(patient_id, percentage):
    """
    Update the uploading percentage of a patient procedure record.

    Args:
        patient_id (str): Unique identifier for the patient
        percentage (int): New uploading percentage to set
    """
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()
    try:
        cursor.execute('''UPDATE procs SET uploading_percentage = ? WHERE patient_id = ?''', (percentage, patient_id))
        conn.commit()
    finally:
        conn.close()

def get_procs():
    """
    Retrieve all patient procedure records.

    Returns:
        list: List of tuples containing procedure records
    """
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT * FROM procs ORDER BY id DESC''')
        return cursor.fetchall()
    finally:
        conn.close()

def get_config():
    """
    Retrieve application configuration.

    Returns:
        dict: Configuration dictionary containing AE_TITLE, PORT, TECHNICIAN_EMAIL, and VERSION
    """
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT * FROM config WHERE id = 1''')
        config = cursor.fetchone()
        if not config:
            cursor.execute('''INSERT INTO config (id, ae_title, port, technician_email, version)
                VALUES (1, 'RADIOLINK', 4008, 'technician@gmail.com', '1.0')''')
            conn.commit()
            return {
                "AE_TITLE": 'RADIOLINK',
                "PORT": 4008,
                "TECHNICIAN_EMAIL": 'technician@gmail.com',
                "VERSION": '1.0'
            }
        return {
            "AE_TITLE": config[1],
            "PORT": config[2],
            "TECHNICIAN_EMAIL": config[3],
            "VERSION": config[4]
        }
    finally:
        conn.close()

def update_config(ae_title, port, technician_email, version=None):
    """
    Update application configuration.

    Args:
        ae_title (str): Application Entity Title for DICOM
        port (int): Port number for DICOM communication
        technician_email (str): Email address of the technician
        version (str, optional): Application version
    """
    if not ae_title or not isinstance(port, int) or not technician_email:
        raise ValueError("Invalid configuration parameters")
        
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()
    try:
        if version:
            cursor.execute('''UPDATE config 
                SET ae_title = ?, port = ?, technician_email = ?, version = ? 
                WHERE id = 1''', (ae_title, port, technician_email, version))
        else:
            cursor.execute('''UPDATE config 
                SET ae_title = ?, port = ?, technician_email = ? 
                WHERE id = 1''', (ae_title, port, technician_email))
        if cursor.rowcount == 0:
            cursor.execute('''INSERT INTO config (id, ae_title, port, technician_email, version)
                VALUES (1, ?, ?, ?, ?)''', (ae_title, port, technician_email, version or '1.0'))
        conn.commit()
    finally:
        conn.close()

def update_version(new_version):
    """
    Update the application version in the config table.

    Args:
        new_version (str): New version to set
    """
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()
    try:
        cursor.execute('''UPDATE config SET version = ? WHERE id = 1''', (new_version,))
        conn.commit()
    finally:
        conn.close()
