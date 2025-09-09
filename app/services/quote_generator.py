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
        selected_material = self._params.base_material
        
        # Map the BaseMaterial enum to the theme key (which is a string)
        if selected_material == BaseMaterial.fr4:
            theme_name = 'default' # Default green for other FR-4 colors
        elif selected_material == BaseMaterial.flex:
            theme_name = 'Flex'
        elif selected_material == BaseMaterial.aluminum:
            theme_name = 'Aluminum'
        elif selected_material == BaseMaterial.copper_core:
            theme_name = 'Copper Core'
        elif selected_material in [BaseMaterial.rogers, BaseMaterial.ptfe_teflon]:
            theme_name = 'default'
        else:
            # Fallback to the.
            theme_name = 'default'
            
        print(f"Selected base material: {selected_material}. Using render theme: '{theme_name}'")
        theme_to_use = theme.THEMES.get(theme_name, theme.THEMES['default'])
        
        # --- Rendering Logic (unchanged) ---
        
        ctx = GerberCairoContext()
        ctx.render_layers(self._pcb.top_layers, filename=None, theme=theme_to_use, max_width=1024)
        top_image_bytes = ctx.dump(None)
        ctx.clear()
        ctx.render_layers(self._pcb.bottom_layers, filename=None, theme=theme_to_use, max_width=1024)
        bottom_image_bytes = ctx.dump(None)
        return top_image_bytes, bottom_image_bytes

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

        area_m2 = self._dimensions.area_m2
        
        effective_rate = settings.YUAN_TO_EGP_RATE * settings.EXCHANGE_RATE_BUFFER
        single_board_cost_yuan = settings.FIXED_ENGINEERING_FEE_YUAN + (area_m2 * settings.PRICE_PER_M2_YUAN)
        direct_cost_yuan = single_board_cost_yuan * self._params.quantity
        direct_cost_egp = direct_cost_yuan * effective_rate
        width_cm = self._dimensions.width_mm / 10.0
        height_cm = self._dimensions.height_mm / 10.0
        thickness_cm = self._params.pcb_thickness_mm / 10.0
        single_pcb_volume_cm3 = width_cm * height_cm * thickness_cm
        single_pcb_weight_g = single_pcb_volume_cm3 * settings.FR4_DENSITY_G_PER_CM3
        total_weight_kg = (single_pcb_weight_g * self._params.quantity) / 1000.0
        shipping_cost_yuan = total_weight_kg * settings.SHIPPING_COST_PER_KG_YUAN
        shipping_cost_egp = shipping_cost_yuan * effective_rate
        customs_rate_egp = (direct_cost_egp + shipping_cost_egp) * settings.CUSTOMS_RATE_MULTIPLIER
        
        if area_m2 >= 1.0:
            final_price_multiplier = settings.FINAL_PRICE_MULTIPLIER_LARGE_AREA
        elif area_m2 >= 0.5:
            final_price_multiplier = settings.FINAL_PRICE_MULTIPLIER_MID_AREA
        else:
            final_price_multiplier = settings.FINAL_PRICE_MULTIPLIER_DEFAULT
            
        final_price_egp = customs_rate_egp * final_price_multiplier

        return PriceQuote(
            direct_cost_egp=round(direct_cost_egp, 2),
            shipping_cost_egp=round(shipping_cost_egp, 2),
            customs_rate_egp=round(customs_rate_egp, 2),
            final_price_egp=round(final_price_egp, 2),
            details={
                "quantity": self._params.quantity,
                "area_m2_per_board": area_m2,
                "pcb_thickness_mm": self._params.pcb_thickness_mm,
                "total_weight_kg": round(total_weight_kg, 3),
                "yuan_to_egp_rate_used": effective_rate,
                "final_price_multiplier_used": final_price_multiplier
            }
        )