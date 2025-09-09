from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from typing import List, Dict

# --- FastAPI App Initialization ---
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080", "http://127.0.0.1:3000", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Google Sheets Integration ---
def get_inventory_data():
    try:
        # Define the scope
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Path to your credentials file
        creds = ServiceAccountCredentials.from_json_keyfile_name("credntials.json", scope)
        # Authorize the client
        client = gspread.authorize(creds)
        # Open the spreadsheet
        spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1djgrDegWTqgDLFNyUB6_OvAsuyKDc5Ya37SFarWMLd4")
        worksheet = spreadsheet.get_worksheet(0)
        # Read as DataFrame
        data = pd.DataFrame(worksheet.get_all_records())
        # Extract short material name (e.g., "PETG")
        data['Material_Short'] = data['Material'].apply(lambda x: x.split(' ')[0])
        return data
    except FileNotFoundError:
        raise RuntimeError("The 'credntials.json' file was not found. Please make sure it is in the root directory.")
    except Exception as e:
        # If credentials fail or sheet is not available, we can either fail hard
        # or return an empty dataframe and log a warning.
        # For now, let's raise an exception to make the issue visible.
        raise RuntimeError(f"Could not connect to Google Sheets: {e}") from e


# --- Pricing Logic ---
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
class PrintRequest(BaseModel):
    volume_cm3: float = Field(..., gt=0, description="Volume of the object in cubic centimeters")
    material: str
    color: str
    infill_percentage: float = Field(..., ge=0.1, le=1.0, description="Infill percentage between 0.1 and 1.0")
    quantity: int = Field(..., gt=0, description="Number of items to print")

class PriceResponse(BaseModel):
    total_price_egp: float
    weight_grams: float
    price_per_unit_egp: float
    quantity: int
    max_quantity: int
    available_grams: float  # Add available grams field

class AvailableOptionsResponse(BaseModel):
    technologies: List[str]
    materials: Dict[str, List[Dict[str, str]]]  # Changed to List of Dict with name and hex

# --- API Endpoints ---
@app.get("/debug-sheet")
def debug_sheet():
    """Debug endpoint to see raw sheet data"""
    try:
        inventory_df = get_inventory_data()
        return {
            "columns": list(inventory_df.columns),
            "sample_data": inventory_df.head().to_dict('records'),
            "total_rows": len(inventory_df)
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/available-options", response_model=AvailableOptionsResponse)
def get_available_options():
    """Get available 3D printing technologies, materials, and colors from inventory"""
    try:
        inventory_df = get_inventory_data()
        
        # Debug: Print available columns
        print("Available columns in sheet:", list(inventory_df.columns))
        
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
                                print(f"Found hex code for {color_name}: {hex_code}")
                                break
                    
                    if hex_code == '#808080':
                        print(f"No hex code found for {color_name}, using default gray")
                    
                    colors.append({
                        'name': color_name,
                        'hex': hex_code
                    })
                
                if colors:  # Only include if there are available colors
                    materials_colors[material_upper] = colors
        
        return AvailableOptionsResponse(
            technologies=["FDM"],  # For now, only FDM
            materials=materials_colors
        )
        
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while fetching available options: {e}")

@app.post("/pricing", response_model=PriceResponse)
def calculate_price(request: PrintRequest):
    try:
        print(f"Received pricing request: {request}")
        
        # --- Input Validation ---
        if request.material.upper() not in material_densities:
            raise HTTPException(status_code=400, detail=f"Invalid material: {request.material}. Available materials are {list(material_densities.keys())}")

        # --- Weight Calculation ---
        density = material_densities[request.material.upper()]
        weight_per_unit = request.volume_cm3 * density * request.infill_percentage
        total_weight_required = weight_per_unit * request.quantity
        
        print(f"Weight calculation: density={density}, weight_per_unit={weight_per_unit}, total_weight={total_weight_required}")

        # --- Inventory Check and Max Quantity Calculation ---
        try:
            print("Fetching inventory data...")
            inventory_df = get_inventory_data()
            
            # Filter for the requested material and color
            print(f"Filtering for material: {request.material.upper()}, color: {request.color.upper()}")
            material_inventory = inventory_df[
                (inventory_df['Material_Short'].str.upper() == request.material.upper()) &
                (inventory_df['Color'].str.upper() == request.color.upper())
            ]
            
            if material_inventory.empty:
                available_materials = inventory_df['Material_Short'].str.upper().unique()
                available_colors = inventory_df['Color'].str.upper().unique()
                print(f"Available materials: {available_materials}")
                print(f"Available colors: {available_colors}")
                raise HTTPException(status_code=404, detail=f"Material not found: {request.material} in color {request.color}. Available materials: {list(available_materials)}")

            # Check remaining quantity
            remaining_col = 'Remaining (g)'
            if remaining_col not in material_inventory.columns:
                print(f"Warning: Column '{remaining_col}' not found. Available columns: {list(material_inventory.columns)}")
                possible_cols = [col for col in material_inventory.columns if 'remaining' in col.lower() or 'quantity' in col.lower()]
                if possible_cols:
                    remaining_col = possible_cols[0]
                    print(f"Using column: {remaining_col}")
                else:
                    raise HTTPException(status_code=500, detail=f"Cannot find remaining quantity column. Available columns: {list(material_inventory.columns)}")
            
            available_grams = material_inventory[remaining_col].sum()
            print(f"Available grams: {available_grams}, Required: {total_weight_required}")

            # Calculate maximum possible quantity
            max_quantity = int(available_grams // weight_per_unit) if weight_per_unit > 0 else 0
            print(f"Maximum possible quantity: {max_quantity}")

            # Check if requested quantity exceeds available
            if total_weight_required > available_grams:
                raise HTTPException(status_code=400, detail=f"Not enough material in stock. Required: {total_weight_required:.2f}g, Available: {available_grams:.2f}g, Max quantity: {max_quantity}")

        except HTTPException:
            raise
        except RuntimeError as e:
            print(f"Runtime error: {e}")
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            print(f"Unexpected error during inventory check: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"An error occurred during inventory check: {e}")

        # --- Price Calculation ---
        print("Calculating price...")
        price_per_unit = weight_per_unit * price_per_gram[request.material.upper()]
        total_price = price_per_unit * request.quantity
        
        result = PriceResponse(
            total_price_egp=round(total_price, 2),
            weight_grams=round(total_weight_required, 2),
            price_per_unit_egp=round(price_per_unit, 2),
            quantity=request.quantity,
            max_quantity=max_quantity,
            available_grams=round(available_grams, 2),
        )
        
        print(f"Returning price response: {result}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in calculate_price: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

# To run this app:
# uvicorn src.main:app --reload