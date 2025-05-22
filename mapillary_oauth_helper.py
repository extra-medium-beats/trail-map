import http.server
import socketserver
import threading
import webbrowser
import requests
import os

CLIENT_ID = "9573143482797266"
CLIENT_SECRET = "254ae8f48ba8fdc5743d0940195df7ac"
REDIRECT_URI = "http://localhost:3000/"
TOKEN_URL = "https://graph.mapillary.com/token"

auth_code = None

class OAuthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        if "/?code=" in self.path:
            auth_code = self.path.split("code=")[1].split("&")[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorization code received. You may close this window.")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid response.")

def run_local_server():
    handler = OAuthHandler
    with socketserver.TCPServer(("", 3000), handler) as httpd:
        httpd.handle_request()

def open_browser_for_auth():
    auth_url = (
        f"https://www.mapillary.com/connect?client_id={CLIENT_ID}"
        f"&response_type=code&redirect_uri={REDIRECT_URI}"
    )
    webbrowser.open(auth_url)

def exchange_code_for_token(code):
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    print("Exchanging with data:", data)
    response = requests.post(TOKEN_URL, data=data)
    print("Status code:", response.status_code)
    print("Response text:", response.text)
    return response.json()

if __name__ == "__main__":
    print("Opening browser for Mapillary OAuth...")
    threading.Thread(target=run_local_server, daemon=True).start()
    open_browser_for_auth()

    print("Waiting for OAuth code from browser...")
    while auth_code is None:
        pass

    print("Exchanging code for token...")
    token_response = exchange_code_for_token(auth_code)
    print("Response:")
    print(token_response)

    if "access_token" in token_response:
        with open(".env", "a") as env_file:
            env_file.write(f"\nMAPILLARY_CLIENT_TOKEN={token_response['access_token']}\n")
        print("\n✅ Token saved to .env file as MAPILLARY_CLIENT_TOKEN")
    else:
        print("❌ Failed to retrieve access token.")