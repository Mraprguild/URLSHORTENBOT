import os

# Bot Token from BotFather
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# API Keys for various services
BITLY_TOKEN = os.getenv('BITLY_TOKEN', '')
CUTTLY_API = os.getenv('CUTTLY_API', '')
GPLINKS_API = os.getenv('GPLINKS_API', '')

# Welcome image URL
WELCOME_IMAGE_URL = "https://ibb.co/BKygJJNw"

# Server port for Render
PORT = int(os.environ.get('PORT', 5000))

# Supported URL shortening services
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
        'api_url': 'https://gplinks.in/api',
        'requires_key': True
    }
}
