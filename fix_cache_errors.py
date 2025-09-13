#!/usr/bin/env python3
"""
Fix Cache Errors Script

This script fixes the JSON parsing errors in the cache files.
"""

import os
import json
import sys
from pathlib import Path

def fix_cache_files():
    """Fix corrupted cache files."""
    cache_dir = Path("cache/pricing")
    
    if not cache_dir.exists():
        print("ℹ️ No cache directory found")
        return
    
    fixed_count = 0
    error_count = 0
    
    for cache_file in cache_dir.glob("*.json"):
        try:
            # Try to read the file
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            # Check if it's the old format
            if 'direct_cost_egp' in data and 'final_price_egp' in data:
                # Convert to new format
                new_data = {
                    "base_price": data.get('direct_cost_egp', 0),
                    "multipliers": data.get('details', {}).get('multipliers', {}),
                    "final_price": data.get('final_price_egp', 0),
                    "breakdown": data.get('details', {}),
                    "from_cache": True,
                    "calculation_time_ms": data.get('details', {}).get('calculation_time_ms', 0),
                    "engine_version": "1.0.0"
                }
                
                # Write back the converted data
                with open(cache_file, 'w') as f:
                    json.dump(new_data, f, indent=2)
                
                print(f"✅ Fixed cache file: {cache_file.name}")
                fixed_count += 1
            else:
                print(f"ℹ️ Cache file already in correct format: {cache_file.name}")
                
        except json.JSONDecodeError as e:
            print(f"❌ Corrupted cache file: {cache_file.name} - {e}")
            # Remove corrupted file
            try:
                cache_file.unlink()
                print(f"🗑️ Removed corrupted file: {cache_file.name}")
                error_count += 1
            except Exception as delete_error:
                print(f"❌ Failed to remove corrupted file: {delete_error}")
        except Exception as e:
            print(f"❌ Error processing {cache_file.name}: {e}")
            error_count += 1
    
    print(f"\n📊 Summary:")
    print(f"   Fixed files: {fixed_count}")
    print(f"   Removed corrupted files: {error_count}")
    print(f"   Total processed: {fixed_count + error_count}")

def main():
    """Main function."""
    print("🔧 Cache Error Fix Utility")
    print("This will fix JSON parsing errors in cache files.")
    
    fix_cache_files()
    
    print("\n🎉 Cache fix completed!")
    print("The 'File cache read failed' errors should now be resolved.")

if __name__ == "__main__":
    main()
