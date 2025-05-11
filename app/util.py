import os
import toml
from pathlib import Path

def create_secrets_toml():
    """環境変数からsecrets.tomlを生成"""

    secrets_data = {
        'auth': {
            'redirect_uri': os.getenv('REDIRECT_URI', 'http://localhost:8502/oauth2callback'),
            'cookie_secret': os.getenv('COOKIE_SECRET'),
            'auth0': {
                'client_id': os.getenv('CLIENT_ID'),
                'client_secret': os.getenv('CLIENT_SECRET'),
                'server_metadata_url': os.getenv('SERVER_METADATA_URL'),
                'client_kwargs': {
                    'prompt': os.getenv('CLIENT_KWARGS_PROMPT'),
                }
            }
        }
    }

    # .streamlit/secrets.tomlを作成
    streamlit_dir = Path.home() / '.streamlit'
    streamlit_dir.mkdir(exist_ok=True)

    with open(streamlit_dir / 'secrets.toml', 'w') as f:
        toml.dump(secrets_data, f)
