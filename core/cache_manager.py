"""
Cache management for the TCF PPC Dashboard.
"""
import os
import hashlib
import pandas as pd

def compute_file_signature(path_or_buffer) -> str:
    """
    Compute a signature for a file or buffer to detect changes.
    
    Args:
        path_or_buffer: File path string or a BytesIO/StringIO object.
        
    Returns:
        str: A hash representing the file signature based on size/mtime or bytes.
    """
    hasher = hashlib.md5()
    
    if isinstance(path_or_buffer, str) and os.path.exists(path_or_buffer):
        # It's a file path
        stat = os.stat(path_or_buffer)
        signature = f"{path_or_buffer}_{stat.st_size}_{stat.st_mtime}"
        hasher.update(signature.encode('utf-8'))
    elif hasattr(path_or_buffer, 'getvalue'):
        # It's a BytesIO or StringIO buffer
        content = path_or_buffer.getvalue()
        if isinstance(content, str):
            hasher.update(content.encode('utf-8'))
        else:
            hasher.update(content)
    else:
        # Fallback for other objects
        hasher.update(str(path_or_buffer).encode('utf-8'))
        
    return hasher.hexdigest()

def compute_source_signature(loaded_data_dict: dict) -> str:
    """
    Compute a combined signature from a dictionary of loaded data sources.
    
    Args:
        loaded_data_dict (dict): Dictionary mapping source names to DataFrames or other data.
        
    Returns:
        str: A hash representing the combined signature of all sources.
    """
    hasher = hashlib.md5()
    
    for key, data in sorted(loaded_data_dict.items()):
        hasher.update(str(key).encode('utf-8'))
        
        if isinstance(data, pd.DataFrame):
            # For dataframes, use shape and column names as a quick signature proxy
            sig = f"{data.shape}_{list(data.columns)}"
            hasher.update(sig.encode('utf-8'))
        else:
            # Fallback
            hasher.update(str(type(data)).encode('utf-8'))
            
    return hasher.hexdigest()
