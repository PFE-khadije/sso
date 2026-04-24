#!/usr/bin/env python3
"""
Automated API test suite for the Identity Platform.
Run with: python test_api.py
"""

import requests
import json
import sys
import pyotp
import random
from typing import Dict, Any

# Configuration
BASE_URL = "https://sso-backend-6b1e.onrender.com"  

# Generate a unique test user
TEST_USER = {
    "email": f"test_{random.randint(1, 999999)}@example.com",
    "phone": f"+2224334{random.randint(1000, 9999)}",
    "first_name": "cheikh",
    "last_name": "User",
    "password": "StrongPass123!",
    "password2": "StrongPass123!"
}

class APITester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
        self.client_id = None
        self.client_secret = None
        self.mfa_token = None
        self.totp_secret = None

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop('headers', {})
        if self.access_token and 'Authorization' not in headers:
            headers['Authorization'] = f"Bearer {self.access_token}"
        kwargs['headers'] = headers
        response = requests.request(method, url, **kwargs)
        self.log_response(method, path, response)
        return response

    def log_response(self, method: str, path: str, resp: requests.Response):
        print(f"\n{method} {path} -> {resp.status_code}")
        try:
            print(f"Response: {json.dumps(resp.json(), indent=2)[:500]}")
        except:
            print(f"Response: {resp.text[:200]}")

    def assert_status(self, resp: requests.Response, expected: int, msg: str = ""):
        if resp.status_code != expected:
            print(f"❌ FAIL: {msg} - Expected {expected}, got {resp.status_code}")
            sys.exit(1)
        else:
            print(f"✅ PASS: {msg}")

    # ------------------- Public endpoints -------------------
    def test_signup(self):
        print("\n--- Testing Signup ---")
        resp = self.request('POST', '/api/signup/', json=TEST_USER)
        if resp.status_code == 201:
            data = resp.json()
            self.access_token = data.get('access')
            self.refresh_token = data.get('refresh')
            self.assert_status(resp, 201, "Signup")
            return True
        else:
            # Try login if user exists
            login_resp = self.request('POST', '/api/login/', json={'identifier': TEST_USER['phone'], 'password': TEST_USER['password']})
            if login_resp.status_code == 200:
                data = login_resp.json()
                if 'mfa_required' in data:
                    self.mfa_token = data['mfa_token']
                else:
                    self.access_token = data['access']
                    self.refresh_token = data['refresh']
                print("Logged in with existing user")
                return True
            return False

    def test_login(self):
        print("\n--- Testing Login ---")
        resp = self.request('POST', '/api/login/', json={'identifier': TEST_USER['email'], 'password': TEST_USER['password']})
        if resp.status_code == 200:
            data = resp.json()
            if 'mfa_required' in data:
                self.mfa_token = data.get('mfa_token')
                print("MFA required, will test MFA later")
            else:
                self.access_token = data.get('access')
                self.refresh_token = data.get('refresh')
        self.assert_status(resp, 200, "Login")

    def test_user_me(self):
        print("\n--- Testing User Profile ---")
        resp = self.request('GET', '/api/user/me/')
        self.assert_status(resp, 200, "Get user profile")

    def test_user_apps(self):
        print("\n--- Testing Authorized Apps ---")
        resp = self.request('GET', '/api/user/apps/')
        self.assert_status(resp, 200, "List apps")

    def test_user_devices(self):
        print("\n--- Testing Trusted Devices ---")
        resp = self.request('GET', '/api/user/devices/')
        self.assert_status(resp, 200, "List devices")

    def test_user_activity(self):
        print("\n--- Testing User Activity ---")
        resp = self.request('GET', '/api/user/activity/')
        self.assert_status(resp, 200, "Get activity")

    

    # ------------------- Biometric -------------------
    def test_biometric_status(self):
        print("\n--- Testing Biometric Status ---")
        resp = self.request('GET', '/api/biometric/status/')
        self.assert_status(resp, 200, "Get biometric status")

    # ------------------- Client creation -------------------
    def test_create_client(self):
        print("\n--- Testing Create Client ---")
        plan_resp = self.request('GET', '/api/plans/')
        if plan_resp.status_code != 200:
            print("Cannot fetch plans, skipping client creation")
            return None
        plans = plan_resp.json()
        if not plans:
            print("No plans available, cannot create client")
            return None
        plan_id = plans[0]['id']
        client_data = {
            'name': f"Test Client {random.randint(1, 9999)}",
            'slug': f"test-client-{random.randint(1, 9999)}",
            'plan': plan_id,
            'primary_color': '#3366FF'
        }
        resp = self.request('POST', '/api/clients/', json=client_data)
        if resp.status_code == 201:
            client = resp.json()
            self.client_id = client['id']
            print(f"Created client ID: {self.client_id}")
        self.assert_status(resp, 201, "Create client")
        return self.client_id

    def test_list_clients(self):
        print("\n--- Testing List Clients ---")
        resp = self.request('GET', '/api/clients/')
        self.assert_status(resp, 200, "List clients")
        return resp.json()

    def test_client_stats(self, client_id):
        print("\n--- Testing Client Stats ---")
        resp = self.request('GET', f'/api/clients/{client_id}/stats/')
        self.assert_status(resp, 200, "Get client stats")

    def test_create_oauth_application(self, client_id):
        print("\n--- Testing Create OAuth Application ---")
        app_data = {
            'name': f"Test App {random.randint(1, 9999)}",
            'redirect_uris': 'https://oauth.pstmn.io/v1/callback',
            'client_type': 'confidential',
            'grant_type': 'authorization-code'
        }
        resp = self.request('POST', f'/api/clients/{client_id}/apps/', json=app_data)
        if resp.status_code == 201:
            data = resp.json()
            self.client_id_oauth = data.get('client_id')
            self.client_secret = data.get('client_secret')
            print(f"OAuth app created: client_id={self.client_id_oauth}")
        self.assert_status(resp, 201, "Create OAuth app")

    def test_client_team(self, client_id):
        print("\n--- Testing Client Team ---")
        resp = self.request('GET', f'/api/clients/{client_id}/team/')
        self.assert_status(resp, 200, "Get client team")

    # ------------------- Logout -------------------
    def test_logout(self):
        if not self.refresh_token:
            print("No refresh token, skip logout")
            return
        print("\n--- Testing Logout ---")
        resp = self.request('POST', '/api/logout/', json={'refresh': self.refresh_token})
        self.assert_status(resp, 205, "Logout")

    # ------------------- Full flow -------------------
    def run_all(self):
        self.test_signup()
        self.test_login()
        self.test_user_me()
        self.test_user_apps()
        self.test_user_devices()
        self.test_user_activity()
        self.test_biometric_status()
        clients = self.test_list_clients()
        if not clients:
            # Create a client if none exist
            client_id = self.test_create_client()
            if client_id:
                self.test_client_stats(client_id)
                self.test_create_oauth_application(client_id)
                self.test_client_team(client_id)
        else:
            # Use first client
            client_id = clients[0]['id']
            self.test_client_stats(client_id)
            self.test_create_oauth_application(client_id)
            self.test_client_team(client_id)
        
        self.test_logout()
        print("\n✅ All tests completed.")

if __name__ == "__main__":
    tester = APITester(BASE_URL)
    tester.run_all()