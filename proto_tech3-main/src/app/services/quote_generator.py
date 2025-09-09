# app/services/quote_generator.py

import io
import os
import re
import tempfile
import zipfile
import rarfile
from typing import Tuple, Optional

from src.gerber import PCB
from src.gerber.render import theme
from src.gerber.render.cairo_backend import GerberCairoContext
from src.gerber.exceptions import ParseError

from src.app.core.config import settings
from src.app.schemas.pcb import BoardDimensions, PriceQuote, ManufacturingParameters,BaseMaterial


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

        # --- Initialize variables ---
        multipliers = {}
        width_cm = self._dimensions.width_mm / 10.0
        height_cm = self._dimensions.height_mm / 10.0
        extra_days = 0

        # --- Rule 1: Base Defaults (Dimension Check) ---
        if (width_cm > settings.MAX_WIDTH_CM and height_cm > settings.MAX_HEIGHT_CM) or \
        (width_cm > settings.MAX_HEIGHT_CM and height_cm > settings.MAX_WIDTH_CM):
            raise ValueError(f"Board dimensions ({width_cm:.1f}x{height_cm:.1f} cm) exceed the maximum allowed size of {settings.MAX_WIDTH_CM}x{settings.MAX_HEIGHT_CM} cm.")

        # --- Rule 2: Panel Pricing ---
        panel_area_cm2 = width_cm * height_cm
        price_per_cm2 = settings.MINIMUM_CM2_PRICE_EGP
        for area_threshold, price in sorted(settings.PANEL_PRICE_BRACKETS_EGP.items()):
            if panel_area_cm2 <= area_threshold:
                price_per_cm2 = price
                break
        
        base_price = panel_area_cm2 * price_per_cm2
        
        # --- Rule 3: Quantity Multiplier ---
        quantity_multiplier = 1.0
        for quantity_threshold, multiplier in sorted(settings.QUANTITY_MULTIPLIERS.items(), reverse=True):
            if self._params.quantity >= quantity_threshold:
                quantity_multiplier = multiplier
                break
        multipliers['quantity'] = quantity_multiplier

        # --- Rule 4: Different Designs Multiplier ---
        designs = self._params.different_designs
        designs_multiplier = 1.0 + (designs - 1) * settings.DIFFERENT_DESIGNS_MULTIPLIER_FACTOR
        multipliers['designs'] = designs_multiplier

        # --- Rule 5: Delivery Format Multiplier ---
        # Assuming 'panels' is a parameter in your ManufacturingParameters. If not, this needs adjustment.
        # For now, let's assume `delivery_format` is the key.
        delivery_multiplier = 1.0
        if self._params.delivery_format == "Panel by Customer":
            # This rule is ambiguous. Let's assume it means if there are 2 different designs, it's 2 panels.
            delivery_multiplier = 1.0 + (designs - 1) * settings.PANEL_BY_CUSTOMER_MULTIPLIER_FACTOR
        multipliers['delivery_format'] = delivery_multiplier

        # --- Rule 6: Thickness Multiplier ---
        thickness = self._params.pcb_thickness_mm # This is now an Enum member, but its value is a float
        
        # --- REVISED LOGIC ---
        # The logic now correctly handles the 1.0-1.6 range having the same multiplier.
        if 1.0 <= thickness <= 1.6:
            thickness_multiplier = 1.0
        else:
            # For other values, look them up in the dictionary.
            # Default to 1.0 if a value is somehow not found.
            thickness_multiplier = settings.THICKNESS_MULTIPLIERS.get(thickness, 1.0)
        
        multipliers['thickness'] = thickness_multiplier

        # --- Rule 7: Color Options ---
        if self._params.pcb_color.lower() == "green":
            color_multiplier = settings.GREEN_COLOR_MULTIPLIER
        else:
            color_multiplier = settings.OTHER_COLOR_MULTIPLIER
            extra_days = settings.OTHER_COLOR_EXTRA_DAYS
        multipliers['color'] = color_multiplier

        # --- Rule 8: High-Spec Options ---
        # Copper Weight
        copper_weight = self._params.outer_copper_weight
        copper_multiplier = settings.OUTER_COPPER_WEIGHT_MULTIPLIERS.get(copper_weight, 1.0)
        multipliers['copper_weight'] = copper_multiplier
        
        # Via Hole (simplified logic)
        via_multiplier = 1.0
        try:
            # Tries to extract the first number from a string like "0.3mm/(0.4/0.45mm)"
            min_via_str = self._params.min_via_hole_size_dia
            min_via_float = float(min_via_str)
            if min_via_float < settings.MIN_VIA_HOLE_THRESHOLD_MM:
                via_multiplier = settings.MIN_VIA_HOLE_MULTIPLIER
        except (ValueError, IndexError):
            pass # Ignore if format is unexpected
        multipliers['via_hole'] = via_multiplier

        # Tolerance
        tolerance = self._params.board_outline_tolerance
        tolerance_multiplier = settings.BOARD_OUTLINE_TOLERANCE_MULTIPLIERS.get(tolerance, 1.0)
        multipliers['tolerance'] = tolerance_multiplier

        # --- Final Price Calculation ---
        final_price = base_price
        for key, value in multipliers.items():
            final_price *= value

        return PriceQuote(
            final_price_egp=round(final_price, 2),
            extra_working_days=extra_days,
            details={
                "base_price_egp": round(base_price, 2),
                "panel_area_cm2": round(panel_area_cm2, 2),
                "price_per_cm2_egp": price_per_cm2,
                "applied_multipliers": multipliers
            }
        )