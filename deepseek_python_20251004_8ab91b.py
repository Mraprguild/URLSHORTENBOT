import os
import logging
import requests
import re
import hashlib
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration from environment variables (for Render)
class Config:
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    BITLY_TOKEN = os.environ.get('BITLY_TOKEN', '')
    CUTTLY_API = os.environ.get('CUTTLY_API', '')
    GPLINKS_API = os.environ.get('GPLINKS_API', '')
    USE_WEBHOOK = os.environ.get('USE_WEBHOOK', 'true').lower() == 'true'
    WEBHOOK_PORT = int(os.environ.get('PORT', 5000))
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')
    WELCOME_IMAGE_URL = os.environ.get('WELCOME_IMAGE_URL', 'https://iili.io/Kcbrql9.th.jpg')
    
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

config = Config()

# Create Flask app for web server
app = Flask(__name__)

class BotStatus:
    def __init__(self):
        self.start_time = datetime.now()
        self.total_requests = 0
        self.successful_shortens = 0
        self.failed_shortens = 0
        self.api_status = {}
        self.last_health_check = None
        
    def increment_requests(self):
        self.total_requests += 1
        
    def increment_successful_shortens(self):
        self.successful_shortens += 1
        
    def increment_failed_shortens(self):
        self.failed_shortens += 1
        
    def update_api_status(self, service, status, response_time=None):
        self.api_status[service] = {
            'status': status,
            'last_checked': datetime.now().isoformat(),
            'response_time': response_time
        }
        
    def get_uptime(self):
        return datetime.now() - self.start_time
    
    def get_stats(self):
        return {
            'start_time': self.start_time.isoformat(),
            'uptime': str(self.get_uptime()),
            'total_requests': self.total_requests,
            'successful_shortens': self.successful_shortens,
            'failed_shortens': self.failed_shortens,
            'success_rate': (self.successful_shortens / self.total_requests * 100) if self.total_requests > 0 else 0,
            'api_status': self.api_status,
            'last_health_check': self.last_health_check
        }

# Global bot status instance
bot_status = BotStatus()

class URLShortenerBot:
    def __init__(self, token):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.url_cache = {}  # Cache for URL storage
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("shorten", self.shorten))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(CommandHandler("stats", self.bot_stats))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
    
    def is_valid_url(self, url: str) -> bool:
        """Enhanced URL validation"""
        pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return re.match(pattern, url) is not None
    
    def generate_url_id(self, url: str) -> str:
        """Generate a short unique ID for the URL to avoid long callback data"""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return url_hash
    
    def store_url(self, url: str) -> str:
        """Store URL in cache and return short ID"""
        url_id = self.generate_url_id(url)
        self.url_cache[url_id] = url
        return url_id
    
    def get_url(self, url_id: str) -> str:
        """Retrieve URL from cache using short ID"""
        return self.url_cache.get(url_id, '')
    
    async def error_handler(self, update: Update, context: CallbackContext):
        """Handle errors in the telegram bot"""
        logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text("❌ An error occurred. Please try again.")
        except Exception as e:
            logger.error(f"Error while sending error message: {e}")

    def is_image_accessible(self, url: str) -> bool:
        """Check if the welcome image URL is accessible"""
        try:
            response = requests.head(url, timeout=10)
            return response.status_code == 200
        except:
            return False

    def check_api_health(self, service: str) -> dict:
        """Check if API service is healthy and responsive"""
        try:
            start_time = time.time()
            
            if service == 'bitly':
                if not config.BITLY_TOKEN:
                    return {'status': 'error', 'message': 'API key not configured'}
                
                headers = {
                    'Authorization': f'Bearer {config.BITLY_TOKEN}',
                    'Content-Type': 'application/json'
                }
                response = requests.get(
                    'https://api-ssl.bitly.com/v4/user',
                    headers=headers,
                    timeout=10
                )
                status = 'connected' if response.status_code == 200 else 'error'
                
            elif service == 'tinyurl':
                # TinyURL doesn't require API key, test with a simple request
                response = requests.get(
                    'http://tinyurl.com/api-create.php?url=https://www.google.com',
                    timeout=10
                )
                status = 'connected' if response.status_code == 200 else 'error'
                
            elif service == 'cuttly':
                if not config.CUTTLY_API:
                    return {'status': 'error', 'message': 'API key not configured'}
                
                params = {'key': config.CUTTLY_API, 'short': 'https://www.google.com'}
                response = requests.get(
                    config.SUPPORTED_SERVICES[service]['api_url'],
                    params=params,
                    timeout=10
                )
                status = 'connected' if response.status_code == 200 else 'error'
                
            elif service == 'gplinks':
                if not config.GPLINKS_API:
                    return {'status': 'error', 'message': 'API key not configured'}
                
                params = {'api': config.GPLINKS_API, 'url': 'https://www.google.com'}
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                }
                response = requests.get(
                    config.SUPPORTED_SERVICES[service]['api_url'],
                    params=params,
                    headers=headers,
                    timeout=15
                )
                status = 'connected' if response.status_code == 200 else 'error'
            
            response_time = round((time.time() - start_time) * 1000, 2)  # Convert to ms
            bot_status.update_api_status(service, status, response_time)
            
            return {
                'status': status,
                'response_time_ms': response_time,
                'service': service
            }
            
        except requests.exceptions.Timeout:
            bot_status.update_api_status(service, 'timeout')
            return {'status': 'timeout', 'service': service}
        except Exception as e:
            bot_status.update_api_status(service, 'error')
            return {'status': 'error', 'message': str(e), 'service': service}

    def shorten_url(self, url, service):
        """Shorten URL using the specified service"""
        try:
            bot_status.increment_requests()
            
            # Validate URL first
            if not self.is_valid_url(url):
                bot_status.increment_failed_shortens()
                return None

            logger.info(f"Shortening URL with {service}: {url}")

            if service == 'bitly':
                if not config.BITLY_TOKEN:
                    logger.error("Bitly token not configured")
                    bot_status.increment_failed_shortens()
                    return None
                
                headers = {
                    'Authorization': f'Bearer {config.BITLY_TOKEN}',
                    'Content-Type': 'application/json'
                }
                data = {'long_url': url}
                response = requests.post(
                    config.SUPPORTED_SERVICES[service]['api_url'], 
                    headers=headers, 
                    json=data, 
                    timeout=10
                )
                if response.status_code == 200:
                    bot_status.increment_successful_shortens()
                    return response.json()['link']
                else:
                    logger.error(f"Bitly API error: {response.status_code} - {response.text}")
                    bot_status.increment_failed_shortens()
                    return None
            
            elif service == 'tinyurl':
                params = {'url': url}
                response = requests.get(
                    config.SUPPORTED_SERVICES[service]['api_url'], 
                    params=params, 
                    timeout=10
                )
                if response.status_code == 200:
                    bot_status.increment_successful_shortens()
                    return response.text.strip()
                else:
                    logger.error(f"TinyURL API error: {response.status_code}")
                    bot_status.increment_failed_shortens()
                    return None
            
            elif service == 'cuttly':
                if not config.CUTTLY_API:
                    logger.error("Cuttly API key not configured")
                    bot_status.increment_failed_shortens()
                    return None
                
                params = {'key': config.CUTTLY_API, 'short': url}
                response = requests.get(
                    config.SUPPORTED_SERVICES[service]['api_url'], 
                    params=params, 
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get('url', {}).get('status') == 7:
                        bot_status.increment_successful_shortens()
                        return data['url']['shortLink']
                    else:
                        logger.error(f"Cuttly API error: {data}")
                        bot_status.increment_failed_shortens()
                        return None
                else:
                    logger.error(f"Cuttly HTTP error: {response.status_code}")
                    bot_status.increment_failed_shortens()
                    return None
            
            elif service == 'gplinks':
                if not config.GPLINKS_API:
                    logger.error("GPLinks API key not configured")
                    bot_status.increment_failed_shortens()
                    return None
                
                api_url = "https://gplinks.in/api"
                params = {'api': config.GPLINKS_API, 'url': url}
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                }
                
                # Try GET request first
                response = requests.get(api_url, params=params, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    response_text = response.text.strip()
                    
                    if response_text.startswith('http'):
                        bot_status.increment_successful_shortens()
                        return response_text
                    
                    try:
                        json_data = response.json()
                        if json_data.get('status') == 'success':
                            bot_status.increment_successful_shortens()
                            return json_data.get('shortenedUrl') or json_data.get('shorturl')
                        elif 'shortenedUrl' in json_data:
                            bot_status.increment_successful_shortens()
                            return json_data['shortenedUrl']
                    except ValueError:
                        if 'http' in response_text:
                            urls = re.findall(r'https?://[^\s]+', response_text)
                            if urls:
                                bot_status.increment_successful_shortens()
                                return urls[0]
                
                # If GET failed, try POST request
                payload = {'api': config.GPLINKS_API, 'url': url}
                response = requests.post(api_url, data=payload, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    response_text = response.text.strip()
                    
                    if response_text.startswith('http'):
                        bot_status.increment_successful_shortens()
                        return response_text
                    
                    try:
                        json_data = response.json()
                        if json_data.get('status') == 'success':
                            bot_status.increment_successful_shortens()
                            return json_data.get('shortenedUrl') or json_data.get('shorturl')
                    except ValueError:
                        if 'http' in response_text:
                            urls = re.findall(r'https?://[^\s]+', response_text)
                            if urls:
                                bot_status.increment_successful_shortens()
                                return urls[0]
                
                logger.error(f"GPLinks API failed. Status: {response.status_code}")
                bot_status.increment_failed_shortens()
                return None
            
            bot_status.increment_failed_shortens()
            return None
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while shortening URL with {service}")
            bot_status.increment_failed_shortens()
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error with {service}: {e}")
            bot_status.increment_failed_shortens()
            return None
        except Exception as e:
            logger.error(f"Error shortening URL with {service}: {str(e)}")
            bot_status.increment_failed_shortens()
            return None
    
    async def start(self, update: Update, context: CallbackContext):
        """Send welcome message when command /start is issued"""
        try:
            user = update.effective_user
            
            welcome_text = f"""
👋 Hello {user.mention_html()}!

**Welcome to URL Shortener Bot!** 🌐

I can shorten your long URLs using various services and help you earn money with shortened links!

✨ **Features:**
• Multiple URL shortening services
• Easy-to-use interface
• Monetization options with GPLinks
• Fast and reliable service

📋 **Available Commands:**
/start - Start the bot
/help - Show help message  
/shorten - Shorten a URL
/status - Check API key status
/stats - Show bot statistics

🚀 **Get Started:**
Simply send me a URL or use /shorten command to begin!
            """
            
            # Try to send with image if available and accessible
            image_sent = False
            if config.WELCOME_IMAGE_URL and self.is_image_accessible(config.WELCOME_IMAGE_URL):
                try:
                    await update.message.reply_photo(
                        photo=config.WELCOME_IMAGE_URL,
                        caption=welcome_text,
                        parse_mode='HTML'
                    )
                    image_sent = True
                    logger.info("Welcome image sent successfully")
                except Exception as photo_error:
                    logger.warning(f"Could not send welcome image: {photo_error}")
                    image_sent = False
            
            # If image failed or not available, send text only
            if not image_sent:
                await update.message.reply_html(welcome_text)
                logger.info("Welcome message sent as text (image not available)")
                
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    
    async def help(self, update: Update, context: CallbackContext):
        """Send help message"""
        try:
            help_text = """
🤖 **URL Shortener Bot Help Guide**

📖 **How to use:**
1. Send me any long URL directly
2. Or use `/shorten <URL>` command
3. Choose your preferred shortening service
4. Get your shortened link instantly!

🔗 **Example:**
`/shorten https://www.example.com/very-long-url-path`

🛠 **Supported Services:**
✅ **Bitly** - Professional URL shortening with analytics
✅ **TinyURL** - Simple, reliable, no API key required  
✅ **Cuttly** - Advanced analytics and customization
✅ **GPLinks** - Earn money from your shortened links!

💰 **Monetization:**
With GPLinks, you can earn revenue from every click!
Sign up at https://gplinks.in for your API key.

🔧 **Need Help?**
Use `/status` to check your API key configuration.
Use `/stats` to view bot statistics.
            """
            await update.message.reply_text(help_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in help command: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    
    async def status(self, update: Update, context: CallbackContext):
        """Check API key status"""
        try:
            status_text = "🔧 **API Key Status**\n\n"
            
            for service_key, service_info in config.SUPPORTED_SERVICES.items():
                service_name = service_info['name']
                requires_key = service_info['requires_key']
                
                if service_key == 'bitly':
                    has_key = bool(config.BITLY_TOKEN)
                    key_preview = config.BITLY_TOKEN[:8] + '...' if has_key else 'Not set'
                elif service_key == 'cuttly':
                    has_key = bool(config.CUTTLY_API)
                    key_preview = config.CUTTLY_API[:8] + '...' if has_key else 'Not set'
                elif service_key == 'gplinks':
                    has_key = bool(config.GPLINKS_API)
                    key_preview = config.GPLINKS_API[:8] + '...' if has_key else 'Not set'
                else:
                    has_key = True
                    key_preview = "Not required"
                
                status_text += f"**{service_name}**: "
                if requires_key:
                    status_text += "✅" if has_key else "❌"
                else:
                    status_text += "✅"
                status_text += f" ({key_preview})\n"
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text("❌ Error checking status")
    
    async def bot_stats(self, update: Update, context: CallbackContext):
        """Show bot statistics"""
        try:
            stats = bot_status.get_stats()
            
            # Format uptime
            uptime = stats['uptime']
            days = bot_status.get_uptime().days
            hours, remainder = divmod(bot_status.get_uptime().seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            stats_text = f"""
📊 **Bot Statistics**

⏰ **Uptime:** {days}d {hours}h {minutes}m {seconds}s
📈 **Total Requests:** {stats['total_requests']}
✅ **Successful Shortens:** {stats['successful_shortens']}
❌ **Failed Shortens:** {stats['failed_shortens']}
📊 **Success Rate:** {stats['success_rate']:.1f}%

🔧 **API Status:**
"""
            
            # Check API status for each service
            for service_key in config.SUPPORTED_SERVICES:
                health = self.check_api_health(service_key)
                service_name = config.SUPPORTED_SERVICES[service_key]['name']
                
                if health['status'] == 'connected':
                    stats_text += f"✅ **{service_name}**: Connected"
                    if 'response_time_ms' in health:
                        stats_text += f" ({health['response_time_ms']}ms)"
                    stats_text += "\n"
                else:
                    stats_text += f"❌ **{service_name}**: {health.get('message', 'Not connected')}\n"
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text("❌ Error retrieving statistics")
    
    async def shorten(self, update: Update, context: CallbackContext):
        """Shorten URL from command"""
        try:
            if not context.args:
                await update.message.reply_text("Please provide a URL to shorten. Usage: `/shorten <URL>`", parse_mode='Markdown')
                return
            
            url = ' '.join(context.args)
            await self.process_url(update, url)
        except Exception as e:
            logger.error(f"Error in shorten command: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    
    async def handle_message(self, update: Update, context: CallbackContext):
        """Handle messages containing URLs"""
        try:
            url = update.message.text.strip()
            
            if not (url.startswith('http://') or url.startswith('https://')):
                await update.message.reply_text("Please send a valid URL starting with http:// or https://")
                return
            
            await self.process_url(update, url)
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    
    async def process_url(self, update: Update, url: str):
        """Process URL and generate shortened versions"""
        try:
            # Validate URL
            if not self.is_valid_url(url):
                await update.message.reply_text("❌ Please provide a valid URL starting with http:// or https://")
                return
            
            # Show typing action
            await update.message.reply_chat_action(action="typing")
            
            # Store URL and get short ID
            url_id = self.store_url(url)
            
            # Create keyboard with service options
            keyboard = [
                [
                    InlineKeyboardButton("🌐 Bitly", callback_data=f"s_bitly_{url_id}"),
                    InlineKeyboardButton("🔗 TinyURL", callback_data=f"s_tiny_{url_id}"),
                ],
                [
                    InlineKeyboardButton("📊 Cuttly", callback_data=f"s_cutt_{url_id}"),
                    InlineKeyboardButton("💰 GPLinks", callback_data=f"s_gpl_{url_id}"),
                ],
                [InlineKeyboardButton("🚀 All Services", callback_data=f"s_all_{url_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Truncate long URLs for display
            display_url = url
            if len(url) > 50:
                display_url = url[:47] + "..."
            
            await update.message.reply_text(
                f"🔗 **Original URL:**\n`{display_url}`\n\n**Choose a service to shorten:**",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error processing URL: {e}")
            await update.message.reply_text("❌ An error occurred while processing your URL. Please try again.")
    
    async def button_handler(self, update: Update, context: CallbackContext):
        """Handle button callbacks"""
        try:
            query = update.callback_query
            await query.answer()
            
            data = query.data
            logger.info(f"Callback data received: {data}")
            
            if data.startswith('s_'):
                parts = data.split('_', 2)
                if len(parts) == 3:
                    _, service_code, url_id = parts
                    
                    # Map short service codes to full service names
                    service_map = {
                        'bitly': 'bitly',
                        'tiny': 'tinyurl', 
                        'cutt': 'cuttly',
                        'gpl': 'gplinks',
                        'all': 'all'
                    }
                    
                    service = service_map.get(service_code, service_code)
                    url = self.get_url(url_id)
                    
                    if not url:
                        await query.edit_message_text("❌ URL not found. Please try again.")
                        return
                    
                    # Show typing action
                    await query.message.reply_chat_action(action="typing")
                    
                    if service == 'all':
                        await self.send_all_shortened_urls(query, url)
                    else:
                        await self.send_single_shortened_url(query, url, service)
                else:
                    await query.edit_message_text("❌ Invalid request. Please try again.")
            else:
                await query.edit_message_text("❌ Unknown command. Please try again.")
                
        except Exception as e:
            logger.error(f"Error in button handler: {e}")
            try:
                await query.edit_message_text("❌ An error occurred. Please try again.")
            except:
                await query.message.reply_text("❌ An error occurred. Please try again.")
    
    async def send_single_shortened_url(self, query, url: str, service: str):
        """Send shortened URL from a single service"""
        try:
            service_info = config.SUPPORTED_SERVICES.get(service, {})
            service_name = service_info.get('name', service.capitalize())
            
            shortened_url = self.shorten_url(url, service)
            
            if shortened_url:
                message = f"✅ **{service_name}**\n🔗 `{shortened_url}`"
                
                if service == 'gplinks':
                    message += "\n\n💰 *Earn money with this shortened link!*"
                
                await query.edit_message_text(
                    text=message,
                    disable_web_page_preview=True,
                    parse_mode='Markdown'
                )
            else:
                error_msg = f"❌ Failed to shorten URL using {service_name}."
                
                if service == 'gplinks':
                    if not config.GPLINKS_API:
                        error_msg += "\n🔑 GPLinks API key not configured."
                    else:
                        error_msg += "\n🔧 Service might be unavailable."
                elif service_info.get('requires_key', True):
                    error_msg += " API key might not be configured."
                else:
                    error_msg += " Service might be temporarily unavailable."
                
                await query.edit_message_text(text=error_msg)
        except Exception as e:
            logger.error(f"Error sending single shortened URL: {e}")
            await query.edit_message_text("❌ Error generating shortened URL. Please try again.")
    
    async def send_all_shortened_urls(self, query, url: str):
        """Send shortened URLs from all available services"""
        try:
            message = "🔗 **Shortened URLs**\n\n"
            successful_shortens = 0
            
            for service_key, service_info in config.SUPPORTED_SERVICES.items():
                service_name = service_info.get('name', service_key.capitalize())
                shortened_url = self.shorten_url(url, service_key)
                
                if shortened_url:
                    message += f"✅ **{service_name}**\n`{shortened_url}`"
                    if service_key == 'gplinks':
                        message += " 💰"
                    message += "\n\n"
                    successful_shortens += 1
                else:
                    message += f"❌ **{service_name}** - Failed\n\n"
            
            if successful_shortens == 0:
                message = "❌ All services failed. Please try again later."
            else:
                message += f"✅ **{successful_shortens}/{len(config.SUPPORTED_SERVICES)} successful**"
            
            await query.edit_message_text(
                text=message,
                disable_web_page_preview=True,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error sending all shortened URLs: {e}")
            await query.edit_message_text("❌ Error generating shortened URLs. Please try again.")
    
    def run_webhook(self):
        """Start the bot with webhook (Render-compatible)"""
        try:
            logger.info(f"Starting URL Shortener Bot with webhook on port {config.WEBHOOK_PORT}...")
            
            # Set webhook explicitly first
            if config.WEBHOOK_URL:
                webhook_url = f"{config.WEBHOOK_URL}/{self.token}"
                logger.info(f"Setting webhook to: {webhook_url}")
                
                # Set the webhook
                self.application.bot.set_webhook(
                    url=webhook_url,
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True
                )
                
                # Run the webhook server
                self.application.run_webhook(
                    listen="0.0.0.0",
                    port=config.WEBHOOK_PORT,
                    webhook_url=webhook_url,
                    url_path=self.token
                )
            else:
                # Fallback for Render without explicit WEBHOOK_URL
                logger.info("Using Render's default webhook configuration")
                self.application.run_webhook(
                    listen="0.0.0.0",
                    port=config.WEBHOOK_PORT,
                    url_path=self.token,
                    webhook_url=None  # Let python-telegram-bot handle it
                )
                
        except Exception as e:
            logger.error(f"Error starting webhook: {e}")
            raise

    def run_polling(self):
        """Alternative polling method for development"""
        logger.info("Starting bot with polling...")
        self.application.run_polling()

# Flask Routes for Web Server
@app.route('/')
def home():
    """Home page with bot status"""
    stats = bot_status.get_stats()
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>URL Shortener Bot Status</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .status {{ padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .online {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
            .offline {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
            .stats {{ background: #e2e3e5; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
            .api-status {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 URL Shortener Bot Status</h1>
            
            <div class="status online">
                <h2>🟢 Bot Status: ONLINE</h2>
                <p><strong>Uptime:</strong> {stats['uptime']}</p>
                <p><strong>Started:</strong> {stats['start_time']}</p>
            </div>
            
            <div class="stats">
                <h3>📊 Statistics</h3>
                <p><strong>Total Requests:</strong> {stats['total_requests']}</p>
                <p><strong>Successful Shortens:</strong> {stats['successful_shortens']}</p>
                <p><strong>Failed Shortens:</strong> {stats['failed_shortens']}</p>
                <p><strong>Success Rate:</strong> {stats['success_rate']:.1f}%</p>
            </div>
            
            <h3>🔧 API Services Status</h3>
            <div class="api-status">
    """
    
    # Add API status for each service
    for service_key, service_info in config.SUPPORTED_SERVICES.items():
        health = bot.check_api_health(service_key)
        service_name = service_info['name']
        
        if health['status'] == 'connected':
            html += f"""
                <div class="status online">
                    <strong>{service_name}</strong><br>
                    ✅ Connected<br>
                    Response: {health.get('response_time_ms', 'N/A')}ms
                </div>
            """
        else:
            html += f"""
                <div class="status offline">
                    <strong>{service_name}</strong><br>
                    ❌ {health.get('message', 'Not connected')}
                </div>
            """
    
    html += """
            </div>
            
            <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border-radius: 5px;">
                <h3>🔗 API Endpoints</h3>
                <ul>
                    <li><a href="/api/status">/api/status</a> - Bot status JSON</li>
                    <li><a href="/api/health">/api/health</a> - Health check</li>
                    <li><a href="/api/stats">/api/stats</a> - Detailed statistics</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

@app.route('/api/status')
def api_status():
    """API endpoint for bot status"""
    stats = bot_status.get_stats()
    return jsonify({
        'status': 'online',
        'bot_uptime': stats['uptime'],
        'start_time': stats['start_time'],
        'services': {
            service: bot.check_api_health(service) 
            for service in config.SUPPORTED_SERVICES.keys()
        },
        'requests': {
            'total': stats['total_requests'],
            'successful': stats['successful_shortens'],
            'failed': stats['failed_shortens'],
            'success_rate': stats['success_rate']
        }
    })

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'bot_running': True,
        'services_configured': len([s for s in config.SUPPORTED_SERVICES if not config.SUPPORTED_SERVICES[s]['requires_key'] or (
            (s == 'bitly' and config.BITLY_TOKEN) or
            (s == 'cuttly' and config.CUTTLY_API) or
            (s == 'gplinks' and config.GPLINKS_API)
        )])
    })

@app.route('/api/stats')
def api_stats():
    """Detailed statistics endpoint"""
    stats = bot_status.get_stats()
    return jsonify(stats)

def start_web_server():
    """Start Flask web server in a separate thread"""
    def run_flask():
        app.run(host='0.0.0.0', port=config.WEBHOOK_PORT, debug=False, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask web server started on port {config.WEBHOOK_PORT}")

# Global bot instance
bot = None

def main():
    """Main function to run the bot"""
    global bot
    
    try:
        if not config.BOT_TOKEN:
            print("❌ Error: Please set BOT_TOKEN environment variable")
            return
        
        print("🤖 URL Shortener Bot Starting...")
        
        # Initialize bot
        bot = URLShortenerBot(config.BOT_TOKEN)
        
        # Check if we should use webhook or polling
        if config.USE_WEBHOOK:
            print("🌐 Webhook Mode: Enabled")
            print(f"📡 Webhook URL: {config.WEBHOOK_URL if config.WEBHOOK_URL else 'Using Render default'}")
            
            # Start Flask web server
            start_web_server()
            print(f"🌍 Web server started on port {config.WEBHOOK_PORT}")
            
            # Run bot with webhook
            print(f"🚀 Starting webhook server...")
            bot.run_webhook()
        else:
            print("🔄 Polling Mode: Enabled")
            
            # Start Flask web server
            start_web_server()
            print(f"🌍 Web server started on port {config.WEBHOOK_PORT}")
            
            print("🔄 Starting polling...")
            bot.run_polling()
        
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Failed to start bot: {e}")

if __name__ == '__main__':
    main()