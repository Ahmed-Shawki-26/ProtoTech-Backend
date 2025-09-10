import requests
import os

def get_exchange_rate_egp_cny():
    """Get EGP to CNY exchange rate with fallback for local development"""
    try:
        # Check if we're in development mode
        if os.getenv("ENVIRONMENT", "development") == "development":
            print("🔧 Development mode: Using fallback exchange rate")
            return 0.21  # Fallback rate for development
        
        # Try to fetch real exchange rate
        url = 'https://api.exchangerate-api.com/v4/latest/CNY'
        response = requests.get(url, timeout=5)  # Add timeout
        if response.status_code == 200:
            data = response.json()
            rate = data['rates'].get('EGP', None)
            if rate:
                print(f"✅ Fetched exchange rate: {rate}")
                return rate
        
        print("⚠️ Failed to fetch exchange rate, using fallback")
        return 0.21  # Fallback rate
        
    except Exception as e:
        print(f"⚠️ Exchange rate API error: {e}, using fallback")
        return 0.21  # Fallback rate
