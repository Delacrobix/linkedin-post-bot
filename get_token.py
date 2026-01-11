#!/usr/bin/env python3
"""
LinkedIn OAuth Token Generator
Run this locally to get your access token.
"""

import http.server
import os
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv

load_dotenv()

# load from .env or set directly here

REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = ["openid", "profile", "w_member_social"]
CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")

print(f"Using CLIENT_ID: {CLIENT_ID}")
print(f"Using CLIENT_SECRET: {CLIENT_SECRET}")


class OAuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/callback"):
            # Parse the authorization code
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)

            if "code" in params:
                code = params["code"][0]
                print(f"\nAuthorization code received!")

                # Exchange code for token
                token = exchange_code_for_token(code)

                if token:
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"<h1>Success!</h1><p>You can close this window. Check your terminal for the access token.</p>"
                    )
                else:
                    self.send_response(500)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<h1>Error</h1><p>Failed to get token.</p>")
            else:
                error = params.get("error", ["Unknown error"])[0]
                print(f"\nError: {error}")
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Error</h1><p>{error}</p>".encode())

    def log_message(self, format, *args):
        pass  # Suppress logging


def exchange_code_for_token(code: str) -> str | None:
    """Exchange authorization code for access token."""
    response = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if response.status_code == 200:
        data = response.json()
        access_token = data["access_token"]
        expires_in = data.get("expires_in", 0)

        print("\n" + "=" * 50)
        print("ACCESS TOKEN (save this!):")
        print("=" * 50)
        print(access_token)
        print("=" * 50)
        print(f"Expires in: {expires_in // 86400} days")
        print("\nAdd this to your GitHub secrets as LINKEDIN_ACCESS_TOKEN")

        return access_token
    else:
        print(f"Error getting token: {response.text}")
        return None


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: LINKEDIN_CLIENT_ID or LINKEDIN_CLIENT_SECRET not set")
        return

    # Build authorization URL
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "scope": " ".join(SCOPES),
            }
        )
    )

    print("Opening browser for LinkedIn authorization...")
    print(f"\nIf browser doesn't open, visit:\n{auth_url}\n")

    # Open browser
    webbrowser.open(auth_url)

    # Start local server to receive callback
    print("Waiting for authorization callback on http://localhost:8000 ...")
    server = http.server.HTTPServer(("localhost", 8000), OAuthHandler)
    server.handle_request()  # Handle one request then stop


if __name__ == "__main__":
    main()
