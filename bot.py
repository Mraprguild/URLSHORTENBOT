import asyncio
import requests
import base64
import sys
from telethon import TelegramClient, events
import config  # Import configuration from config.py

# --- Configuration Loading and Validation ---
try:
    API_ID = config.API_ID
    API_HASH = config.API_HASH
    BOT_TOKEN = config.BOT_TOKEN
    API_KEY = config.API_KEY # Load Gemini API Key from config

    # Check if the values are actually filled in
    if not all([API_ID, API_HASH, BOT_TOKEN, API_KEY]):
        print("ERROR: One or more configuration variables are missing in config.py.")
        print("Please fill in API_ID, API_HASH, BOT_TOKEN, and API_KEY.")
        sys.exit(1)

    # Safely convert API_ID to integer
    API_ID_INT = int(API_ID)

except (AttributeError, ValueError) as e:
    print(f"ERROR: config.py is missing or a value is incorrect: {e}")
    print("Please ensure config.py exists and all credentials are set correctly.")
    sys.exit(1)
# -----------------------------------------

# Initialize the Telegram client
client = TelegramClient('bot_session', API_ID_INT, API_HASH)

# Gemini API configuration (loaded from config)
MODEL_NAME = None
API_URL = None

async def get_latest_image_model():
    """Fetches the latest available image generation model from the Gemini API."""
    list_models_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    fallback_model = "imagen-3.0-generate-002"
    try:
        response = await asyncio.to_thread(requests.get, list_models_url)
        response.raise_for_status()
        models = response.json().get("models", [])
        
        imagen_models = [
            m for m in models 
            if "imagen" in m.get("name", "") and 
               "predict" in m.get("supportedGenerationMethods", [])
        ]
        
        if imagen_models:
            latest_model = sorted(imagen_models, key=lambda x: x['name'], reverse=True)[0]
            model_name = latest_model["name"].split('/')[-1]
            print(f"Auto-detected image model: {model_name}")
            return model_name
        
        print(f"Could not auto-detect image model. Falling back to {fallback_model}.")
        return fallback_model
    except (requests.exceptions.RequestException, KeyError) as e:
        print(f"Failed to fetch models: {e}. Falling back to {fallback_model}.")
        return fallback_model

async def generate_image_with_retry(prompt, max_retries=3):
    """Generates an image using the Gemini API with exponential backoff."""
    headers = {'Content-Type': 'application/json'}
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1}
    }
    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(
                requests.post, API_URL, json=payload, headers=headers
            )
            response.raise_for_status()
            result = response.json()

            if "predictions" in result and result["predictions"]:
                b64_string = result["predictions"][0].get("bytesBase64Encoded")
                if b64_string:
                    return base64.b64decode(b64_string)
            return None
        except requests.exceptions.RequestException as e:
            print(f"API request failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                print("Max retries reached. Could not generate image.")
                return None

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    """Handler for the /start command."""
    await event.respond('Hello! I am a banana bot.\nSend /banana to get a fresh banana image!')

@client.on(events.NewMessage(pattern='/banana'))
async def banana(event):
    """Handler for the /banana command."""
    sender = await event.get_sender()
    print(f"Received /banana command from {sender.username}")

    processing_message = await event.respond('🍌 Generating a banana for you... Please wait.')

    prompt = "a single, ripe, yellow banana on a clean white background, studio lighting, hyperrealistic"
    image_bytes = await generate_image_with_retry(prompt)

    await client.delete_messages(event.chat_id, [processing_message.id])

    if image_bytes:
        print("Image generated successfully. Sending to user.")
        await client.send_file(event.chat_id, image_bytes, caption="Here is your banana!")
    else:
        print("Failed to generate image.")
        await event.respond("Sorry, I couldn't generate a banana image right now. Please try again later.")

async def main():
    """Main function to start the bot."""
    global MODEL_NAME, API_URL

    MODEL_NAME = await get_latest_image_model()
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:predict?key={API_KEY}"

    print("Starting bot...")
    await client.start(bot_token=BOT_TOKEN)
    print("Bot started successfully!")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
