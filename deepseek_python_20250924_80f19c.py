import logging
import requests
import re
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

import config

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class URLShortenerBot:
    def __init__(self, token):
        self.token = token
        self.application = Application.builder().token(token).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("shorten", self.shorten))
        self.application.add_handler(CommandHandler("status", self.status))
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
    
    async def error_handler(self, update: Update, context: CallbackContext):
        """Handle errors in the telegram bot"""
        logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text("❌ An error occurred. Please try again.")
        except Exception as e:
            logger.error(f"Error while sending error message: {e}")

    def shorten_url(self, url, service):
        """Shorten URL using the specified service"""
        try:
            # Validate URL first
            if not self.is_valid_url(url):
                return None

            logger.info(f"Shortening URL with {service}: {url}")

            if service == 'bitly':
                if not config.BITLY_TOKEN:
                    logger.error("Bitly token not configured")
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
                    return response.json()['link']
                else:
                    logger.error(f"Bitly API error: {response.status_code} - {response.text}")
            
            elif service == 'tinyurl':
                params = {'url': url}
                response = requests.get(
                    config.SUPPORTED_SERVICES[service]['api_url'], 
                    params=params, 
                    timeout=10
                )
                if response.status_code == 200:
                    return response.text.strip()
                else:
                    logger.error(f"TinyURL API error: {response.status_code}")
            
            elif service == 'cuttly':
                if not config.CUTTLY_API:
                    logger.error("Cuttly API key not configured")
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
                        return data['url']['shortLink']
                    else:
                        logger.error(f"Cuttly API error: {data}")
                else:
                    logger.error(f"Cuttly HTTP error: {response.status_code}")
            
            elif service == 'gplinks':
                if not config.GPLINKS_API or config.GPLINKS_API == 'YOUR_GPLINKS_API_KEY_HERE':
                    logger.error("GPLinks API key not configured")
                    return None
                
                # GPLinks API - Multiple implementation attempts
                api_url = "https://gplinks.in/api"
                
                # Try GET request first
                params = {
                    'api': config.GPLINKS_API,
                    'url': url
                }
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                }
                
                # First try GET request
                response = requests.get(api_url, params=params, headers=headers, timeout=15)
                
                logger.info(f"GPLinks API attempt 1 (GET): {response.status_code}")
                
                if response.status_code == 200:
                    response_text = response.text.strip()
                    
                    # Check if response is a direct URL
                    if response_text.startswith('http'):
                        return response_text
                    
                    # Try to parse JSON
                    try:
                        json_data = response.json()
                        if json_data.get('status') == 'success':
                            return json_data.get('shortenedUrl') or json_data.get('shorturl')
                        elif 'shortenedUrl' in json_data:
                            return json_data['shortenedUrl']
                    except ValueError:
                        # If not JSON, check if it contains a URL
                        if 'http' in response_text:
                            import re
                            urls = re.findall(r'https?://[^\s]+', response_text)
                            if urls:
                                return urls[0]
                
                # If GET failed, try POST request
                payload = {
                    'api': config.GPLINKS_API,
                    'url': url
                }
                
                response = requests.post(api_url, data=payload, headers=headers, timeout=15)
                logger.info(f"GPLinks API attempt 2 (POST): {response.status_code}")
                
                if response.status_code == 200:
                    response_text = response.text.strip()
                    
                    if response_text.startswith('http'):
                        return response_text
                    
                    try:
                        json_data = response.json()
                        if json_data.get('status') == 'success':
                            return json_data.get('shortenedUrl') or json_data.get('shorturl')
                    except ValueError:
                        if 'http' in response_text:
                            import re
                            urls = re.findall(r'https?://[^\s]+', response_text)
                            if urls:
                                return urls[0]
                
                logger.error(f"GPLinks API failed after both attempts. Status: {response.status_code}, Response: {response.text}")
                return None
            
            return None
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while shortening URL with {service}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error with {service}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error shortening URL with {service}: {str(e)}")
            return None
    
    async def start(self, update: Update, context: CallbackContext):
        """Send welcome message when command /start is issued"""
        try:
            user = update.effective_user
            
            # Welcome message with image
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

🚀 **Get Started:**
Simply send me a URL or use /shorten command to begin!
            """
            
            # Try to send image with caption first, fallback to text only
            try:
                await update.message.reply_photo(
                    photo=config.WELCOME_IMAGE_URL,
                    caption=welcome_text,
                    parse_mode='HTML'
                )
            except Exception as photo_error:
                logger.warning(f"Could not send welcome image: {photo_error}. Sending text only.")
                await update.message.reply_html(welcome_text)
                
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
With GPLinks, you can earn revenue from every click on your shortened URLs! 
Sign up at https://gplinks.in to get your API key.

🔧 **Need Help?**
Use `/status` to check your API key configuration.
Contact support if you need assistance setting up monetization.
            """
            await update.message.reply_text(help_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in help command: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    
    async def status(self, update: Update, context: CallbackContext):
        """Check API key status"""
        try:
            status_text = "🔧 **API Key Status Dashboard**\n\n"
            
            for service_key, service_info in config.SUPPORTED_SERVICES.items():
                service_name = service_info['name']
                requires_key = service_info['requires_key']
                
                # Get API key based on service naming convention
                if service_key == 'bitly':
                    has_key = bool(config.BITLY_TOKEN and config.BITLY_TOKEN != 'YOUR_BITLY_TOKEN_HERE')
                    key_preview = config.BITLY_TOKEN[:10] + '...' if config.BITLY_TOKEN and len(config.BITLY_TOKEN) > 10 else 'Not set'
                elif service_key == 'cuttly':
                    has_key = bool(config.CUTTLY_API and config.CUTTLY_API != 'YOUR_CUTTLY_API_HERE')
                    key_preview = config.CUTTLY_API[:10] + '...' if config.CUTTLY_API and len(config.CUTTLY_API) > 10 else 'Not set'
                elif service_key == 'gplinks':
                    has_key = bool(config.GPLINKS_API and config.GPLINKS_API != 'YOUR_GPLINKS_API_KEY_HERE')
                    key_preview = config.GPLINKS_API[:10] + '...' if config.GPLINKS_API and len(config.GPLINKS_API) > 10 else 'Not set'
                else:
                    has_key = True  # TinyURL doesn't need API key
                    key_preview = "Not required"
                
                status_text += f"**{service_name}**: "
                if requires_key:
                    status_text += "✅ Configured" if has_key else "❌ Not configured"
                else:
                    status_text += "✅ No API needed"
                status_text += f" (`{key_preview}`)\n"
            
            status_text += "\n💡 **Quick Tips:**"
            status_text += "\n• TinyURL works instantly without setup"
            status_text += "\n• Get Bitly token at: https://bitly.com"
            status_text += "\n• Get Cuttly API at: https://cutt.ly"
            status_text += "\n• Get GPLinks API at: https://gplinks.in"
            status_text += "\n• Restart bot after updating API keys"
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text("❌ Error checking status")
    
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
            url = update.message.text
            
            # Basic URL validation
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
            
            # URL encoding for callback data (Telegram has limits on callback data length)
            encoded_url = url.replace('/', '_').replace(':', '|')
            
            # Create keyboard with service options
            keyboard = [
                [
                    InlineKeyboardButton("🌐 Bitly", callback_data=f"shorten_bitly_{encoded_url}"),
                    InlineKeyboardButton("🔗 TinyURL", callback_data=f"shorten_tinyurl_{encoded_url}"),
                ],
                [
                    InlineKeyboardButton("📊 Cuttly", callback_data=f"shorten_cuttly_{encoded_url}"),
                    InlineKeyboardButton("💰 GPLinks", callback_data=f"shorten_gplinks_{encoded_url}"),
                ],
                [InlineKeyboardButton("🚀 All Services", callback_data=f"shorten_all_{encoded_url}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🔗 **Original URL:**\n`{url}`\n\n**Choose a service to shorten:**",
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
            if data.startswith('shorten_'):
                parts = data.split('_', 2)
                if len(parts) == 3:
                    _, service, encoded_url = parts
                    url = encoded_url.replace('_', '/').replace('|', ':')  # Reverse URL encoding
                    
                    # Show typing action
                    await query.message.reply_chat_action(action="typing")
                    
                    if service == 'all':
                        await self.send_all_shortened_urls(query, url)
                    else:
                        await self.send_single_shortened_url(query, url, service)
                else:
                    await query.edit_message_text("❌ Invalid request. Please try again.")
        except Exception as e:
            logger.error(f"Error in button handler: {e}")
            try:
                await query.edit_message_text("❌ An error occurred. Please try again.")
            except:
                pass
    
    async def send_single_shortened_url(self, query, url: str, service: str):
        """Send shortened URL from a single service"""
        try:
            # Get service name safely
            service_info = config.SUPPORTED_SERVICES.get(service, {})
            service_name = service_info.get('name', service.capitalize())
            
            shortened_url = self.shorten_url(url, service)
            
            if shortened_url:
                message = f"✅ **{service_name}**\n🔗 `{shortened_url}`"
                
                # Add special note for GPLinks
                if service == 'gplinks':
                    message += "\n\n💰 *Earn money with this shortened link!*"
                
                await query.edit_message_text(
                    text=message,
                    disable_web_page_preview=True,
                    parse_mode='Markdown'
                )
            else:
                requires_key = service_info.get('requires_key', True)
                error_msg = f"❌ Failed to shorten URL using {service_name}."
                
                # Provide specific error messages
                if service == 'gplinks':
                    if not config.GPLINKS_API or config.GPLINKS_API == 'YOUR_GPLINKS_API_KEY_HERE':
                        error_msg += "\n🔑 GPLinks API key is not configured."
                        error_msg += "\n💡 Get your API key from https://gplinks.in and add it to config.py"
                    else:
                        error_msg += "\n🔧 The GPLinks API might be temporarily unavailable or your API key may be invalid."
                elif requires_key:
                    error_msg += " API key might not be configured or is invalid."
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
                    requires_key = service_info.get('requires_key', True)
                    reason = "API key not configured" if requires_key else "Service unavailable"
                    message += f"❌ **{service_name}** - {reason}\n\n"
            
            if successful_shortens == 0:
                message = "❌ All services failed to shorten the URL. Please try again later.\n\n💡 **Tip:** TinyURL works without API key setup!"
            else:
                message += f"\n✅ **{successful_shortens} out of {len(config.SUPPORTED_SERVICES)} services successful**"
                if successful_shortens > 0 and any('gplinks' in service for service in config.SUPPORTED_SERVICES):
                    message += "\n💰 *GPLinks links can generate revenue!*"
            
            await query.edit_message_text(
                text=message,
                disable_web_page_preview=True,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error sending all shortened URLs: {e}")
            await query.edit_message_text("❌ Error generating shortened URLs. Please try again.")
    
    def run(self, use_webhook=False):
        """Start the bot with either polling or webhook"""
        if use_webhook:
            # Webhook mode for Render
            self.application.run_webhook(
                listen="0.0.0.0",
                port=config.PORT,
                url_path=self.token,
                webhook_url=f"https://your-render-app-name.onrender.com/{self.token}"
            )
        else:
            # Polling mode for development
            logger.info("Starting URL Shortener Bot in polling mode...")
            self.application.run_polling()

def main():
    """Main function to run the bot"""
    try:
        if not config.BOT_TOKEN or config.BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
            print("❌ Error: Please set your BOT_TOKEN in environment variables or config.py file")
            print("💡 Get your token from @BotFather on Telegram")
            return
        
        # Check if config has SUPPORTED_SERVICES
        if not hasattr(config, 'SUPPORTED_SERVICES') or not config.SUPPORTED_SERVICES:
            print("❌ Error: SUPPORTED_SERVICES not configured in config.py")
            return
        
        print("🤖 URL Shortener Bot Starting...")
        print(f"🌐 Port: {config.PORT}")
        print("📊 Supported Services:")
        for service, info in config.SUPPORTED_SERVICES.items():
            status = "✅" if not info['requires_key'] or (
                getattr(config, f"{service.upper()}_TOKEN", None) or 
                getattr(config, f"{service.upper()}_API", None)
            ) else "❌"
            print(f"   {status} {info['name']}")
        
        bot = URLShortenerBot(config.BOT_TOKEN)
        
        # Check if we're in production (Render sets RENDER env var)
        if os.environ.get('RENDER', None):
            print("🚀 Starting in webhook mode (Production)...")
            bot.run(use_webhook=True)
        else:
            print("🔧 Starting in polling mode (Development)...")
            print("🚀 Bot is running... Press Ctrl+C to stop")
            bot.run(use_webhook=False)
        
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Failed to start bot: {e}")

if __name__ == '__main__':
    main()