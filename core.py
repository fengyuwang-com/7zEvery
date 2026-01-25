import os
import subprocess
import threading
import re
from utils import get_7z_path

class BatchProcessor:
    def __init__(self, update_progress_callback, log_callback, task_complete_callback, file_progress_callback=None):
        self.update_progress = update_progress_callback
        self.log = log_callback
        self.task_complete = task_complete_callback
        self.file_progress = file_progress_callback # New callback for single file progress
        self.stop_event = threading.Event()
        self.seven_z_path = get_7z_path()

    def stop(self):
        self.stop_event.set()

    def run_compression(self, source_dir, output_suffix, password, compression_level, overwrite_mode, custom_output_dir=None):
        if not self.seven_z_path:
            self.log("Error: 7z.exe not found.", error=True)
            self.task_complete(success=False, summary={})
            return

        self.log(f"Starting compression task...")
        self.log(f"Source: {source_dir}")
        
        # Calculate source root name and output root path
        source_root_name = os.path.basename(os.path.normpath(source_dir))
        
        if custom_output_dir and os.path.exists(custom_output_dir):
            parent_dir = custom_output_dir
        else:
            parent_dir = os.path.dirname(os.path.normpath(source_dir))
            
        output_root_dir = os.path.join(parent_dir, source_root_name + output_suffix)
        
        self.log(f"Output Root: {output_root_dir}")

        # Collect files
        all_files = []
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                all_files.append(os.path.join(root, file))

        total_files = len(all_files)
        if total_files == 0:
            self.log("No files found to compress.")
            self.task_complete(success=True, summary={"total": 0, "success": 0, "fail": 0, "output_path": output_root_dir})
            return

        success_count = 0
        fail_count = 0

        # Compression level map
        level_map = {"快速": 1, "标准": 5, "最高": 9}
        mx = level_map.get(compression_level, 5)

        for idx, file_path in enumerate(all_files):
            if self.stop_event.is_set():
                self.log("Operation cancelled by user.", error=True)
                break

            # Rel path for structure
            rel_path = os.path.relpath(file_path, source_dir)
            rel_dir = os.path.dirname(rel_path)
            
            # Target dir
            target_dir = os.path.join(output_root_dir, rel_dir)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            
            # Target file name (Original.7z)
            file_name = os.path.basename(file_path)
            target_file = os.path.join(target_dir, file_name + ".7z")

            # Check existence
            if os.path.exists(target_file):
                if overwrite_mode == "skip":
                    self.log(f"Skipping existing file: {target_file}")
                    continue
                try:
                    os.remove(target_file)
                except Exception as e:
                    self.log(f"Failed to remove existing file {target_file}: {e}", error=True)
                    fail_count += 1
                    continue

            # Notify GUI
            self.update_progress(idx + 1, total_files, os.path.dirname(file_path), file_name)
            self.log(f"Compressing: {file_name}")

            # Build command
            # -bsp1 enables progress output to stdout
            cmd = [
                self.seven_z_path, 'a', '-t7z',
                target_file,
                file_path,
                f'-mx{mx}',
                '-bsp1' 
            ]
            if password:
                cmd.append(f'-p{password}')
            
            # Execute
            success = self._execute_7z(cmd)
            if success:
                success_count += 1
            else:
                fail_count += 1

        self.task_complete(success=True, summary={
            "total": total_files,
            "success": success_count,
            "fail": fail_count,
            "output_path": output_root_dir
        })

    def run_decryption(self, source_dir, output_suffix, password, overwrite_mode, custom_output_dir=None):
        if not self.seven_z_path:
            self.log("Error: 7z.exe not found.", error=True)
            self.task_complete(success=False, summary={})
            return

        self.log(f"Starting decryption task...")
        
        source_root_name = os.path.basename(os.path.normpath(source_dir))
        
        if custom_output_dir and os.path.exists(custom_output_dir):
            parent_dir = custom_output_dir
        else:
            parent_dir = os.path.dirname(os.path.normpath(source_dir))
            
        output_root_dir = os.path.join(parent_dir, source_root_name + output_suffix)
        
        self.log(f"Output Root: {output_root_dir}")

        all_files = []
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.lower().endswith('.7z'):
                    all_files.append(os.path.join(root, file))

        total_files = len(all_files)
        if total_files == 0:
            self.log("No .7z files found to decrypt.")
            self.task_complete(success=True, summary={"total": 0, "success": 0, "fail": 0, "output_path": output_root_dir})
            return

        success_count = 0
        fail_count = 0

        for idx, file_path in enumerate(all_files):
            if self.stop_event.is_set():
                self.log("Operation cancelled by user.", error=True)
                break

            rel_path = os.path.relpath(file_path, source_dir)
            rel_dir = os.path.dirname(rel_path)
            target_dir = os.path.join(output_root_dir, rel_dir)
            
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)

            file_name = os.path.basename(file_path)
            expected_content_name = file_name[:-3] # remove .7z
            expected_output_path = os.path.join(target_dir, expected_content_name)

            if os.path.exists(expected_output_path) and overwrite_mode == "skip":
                self.log(f"Skipping existing file: {expected_output_path}")
                continue

            self.update_progress(idx + 1, total_files, os.path.dirname(file_path), file_name)
            self.log(f"Decrypting: {file_name}")

            # -bsp1 enables progress output
            cmd = [
                self.seven_z_path, 'x',
                file_path,
                f'-o{target_dir}',
                '-y',
                '-bsp1'
            ]
            if password:
                cmd.append(f'-p{password}')
            
            success = self._execute_7z(cmd)
            if success:
                success_count += 1
            else:
                fail_count += 1

        self.task_complete(success=True, summary={
            "total": total_files,
            "success": success_count,
            "fail": fail_count,
            "output_path": output_root_dir
        })

    def _execute_7z(self, cmd):
        # Delegate directly to the progress-aware implementation
        return self._execute_7z_with_progress(cmd)

    def _execute_7z_with_progress(self, cmd):
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo
            )
            
            # We will read char by char to catch the percentage updates
            buffer = ""
            while True:
                if self.stop_event.is_set():
                    process.terminate()
                    return False
                
                char = process.stdout.read(1)
                if not char and process.poll() is not None:
                    break
                
                if char:
                    buffer += char
                    # 7z output example: " 99%"
                    # We look for a sequence of digits followed by %
                    if char == '%':
                        # Find the number immediately preceding '%'
                        # buffer might look like "... 12%"
                        match = re.search(r'(\d+)%$', buffer)
                        if match:
                            percent = int(match.group(1))
                            if self.file_progress:
                                self.file_progress(percent)
                            # Reset buffer to keep it small, but keep enough context if needed?
                            # Actually we can clear buffer after match
                            buffer = ""
                    elif char == '\n' or char == '\r':
                         buffer = ""
            
            stderr = process.stderr.read()
            if process.returncode == 0:
                if self.file_progress:
                    self.file_progress(100) # Ensure 100% at end
                return True
            else:
                self.log(f"Failed: {stderr.strip()}", error=True)
                return False

        except Exception as e:
            self.log(f"Exception executing 7z: {e}", error=True)
            return False
