#!/usr/bin/env python3
"""
Script to clear all Python cache and restart the server with fresh code.
This ensures that any changes to the codebase are properly loaded.
"""

import os
import sys
import subprocess
import shutil
import glob
from pathlib import Path

def clear_python_cache():
    """Clear all Python cache files and directories."""
    print("🧹 Clearing Python cache...")
    
    # Get the current directory
    current_dir = Path.cwd()
    
    # Find and remove all __pycache__ directories
    pycache_dirs = list(current_dir.rglob("__pycache__"))
    for pycache_dir in pycache_dirs:
        print(f"  Removing: {pycache_dir}")
        shutil.rmtree(pycache_dir, ignore_errors=True)
    
    # Find and remove all .pyc files
    pyc_files = list(current_dir.rglob("*.pyc"))
    for pyc_file in pyc_files:
        print(f"  Removing: {pyc_file}")
        pyc_file.unlink(missing_ok=True)
    
    # Find and remove all .pyo files
    pyo_files = list(current_dir.rglob("*.pyo"))
    for pyo_file in pyo_files:
        print(f"  Removing: {pyo_file}")
        pyo_file.unlink(missing_ok=True)
    
    print("✅ Python cache cleared!")

def kill_python_processes():
    """Kill all Python processes to ensure clean restart."""
    print("🔄 Killing existing Python processes...")
    
    try:
        if sys.platform == "win32":
            # Windows
            subprocess.run(["taskkill", "/F", "/IM", "python.exe"], 
                         capture_output=True, text=True)
        else:
            # Unix-like systems
            subprocess.run(["pkill", "-f", "python"], 
                         capture_output=True, text=True)
        print("✅ Python processes terminated!")
    except Exception as e:
        print(f"⚠️ Could not kill Python processes: {e}")

def start_server():
    """Start the server with fresh code."""
    print("🚀 Starting server with fresh code...")
    
    # Choose the appropriate server file
    server_files = ["working_server.py", "main.py", "start.py"]
    server_file = None
    
    for file in server_files:
        if os.path.exists(file):
            server_file = file
            break
    
    if not server_file:
        print("❌ No server file found!")
        return
    
    print(f"📁 Using server file: {server_file}")
    
    try:
        # Start server with unbuffered output and no bytecode
        cmd = [sys.executable, "-B", "-u", server_file]
        print(f"🔧 Running command: {' '.join(cmd)}")
        
        # Start the server
        subprocess.Popen(cmd)
        print("✅ Server started!")
        print("📝 Check the server logs for debug output...")
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")

def main():
    """Main function to clear cache and restart server."""
    print("🔧 ProtoTech Server Cache Clear & Restart")
    print("=" * 50)
    
    # Clear cache
    clear_python_cache()
    print()
    
    # Kill existing processes
    kill_python_processes()
    print()
    
    # Start server
    start_server()
    print()
    
    print("🎉 Done! Server should be running with fresh code.")
    print("💡 Watch the server logs for the DEBUG messages we added.")

if __name__ == "__main__":
    main()
