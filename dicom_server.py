import os
import logging
from pynetdicom import AE, evt, AllStoragePresentationContexts, StoragePresentationContexts
import pydicom
from pydicom.errors import InvalidDicomError
import requests
import json
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian
from db import insert_proc
import sys
from db import get_config

def dicom_server():
    # Get config values
    config = get_config()
    print("Config in dicom_server: ", config)
    AE_TITLE = config["AE_TITLE"]
    PORT = config["PORT"]
    TECHNICIAN_EMAIL = config["TECHNICIAN_EMAIL"]

    # Enable detailed logging for radiolink
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('radiolink')

    if not TECHNICIAN_EMAIL:
        raise ValueError("TECHNICIAN_EMAIL must be set in conf.py")

    # Create the Application Entity (AE)
    ae = AE(ae_title=AE_TITLE)

    # Add support for both explicit and implicit transfer syntaxes
    for context in AllStoragePresentationContexts:
        ae.add_supported_context(context.abstract_syntax, [ExplicitVRLittleEndian, ImplicitVRLittleEndian])

    # Add additional presentation contexts for specific SOP classes
    for context in StoragePresentationContexts:
        ae.add_supported_context(context.abstract_syntax, [ExplicitVRLittleEndian, ImplicitVRLittleEndian])

    def handle_store(event):
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

            try:
                url = "https://admin.gmrnetwork.in/api/v1/cases/"
                
                # Open the file to upload
                with open(temp_file_path, 'rb') as file:
                    files = {'files': (f"{ds.SOPInstanceUID}.dcm", file, 'application/dicom')}
                    data = {
                        "technician_email": str(TECHNICIAN_EMAIL),
                    }
                    
                    # Send the saved DICOM file to the remote server
                    response = requests.post(url, files=files, data=data, timeout=600)

                    logger.info(response.json())
                    if response.status_code == 201 or response.status_code == 200:
                        logger.info("DICOM file sent successfully to the remote server.")
                        file.close()
                        os.remove(temp_file_path)
                        insert_proc(str(ds.PatientID), str(ds.PatientName), 1)

                        return 0x0000  # Success
                    else:
                        logger.error(f"Error sending DICOM file to the remote server: HTTP status code {response.status_code}")
                        return 0xA702  # Failure, unable to process
            
            except Exception as e:
                logger.error(f"Error sending DICOM file: {e}")
                return 0xA702  # Failure, unable to process

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
