# app/api/endpoints/printing_3d.py

import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict
import os

router = APIRouter()

# --- Enhanced Google Sheets Integration ---
# Global inventory cache
_inventory_cache = None

def get_3d_inventory_data():
    """Get 3D printing inventory data with caching"""
    global _inventory_cache
    
    if _inventory_cache is None:
        print("🔄 Loading 3D printing inventory data...")
        _inventory_cache = initialize_inventory()
    
    return _inventory_cache

def reload_inventory_data():
    """Force reload inventory data (for development/debugging)"""
    global _inventory_cache
    print("🔄 Forcing inventory data reload...")
    _inventory_cache = initialize_inventory()
    return _inventory_cache
    
    # Original Google Sheets code (commented out for now)
    """
    try:
        # Define the scope
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Path to your credentials file
        credentials_path = os.path.join(os.path.dirname(__file__), "../../../3d_credentials.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
        
        # Authorize the client
        client = gspread.authorize(creds)
        
        # Open the spreadsheet
        spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1djgrDegWTqgDLFNyUB6_OvAsuyKDc5Ya37SFarWMLd4")
        worksheet = spreadsheet.get_worksheet(0)
        
        # Read as DataFrame
        data = pd.DataFrame(worksheet.get_all_records())
        
        # Enhanced data processing
        data['Material_Short'] = data['Material'].apply(lambda x: x.split(' ')[0])
        data['Color_Upper'] = data['Color'].str.upper()
        
        # Add hex color codes for better frontend display
        color_hex_map = {
            'BLACK': '#000000',
            'WHITE': '#FFFFFF', 
            'RED': '#FF0000',
            'BLUE': '#0000FF',
            'GREEN': '#00FF00',
            'YELLOW': '#FFFF00',
            'ORANGE': '#FFA500',
            'PURPLE': '#800080',
            'GRAY': '#808080',
            'GREY': '#808080'
        }
        data['Color_Hex'] = data['Color_Upper'].map(color_hex_map).fillna('#808080')
        
        return data
        
    except FileNotFoundError:
        print("⚠️ Google Sheets credentials not found, using fallback data")
        return get_fallback_inventory_data()
    except Exception as e:
        print(f"⚠️ Could not connect to Google Sheets: {e}, using fallback data")
        return get_fallback_inventory_data()
    """

def initialize_inventory():
    """Force reload inventory data on server start"""
    print("🔄 Initializing 3D printing inventory data...")
    
    try:
        # Generate fallback data (since Google Sheets is disabled)
        inventory_df = get_fallback_inventory_data()
        print(f"✅ Generated {len(inventory_df)} fallback inventory rows")
        
        # Validate we have all combinations
        expected_rows = 4 * 16  # 4 materials × 16 colors
        if len(inventory_df) < expected_rows:
            print(f"⚠️ WARNING: Only {len(inventory_df)} inventory rows, expected {expected_rows}")
            inventory_df = get_fallback_inventory_data()
            print(f"✅ Regenerated complete inventory with {len(inventory_df)} rows")
        
        # Log inventory summary
        materials = inventory_df['Material_Short'].unique()
        colors = inventory_df['Color'].unique()
        print(f"📊 Inventory loaded: {len(materials)} materials × {len(colors)} colors = {len(inventory_df)} combinations")
        print(f"📊 Materials: {list(materials)}")
        print(f"📊 Colors: {list(colors)}")
        
        return inventory_df
        
    except Exception as e:
        print(f"❌ Error initializing inventory: {e}")
        raise

def get_fallback_inventory_data():
    """Fallback inventory data when Google Sheets is unavailable"""
    # Comprehensive color palette for 3D printing
    colors = [
        'Black', 'White', 'Blue', 'Red', 'Green', 'Yellow', 'Orange', 'Purple', 
        'Pink', 'Gray', 'Grey', 'Brown', 'Silver', 'Gold', 'Transparent', 'Clear'
    ]
    
    hex_colors = [
        '#000000', '#FFFFFF', '#0000FF', '#FF0000', '#00FF00', '#FFFF00', '#FFA500', '#800080',
        '#FFC0CB', '#808080', '#808080', '#A52A2A', '#C0C0C0', '#FFD700', '#FFFFFF', '#FFFFFF'
    ]
    
    materials = ['PLA', 'ABS', 'PETG', 'TPU']
    
    # Create all combinations of materials and colors
    import itertools
    combinations = list(itertools.product(materials, colors))
    
    data_rows = []
    for material, color in combinations:
        hex_code = hex_colors[colors.index(color)]
        data_rows.append({
            'Material': material,
            'Material_Short': material,
            'Color': color,
            'Color_Upper': color.upper(),
            'Remaining (g)': 1000,  # Assume 1000g available for all combinations
            'Color_Hex': hex_code
        })
    
    return pd.DataFrame(data_rows)

def get_fallback_available_options():
    """Fallback available options when Google Sheets is unavailable"""
    # Comprehensive color palette for all materials
    all_colors = [
        {"name": "Black", "hex": "#000000"},
        {"name": "White", "hex": "#FFFFFF"},
        {"name": "Blue", "hex": "#0000FF"},
        {"name": "Red", "hex": "#FF0000"},
        {"name": "Green", "hex": "#00FF00"},
        {"name": "Yellow", "hex": "#FFFF00"},
        {"name": "Orange", "hex": "#FFA500"},
        {"name": "Purple", "hex": "#800080"},
        {"name": "Pink", "hex": "#FFC0CB"},
        {"name": "Gray", "hex": "#808080"},
        {"name": "Brown", "hex": "#A52A2A"},
        {"name": "Silver", "hex": "#C0C0C0"},
        {"name": "Gold", "hex": "#FFD700"},
        {"name": "Transparent", "hex": "#FFFFFF"},
        {"name": "Clear", "hex": "#FFFFFF"}
    ]
    
    return Available3DOptionsResponse(
        technologies=["FDM"],
        materials={
            "PLA": all_colors,
            "ABS": all_colors,
            "PETG": all_colors,
            "TPU": all_colors
        }
    )

# --- Enhanced Pricing Logic ---
material_densities = {
    "ABS": 1.05,
    "PLA": 1.24,
    "TPU": 1.18,
    "PETG": 1.30
}

price_per_gram = {
    "TPU": 5,
    "ABS": 2.5,
    "PLA": 2.5,
    "PETG": 2.5
}

# --- Request and Response Models ---
class Print3DRequest(BaseModel):
    volume_cm3: float = Field(..., gt=0, description="Volume of the object in cubic centimeters")
    material: str
    color: str
    infill_percentage: float = Field(..., ge=0.1, le=1.0, description="Infill percentage between 0.1 and 1.0")
    quantity: int = Field(..., gt=0, description="Number of items to print")

class Print3DPriceResponse(BaseModel):
    total_price_egp: float
    weight_grams: float
    price_per_unit_egp: float
    quantity: int
    max_quantity: int
    available_grams: float

class Available3DOptionsResponse(BaseModel):
    technologies: List[str]
    materials: Dict[str, List[Dict[str, str]]]

# --- API Endpoints ---
@router.get("/debug-sheet")
def debug_3d_sheet():
    """Debug endpoint to see raw 3D printing sheet data"""
    try:
        inventory_df = get_3d_inventory_data()
        print(f"🔍 DEBUG SHEET: Inventory data shape: {inventory_df.shape}")
        print(f"🔍 DEBUG SHEET: Available materials: {inventory_df['Material_Short'].unique()}")
        print(f"🔍 DEBUG SHEET: Available colors: {inventory_df['Color'].unique()}")
        
        # Show all materials and their colors
        for material in inventory_df['Material_Short'].unique():
            material_colors = inventory_df[inventory_df['Material_Short'] == material]['Color'].unique()
            print(f"🔍 DEBUG SHEET: {material} colors: {list(material_colors)}")
        
        return {
            "columns": list(inventory_df.columns),
            "sample_data": inventory_df.head().to_dict('records'),
            "total_rows": len(inventory_df),
            "all_materials": list(inventory_df['Material_Short'].unique()),
            "all_colors": list(inventory_df['Color'].unique()),
            "abs_colors": list(inventory_df[inventory_df['Material_Short'] == 'ABS']['Color'].unique())
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/reload-inventory")
def reload_inventory():
    """Development endpoint to force reload inventory"""
    try:
        inventory_df = reload_inventory_data()
        return {
            "status": "reloaded",
            "total_rows": len(inventory_df),
            "materials": list(inventory_df['Material_Short'].unique()),
            "colors": list(inventory_df['Color'].unique()),
            "expected_rows": 64,
            "is_complete": len(inventory_df) >= 64
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}

@router.get("/health")
def health_check():
    """Health check endpoint for inventory status"""
    try:
        inventory_df = get_3d_inventory_data()
        expected_rows = 64
        actual_rows = len(inventory_df)
        
        return {
            "status": "healthy" if actual_rows >= expected_rows else "degraded",
            "inventory_rows": actual_rows,
            "expected_rows": expected_rows,
            "is_complete": actual_rows >= expected_rows,
            "materials_count": len(inventory_df['Material_Short'].unique()),
            "colors_count": len(inventory_df['Color'].unique()),
            "available_combinations": f"{len(inventory_df['Material_Short'].unique())} materials × {len(inventory_df['Color'].unique())} colors"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@router.get("/available-options", response_model=Available3DOptionsResponse)
def get_3d_available_options():
    """Get available 3D printing technologies, materials, and colors from inventory"""
    try:
        inventory_df = get_3d_inventory_data()
        print(f"📊 Retrieved inventory data with {len(inventory_df)} rows")
        print(f"📊 Columns: {list(inventory_df.columns)}")
        
        # Group by material and get available colors with hex codes
        materials_colors = {}
        
        # Get unique materials and their colors
        for material in inventory_df['Material_Short'].unique():
            material_upper = material.upper()
            if material_upper in material_densities:  # Only include supported materials
                # Get colors for this material where remaining quantity > 0
                material_rows = inventory_df[
                    (inventory_df['Material_Short'].str.upper() == material_upper) &
                    (inventory_df['Remaining (g)'] > 0)
                ]
                
                # Create color objects with name and hex
                colors = []
                for _, row in material_rows.iterrows():
                    color_name = row['Color']
                    
                    # Try different possible column names for hex code
                    hex_code = '#808080'  # Default gray
                    possible_hex_columns = [
                        'color HEX code ',  # Exact match from sheet (with trailing space)
                        'Color HEX code', 
                        'Color HEX Code', 
                        'color hex code',
                        'Color Hex Code',
                        'HEX Code',
                        'Hex Code',
                        'hex code',
                        'HEX',
                        'Hex'
                    ]
                    
                    for col_name in possible_hex_columns:
                        if col_name in inventory_df.columns:
                            hex_value = row.get(col_name)
                            if hex_value and not pd.isna(hex_value) and str(hex_value).strip() != '':
                                hex_code = str(hex_value).strip()
                                if not hex_code.startswith('#'):
                                    hex_code = '#' + hex_code
                                break
                    
                    colors.append({
                        'name': color_name,
                        'hex': hex_code
                    })
                
                if colors:  # Only include if there are available colors
                    materials_colors[material_upper] = colors
        
        return Available3DOptionsResponse(
            technologies=["FDM"],  # For now, only FDM
            materials=materials_colors
        )
        
    except Exception as e:
        # If there's any error, return fallback data instead of failing
        print(f"⚠️ Error in get_3d_available_options: {e}, returning fallback data")
        return get_fallback_available_options()

@router.post("/pricing", response_model=Print3DPriceResponse)
def calculate_3d_price(request: Print3DRequest):
    """Calculate 3D printing price based on volume, material, and quantity"""
    try:
        # --- Input Validation ---
        if request.material.upper() not in material_densities:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid material: {request.material}. Available materials are {list(material_densities.keys())}"
            )

        # --- Weight Calculation ---
        density = material_densities[request.material.upper()]
        weight_per_unit = request.volume_cm3 * density * request.infill_percentage
        total_weight_required = weight_per_unit * request.quantity

        # --- Inventory Check and Max Quantity Calculation ---
        try:
            inventory_df = get_3d_inventory_data()
            print(f"🔍 DEBUG: Inventory data shape: {inventory_df.shape}")
            print(f"🔍 DEBUG: Available materials: {inventory_df['Material_Short'].unique()}")
            print(f"🔍 DEBUG: Available colors: {inventory_df['Color'].unique()}")
            print(f"🔍 DEBUG: Looking for material: {request.material.upper()}, color: {request.color.upper()}")
            
            # Filter for the requested material and color
            material_inventory = inventory_df[
                (inventory_df['Material_Short'].str.upper() == request.material.upper()) &
                (inventory_df['Color'].str.upper() == request.color.upper())
            ]
            print(f"🔍 DEBUG: Found {len(material_inventory)} matching rows")
            
            if material_inventory.empty:
                available_materials = inventory_df['Material_Short'].str.upper().unique()
                available_colors = inventory_df['Color'].str.upper().unique()
                raise HTTPException(
                    status_code=404, 
                    detail=f"Material not found: {request.material} in color {request.color}. Available materials: {list(available_materials)}"
                )

            # Check remaining quantity
            remaining_col = 'Remaining (g)'
            if remaining_col not in material_inventory.columns:
                possible_cols = [col for col in material_inventory.columns if 'remaining' in col.lower() or 'quantity' in col.lower()]
                if possible_cols:
                    remaining_col = possible_cols[0]
                else:
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Cannot find remaining quantity column. Available columns: {list(material_inventory.columns)}"
                    )
            
            available_grams = material_inventory[remaining_col].sum()

            # Calculate maximum possible quantity
            max_quantity = int(available_grams // weight_per_unit) if weight_per_unit > 0 else 0

            # Check if requested quantity exceeds available
            if total_weight_required > available_grams:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Not enough material in stock. Required: {total_weight_required:.2f}g, Available: {available_grams:.2f}g, Max quantity: {max_quantity}"
                )

        except HTTPException:
            raise
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An error occurred during inventory check: {e}")

        # --- Price Calculation ---
        price_per_unit = weight_per_unit * price_per_gram[request.material.upper()]
        total_price = price_per_unit * request.quantity
        
        result = Print3DPriceResponse(
            total_price_egp=round(total_price, 2),
            weight_grams=round(total_weight_required, 2),
            price_per_unit_egp=round(price_per_unit, 2),
            quantity=request.quantity,
            max_quantity=max_quantity,
            available_grams=round(available_grams, 2),
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 