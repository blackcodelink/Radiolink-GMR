# Copyright (c) 2024 BlackCodeLink. All rights reserved.
# RadioLink - Medical Image Transfer Solution

import requests
import logging
from typing import Dict, Any
import os

def send_to_server(data: Dict[str, Any], dicom_file_path: str) -> bool:
    """
    Sends a DICOM file and associated metadata to the server.
    
    Args:
        data (Dict[str, Any]): Metadata dictionary to send with the DICOM file
        dicom_file_path (str): Path to the DICOM file to upload
        
    Returns:
        Dict[str, Any]: JSON response from the server
        
    Raises:
        requests.exceptions.RequestException: If there is any error in uploading the file
    """
    url = "http://localhost:8000/upload"
    logger = logging.getLogger(__name__)
    
    try:
        # Open and upload the DICOM file along with metadata
        with open(dicom_file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, data=data, files=files, timeout=30)
            response.raise_for_status()
            
        logger.info(f"Successfully uploaded {dicom_file_path}")
        status = response.status_code
        if status == 200:
            return True
        else:
            return False
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to upload {dicom_file_path}: {str(e)}")
        return False



# send_to_server(
#     data=
#        {
#   "patient_name": "John Doe",
#   "patient_id": "12345",
#   "patient_sex": "M",
#   "patient_age": "35",
#   "patient_size": "180",
#   "patient_weight": "75",
#   "patient_position": "Standing",
#   "study_instance_uid": "1.2.840.113619.2.55.3.2831164356.781.1597212243.160",
#   "study_id": "STUDY123",
#   "study_date": "2024-10-31",
#   "study_time": "12:45:00",
#   "study_description": "Chest X-Ray",
#   "modality": "CR",
#   "image_type": "ORIGINAL",
#   "protocol_name": "Standard Protocol"
# }
#     ,
#     dicom_file_path="C:\\Users\\Rohan\\Desktop\\rdlnk\\zip_files\\2510247.zip"
# )