# app/services/quote_generator.py

import io
import os
import re
import tempfile
import zipfile
import rarfile
from typing import Tuple, Optional

from gerber import PCB
from gerber.render import theme
from gerber.render.cairo_backend import GerberCairoContext
from gerber.exceptions import ParseError

from app.core.config import settings
from app.schemas.pcb import BoardDimensions, PriceQuote, ManufacturingParameters,BaseMaterial
from app.services.image_cache_service import image_cache
from app.services.robust_pricing_service import RobustPricingService

class QuoteGenerator:
    """
    Processes a Gerber ZIP or RAR, calculates dimensions, renders images,
    and generates a price quote.
    """
    def __init__(self, archive_content: bytes, filename: str, params: ManufacturingParameters):
        self._archive_content = archive_content
        self._filename = filename
        self._params = params
        self._pcb: Optional[PCB] = None
        self._dimensions: Optional[BoardDimensions] = None

    def process(self) -> Tuple[bytes, bytes, Optional[BoardDimensions], Optional[PriceQuote]]:
        """Main processing method."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            self._extract_archive(tmpdirname)
            
            gerber_source_path = self._find_gerber_path(tmpdirname)
            
            # --- NEW: Rename files for compatibility ---
            self._rename_files_for_compatibility(gerber_source_path)
            
            self._load_pcb(gerber_source_path)
            
            top_image_bytes, bottom_image_bytes = self._render_images()
            self._calculate_dimensions()
            price_quote = self._calculate_price()

            return top_image_bytes, bottom_image_bytes, self._dimensions, price_quote

    def process_quote_only(self) -> Tuple[Optional[BoardDimensions], Optional[PriceQuote]]:
        """Processes the archive to get dimensions and a price quote without rendering images."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            self._extract_archive(tmpdirname)
            gerber_source_path = self._find_gerber_path(tmpdirname)
            self._rename_files_for_compatibility(gerber_source_path)
            self._load_pcb(gerber_source_path)
            self._calculate_dimensions()
            price_quote = self._calculate_price()
                
        return self._dimensions, price_quote

    def _extract_archive(self, target_dir: str):
        archive_in_memory = io.BytesIO(self._archive_content)
        if self._filename.lower().endswith('.zip'):
            try:
                with zipfile.ZipFile(archive_in_memory, 'r') as zip_ref:
                    zip_ref.extractall(target_dir)
            except zipfile.BadZipFile:
                raise ValueError("Uploaded file is not a valid ZIP archive.")
        elif self._filename.lower().endswith('.rar'):
            try:
                with rarfile.RarFile(archive_in_memory, 'r') as rar_ref:
                    rar_ref.extractall(target_dir)
            except rarfile.BadRarFile:
                raise ValueError("Uploaded file is not a valid RAR archive.")
        else:
            raise ValueError("Unsupported archive type.")

    def _find_gerber_path(self, source_dir: str) -> str:
        """
        Determines the correct directory containing Gerber files.
        It handles cases where files are in the root or in a single sub-directory.
        """
        dir_contents = os.listdir(source_dir)

        # Ignore common junk folders like __MACOSX
        dir_contents = [item for item in dir_contents if item != '__MACOSX']
        
        # Check for Gerber files in the root directory first
        gerber_extensions = ('.gbr', '.gbl', '.gtl', '.gbs', '.gts', '.gbo', '.gto', '.drl', '.txt', '.gm1')
        for item in dir_contents:
            if item.lower().endswith(gerber_extensions):
                # Found Gerber files in the root, so this is the correct path
                return source_dir

        # If no gerbers in root, check for a single subdirectory
        subdirectories = [os.path.join(source_dir, item) for item in dir_contents if os.path.isdir(os.path.join(source_dir, item))]
        
        if len(subdirectories) == 1:
            # Exactly one subdirectory found, assume the files are in there.
            return subdirectories[0]

        # If multiple subdirectories or no Gerbers found, return the original path
        # and let the _load_pcb method handle the potential error.
        return source_dir

    def _rename_files_for_compatibility(self, source_dir: str):
        """
        Renames Gerber files based on their names to improve compatibility.
        """
        # More specific patterns first
        rename_map = {
            r'.*top copper.*\.gbr': '.gtl',
            r'.*bottom copper.*\.gbr': '.gbl',
            r'.*top solder resist.*\.gbr': '.gts',
            r'.*bottom solder resist.*\.gbr': '.gbs',
            r'.*top silk screen.*\.gbr': '.gto',
            r'.*bottom silk screen.*\.gbr': '.gbo',
            r'.*drill.*\.gbr': '.drl',
            r'.*mechanical.*\.gbr': '.gm1',
            r'.*outline.*\.gbr': '.gm1',
            r'.*soldermask_top.*\.gbr': '.gts',
            r'.*soldermask_bot.*\.gbr': '.gbs',
            r'.*legend_top.*\.gbr': '.gto',
            r'.*legend_bot.*\.gbr': '.gbo',
            r'.*paste_top.*\.gbr': '.gtp',
            r'.*paste_bot.*\.gbr': '.gbp',
            r'.*profile.*\.gbr': '.gm1',
            r'.*keep-out.*\.gbr': '.gm1',
            # For files that are just .gbr, we can try to guess based on common names
            r'top\.gbr': '.gtl',
            r'bottom\.gbr': '.gbl',
            r'topsolder\.gbr': '.gts',
            r'bottomsolder\.gbr': '.gbs',
            r'topsilk\.gbr': '.gto',
            r'bottomsilk\.gbr': '.gbo',
            r'drill\.gbr': '.drl',
            r'outline\.gbr': '.gm1',
        }
  

        for filename in os.listdir(source_dir):
            if filename.lower().endswith('.ipc'):
                os.remove(os.path.join(source_dir, filename))
                print(f"INFO: Removed unsupported file: {filename}")
                continue

            for pattern, new_ext in rename_map.items():
                if re.match(pattern, filename.lower()): # Match case-insensitively
                    old_path = os.path.join(source_dir, filename)
                    # Keep the original name but change extension
                    new_filename = os.path.splitext(filename)[0] + new_ext
                    new_path = os.path.join(source_dir, new_filename)
                    try:
                        os.rename(old_path, new_path)
                        print(f"INFO: Renamed for compatibility: {filename} -> {new_filename}")                        
                    except OSError as e:
                        print(f"WARNING: Could not rename {filename}: {e}")                        
                    break

    def _load_pcb(self, source_dir: str):
        """
        Loads the PCB from the given source directory.
        This directory should be the one containing the actual Gerber files.
        """
        try:
            self._pcb = PCB.from_directory(source_dir)
            if not self._pcb.layers:
                # This error is now much more accurate
                raise ValueError("No valid Gerber or Excellon layers found in the ZIP file. Please ensure files are in the root or a single subfolder.")
        except (ParseError, Exception) as e:
            # Check if the original error was due to no layers found and enhance the message
            if "No valid Gerber or Excellon layers found" in str(e):
                 raise ValueError("No valid Gerber or Excellon layers found in the ZIP file. Please ensure files are in the root or a single subfolder.")
            raise ValueError(f"Failed to parse Gerber files. Error: {e}")

    # --- NO CHANGES BELOW THIS LINE ---

    def _render_images(self) -> Tuple[bytes, bytes]:
        if not self._pcb: raise RuntimeError("PCB must be loaded before rendering.")
        
        # --- THEME SELECTION LOGIC ---
        # Use PCB color for theme selection, with material-based restrictions
        selected_color = self._params.pcb_color
        selected_material = self._params.base_material
        
        # Apply material-based color restrictions (same as frontend logic)
        if selected_material == BaseMaterial.flex:
            # Flex material is ALWAYS Yellow, regardless of user selection
            effective_color = 'Yellow'
            theme_name = 'Yellow'
        elif selected_material == BaseMaterial.aluminum:
            # Aluminum material supports all colors like FR-4
            effective_color = selected_color
            if selected_color == 'Green':
                theme_name = 'default'
            elif selected_color == 'Blue':
                theme_name = 'Blue'
            elif selected_color == 'Red':
                theme_name = 'Red'
            elif selected_color == 'Black':
                theme_name = 'Black'
            elif selected_color == 'White':
                theme_name = 'White'
            elif selected_color == 'Yellow':
                theme_name = 'Yellow'
            else:
                theme_name = 'default'
        else:
            # FR-4 and other materials - use selected color
            effective_color = selected_color
            if selected_color == 'Green':
                theme_name = 'default'
            elif selected_color == 'Blue':
                theme_name = 'Blue'
            elif selected_color == 'Red':
                theme_name = 'Red'
            elif selected_color == 'Black':
                theme_name = 'Black'
            elif selected_color == 'White':
                theme_name = 'White'
            elif selected_color == 'Yellow':
                theme_name = 'Yellow'
            else:
                theme_name = 'default'
            
        print(f"Selected PCB color: {selected_color}, material: {selected_material}. Effective color: {effective_color}. Using render theme: '{theme_name}'")
        
        # --- CACHE CHECK ---
        # Try to get cached images first (use effective color for cache key)
        cached_images = image_cache.get_cached_images(
            self._archive_content, 
            effective_color, 
            selected_material
        )
        
        if cached_images:
            print(f"⚡ Using cached images for {effective_color} PCB - saved ~5-7 seconds!")
            return cached_images
        
        # --- RENDERING LOGIC ---
        # If no cache found, generate new images
        print(f"🎨 Generating new images for {effective_color} PCB...")
        theme_to_use = theme.THEMES.get(theme_name, theme.THEMES['default'])
        
        ctx = GerberCairoContext()
        ctx.render_layers(self._pcb.top_layers, filename=None, theme=theme_to_use, max_width=1024)
        top_image_bytes = ctx.dump(None)
        ctx.clear()
        ctx.render_layers(self._pcb.bottom_layers, filename=None, theme=theme_to_use, max_width=1024)
        bottom_image_bytes = ctx.dump(None)
        
        # --- CACHE THE NEW IMAGES ---
        # Cache the newly generated images for future use (use effective color for cache key)
        image_cache.cache_images(
            self._archive_content,
            effective_color,
            selected_material,
            top_image_bytes,
            bottom_image_bytes
        )
        
        return top_image_bytes, bottom_image_bytes

    # ===================================================================
    #  NEW: Base/Mask Rendering Methods
    # ===================================================================
    
    def _render_base_and_mask_layers(self, side: str, max_width: int = 1024) -> Tuple[bytes, bytes]:
        """
        Render base layer (no mask) and mask layer separately for client-side recoloring.
        
        Args:
            side: 'top' or 'bottom'
            max_width: Maximum width for the rendered image
            
        Returns:
            (base_png_bytes, mask_png_bytes)
        """
        if not self._pcb:
            raise RuntimeError("PCB must be loaded before rendering.")
        
        # Get the appropriate layers based on side
        if side == 'top':
            layers = self._pcb.top_layers
            side_label = "top"
        elif side == 'bottom':
            layers = self._pcb.bottom_layers
            side_label = "bottom"
        else:
            raise ValueError(f"Invalid side: {side}. Must be 'top' or 'bottom'")
        
        # Determine material-specific theme names
        material = self._params.base_material
        
        if material == BaseMaterial.flex:
            base_theme_name = 'Base_Flex'
            mask_theme_name = 'Mask_Flex'
        elif material == BaseMaterial.aluminum:
            base_theme_name = 'Base_Aluminum'
            mask_theme_name = 'Mask'
        else:  # FR-4 and others
            base_theme_name = 'Base'
            mask_theme_name = 'Mask'
        
        print(f"🎨 Rendering {side_label} base layer with theme: {base_theme_name}")
        
        # Render base layer (everything except solder mask)
        base_theme = theme.THEMES.get(base_theme_name, theme.THEMES['Base'])
        base_ctx = GerberCairoContext()
        base_ctx.render_layers(layers, filename=None, theme=base_theme, max_width=max_width)
        base_image_bytes = base_ctx.dump(None)
        
        print(f"🎭 Rendering {side_label} mask layer with theme: {mask_theme_name}")
        
        # Render mask layer (only solder mask)
        mask_theme = theme.THEMES.get(mask_theme_name, theme.THEMES['Mask'])
        mask_ctx = GerberCairoContext()
        mask_ctx.render_layers(layers, filename=None, theme=mask_theme, max_width=max_width)
        mask_image_bytes = mask_ctx.dump(None)
        
        print(f"✅ Successfully rendered {side_label} base and mask layers")
        return base_image_bytes, mask_image_bytes
    
    def _downscale_image(self, image_bytes: bytes, target_size: int) -> bytes:
        """
        Downscale image to target size maintaining aspect ratio.
        
        Args:
            image_bytes: Original image bytes
            target_size: Target size in pixels
            
        Returns:
            Downscaled image bytes
        """
        try:
            from PIL import Image
            
            img = Image.open(io.BytesIO(image_bytes))
            img.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            # Save as WebP if possible, fallback to PNG
            try:
                img.save(buffer, format='WEBP', quality=85, method=6)
                print(f"📦 Saved as WebP ({target_size}px)")
            except Exception as e:
                print(f"⚠️ WebP failed ({e}), falling back to PNG")
                img.save(buffer, format='PNG', optimize=True)
                print(f"📦 Saved as PNG ({target_size}px)")
            
            return buffer.getvalue()
            
        except ImportError:
            print("⚠️ PIL not available, returning original image")
            return image_bytes
        except Exception as e:
            print(f"⚠️ Downscaling failed: {e}, returning original image")
            return image_bytes
    
    def _generate_cache_key_v2(self, file_hash: str, side: str, size: int, variant: str) -> str:
        """
        Generate cache key for base/mask artifacts.
        
        Args:
            file_hash: Hash of the uploaded file
            side: 'top' or 'bottom'
            size: Image size (256, 1024)
            variant: 'base' or 'mask'
            
        Returns:
            Cache key string
        """
        render_version = "v2"
        return f"{file_hash[:16]}.{render_version}.{side}.{size}.{variant}"
    
    def generate_base_mask_artifacts(self, file_hash: str) -> dict:
        """
        Generate all base/mask artifacts for both sides and sizes.
        
        Args:
            file_hash: Hash of the uploaded file
            
        Returns:
            Dictionary with artifact data for caching/storage
        """
        if not self._pcb:
            raise RuntimeError("PCB must be loaded before generating artifacts.")
        
        print("🚀 Starting base/mask artifact generation...")
        
        # Determine which sides exist
        sides = []
        if self._pcb.has_top_layers():
            sides.append('top')
        if self._pcb.has_bottom_layers():
            sides.append('bottom')
        
        if not sides:
            raise RuntimeError("No PCB layers found")
        
        print(f"📋 Found sides: {sides}")
        
        artifacts = {}
        
        for side in sides:
            print(f"🎯 Processing {side} side...")
            
            # Render at full resolution first
            base_1024, mask_1024 = self._render_base_and_mask_layers(side, 1024)
            
            # Generate smaller versions
            print(f"📐 Downscaling {side} images to 256px...")
            base_256 = self._downscale_image(base_1024, 256)
            mask_256 = self._downscale_image(mask_1024, 256)
            
            # Store artifacts with cache keys
            artifacts[f"{side}.base.256"] = {
                'data': base_256,
                'cache_key': self._generate_cache_key_v2(file_hash, side, 256, 'base'),
                'size': 256,
                'type': 'base'
            }
            
            artifacts[f"{side}.base.1024"] = {
                'data': base_1024,
                'cache_key': self._generate_cache_key_v2(file_hash, side, 1024, 'base'),
                'size': 1024,
                'type': 'base'
            }
            
            artifacts[f"{side}.mask.256"] = {
                'data': mask_256,
                'cache_key': self._generate_cache_key_v2(file_hash, side, 256, 'mask'),
                'size': 256,
                'type': 'mask'
            }
            
            artifacts[f"{side}.mask.1024"] = {
                'data': mask_1024,
                'cache_key': self._generate_cache_key_v2(file_hash, side, 1024, 'mask'),
                'size': 1024,
                'type': 'mask'
            }
            
            print(f"✅ Completed {side} side artifacts")
        
        print(f"🎉 Generated {len(artifacts)} artifacts total")
        return artifacts

    def _calculate_dimensions(self):
        if not self._pcb or not self._pcb.board_bounds:
            self._dimensions = None
            return

        board_bounds = self._pcb.board_bounds
        unit_multiplier = 25.4 if self._pcb.layers[0].cam_source.units == 'inch' else 1.0
        
        x_min, x_max = board_bounds[0]
        y_min, y_max = board_bounds[1]
        
        width_mm = (x_max - x_min) * unit_multiplier
        height_mm = (y_max - y_min) * unit_multiplier
        area_m2 = (width_mm / 1000) * (height_mm / 1000)

        self._dimensions = BoardDimensions(
            width_mm=round(width_mm, 2),
            height_mm=round(height_mm, 2),
            area_m2=round(area_m2, 6)
        )



    def _calculate_price(self) -> Optional[PriceQuote]:
        if not self._dimensions:
            return None

        try:
            # Use robust pricing service for all materials
            pricing_result = RobustPricingService.calculate_robust_price(
                self._dimensions, 
                self._params
            )
            
            # Convert to PriceQuote format
            return PriceQuote(
                direct_cost_egp=pricing_result["details"].get("base_price_egp", 0),
                shipping_cost_egp=pricing_result["details"].get("shipping_cost_egp", 0),
                customs_rate_egp=pricing_result["details"].get("customs_rate_egp", 0),
                final_price_egp=pricing_result["final_price_egp"],
                currency="EGP",
                details=pricing_result["details"]
            )
            
        except Exception as e:
            print(f"❌ Error in price calculation: {e}")
            # Return a basic fallback price to prevent crashes
            return PriceQuote(
                direct_cost_egp=100.0,
                shipping_cost_egp=50.0,
                customs_rate_egp=25.0,
                final_price_egp=500.0,
                currency="EGP",
                details={
                    "error": str(e),
                    "note": "Fallback price due to calculation error",
                    "material": str(self._params.base_material),
                    "quantity": getattr(self._params, 'quantity', 1)
                }
            )