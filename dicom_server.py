"""
DICOM Server Module for Radiolink
Copyright (c) 2024 BlackCodeLink. All rights reserved.

This module implements a DICOM server that can receive and process medical imaging files.
It handles C-STORE operations, file storage, compression, and uploading to a remote server.

Key features:
- Receives DICOM files via C-STORE operations
- Saves files with proper metadata and organization
- Compresses files into patient-specific ZIP archives immediately upon receipt
- Uploads processed data to remote server after 1 minute of inactivity
- Maintains queues for background processing
- Provides logging and error handling

Dependencies:
- pynetdicom: For DICOM networking
- pydicom: For DICOM file handling
- Other standard Python libraries

Author: BlackCodeLink
Version: 1.0
"""

import os
import logging
from pynetdicom import AE, evt
from pynetdicom.presentation import AllStoragePresentationContexts, StoragePresentationContexts
import pydicom
from pydicom.errors import InvalidDicomError
import time
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian
from db import insert_proc, update_proc_status, update_proc_uploading_percentage
from db import get_config
from send_to_server import send_to_server
import zipfile
from datetime import datetime, timedelta
import threading
import queue
from typing import Dict, Any, Optional

# Global queues for managing patient data and file operations
patient_queue = []  # Stores patient information before upload
patient_files = {}  # Dictionary to store files per patient before zipping
patient_zip_files = {}  # Dictionary to store zip file paths and last update times

def get_patient_by_id(patient_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve patient data from the queue by patient ID.
    
    Args:
        patient_id: The ID of the patient to find
        
    Returns:
        Dict containing patient data if found, None otherwise
    """
    for patient in patient_queue:
        if patient["patient_id"] == patient_id:
            return patient
    return None

def append_to_zip(patient_id: str, file_path: str) -> None:
    """
    Appends a file to patient's ZIP archive immediately upon receipt.
    Creates new ZIP if none exists.
    
    Args:
        patient_id: The ID of the patient
        file_path: Path to the file to be added
    """
    try:
        # Create zip file directory if it doesn't exist
        ZIP_FILE_DIR = os.path.join("zip_files")
        if not os.path.exists(ZIP_FILE_DIR):
            os.makedirs(ZIP_FILE_DIR)

        zip_file_path = os.path.join("zip_files", f"{patient_id}.zip")
        
        # Create or append to zip file
        mode = 'a' if os.path.exists(zip_file_path) else 'w'
        with zipfile.ZipFile(zip_file_path, mode, compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zip_file:
            if os.path.exists(file_path):
                zip_file.write(file_path, arcname=os.path.basename(file_path))
                os.remove(file_path)  # Remove original file after adding to zip
        
        # Update zip file tracking
        patient_zip_files[patient_id] = {
            "path": zip_file_path,
            "last_update": datetime.now()
        }
        
    except Exception as e:
        logging.error(f"Error appending to zip file for patient {patient_id}: {e}")
        update_proc_status(patient_id, "pending")

def upload_patient_data(patient_id: str) -> None:
    """
    Uploads patient data and ZIP file to remote server.
    
    Args:
        patient_id: The ID of the patient whose data to upload
    """
    try:
        patient_data = get_patient_by_id(patient_id)
        if not patient_data:
            logging.error(f"Patient data not found for {patient_id}")
            return
            
        zip_info = patient_zip_files.get(patient_id)
        if not zip_info:
            logging.error(f"No zip file found for patient {patient_id}")
            return
            
        patient_data["zip_file_path"] = zip_info["path"]
            
        # Update status to uploading
        try:
            update_proc_status(patient_id, "uploading")
            update_proc_uploading_percentage(patient_id, 75)
        except ValueError:
            logging.error(f"Patient {patient_id} not found in database - skipping status update")
        
        # Send data to server
        if send_to_server(patient_data, patient_data["zip_file_path"]):
            try:
                update_proc_status(patient_id, "uploaded")
                update_proc_uploading_percentage(patient_id, 100)
                logging.info(f"Successfully uploaded data for patient {patient_id}")
            except ValueError:
                logging.error(f"Patient {patient_id} not found in database - skipping completion status update")
            
            # Clean up after successful upload
            with threading.Lock():
                patient_queue.remove(patient_data)
                if os.path.exists(patient_data["zip_file_path"]):
                    os.remove(patient_data["zip_file_path"])
                del patient_zip_files[patient_id]
        else:
            logging.error(f"Failed to upload data for patient {patient_id}")
            update_proc_status(patient_id, "pending")
            update_proc_uploading_percentage(patient_id, 0)
                
    except Exception as e:
        logging.error(f"Error uploading patient data: {e}")
        try:
            update_proc_status(patient_id, "pending")
            update_proc_uploading_percentage(patient_id, 0)
        except ValueError:
            logging.error(f"Patient {patient_id} not found in database - skipping error status update")

def check_patient_updates() -> None:
    """
    Background worker that periodically checks for patients ready for upload.
    Initiates upload when no new files have been received for a patient after timeout.
    """
    while True:
        try:
            current_time = datetime.now()
            with threading.Lock():
                for patient_id, zip_info in list(patient_zip_files.items()):
                    if (current_time - zip_info["last_update"]) > timedelta(minutes=1):
                        upload_patient_data(patient_id)
            time.sleep(60)  # Wait 1 minute before next check
        except Exception as e:
            logging.error(f"Error checking patient updates: {e}")

def dicom_server() -> None:
    """
    Main DICOM server function that initializes and runs the DICOM service.
    Sets up logging, workers, and network listeners.
    """
    # Get config values
    config = get_config()
    AE_TITLE = config["AE_TITLE"]
    PORT = config["PORT"]
    TECHNICIAN_EMAIL = config["TECHNICIAN_EMAIL"]

    # Enable detailed logging for radiolink
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('radiolink')

    if not TECHNICIAN_EMAIL:
        raise ValueError("TECHNICIAN_EMAIL must be set in conf.py")

    # Start update checker thread
    update_checker_thread = threading.Thread(target=check_patient_updates, daemon=True)
    update_checker_thread.start()

    # Create the Application Entity (AE)
    ae = AE(ae_title=AE_TITLE)

    # Add support for both explicit and implicit transfer syntaxes
    for context in AllStoragePresentationContexts:
        ae.add_supported_context(str(context.abstract_syntax), [ExplicitVRLittleEndian, ImplicitVRLittleEndian])

    # Add additional presentation contexts for specific SOP classes
    for context in StoragePresentationContexts:
        ae.add_supported_context(str(context.abstract_syntax), [ExplicitVRLittleEndian, ImplicitVRLittleEndian])

    def handle_store(event) -> int:
        """
        Handles incoming C-STORE requests.
        
        Args:
            event: The C-STORE event containing the DICOM dataset
            
        Returns:
            0x0000 on success, 0xA702 on failure
        """
        try:
            # Extract the received DICOM dataset
            ds = event.dataset
            context = event.context

            # Log association details
            logger.info(f"Received C-STORE request from {event.assoc.requestor.ae_title}")
            logger.info(f"Transfer Syntax: {context.transfer_syntax}")

            # Define the directory where the files will be saved, organized by PatientID and StudyInstanceUID
            SAVE_DIR = os.path.join("dicom_files", str(ds.PatientID), str(ds.StudyInstanceUID))

            # Ensure the SAVE_DIR exists
            if not os.path.exists(SAVE_DIR):
                os.makedirs(SAVE_DIR)
            
            # Create a new DICOM file with proper meta information
            file_meta = event.file_meta
            ds.file_meta = file_meta
            
            # Ensure required DICOM file meta information is present
            ds.file_meta.MediaStorageSOPClassUID = file_meta.MediaStorageSOPClassUID
            ds.file_meta.MediaStorageSOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
            ds.file_meta.ImplementationClassUID = file_meta.ImplementationClassUID
            ds.file_meta.TransferSyntaxUID = file_meta.TransferSyntaxUID
            
            # Add additional DICOM attributes if missing
            if not hasattr(ds, 'InstanceCreationDate'):
                ds.InstanceCreationDate = ds.StudyDate
            if not hasattr(ds, 'InstanceCreationTime'):
                ds.InstanceCreationTime = ds.StudyTime

            # Create a file path for the DICOM file based on modality and SOPInstanceUID
            modality = getattr(ds, 'Modality', 'UNKNOWN')
            temp_file_path = os.path.join(SAVE_DIR, f"{modality}_{ds.SOPInstanceUID}")

            # Log the file path and DICOM details
            logger.info(f"Saving DICOM file to: {temp_file_path}")
            logger.info(f"Patient Name: {str(ds.PatientName)}")
            logger.info(f"Study Description: {str(getattr(ds, 'StudyDescription', 'N/A'))}")
            logger.info(f"Series Description: {str(getattr(ds, 'SeriesDescription', 'N/A'))}")
            
            # Save the DICOM file with proper headers
            ds.save_as(temp_file_path, write_like_original=False)

            # Verify the saved file is valid DICOM and check image quality
            try:
                verified_ds = pydicom.dcmread(temp_file_path)
                # Check image pixel data if present
                if hasattr(verified_ds, 'PixelData'):
                    logger.info(f"Image size: {verified_ds.Rows}x{verified_ds.Columns}")
                    logger.info(f"Bits Allocated: {verified_ds.BitsAllocated}")
            except InvalidDicomError:
                logger.error(f"Invalid DICOM file created: {temp_file_path}")
                return 0xA702  # Failure, unable to process

            # Confirm the file exists and has content
            if not os.path.exists(temp_file_path) or os.path.getsize(temp_file_path) == 0:
                logger.error(f"File not found or empty after saving: {temp_file_path}")
                return 0xA702  # Failure, unable to process

            # Update database with initial pending status
            insert_proc(str(ds.PatientID), str(ds.PatientName), "pending")
            update_proc_uploading_percentage(str(ds.PatientID), 0)

            # Add file to patient's file list and append to zip
            if str(ds.PatientID) not in patient_files:
                patient_files[str(ds.PatientID)] = []
            patient_files[str(ds.PatientID)].append(temp_file_path)
            append_to_zip(str(ds.PatientID), temp_file_path)

            # Update existing patient record or create new one
            patient = get_patient_by_id(str(ds.PatientID))
            if patient:
                patient["images"] += 1
                patient["updated_at"] = datetime.now()
            else:
                patient_queue.append({
                    "patient_id": getattr(ds, 'PatientID', ''),
                    "patient_name": getattr(ds, 'PatientName', 'N/A'),
                    "patient_sex": getattr(ds, 'PatientSex', 'N/A'),
                    "patient_age": getattr(ds, 'PatientAge', 'N/A'),
                    "patient_size": getattr(ds, 'PatientSize', '0'),
                    "patient_weight": getattr(ds, 'PatientWeight', '0'),
                    "patient_position": getattr(ds, 'PatientPosition', 'N/A'),
                    "study_instance_uid": getattr(ds, 'StudyInstanceUID', 'N/A'),
                    "study_id": getattr(ds, 'StudyID', 'N/A'),
                    "study_date": getattr(ds, 'StudyDate', 'N/A'),
                    "study_time": getattr(ds, 'StudyTime', 'N/A'),
                    "study_description": getattr(ds, 'StudyDescription', 'N/A'),
                    "modality": modality,
                    "image_type": getattr(ds, 'ImageType', 'N/A'),
                    "protocol_name": getattr(ds, 'ProtocolName', 'N/A'),
                    "technician_email": str(TECHNICIAN_EMAIL),
                    "images": 1,
                    "updated_at": datetime.now()
                })
            
            # Successfully processed
            return 0x0000

        except Exception as e:
            logger.error(f"Error handling C-STORE request: {e}")
            return 0xA702  # Failure, unable to process

    # Define event handlers
    handlers = [
        (evt.EVT_C_STORE, handle_store),
        (evt.EVT_CONN_OPEN, lambda event: logger.info(f"Connection opened from {event.assoc.requestor.ae_title}")),
        (evt.EVT_CONN_CLOSE, lambda event: logger.info("Connection closed")),
        (evt.EVT_ACCEPTED, lambda event: logger.info(f"Association accepted from {event.assoc.requestor.ae_title}"))
    ]

    # Start the DICOM server
    try:
        logger.info(f"Starting DICOM server (AE Title: {AE_TITLE}) on port {PORT}...")
        ae.start_server(('0.0.0.0', int(PORT)), block=True, evt_handlers=handlers)
    except Exception as e:
        logger.error(f"Failed to start DICOM server: {e}")
