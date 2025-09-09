import requests

def get_exchange_rate_egp_cny():
    url = 'https://api.exchangerate-api.com/v4/latest/CNY'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['rates'].get('EGP', None)
    return None
