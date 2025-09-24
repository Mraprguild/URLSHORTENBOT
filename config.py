import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# URL Shortener Services API Keys
BITLY_TOKEN = os.getenv('BITLY_TOKEN', '')
TINYURL_API = os.getenv('TINYURL_API', '')
ISGD_API = os.getenv('ISGD_API', '')  # No API key needed but included for structure
CUTTLY_API = os.getenv('CUTTLY_API', '')

# Service Configuration
SUPPORTED_SERVICES = {
    'bitly': {
        'name': 'Bitly',
        'api_url': 'https://api-ssl.bitly.com/v4/shorten',
        'requires_key': True
    },
    'tinyurl': {
        'name': 'TinyURL',
        'api_url': 'http://tinyurl.com/api-create.php',
        'requires_key': False
    },
    'isgd': {
        'name': 'ISGD',
        'api_url': 'https://is.gd/create.php',
        'requires_key': False
    },
    'cuttly': {
        'name': 'Cuttly',
        'api_url': 'https://cutt.ly/api/api.php',
        'requires_key': True
    }
}
