import asyncio
import requests
import base64
import sys
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from telethon import TelegramClient, events, Button
import config

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('BananaBot')

# --- Configuration Validation ---
try:
    API_ID = config.API_ID
    API_HASH = config.API_HASH
    BOT_TOKEN = config.BOT_TOKEN
    API_KEY = config.API_KEY
    
    # Check if placeholders are still there
    placeholder_values = ['your_api_id_here', 'your_api_hash_here', 
                         'your_bot_token_here', 'your_gemini_api_key_here']
    
    if any(val in placeholder_values for val in [API_ID, API_HASH, BOT_TOKEN, API_KEY]):
        logger.error("❌ Please replace placeholder values in config.py with your actual API credentials!")
        logger.error("Get credentials from:")
        logger.error("Telegram API: https://my.telegram.org")
        logger.error("Bot Token: @BotFather on Telegram")
        logger.error("Gemini API: https://aistudio.google.com/")
        sys.exit(1)
    
    if not all([API_ID, API_HASH, BOT_TOKEN, API_KEY]):
        logger.error("One or more configuration variables are missing")
        sys.exit(1)
    
    API_ID_INT = int(API_ID)
    
except (AttributeError, ValueError) as e:
    logger.error(f"Configuration error: {e}")
    logger.error("Please ensure config.py exists and all credentials are set correctly.")
    sys.exit(1)

# --- Initialize Telegram Client FIRST ---
client = TelegramClient('banana_bot_session', API_ID_INT, API_HASH)

# --- Global Variables ---
MODEL_NAME = None
API_URL = None
user_requests = defaultdict(list)
user_stats = defaultdict(lambda: {'requests': 0, 'successful': 0})

# --- Rate Limiting Function ---
def is_rate_limited(user_id):
    """Check if user has exceeded rate limit"""
    now = datetime.now()
    user_requests[user_id] = [req_time for req_time in user_requests[user_id] 
                             if now - req_time < timedelta(minutes=1)]
    
    if len(user_requests[user_id]) >= config.RATE_LIMIT_PER_USER:
        return True
    
    user_requests[user_id].append(now)
    return False

# --- Model Detection ---
async def get_latest_image_model():
    """Fetches the latest available image generation model"""
    list_models_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    fallback_model = "imagen-3.0-generate-002"
    
    try:
        response = await asyncio.to_thread(requests.get, list_models_url, timeout=10)
        response.raise_for_status()
        models = response.json().get("models", [])
        
        imagen_models = [
            m for m in models 
            if "imagen" in m.get("name", "").lower() and 
               "generate" in m.get("supportedGenerationMethods", [])
        ]
        
        if imagen_models:
            latest_model = sorted(imagen_models, key=lambda x: x['name'], reverse=True)[0]
            model_name = latest_model["name"].split('/')[-1]
            logger.info(f"Auto-detected image model: {model_name}")
            return model_name
        
        logger.warning(f"Could not auto-detect image model. Using fallback: {fallback_model}")
        return fallback_model
        
    except Exception as e:
        logger.error(f"Failed to fetch models: {e}. Using fallback: {fallback_model}")
        return fallback_model

# --- Image Generation ---
async def generate_image_with_retry(prompt, max_retries=config.MAX_RETRIES):
    """Generates an image using the Gemini API with exponential backoff"""
    headers = {'Content-Type': 'application/json'}
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "1:1",
            "quality": "high"
        }
    }
    
    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(
                requests.post, API_URL, json=payload, headers=headers, timeout=30
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                wait_time = 2 ** attempt
                logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                continue
                
            response.raise_for_status()
            result = response.json()

            if "predictions" in result and result["predictions"]:
                b64_string = result["predictions"][0].get("bytesBase64Encoded")
                if b64_string:
                    logger.info("Image generated successfully")
                    return base64.b64decode(b64_string)
                else:
                    logger.error("No image data in response")
                    return None
            else:
                logger.error(f"Unexpected response format: {result}")
                return None
                
        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout on attempt {attempt + 1}")
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed on attempt {attempt + 1}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            
        # Exponential backoff
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            await asyncio.sleep(wait_time)
    
    logger.error("Max retries reached. Could not generate image.")
    return None

async def generate_banana_image(event, prompt):
    """Generate and send banana image"""
    user_id = event.sender_id
    
    # Rate limiting check
    if is_rate_limited(user_id):
        await event.respond("⏰ Too many requests! Please wait a minute before generating more bananas.")
        return
    
    # Update statistics
    user_stats[user_id]['requests'] += 1
    
    logger.info(f"Generating banana for user {user_id} with prompt: {prompt}")
    
    # Send processing message
    processing_msg = await event.respond('🍌 Generating your banana... Please wait 10-20 seconds.')
    
    # Generate image
    image_bytes = await generate_image_with_retry(prompt)
    
    # Delete processing message
    await processing_msg.delete()
    
    if image_bytes:
        user_stats[user_id]['successful'] += 1
        await event.respond(file=image_bytes, caption="🍌 Here's your fresh banana!")
        logger.info(f"Successfully sent banana to user {user_id}")
    else:
        await event.respond("❌ Sorry, I couldn't generate a banana image right now. Please try again later.")
        logger.error(f"Failed to generate banana for user {user_id}")

# --- Telegram Bot Handlers ---
@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    """Handler for the /start command"""
    user = await event.get_sender()
    logger.info(f"Start command from {user.username} (ID: {user.id})")
    
    welcome_text = """
🍌 **Welcome to Banana Bot!** 🍌

I can generate realistic banana images using AI!

**Commands:**
/banana - Generate a fresh banana
/custom - Generate a custom banana image
/stats - See your usage statistics
/help - Show this help message

Click the buttons below to get started!
"""
    
    buttons = [
        [Button.inline("🍌 Get Banana", b"get_banana")],
        [Button.inline("🎨 Custom Banana", b"custom_banana"), 
         Button.inline("📊 Statistics", b"show_stats")],
        [Button.inline("ℹ️ Help", b"show_help")]
    ]
    
    await event.respond(welcome_text, buttons=buttons)

@client.on(events.NewMessage(pattern='/banana'))
async def banana_handler(event):
    """Handler for the /banana command"""
    await generate_banana_image(event, "a single, ripe, yellow banana on a clean white background, studio lighting, hyperrealistic")

@client.on(events.NewMessage(pattern='/custom'))
async def custom_handler(event):
    """Handler for custom banana requests"""
    await event.respond("🍌 What kind of banana would you like? Describe it!\n\nExamples:\n- 'a banana wearing sunglasses'\n- 'a banana on the beach'\n- 'a cartoon banana dancing'")
    
    # Wait for user response
    try:
        response = await client.wait_for(
            events.NewMessage(chats=event.chat_id, from_users=event.sender_id),
            timeout=60
        )
        custom_prompt = f"a banana, {response.text}, realistic style"
        await generate_banana_image(event, custom_prompt)
    except asyncio.TimeoutError:
        await event.respond("⏰ Sorry, you took too long to respond. Please try again!")

@client.on(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    """Handler for user statistics"""
    user_id = event.sender_id
    stats = user_stats[user_id]
    
    success_rate = (stats['successful'] / stats['requests'] * 100) if stats['requests'] > 0 else 0
    
    stats_text = f"""
📊 **Your Banana Statistics**

🍌 Total Requests: {stats['requests']}
✅ Successful Generations: {stats['successful']}
🎯 Success Rate: {success_rate:.1f}%

Keep generating bananas! 🍌
"""
    await event.respond(stats_text)

@client.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    """Handler for help command"""
    help_text = f"""
🆘 **Banana Bot Help**

**Commands:**
/start - Start the bot and show welcome message
/banana - Generate a standard banana image
/custom - Create a custom banana with your description
/stats - View your usage statistics
/help - Show this help message

**Rate Limits:** 
- {config.RATE_LIMIT_PER_USER} requests per minute per user

**Tips:**
- Be creative with your custom banana descriptions!
- The bot works best with clear, descriptive prompts
- If generation fails, try again with a simpler description

Enjoy your bananas! 🍌
"""
    await event.respond(help_text)

@client.on(events.CallbackQuery)
async def callback_handler(event):
    """Handle button clicks"""
    user_id = event.sender_id
    data = event.data.decode('utf-8')
    
    if data == "get_banana":
        # Edit the original message to show we're processing
        await event.edit("🍌 Generating your banana...")
        await generate_banana_image(event, "a single, ripe, yellow banana on a clean white background, studio lighting, hyperrealistic")
    elif data == "custom_banana":
        await event.edit("🍌 Please describe your custom banana...")
        await custom_handler(event)
    elif data == "show_stats":
        await stats_handler(event)
    elif data == "show_help":
        await help_handler(event)
    
    await event.answer()

# --- Admin Commands ---
@client.on(events.NewMessage(pattern='/admin_stats'))
async def admin_stats_handler(event):
    """Admin command to view bot statistics"""
    user_id = event.sender_id
    
    if user_id not in config.ADMIN_USER_IDS:
        await event.respond("🚫 Access denied.")
        return
    
    total_requests = sum(stats['requests'] for stats in user_stats.values())
    total_successful = sum(stats['successful'] for stats in user_stats.values())
    unique_users = len(user_stats)
    
    overall_success_rate = (total_successful / total_requests * 100) if total_requests > 0 else 0
    
    admin_text = f"""
👑 **Admin Statistics**

👥 Unique Users: {unique_users}
🍌 Total Requests: {total_requests}
✅ Successful Generations: {total_successful}
🎯 Overall Success Rate: {overall_success_rate:.1f}%

**Current Model:** {MODEL_NAME}
"""
    await event.respond(admin_text)

@client.on(events.NewMessage(pattern='/myid'))
async def get_my_id(event):
    """Temporary command to get your user ID"""
    user = await event.get_sender()
    await event.respond(f"Your User ID is: `{user.id}`", parse_mode='markdown')

# --- Main Function ---
async def main():
    """Main function to start the bot"""
    global MODEL_NAME, API_URL
    
    logger.info("Starting Banana Bot...")
    
    # Detect latest model
    MODEL_NAME = await get_latest_image_model()
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:predict?key={API_KEY}"
    
    logger.info(f"Using API URL: {API_URL}")
    
    # Start the bot
    await client.start(bot_token=BOT_TOKEN)
    
    me = await client.get_me()
    logger.info(f"Bot started successfully as @{me.username}")
    logger.info("Bot is now running...")
    
    # Bot is ready
    await client.send_message(
        config.ADMIN_USER_IDS[0],
        "🍌 Banana Bot started successfully!"
    )
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info("Bot shutdown complete")
