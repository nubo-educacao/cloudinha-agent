import requests
import traceback

try:
    response = requests.get('https://viacep.com.br/ws/04107000/json/', timeout=5.0)
    print("Status:", response.status_code)
    print("Body:", response.text)
except Exception as e:
    print(traceback.format_exc())
