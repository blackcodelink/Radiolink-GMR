import sqlite3
import os

import sys
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def create_db():
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS procs (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT UNIQUE, patient_name TEXT, images INTEGER)''')
    
    # Check if config table exists
    cursor.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name='config' ''')
    if not cursor.fetchone():
        cursor.execute('''CREATE TABLE config (id INTEGER PRIMARY KEY, ae_title TEXT, port INTEGER, technician_email TEXT)''')
        cursor.execute('''INSERT INTO config (id, ae_title, port, technician_email) VALUES (1, 'RADIOLINK', 4008, 'technician@gmail.com')''')
    
    conn.commit()
    conn.close()

create_db()

def insert_proc(patient_id, patient_name, images):
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()
    
    # Check if patient_id already exists
    cursor.execute('''SELECT images FROM procs WHERE patient_id = ?''', (patient_id,))
    result = cursor.fetchone()
    
    if result:
        # Update existing record by incrementing images count
        cursor.execute('''UPDATE procs SET images = images + 1 WHERE patient_id = ?''', (patient_id,))
    else:
        # Insert new record
        cursor.execute('''INSERT INTO procs (patient_id, patient_name, images) VALUES (?, ?, ?)''', (patient_id, patient_name, 1))
    
    conn.commit()
    conn.close()

def get_procs():
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM procs''')
    return cursor.fetchall()

def get_config():
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM config WHERE id = 1''')
    config = cursor.fetchone()
    conf = {
        "AE_TITLE": config[1],  
        "PORT": config[2],
        "TECHNICIAN_EMAIL": config[3]
    }
    return conf

def update_config(ae_title, port, technician_email):
    conn = sqlite3.connect(resource_path('radiolink.db'))
    cursor = conn.cursor()
    cursor.execute('''UPDATE config SET ae_title = ?, port = ?, technician_email = ? WHERE id = 1''', (ae_title, port, technician_email))
    conn.commit()
    conn.close()
