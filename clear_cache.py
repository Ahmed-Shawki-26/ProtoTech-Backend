#!/usr/bin/env python3
"""
Cache Cleanup Utility

This script clears old cache files that might be causing JSON parsing errors.
"""

import os
import shutil
import sys

def clear_cache():
    """Clear all cache directories."""
    cache_dirs = [
        "cache/pricing",
        "cache/images",
        "cache"
    ]
    
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                print(f"✅ Cleared cache directory: {cache_dir}")
            except Exception as e:
                print(f"❌ Failed to clear {cache_dir}: {e}")
        else:
            print(f"ℹ️ Cache directory doesn't exist: {cache_dir}")
    
    # Recreate empty cache directories
    for cache_dir in cache_dirs:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            print(f"✅ Created cache directory: {cache_dir}")
        except Exception as e:
            print(f"❌ Failed to create {cache_dir}: {e}")

def main():
    """Main function."""
    print("🧹 Cache Cleanup Utility")
    print("This will clear all cache files that might be causing JSON parsing errors.")
    
    response = input("Do you want to proceed? (y/N): ")
    if response.lower() in ['y', 'yes']:
        clear_cache()
        print("\n🎉 Cache cleanup completed!")
        print("The JSON parsing errors should now be resolved.")
    else:
        print("❌ Cache cleanup cancelled.")

if __name__ == "__main__":
    main()
