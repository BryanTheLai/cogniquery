# src/cogniquery/mcps/secure_file_storage.py
import os
import uuid
from pathlib import Path

from .base import StoreDataInput, RetrievedDataOutput, FileHandleOutput, RetrieveDataInput
from . import s3_storage

STORAGE_DIR = Path("./.tmp_secure_storage")

# Ensure the storage directory exists
STORAGE_DIR.mkdir(exist_ok=True)

def store_data(input_data: StoreDataInput) -> FileHandleOutput:
    """
    Securely stores data to a temporary local directory with UUID-based file handles.
    This tool protects against path traversal attacks and provides secure file storage.
    Handles both text and binary data automatically.
    """
    try:
        backend = os.getenv("STORAGE_BACKEND", "local").lower()
        if backend == "s3":
            return s3_storage.store_data_s3(input_data)
        # Generate a unique handle to prevent path traversal issues
        unique_id = str(uuid.uuid4())
        file_handle = f"{unique_id}_{input_data.file_name}"
        file_path = STORAGE_DIR / file_handle

        # Determine if this is binary data
        file_extension = os.path.splitext(input_data.file_name)[1].lower() if input_data.file_name else ""
        is_binary = (file_extension in ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp'] or 
                    isinstance(input_data.data, bytes))

        if is_binary:
            if isinstance(input_data.data, bytes):
                # Direct binary data
                with open(file_path, "wb") as f:
                    f.write(input_data.data)
            else:
                # String data that represents binary (latin1 encoded)
                with open(file_path, "wb") as f:
                    f.write(input_data.data.encode('latin1'))
        else:
            # Text data
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(input_data.data)

        return FileHandleOutput(success=True, file_handle=file_handle)
    except Exception as e:
        return FileHandleOutput(success=False, error_message=str(e))

def retrieve_data(input_data: RetrieveDataInput) -> RetrievedDataOutput:
    """
    Securely retrieves data from the temporary storage using a file handle.
    This tool validates file handles to prevent directory traversal attacks.
    Automatically handles both text and binary data.
    """
    try:
        backend = os.getenv("STORAGE_BACKEND", "local").lower()
        if backend == "s3":
            return s3_storage.retrieve_data_s3(input_data)
        file_handle = input_data.file_handle
        # Basic security check to prevent directory traversal
        if ".." in file_handle or "/" in file_handle or "\\" in file_handle:
            raise ValueError("Invalid file handle format.")

        file_path = STORAGE_DIR / file_handle
        
        if not file_path.exists():
             return RetrievedDataOutput(success=False, error_message="File not found.")

        # Determine if this is binary data based on file extension
        file_extension = os.path.splitext(file_handle)[1].lower()
        is_binary = file_extension in ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp']

        if is_binary:
            # Read binary data and return as latin1 string for compatibility
            with open(file_path, "rb") as f:
                binary_data = f.read()
                data = binary_data.decode('latin1')
        else:
            # Read text data
            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read()
        
        return RetrievedDataOutput(success=True, data=data)
    except Exception as e:
        return RetrievedDataOutput(success=False, error_message=str(e))

# Legacy class for backward compatibility - will be removed in future versions
class SecureFileStorageMCP:
    def __init__(self):
        # Ensure the storage directory exists
        STORAGE_DIR.mkdir(exist_ok=True)

    def store_data(self, input_data: StoreDataInput) -> FileHandleOutput:
        return store_data(input_data)

    def retrieve_data(self, file_handle: str) -> RetrievedDataOutput:
        retrieve_input = RetrieveDataInput(file_handle=file_handle)
        return retrieve_data(retrieve_input)
