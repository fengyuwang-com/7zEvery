import os
import sys
import shutil
import winreg

_custom_7z_path = None

def set_custom_7z_path(path):
    global _custom_7z_path
    _custom_7z_path = path

def get_7z_path():
    """
    Locate 7z.exe. 
    Priority:
    1. Manually set path (Runtime)
    2. Current directory
    3. System PATH
    4. Windows Registry
    5. Common default locations
    """
    global _custom_7z_path
    
    # 1. Custom Path
    if _custom_7z_path and os.path.exists(_custom_7z_path):
        return _custom_7z_path

    # 2. Current Directory
    # We use sys.argv[0] directory or os.getcwd() to be safe for frozen apps or running from different dirs
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    local_7z = os.path.join(base_dir, '7z.exe')
    if os.path.exists(local_7z):
        return local_7z
        
    cwd_7z = os.path.join(os.getcwd(), '7z.exe')
    if os.path.exists(cwd_7z):
        return cwd_7z

    # 3. System PATH
    path_7z = shutil.which("7z")
    if path_7z:
        return path_7z
    path_7z_exe = shutil.which("7z.exe")
    if path_7z_exe:
        return path_7z_exe

    # 4. Windows Registry
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\7-Zip") as key:
            path_val, _ = winreg.QueryValueEx(key, "Path")
            reg_7z = os.path.join(path_val, "7z.exe")
            if os.path.exists(reg_7z):
                return reg_7z
    except OSError:
        pass
        
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\7-Zip") as key:
            path_val, _ = winreg.QueryValueEx(key, "Path")
            reg_7z = os.path.join(path_val, "7z.exe")
            if os.path.exists(reg_7z):
                return reg_7z
    except OSError:
        pass

    # 5. Common default locations (fallback)
    common_paths = [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe"
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path
            
    return None

def is_valid_suffix(suffix):
    """Check if the suffix contains illegal characters."""
    illegal_chars = r'/\:*?"<>|'
    return not any(char in suffix for char in illegal_chars)
