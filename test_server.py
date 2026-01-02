import requests
import uuid

url = "http://localhost:8002/chat"
payload = {
    "chatInput": "Oi Cloudinha, como você está?",
    "userId": "test-user-123",
    "sessionId": str(uuid.uuid4())
}

try:
    print(f"Sending request to {url}...")
    response = requests.post(url, json=payload)
    import json
    with open('error_detail.txt', 'w', encoding='utf-8') as f:
        json.dump(response.json(), f, indent=2)
    print("Error detail written to error_detail.txt")
except Exception as e:
    print(f"Error: {e}")
