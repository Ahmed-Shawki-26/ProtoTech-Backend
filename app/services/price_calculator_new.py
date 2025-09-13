# app/services/price_calculator_new.py

import logging
from typing import Dict, Any
import math

from app.schemas.pcb import ManufacturingParameters, BoardDimensions
from app.services.pricing_rules_engine import PricingRulesEngine

logger = logging.getLogger(__name__)

class PriceCalculator:
    """
    Core price calculation engine.
    Handles base price calculations and pricing formulas.
    """
    
    # Base pricing constants (EGP)
    BASE_PRICE_PER_CM2 = 1.5  # Base price per cm²
    MINIMUM_ORDER_VALUE = 50.0  # Minimum order value
    PANEL_SETUP_COST = 25.0  # Panel setup cost
    
    # Panel size limits
    MAX_PANEL_WIDTH_CM = 38.0
    MAX_PANEL_HEIGHT_CM = 28.0
    
    # Quantity-based pricing brackets
    QUANTITY_PRICING_BRACKETS = [
        (1, 2.0),      # 1 piece: 2x multiplier
        (3, 1.5),      # 3 pieces: 1.5x
        (5, 1.0),      # 5+ pieces: 1x
        (10, 0.9),     # 10+ pieces: 0.9x
        (50, 0.8),     # 50+ pieces: 0.8x
        (100, 0.7),    # 100+ pieces: 0.7x
        (500, 0.6),    # 500+ pieces: 0.6x
    ]
    
    # Panel utilization pricing
    PANEL_UTILIZATION_BRACKETS = [
        (0.0, 1.0),    # 0-25% utilization: 1.0x
        (0.25, 0.9),   # 25-50% utilization: 0.9x
        (0.5, 0.8),    # 50-75% utilization: 0.8x
        (0.75, 0.7),   # 75-100% utilization: 0.7x
    ]
    
    def __init__(self):
        self.rules_engine = PricingRulesEngine()
        logger.info("PriceCalculator initialized")
    
    def calculate_base_price(
        self, 
        dimensions: BoardDimensions, 
        params: ManufacturingParameters
    ) -> float:
        """
        Calculate base price for PCB manufacturing.
        
        Args:
            dimensions: Board dimensions
            params: Manufacturing parameters
            
        Returns:
            Base price in EGP
        """
        try:
            # Calculate board area in cm²
            area_cm2 = dimensions.area_m2 * 10000
            
            # Get material-specific pricing
            material = params.base_material.value
            
            # Use panel area pricing for FR-4, fallback to base price for others
            if material == "FR-4":
                base_price = self._calculate_fr4_panel_price(area_cm2)
            else:
                base_price = area_cm2 * self.BASE_PRICE_PER_CM2
            
            # Apply quantity-based pricing
            quantity_multiplier = self._get_quantity_multiplier(params.quantity)
            base_price *= quantity_multiplier
            
            # Apply panel utilization pricing
            panel_utilization = self._calculate_panel_utilization(dimensions, params.quantity)
            utilization_multiplier = self._get_utilization_multiplier(panel_utilization)
            base_price *= utilization_multiplier
            
            # Add setup costs for small quantities
            if params.quantity < 5:
                base_price += self.PANEL_SETUP_COST
            
            # Apply minimum order value
            base_price = max(base_price, self.MINIMUM_ORDER_VALUE)
            
            logger.debug(f"Base price calculated: {base_price:.2f} EGP "
                        f"(area: {area_cm2:.2f} cm², quantity: {params.quantity})")
            
            return base_price
            
        except Exception as e:
            logger.error(f"Base price calculation failed: {e}")
            # Return a reasonable fallback
            return dimensions.area_m2 * 10000 * self.BASE_PRICE_PER_CM2
    
    def _calculate_fr4_panel_price(self, area_cm2: float) -> float:
        """
        Calculate FR-4 panel pricing based on area brackets.
        
        Args:
            area_cm2: Board area in cm²
            
        Returns:
            Base price in EGP
        """
        # FR-4 panel area pricing brackets
        panel_pricing = {
            "≤1000": 1.6,
            "1001-1500": 1.5,
            "1501-2000": 1.4,
            "2001-2500": 1.3,
            "2501-3000": 1.2,
            "min_price": 1.2
        }
        
        # Determine which bracket the area falls into
        if area_cm2 <= 1000:
            price_per_cm2 = panel_pricing["≤1000"]
        elif area_cm2 <= 1500:
            price_per_cm2 = panel_pricing["1001-1500"]
        elif area_cm2 <= 2000:
            price_per_cm2 = panel_pricing["1501-2000"]
        elif area_cm2 <= 2500:
            price_per_cm2 = panel_pricing["2001-2500"]
        elif area_cm2 <= 3000:
            price_per_cm2 = panel_pricing["2501-3000"]
        else:
            # For areas larger than 3000 cm², use minimum price
            price_per_cm2 = panel_pricing["min_price"]
        
        base_price = area_cm2 * price_per_cm2
        
        logger.debug(f"FR-4 panel pricing: {area_cm2:.2f} cm² × {price_per_cm2:.2f} EGP/cm² = {base_price:.2f} EGP")
        
        return base_price
    
    def _get_quantity_multiplier(self, quantity: int) -> float:
        """Get quantity-based pricing multiplier."""
        # Sort brackets by quantity (descending) for efficient lookup
        for threshold, multiplier in sorted(
            self.QUANTITY_PRICING_BRACKETS, 
            key=lambda x: x[0], 
            reverse=True
        ):
            if quantity >= threshold:
                return multiplier
        
        # Return the highest multiplier if below all thresholds
        return max(multiplier for _, multiplier in self.QUANTITY_PRICING_BRACKETS)
    
    def _calculate_panel_utilization(
        self, 
        dimensions: BoardDimensions, 
        quantity: int
    ) -> float:
        """
        Calculate panel utilization percentage.
        
        Args:
            dimensions: Board dimensions
            quantity: Number of boards
            
        Returns:
            Panel utilization as a percentage (0.0 to 1.0)
        """
        try:
            # Calculate board area
            board_area_cm2 = dimensions.area_m2 * 10000
            
            # Calculate panel area
            panel_area_cm2 = self.MAX_PANEL_WIDTH_CM * self.MAX_PANEL_HEIGHT_CM
            
            # Calculate how many boards fit on a panel
            # Simple calculation - could be more sophisticated
            boards_per_panel = int(
                (self.MAX_PANEL_WIDTH_CM / dimensions.width_mm * 10) * 
                (self.MAX_PANEL_HEIGHT_CM / dimensions.height_mm * 10)
            )
            
            if boards_per_panel == 0:
                boards_per_panel = 1  # Minimum 1 board per panel
            
            # Calculate number of panels needed
            panels_needed = math.ceil(quantity / boards_per_panel)
            
            # Calculate utilization
            total_board_area = board_area_cm2 * quantity
            total_panel_area = panel_area_cm2 * panels_needed
            utilization = min(total_board_area / total_panel_area, 1.0)
            
            logger.debug(f"Panel utilization: {utilization:.2%} "
                        f"({quantity} boards, {panels_needed} panels)")
            
            return utilization
            
        except Exception as e:
            logger.error(f"Panel utilization calculation failed: {e}")
            return 0.5  # Default to 50% utilization
    
    def _get_utilization_multiplier(self, utilization: float) -> float:
        """Get panel utilization multiplier."""
        for threshold, multiplier in sorted(
            self.PANEL_UTILIZATION_BRACKETS, 
            key=lambda x: x[0], 
            reverse=True
        ):
            if utilization >= threshold:
                return multiplier
        
        return 1.0  # Default multiplier
    
    def calculate_engineering_fees(
        self, 
        params: ManufacturingParameters, 
        base_price: float
    ) -> float:
        """Calculate engineering fees based on complexity."""
        try:
            engineering_fee = 0.0
            
            # Base engineering fee
            if params.quantity < 10:
                engineering_fee = base_price * 0.05  # 5% for small quantities
            
            # Additional fees for complex requirements
            if hasattr(params, 'min_via_hole_size_dia'):
                via_hole = float(params.min_via_hole_size_dia.value)
                if via_hole < 0.2:
                    engineering_fee += 25.0  # Small via holes
            
            if hasattr(params, 'board_outline_tolerance'):
                tolerance = params.board_outline_tolerance.value
                if "Precision" in tolerance:
                    engineering_fee += 15.0  # Precision tolerance
            
            if hasattr(params, 'outer_copper_weight'):
                copper_weight = params.outer_copper_weight
                if copper_weight in ["2 oz", "3 oz"]:
                    engineering_fee += 20.0  # Heavy copper
            
            logger.debug(f"Engineering fees calculated: {engineering_fee:.2f} EGP")
            return engineering_fee
            
        except Exception as e:
            logger.error(f"Engineering fee calculation failed: {e}")
            return 0.0
    
    def calculate_shipping_cost(
        self, 
        params: ManufacturingParameters, 
        base_price: float
    ) -> float:
        """Calculate shipping costs."""
        try:
            # Base shipping cost
            shipping_cost = 45.0
            
            # Additional shipping for large orders
            if params.quantity > 100:
                shipping_cost += 25.0  # Extra handling for large quantities
            
            if base_price > 1000:
                shipping_cost += 15.0  # Insurance for high-value orders
            
            logger.debug(f"Shipping cost calculated: {shipping_cost:.2f} EGP")
            return shipping_cost
            
        except Exception as e:
            logger.error(f"Shipping cost calculation failed: {e}")
            return 45.0  # Default shipping cost
    
    def calculate_tax_amount(self, subtotal: float) -> float:
        """Calculate tax amount (VAT)."""
        try:
            # 14% VAT
            tax_rate = 0.14
            tax_amount = subtotal * tax_rate
            
            logger.debug(f"Tax amount calculated: {tax_amount:.2f} EGP")
            return tax_amount
            
        except Exception as e:
            logger.error(f"Tax calculation failed: {e}")
            return subtotal * 0.14
    
    def calculate_customs_rate(self, subtotal: float) -> float:
        """Calculate customs and duties."""
        try:
            # 5% customs rate
            customs_rate = 0.05
            customs_amount = subtotal * customs_rate
            
            logger.debug(f"Customs rate calculated: {customs_amount:.2f} EGP")
            return customs_amount
            
        except Exception as e:
            logger.error(f"Customs calculation failed: {e}")
            return subtotal * 0.05
    
    def get_pricing_breakdown(
        self, 
        dimensions: BoardDimensions, 
        params: ManufacturingParameters
    ) -> Dict[str, Any]:
        """
        Get detailed pricing breakdown.
        
        Args:
            dimensions: Board dimensions
            params: Manufacturing parameters
            
        Returns:
            Dictionary with pricing breakdown
        """
        try:
            # Calculate base price
            base_price = self.calculate_base_price(dimensions, params)
            
            # Calculate fees
            engineering_fees = self.calculate_engineering_fees(params, base_price)
            shipping_cost = self.calculate_shipping_cost(params, base_price)
            
            # Calculate subtotal
            subtotal = base_price + engineering_fees
            
            # Calculate taxes and customs
            customs_rate = self.calculate_customs_rate(subtotal)
            tax_amount = self.calculate_tax_amount(subtotal)
            
            # Calculate final total
            final_total = subtotal + shipping_cost + customs_rate + tax_amount
            
            breakdown = {
                "base_price_egp": base_price,
                "engineering_fees_egp": engineering_fees,
                "shipping_cost_egp": shipping_cost,
                "customs_rate_egp": customs_rate,
                "tax_amount_egp": tax_amount,
                "subtotal_egp": subtotal,
                "final_total_egp": final_total,
                "area_cm2": dimensions.area_m2 * 10000,
                "quantity": params.quantity,
                "panel_utilization": self._calculate_panel_utilization(dimensions, params.quantity)
            }
            
            logger.debug(f"Pricing breakdown calculated: {final_total:.2f} EGP total")
            return breakdown
            
        except Exception as e:
            logger.error(f"Pricing breakdown calculation failed: {e}")
            # Return minimal breakdown
            base_price = dimensions.area_m2 * 10000 * self.BASE_PRICE_PER_CM2
            return {
                "base_price_egp": base_price,
                "engineering_fees_egp": 0.0,
                "shipping_cost_egp": 45.0,
                "customs_rate_egp": base_price * 0.05,
                "tax_amount_egp": base_price * 0.14,
                "subtotal_egp": base_price,
                "final_total_egp": base_price * 1.19 + 45.0,
                "area_cm2": dimensions.area_m2 * 10000,
                "quantity": params.quantity,
                "panel_utilization": 0.5
            }

# Global price calculator instance
price_calculator = PriceCalculator()
