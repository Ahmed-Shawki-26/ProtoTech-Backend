# app/services/image_cache_service.py

import os
import hashlib
import tempfile
import shutil
from typing import Optional, Tuple
from pathlib import Path
import time

class ImageCacheService:
    """
    Service for caching PCB images based on color and file content.
    This saves 5-7 seconds when users switch back to previously generated colors.
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the cache service.
        
        Args:
            cache_dir: Optional custom cache directory. If None, uses system temp directory.
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # Use system temp directory with our app-specific subdirectory
            self.cache_dir = Path(tempfile.gettempdir()) / "prototech_pcb_cache"
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache expiration time (24 hours)
        self.cache_expiry_hours = 24
        
    def _generate_cache_key(self, file_content: bytes, pcb_color: str, base_material: str) -> str:
        """
        Generate a unique cache key based on file content, PCB color, and base material.
        
        Args:
            file_content: The uploaded file content
            pcb_color: Selected PCB color
            base_material: Selected base material
            
        Returns:
            Unique cache key string
        """
        # Create hash of file content
        file_hash = hashlib.md5(file_content).hexdigest()[:16]
        
        # Create cache key combining file hash, color, and material
        cache_key = f"{file_hash}_{pcb_color}_{base_material}"
        
        return cache_key
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """
        Get the cache directory path for a specific cache key.
        
        Args:
            cache_key: The cache key
            
        Returns:
            Path to the cache directory for this key
        """
        return self.cache_dir / cache_key
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """
        Check if cached images are still valid (not expired).
        
        Args:
            cache_path: Path to the cache directory
            
        Returns:
            True if cache is valid, False otherwise
        """
        if not cache_path.exists():
            return False
            
        # Check if cache directory is too old
        cache_time = cache_path.stat().st_mtime
        current_time = time.time()
        expiry_seconds = self.cache_expiry_hours * 3600
        
        return (current_time - cache_time) < expiry_seconds
    
    def get_cached_images(self, file_content: bytes, pcb_color: str, base_material: str) -> Optional[Tuple[bytes, bytes]]:
        """
        Retrieve cached images if they exist and are valid.
        
        Args:
            file_content: The uploaded file content
            pcb_color: Selected PCB color
            base_material: Selected base material
            
        Returns:
            Tuple of (top_image_bytes, bottom_image_bytes) if cached, None otherwise
        """
        cache_key = self._generate_cache_key(file_content, pcb_color, base_material)
        cache_path = self._get_cache_path(cache_key)
        
        if not self._is_cache_valid(cache_path):
            return None
        
        # Check if both image files exist
        top_image_path = cache_path / "pcb_top.png"
        bottom_image_path = cache_path / "pcb_bottom.png"
        
        if not (top_image_path.exists() and bottom_image_path.exists()):
            return None
        
        try:
            # Read cached images
            with open(top_image_path, 'rb') as f:
                top_image_bytes = f.read()
            with open(bottom_image_path, 'rb') as f:
                bottom_image_bytes = f.read()
            
            print(f"✅ Retrieved cached images for color: {pcb_color}, material: {base_material}")
            return top_image_bytes, bottom_image_bytes
            
        except Exception as e:
            print(f"❌ Error reading cached images: {e}")
            return None
    
    def cache_images(self, file_content: bytes, pcb_color: str, base_material: str, 
                    top_image_bytes: bytes, bottom_image_bytes: bytes) -> bool:
        """
        Cache the generated images for future use.
        
        Args:
            file_content: The uploaded file content
            pcb_color: Selected PCB color
            base_material: Selected base material
            top_image_bytes: Top PCB image bytes
            bottom_image_bytes: Bottom PCB image bytes
            
        Returns:
            True if caching was successful, False otherwise
        """
        cache_key = self._generate_cache_key(file_content, pcb_color, base_material)
        cache_path = self._get_cache_path(cache_key)
        
        try:
            # Create cache directory
            cache_path.mkdir(parents=True, exist_ok=True)
            
            # Write images to cache
            top_image_path = cache_path / "pcb_top.png"
            bottom_image_path = cache_path / "pcb_bottom.png"
            
            with open(top_image_path, 'wb') as f:
                f.write(top_image_bytes)
            with open(bottom_image_path, 'wb') as f:
                f.write(bottom_image_bytes)
            
            print(f"💾 Cached images for color: {pcb_color}, material: {base_material}")
            return True
            
        except Exception as e:
            print(f"❌ Error caching images: {e}")
            return False
    
    def cleanup_expired_cache(self) -> int:
        """
        Clean up expired cache entries.
        
        Returns:
            Number of cache entries cleaned up
        """
        cleaned_count = 0
        
        try:
            for cache_dir in self.cache_dir.iterdir():
                if cache_dir.is_dir() and not self._is_cache_valid(cache_dir):
                    shutil.rmtree(cache_dir)
                    cleaned_count += 1
                    print(f"🗑️ Cleaned up expired cache: {cache_dir.name}")
            
            if cleaned_count > 0:
                print(f"✅ Cleaned up {cleaned_count} expired cache entries")
                
        except Exception as e:
            print(f"❌ Error during cache cleanup: {e}")
        
        return cleaned_count
    
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            cache_dirs = [d for d in self.cache_dir.iterdir() if d.is_dir()]
            valid_dirs = [d for d in cache_dirs if self._is_cache_valid(d)]
            
            total_size = sum(
                sum(f.stat().st_size for f in d.rglob('*') if f.is_file())
                for d in cache_dirs
            )
            
            return {
                "total_entries": len(cache_dirs),
                "valid_entries": len(valid_dirs),
                "expired_entries": len(cache_dirs) - len(valid_dirs),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "cache_dir": str(self.cache_dir)
            }
            
        except Exception as e:
            print(f"❌ Error getting cache stats: {e}")
            return {"error": str(e)}


# Global cache service instance
image_cache = ImageCacheService()
