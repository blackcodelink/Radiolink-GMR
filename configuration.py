import os
import json
import sys


def get_external_config_path():
    """Get the path for an external settings.json located in the same folder as the executable."""
    if getattr(sys, 'frozen', False):  # If bundled as an executable
        return os.path.join(os.path.dirname(sys.executable), 'settings.json')
    else:  # If running as a script
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')

def load_config():
    """Load configuration from an external JSON file, or create default if it doesn't exist."""
    config_path = get_external_config_path()
    if not os.path.exists(config_path):
        create_default_config(config_path)

    with open(config_path, 'r') as file:
        return json.load(file)

def create_default_config(config_path):
    """Create a new config file with default settings at the specified path."""
    with open(config_path, 'w') as file:
        json.dump({}, file, indent=4)

def update_config(ae_title, port_number, technician_email):
    """Update the configuration file with new values."""
    updated_config = {
        "AE_TITLE": ae_title,
        "PORT": port_number,
        "TECHNICIAN_EMAIL": technician_email
    }
    config_path = get_external_config_path()
    with open(config_path, 'w') as file:
        json.dump(updated_config, file, indent=4)
