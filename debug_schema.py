# debug_schema.py
# Simple test to debug schema issues

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.schemas.pcb import ManufacturingParameters, BaseMaterial, MinViaHole, BoardOutlineTolerance

def test_schema_creation():
    """Test creating ManufacturingParameters directly."""
    print("🧪 Testing ManufacturingParameters creation...")
    
    try:
        # Test with minimal parameters
        params = ManufacturingParameters(
            quantity=5,
            base_material=BaseMaterial.fr4,
            min_via_hole_size_dia=MinViaHole.h_30_mm,
            board_outline_tolerance=BoardOutlineTolerance.regular
        )
        
        print(f"✅ Created successfully!")
        print(f"   confirm_production_file: {params.confirm_production_file} (type: {type(params.confirm_production_file)})")
        print(f"   electrical_test: {params.electrical_test} (type: {type(params.electrical_test)})")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create ManufacturingParameters: {e}")
        return False

def test_schema_with_explicit_values():
    """Test with explicit string values."""
    print("\n🧪 Testing with explicit string values...")
    
    try:
        params = ManufacturingParameters(
            quantity=5,
            base_material=BaseMaterial.fr4,
            min_via_hole_size_dia=MinViaHole.h_30_mm,
            board_outline_tolerance=BoardOutlineTolerance.regular,
            confirm_production_file="No",
            electrical_test="optical manual inspection"
        )
        
        print(f"✅ Created successfully!")
        print(f"   confirm_production_file: {params.confirm_production_file} (type: {type(params.confirm_production_file)})")
        print(f"   electrical_test: {params.electrical_test} (type: {type(params.electrical_test)})")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create ManufacturingParameters: {e}")
        return False

if __name__ == "__main__":
    test_schema_creation()
    test_schema_with_explicit_values()
