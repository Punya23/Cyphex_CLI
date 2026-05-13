import requests

res = requests.post("http://localhost:8000/api/scan", json={"target_url": "http://localhost:56842/"})
print(res.status_code)
print(res.text)
