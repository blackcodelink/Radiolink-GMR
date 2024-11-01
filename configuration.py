# Copyright (c) 2024 BlackCodeLink. All rights reserved.
# RadioLink Configuration Module
# This module handles configuration management for the RadioLink software,
# including loading, creating and updating configuration settings.

import os
import json
import sys


def get_external_config_path():
    """
    Get the path for an external settings.json file.
    
    The settings file is located in the same folder as the executable when bundled,
    or in the same directory as this script when running from source.
    
    Returns:
        str: Absolute path to the settings.json file
    """
    if getattr(sys, 'frozen', False):  # If bundled as an executable
        return os.path.join(os.path.dirname(sys.executable), 'settings.json')
    else:  # If running as a script
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')

def load_config():
    """
    Load configuration from an external JSON file.
    
    If the configuration file doesn't exist, creates a new one with default settings.
    
    Returns:
        dict: Configuration settings loaded from the JSON file
    """
    config_path = get_external_config_path()
    if not os.path.exists(config_path):
        create_default_config(config_path)

    with open(config_path, 'r') as file:
        return json.load(file)

def create_default_config(config_path):
    """
    Create a new config file with default settings.
    
    Args:
        config_path (str): Path where the default configuration file should be created
    """
    with open(config_path, 'w') as file:
        json.dump({}, file, indent=4)

def update_config(ae_title, port_number, technician_email):
    """
    Update the configuration file with new values.
    
    Args:
        ae_title (str): Application Entity Title for DICOM configuration
        port_number (int): Port number for network communication
        technician_email (str): Email address of the responsible technician
    """
    updated_config = {
        "AE_TITLE": ae_title,
        "PORT": port_number,
        "TECHNICIAN_EMAIL": technician_email
    }
    config_path = get_external_config_path()
    with open(config_path, 'w') as file:
        json.dump(updated_config, file, indent=4)
