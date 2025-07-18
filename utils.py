import firebase_admin
from firebase_admin import auth, credentials
import requests, json

cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred)

def make_user_admin(uid: str):
    try:
        user = auth.get_user(uid)
        current_claims = user.custom_claims if user.custom_claims else {}
        auth.set_custom_user_claims(uid, {**current_claims, 'admin': True})
        print(f"Successfully set user {uid} as admin.")
        print("User must re-authenticate (e.g., refresh their app) to get the updated ID token with admin claim.")
    except Exception as e:
        print(f"Error setting admin claims for user {uid}: {e}")

def post_request(url: str, id_token: str):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {id_token}"
    }
    response = requests.post(url, headers=headers)
    if response.ok:
        data = response.json()
        print("Success! Response from function:")
        print(json.dumps(data, indent=2))
    else:
        error_data = response.json()
        print(f"Error! Function returned status code: {response.status_code}")
        print("Error details:")
        print(json.dumps(error_data, indent=2))
