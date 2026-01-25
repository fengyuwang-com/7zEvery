import os
import shutil
import time
from core import BatchProcessor

def create_test_data():
    base = os.path.abspath("test_env")
    if os.path.exists(base):
        shutil.rmtree(base)
    
    input_dir = os.path.join(base, "input")
    os.makedirs(os.path.join(input_dir, "sub1"))
    os.makedirs(os.path.join(input_dir, "sub2", "sub2_1"))
    
    with open(os.path.join(input_dir, "root.txt"), "w") as f: f.write("root content")
    with open(os.path.join(input_dir, "sub1", "file1.txt"), "w") as f: f.write("file1 content")
    with open(os.path.join(input_dir, "sub2", "file2.txt"), "w") as f: f.write("file2 content")
    with open(os.path.join(input_dir, "sub2", "sub2_1", "file3.txt"), "w") as f: f.write("file3 content")
    
    return input_dir

def mock_progress(current, total, folder, file):
    print(f"[Progress] {current}/{total} - {folder} - {file}")

def mock_log(msg, error=False):
    prefix = "[ERROR]" if error else "[INFO]"
    print(f"{prefix} {msg}")

def mock_complete(success, summary):
    print(f"[Complete] Success: {success}, Summary: {summary}")

def test_core():
    print("=== Creating Test Data ===")
    input_dir = create_test_data()
    
    processor = BatchProcessor(mock_progress, mock_log, mock_complete)
    
    print("\n=== Testing Compression ===")
    processor.run_compression(
        source_dir=input_dir,
        output_suffix="_compressed",
        password="123",
        compression_level="标准",
        overwrite_mode="overwrite"
    )
    
    compressed_dir = input_dir + "_compressed"
    if not os.path.exists(compressed_dir):
        print("FAILED: Compressed directory not created")
        return

    print("\n=== Testing Decryption ===")
    processor.run_decryption(
        source_dir=compressed_dir,
        output_suffix="_decrypted",
        password="123",
        overwrite_mode="overwrite"
    )
    
    decrypted_dir = compressed_dir + "_decrypted"
    if not os.path.exists(decrypted_dir):
        print("FAILED: Decrypted directory not created")
        return
        
    # Verify content structure
    expected_file = os.path.join(decrypted_dir, "sub2", "sub2_1", "file3.txt")
    if os.path.exists(expected_file):
        print(f"SUCCESS: Found decrypted file at {expected_file}")
    else:
        print(f"FAILED: Missing decrypted file at {expected_file}")

if __name__ == "__main__":
    test_core()
