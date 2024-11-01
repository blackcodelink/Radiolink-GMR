import requests
import os
from db import get_config, update_version
import subprocess

def get_user_profile_folder():
    return str(os.environ.get("USERPROFILE"))

# Constants
UPDATE_URL = "https://futurdigi.com/api/latest_version"  # Replace with actual version metadata URL
DOWNLOAD_DIR = os.path.join(get_user_profile_folder(), "Downloads")
INSTALLER_PATH = os.path.join(DOWNLOAD_DIR, "latest_installer.exe")

def check_for_update():
    """
    Checks if a new version is available by calling the update API.
    
    Returns:
        str, str: URL to download the new version if available, and the new version.
    """
    try:
        response = requests.get(UPDATE_URL)
        response.raise_for_status()
        latest_version_info = response.json()
        current_version = get_config().get("VERSION", "1.0")
        
        if latest_version_info["version"] > current_version:
            return latest_version_info["download_url"], latest_version_info["version"]
    except requests.RequestException as e:
        print("Error checking for update:", e)
    return None, None

def download_update(url, on_complete):
    """
    Downloads the latest installer to a temporary folder.
    
    Args:
        url (str): The URL to download the installer from.
        on_complete (function): Callback to execute when the download is complete.
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    try:
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            with open(INSTALLER_PATH, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
        on_complete()
    except requests.RequestException as e:
        print("Error downloading update:", e)

def install_update(new_version):
    """
    Launches the installer. Assumes a silent installation mode.
    
    Args:
        new_version (str): The new version to set in the config.
    """
    try:
        subprocess.Popen([INSTALLER_PATH], shell=True)  # Execute installer
        update_version(new_version)  # Update the app version in the database
        print(f"Updated to version {new_version}")
    except Exception as e:
        print(f"Error during installation: {e}")