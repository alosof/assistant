import os
import sys
import time
import urllib.parse
from pathlib import Path

import httpx
import requests
from authlib.jose import jwt
from authlib.jose.rfc7517.jwk import JsonWebKey
from dotenv import load_dotenv
from langchain_core.tools import tool
from markdownify import markdownify

load_dotenv()

AUTH0_DOMAIN = os.environ["AUTH0_DOMAIN"]
AUTH0_DEVICE_CODE_CLIENT_ID = os.environ["AUTH0_DEVICE_CODE_CLIENT_ID"]
AUTH0_DOCTRINE_API_AUDIENCE = os.environ["AUTH0_DOCTRINE_API_AUDIENCE"]
DOCTRINE_HOST = os.environ["DOCTRINE_HOST"]

ACCESS_TOKEN_FILE = Path(__file__).parent.joinpath(".access_token")


def get_access_token() -> str:
    """Get a valid access token, reusing cached one if still valid."""
    if ACCESS_TOKEN_FILE.is_file():
        token_str = ACCESS_TOKEN_FILE.read_text()
        jwks_url = f"{AUTH0_DOMAIN}/.well-known/jwks.json"
        public_key = JsonWebKey.import_key_set(requests.get(jwks_url, timeout=10).json())
        claims = jwt.decode(token_str, public_key)
        if claims["exp"] > time.time():
            print("Using existing valid access token.")
            return token_str

    # Device auth flow
    print("Starting device auth flow...")
    resp = requests.post(
        f"{AUTH0_DOMAIN}/oauth/device/code",
        data={
            "client_id": AUTH0_DEVICE_CODE_CLIENT_ID,
            "scope": "openid profile get:ai_service_endpoints",
            "audience": AUTH0_DOCTRINE_API_AUDIENCE,
        },
        timeout=30,
    )
    resp.raise_for_status()
    device_data = resp.json()

    print(f"\nOpen this URL: {device_data['verification_uri_complete']}")
    print(f"Code: {device_data['user_code']}\n")

    while True:
        print("Waiting for authorization...")
        token_resp = requests.post(
            f"{AUTH0_DOMAIN}/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_data["device_code"],
                "client_id": AUTH0_DEVICE_CODE_CLIENT_ID,
            },
            timeout=30,
        )
        token_data = token_resp.json()
        if token_resp.status_code == 200:
            access_token = token_data["access_token"]
            ACCESS_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            ACCESS_TOKEN_FILE.write_text(access_token)
            print("Authenticated!")
            return access_token
        if token_data.get("error") not in ("authorization_pending", "slow_down"):
            print(f"Auth error: {token_data.get('error_description', token_data)}")
            sys.exit(1)
        time.sleep(device_data["interval"])


def _make_client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=f"https://{DOCTRINE_HOST}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )


def html_to_markdown(html: str) -> str:
    return markdownify(html, strip=["a", "img"])


@tool
def doctrine_search_tool(query: str) -> list[dict[str, str]]:
    """Search French court decisions on Doctrine.fr, the largest database of French case law.

    Use this tool to find jurisprudence relevant to a legal question.
    The query should be in French and describe the legal topic, concept, or situation you are researching.
    Returns up to 10 decisions with their metadata (title, date, jurisdiction) and full text content.
    """
    token = get_access_token()
    client = _make_client(token)

    parsed_query = urllib.parse.quote_plus(query)
    url = (
        f"/api/v2/search/retrieval?q={parsed_query}&type=arret&size=3"
        f"&chrono=false&sort_nbr_commentaire=false&chrono_inverted=false"
        f"&sort_alphanumeric=false&from=0&only_top_results=true&exclude_moyens=false"
    )

    response = client.get(url)
    response.raise_for_status()
    hits = response.json().get("hits", [])

    decisions = []
    for hit in hits:
        result_position = str(hit["position"])
        decision_id = hit["id"]
        decision_date = hit["date"]
        decision_title = hit["title"]
        jurisdiction = hit["court"]
        resp = client.get(f"/api/v2/decisions/{decision_id}/content")
        resp.raise_for_status()
        resp_dict = resp.json()
        decision_content = html_to_markdown(resp_dict["highlightedContent"])
        decision_dict = {
            "result_position": result_position,
            "decision_id": decision_id,
            "decision_title": decision_title,
            "decision_date": decision_date,
            "jurisdiction": jurisdiction,
            "content": decision_content,
        }
        decisions.append(decision_dict)
    return decisions
