import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# URL Shortener Services API Keys
BITLY_TOKEN = os.getenv('BITLY_TOKEN', '')
TINYURL_API = os.getenv('TINYURL_API', '')  # Actually no API key needed, but kept for structure
CUTTLY_API = os.getenv('CUTTLY_API', '')
GPLINKS_API = os.getenv('GPLINKS_API', '')

# Optional: Welcome image URL
WELCOME_IMAGE_URL = ('https://ibb.co/BKygJJNw')

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
    'cuttly': {
        'name': 'Cuttly',
        'api_url': 'https://cutt.ly/api/api.php',
        'requires_key': True
    },
    'gplinks': {
        'name': 'GPLinks',
        'api_url': 'https://gplinks.com/api',
        'requires_key': True,
        'method': 'POST'
    }
}
