# src/cogniquery/mcps/secure_file_storage.py
import os
import uuid
import json
from pathlib import Path
from typing import Dict, Optional

from .base import StoreDataInput, RetrievedDataOutput, FileHandleOutput, RetrieveDataInput
try:
    from . import s3_storage  # optional backend
except Exception:
    s3_storage = None  # type: ignore

STORAGE_DIR = Path("./.tmp_secure_storage")
FILENAME_MAP_FILE = STORAGE_DIR / "filename_mapping.json"

# Ensure the storage directory exists
STORAGE_DIR.mkdir(exist_ok=True)

# Load/save filename mapping for chart handle resolution
def _load_filename_mapping() -> Dict[str, str]:
    """Load mapping from original filenames to UUID handles"""
    try:
        if FILENAME_MAP_FILE.exists():
            with open(FILENAME_MAP_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_filename_mapping(mapping: Dict[str, str]) -> None:
    """Save mapping from original filenames to UUID handles"""
    try:
        with open(FILENAME_MAP_FILE, 'w') as f:
            json.dump(mapping, f, indent=2)
    except Exception:
        pass

def resolve_chart_handle(chart_handle: str) -> Optional[str]:
    """Resolve chart handle from original filename to UUID handle"""
    # If it's already a UUID handle, return as-is
    if '_' in chart_handle and len(chart_handle.split('_')[0]) == 36:
        return chart_handle
    
    # Try to resolve from filename mapping
    mapping = _load_filename_mapping()
    return mapping.get(chart_handle)

def store_data(input_data: StoreDataInput) -> FileHandleOutput:
    """
    Securely stores data to a temporary local directory with UUID-based file handles.
    This tool protects against path traversal attacks and provides secure file storage.
    Handles both text and binary data automatically.
    """
    try:
        backend = os.getenv("STORAGE_BACKEND", "local").lower()
        if backend == "s3":
            if s3_storage is None:
                return FileHandleOutput(success=False, error_message="S3 backend requested but not available")
            return s3_storage.store_data_s3(input_data)
        # Generate a unique handle to prevent path traversal issues
        unique_id = str(uuid.uuid4())
        file_handle = f"{unique_id}_{input_data.file_name}"
        file_path = STORAGE_DIR / file_handle
        
        # Update filename mapping for chart handle resolution
        if input_data.file_name:
            mapping = _load_filename_mapping()
            # Map both the full filename and any output/ prefixed version
            mapping[input_data.file_name] = file_handle
            if not input_data.file_name.startswith('output/'):
                mapping[f"output/{input_data.file_name}"] = file_handle
            _save_filename_mapping(mapping)

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
            if s3_storage is None:
                return RetrievedDataOutput(success=False, error_message="S3 backend requested but not available")
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
