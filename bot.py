import logging
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
    
    def is_valid_url(self, url: str) -> bool:
        """Enhanced URL validation"""
        # Simple validation for now - you can enhance this
        return url.startswith(('http://', 'https://'))
    
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
            
            elif service == 'gplinks':
                if not config.GPLINKS_API:
                    logger.error("GPLinks API key not configured")
                    return None
                
                headers = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
                data = {
                    'api': config.GPLINKS_API,
                    'url': url
                }
                response = requests.post(
                    config.SUPPORTED_SERVICES[service]['api_url'], 
                    data=data, 
                    headers=headers, 
                    timeout=10
                )
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        if result.get('status') == 'success':
                            return result.get('shortenedUrl', result.get('shortenedURL', result.get('shorturl')))
                    except ValueError:
                        # If response is plain text
                        if 'http' in response.text:
                            return response.text.strip()
            
            return None
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while shortening URL with {service}")
            return None
        except Exception as e:
            logger.error(f"Error shortening URL with {service}: {e}")
            return None
    
    async def start(self, update: Update, context: CallbackContext):
        """Send welcome message when command /start is issued"""
        try:
            user = update.effective_user
            welcome_text = f"""
👋 Hello {user.mention_html()}!

I'm a URL Shortener Bot! I can shorten your long URLs using various services.

📋 **Available Commands:**
/start - Start the bot
/help - Show help message
/shorten - Shorten a URL

📊 **Supported Services:**
- Bitly (Professional shortening)
- TinyURL (Simple & reliable)
- Cuttly (With analytics)
- GPLinks (Monetization options)

Simply send me a URL or use /shorten command!
            """
            await update.message.reply_html(welcome_text)
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    
    async def help(self, update: Update, context: CallbackContext):
        """Send help message"""
        try:
            help_text = """
🤖 **URL Shortener Bot Help**

📖 **How to use:**
1. Send me any long URL
2. Or use /shorten <URL> command
3. I'll provide shortened versions from different services

🔗 **Example:**
/shorten https://www.example.com/very-long-url-path

🛠 **Supported Services:**
- Bitly (requires API key setup)
- TinyURL (works without API key)
- Cuttly (requires API key setup)
- GPLinks (requires API key setup)

📝 **Note:** For Bitly, Cuttly, and GPLinks, you need to set up API keys in the bot configuration.
TinyURL works without any API key!

💰 **GPLinks Bonus:** Earn money from your shortened links!
            """
            await update.message.reply_text(help_text)
        except Exception as e:
            logger.error(f"Error in help command: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    
    async def shorten(self, update: Update, context: CallbackContext):
        """Shorten URL from command"""
        try:
            if not context.args:
                await update.message.reply_text("Please provide a URL to shorten. Usage: /shorten <URL>")
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
            if not self.is_valid_url(url):
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
            
            # URL encoding for callback data
            encoded_url = url.replace('/', '_').replace(':', '|')
            
            # Create keyboard with service options
            keyboard = [
                [
                    InlineKeyboardButton("Bitly", callback_data=f"shorten_bitly_{encoded_url}"),
                    InlineKeyboardButton("TinyURL", callback_data=f"shorten_tinyurl_{encoded_url}"),
                ],
                [
                    InlineKeyboardButton("Cuttly", callback_data=f"shorten_cuttly_{encoded_url}"),
                    InlineKeyboardButton("GPLinks", callback_data=f"shorten_gplinks_{encoded_url}"),
                ],
                [InlineKeyboardButton("All Services", callback_data=f"shorten_all_{encoded_url}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🔗 Original URL: {url}\n\nChoose a service to shorten:",
                reply_markup=reply_markup,
                disable_web_page_preview=True
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
                message = f"✅ **{service_name}**\n🔗 {shortened_url}"
                
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
                if requires_key:
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
                    message += f"✅ **{service_name}**\n{shortened_url}"
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
                if successful_shortens > 0:
                    message += "\n💰 *GPLinks links can generate revenue!*"
            
            await query.edit_message_text(
                text=message,
                disable_web_page_preview=True,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error sending all shortened URLs: {e}")
            await query.edit_message_text("❌ Error generating shortened URLs. Please try again.")
    
    def run(self):
        """Start the bot"""
        self.application.run_polling()

def main():
    """Main function to run the bot"""
    try:
        if not config.BOT_TOKEN or config.BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
            print("Error: Please set your BOT_TOKEN in environment variables or .env file")
            return
        
        # Check if config has SUPPORTED_SERVICES
        if not hasattr(config, 'SUPPORTED_SERVICES') or not config.SUPPORTED_SERVICES:
            print("Error: SUPPORTED_SERVICES not configured in config.py")
            return
        
        bot = URLShortenerBot(config.BOT_TOKEN)
        print("Bot is running...")
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == '__main__':
    main()
