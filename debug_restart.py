#!/usr/bin/env python3
"""
Debug restart script to clear all caches and restart the server
This ensures that all code changes take effect properly.
"""

import os
import sys
import subprocess
import shutil
import glob
import time

def clear_python_cache():
    """Clear all Python cache files"""
    print("🧹 Clearing Python cache files...")
    
    # Find and remove __pycache__ directories
    for root, dirs, files in os.walk("."):
        for dir_name in dirs[:]:  # Use slice to avoid modifying list while iterating
            if dir_name == "__pycache__":
                cache_path = os.path.join(root, dir_name)
                try:
                    shutil.rmtree(cache_path)
                    print(f"  ✅ Removed: {cache_path}")
                except Exception as e:
                    print(f"  ⚠️ Failed to remove {cache_path}: {e}")
                dirs.remove(dir_name)  # Don't recurse into removed directory
    
    # Find and remove .pyc files
    pyc_files = glob.glob("**/*.pyc", recursive=True)
    for pyc_file in pyc_files:
        try:
            os.remove(pyc_file)
            print(f"  ✅ Removed: {pyc_file}")
        except Exception as e:
            print(f"  ⚠️ Failed to remove {pyc_file}: {e}")
    
    print(f"✅ Cleared {len(pyc_files)} .pyc files")

def kill_python_processes():
    """Kill all running Python processes"""
    print("🔄 Killing existing Python processes...")
    
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("  ✅ Killed Python processes on Windows")
            else:
                print(f"  ⚠️ No Python processes to kill: {result.stderr}")
        else:  # Unix/Linux/Mac
            result = subprocess.run(['pkill', '-f', 'python'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("  ✅ Killed Python processes on Unix")
            else:
                print(f"  ⚠️ No Python processes to kill: {result.stderr}")
    except Exception as e:
        print(f"  ⚠️ Error killing processes: {e}")

def clear_logs():
    """Clear log files"""
    print("🧹 Clearing log files...")
    
    log_files = [
        "logs/app.log",
        "app.log",
        "*.log"
    ]
    
    for log_pattern in log_files:
        for log_file in glob.glob(log_pattern):
            try:
                with open(log_file, 'w') as f:
                    f.write("")  # Clear the file
                print(f"  ✅ Cleared: {log_file}")
            except Exception as e:
                print(f"  ⚠️ Failed to clear {log_file}: {e}")

def start_server():
    """Start the server with debug flags"""
    print("🚀 Starting server with debug flags...")
    
    # Change to Backend directory
    os.chdir("Backend")
    
    # Start server with explicit flags
    cmd = [
        sys.executable, "-B", "-u", "working_server.py"
    ]
    
    print(f"  Running: {' '.join(cmd)}")
    print("  Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Server failed to start: {e}")
        return False
    
    return True

def main():
    """Main function to perform complete restart"""
    print("🔍 ProtoTech Debug Restart Script")
    print("=" * 60)
    
    # Step 1: Clear Python cache
    clear_python_cache()
    print()
    
    # Step 2: Kill existing processes
    kill_python_processes()
    print()
    
    # Step 3: Clear logs
    clear_logs()
    print()
    
    # Step 4: Wait a moment
    print("⏳ Waiting 2 seconds for cleanup...")
    time.sleep(2)
    print()
    
    # Step 5: Start server
    start_server()

if __name__ == "__main__":
    main()
