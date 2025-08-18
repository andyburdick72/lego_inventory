import requests

from app.settings import get_settings

settings = get_settings()
api_key = settings.rebrickable_api_key
user_token = settings.rebrickable_user_token
username = settings.rebrickable_username
password = settings.rebrickable_password

payload = {"username": username, "password": password}
headers = {"Authorization": f"key {api_key}"}
r = requests.post("https://rebrickable.com/api/v3/users/_token/", data=payload, headers=headers)
print(r.status_code, r.text)
