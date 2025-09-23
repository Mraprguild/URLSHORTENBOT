import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

# Import configuration
from config import config, Config

# --- Setup Logging ---
logging.basicConfig(
    level=config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Validate Configuration ---
if not config.validate_config():
    logger.critical("Invalid configuration. Please check your environment variables.")
    exit(1)

# --- Initialize Pyrogram Client ---
try:
    app = Client(
        "FileStoreBot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        parse_mode=ParseMode.MARKDOWN
    )
    logger.info("Bot client initialized successfully")
except Exception as e:
    logger.critical(f"Failed to initialize Pyrogram client: {e}")
    exit(1)

# --- Utility Functions ---
class FileUtils:
    """Utility functions for file handling"""
    
    @staticmethod
    def human_readable_size(size_bytes: int) -> str:
        """Convert bytes to human readable format"""
        if not size_bytes:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.2f} {size_names[i]}"
    
    @staticmethod
    def get_file_info(message: Message) -> Dict[str, Any]:
        """Extract file information from message"""
        file_info = {
            "name": "Unknown",
            "size": 0,
            "type": "Unknown",
            "mime_type": "",
            "caption": message.caption or "",
            "duration": 0,
            "width": 0,
            "height": 0
        }
        
        if message.document:
            file_info.update({
                "name": message.document.file_name or "Unnamed document",
                "size": message.document.file_size or 0,
                "type": "Document",
                "mime_type": message.document.mime_type or "Unknown"
            })
        elif message.video:
            file_info.update({
                "name": message.video.file_name or "Unnamed video",
                "size": message.video.file_size or 0,
                "type": "Video",
                "mime_type": message.video.mime_type or "video/mp4",
                "duration": message.video.duration or 0,
                "width": message.video.width or 0,
                "height": message.video.height or 0
            })
        elif message.audio:
            file_info.update({
                "name": message.audio.file_name or "Unnamed audio",
                "size": message.audio.file_size or 0,
                "type": "Audio",
                "mime_type": message.audio.mime_type or "audio/mpeg",
                "duration": message.audio.duration or 0
            })
        elif message.photo:
            file_info.update({
                "name": "Photo",
                "size": message.photo.file_size or 0,
                "type": "Photo",
                "mime_type": "image/jpeg"
            })
        elif message.voice:
            file_info.update({
                "name": "Voice message",
                "size": message.voice.file_size or 0,
                "type": "Voice",
                "mime_type": "audio/ogg",
                "duration": message.voice.duration or 0
            })
        elif message.sticker:
            file_info.update({
                "name": "Sticker",
                "size": message.sticker.file_size or 0,
                "type": "Sticker",
                "mime_type": "image/webp"
            })
        elif message.animation:
            file_info.update({
                "name": "Animation",
                "size": message.animation.file_size or 0,
                "type": "Animation",
                "mime_type": "video/mp4",
                "duration": message.animation.duration or 0,
                "width": message.animation.width or 0,
                "height": message.animation.height or 0
            })
        
        return file_info
    
    @staticmethod
    def format_file_caption(file_info: Dict[str, Any], user_mention: str) -> str:
        """Format caption for stored files"""
        caption = f"📁 **{file_info['name']}**\n\n"
        caption += f"**Type:** {file_info['type']}\n"
        caption += f"**Size:** {FileUtils.human_readable_size(file_info['size'])}\n"
        
        if file_info['mime_type']:
            caption += f"**MIME Type:** {file_info['mime_type']}\n"
        
        if file_info['duration'] > 0:
            minutes, seconds = divmod(file_info['duration'], 60)
            caption += f"**Duration:** {minutes:02d}:{seconds:02d}\n"
        
        if file_info['width'] and file_info['height']:
            caption += f"**Resolution:** {file_info['width']}x{file_info['height']}\n"
        
        caption += f"**Stored:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        caption += f"**Owner:** {user_mention}"
        
        if file_info['caption']:
            caption += f"\n**Original Caption:** {file_info['caption']}"
        
        return caption


# --- Command Handlers ---
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    """Handle /start command"""
    if message.from_user.id != config.OWNER_ID:
        await message.reply_text("❌ Sorry, this is a private bot. You do not have permission to use it.")
        logger.warning(f"Unauthorized access attempt by user {message.from_user.id}")
        return

    welcome_text = config.WELCOME_MESSAGE.format(
        user_name=message.from_user.first_name,
        bot_name=config.BOT_NAME,
        max_size=int(config.MAX_FILE_SIZE / (1024 * 1024 * 1024))
    )
    
    await message.reply_text(welcome_text)
    logger.info(f"Owner {config.OWNER_ID} started the bot.")


@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    """Handle /help command"""
    if message.from_user.id != config.OWNER_ID:
        return

    help_text = config.HELP_MESSAGE.format(
        max_size=int(config.MAX_FILE_SIZE / (1024 * 1024 * 1024))
    )
    
    await message.reply_text(help_text)


@app.on_message(filters.command("stats") & filters.private)
async def stats_handler(client: Client, message: Message):
    """Handle /stats command"""
    if message.from_user.id != config.OWNER_ID or not config.ENABLE_STATS:
        return

    try:
        bot_info = config.get_bot_info()
        stats_text = (
            f"📊 **{config.BOT_NAME} - Statistics**\n\n"
            f"**Storage Channel:** `{config.STORAGE_CHANNEL_ID}`\n"
            f"**Max File Size:** {bot_info['max_file_size_gb']}GB\n"
            f"**Supported Formats:** {', '.join(bot_info['supported_formats'])}\n"
            f"**Owner:** {message.from_user.mention}\n"
            f"**Bot Status:** ✅ Operational\n\n"
            f"*Detailed analytics coming in future updates...*"
        )
        
        await message.reply_text(stats_text)
        logger.info(f"Stats requested by owner {config.OWNER_ID}")
        
    except Exception as e:
        await message.reply_text(f"❌ Error getting statistics: {str(e)}")
        logger.error(f"Error in stats handler: {e}")


@app.on_message(filters.command("config") & filters.private & filters.user(config.OWNER_ID))
async def config_handler(client: Client, message: Message):
    """Show current configuration (owner only)"""
    bot_info = config.get_bot_info()
    
    config_text = (
        f"⚙️ **{config.BOT_NAME} - Configuration**\n\n"
        f"**Environment:** {os.getenv('ENVIRONMENT', 'production')}\n"
        f"**Owner ID:** `{config.OWNER_ID}`\n"
        f"**Storage Channel:** `{config.STORAGE_CHANNEL_ID}`\n"
        f"**Max File Size:** {bot_info['max_file_size_gb']}GB\n\n"
        f"**Enabled Features:**\n"
    )
    
    for feature, enabled in bot_info['features'].items():
        config_text += f"• {feature}: {'✅' if enabled else '❌'}\n"
    
    await message.reply_text(config_text)


@app.on_message(config.get_supported_media_filters() & filters.private)
async def file_handler(client: Client, message: Message):
    """Handle incoming files"""
    if message.from_user.id != config.OWNER_ID:
        await message.reply_text("❌ Sorry, you are not authorized to store files.")
        return

    # Get file information
    file_info = FileUtils.get_file_info(message)
    
    # Check file size
    if file_info['size'] > config.MAX_FILE_SIZE:
        await message.reply_text(
            f"❌ File too large! Maximum size is {config.MAX_FILE_SIZE / (1024**3):.1f}GB. "
            f"Your file is {file_info['size'] / (1024**3):.1f}GB."
        )
        return

    logger.info(f"Received {file_info['type']} from owner: {file_info['name']}")

    # Show processing message
    processing_text = (
        f"📤 **Uploading File...**\n\n"
        f"**Name:** {file_info['name']}\n"
        f"**Type:** {file_info['type']}\n"
        f"**Size:** {FileUtils.human_readable_size(file_info['size'])}\n"
        f"**Status:** Processing..."
    )
    
    processing_message = await message.reply_text(processing_text)

    try:
        # Format caption and store file
        file_caption = FileUtils.format_file_caption(file_info, message.from_user.mention)
        
        # Forward the file to storage channel
        forwarded_message = await message.copy(
            config.STORAGE_CHANNEL_ID,
            caption=file_caption
        )
        
        # Create download button
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📥 Download File", url=forwarded_message.link)
        ]])
        
        # Success message
        success_text = (
            f"✅ **File Stored Successfully!**\n\n"
            f"**Name:** {file_info['name']}\n"
            f"**Type:** {file_info['type']}\n"
            f"**Size:** {FileUtils.human_readable_size(file_info['size'])}\n"
            f"**Storage:** Private Channel\n\n"
            f"**Download Link Ready!**"
        )
        
        await processing_message.edit_text(
            success_text, 
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        
        logger.info(f"File stored successfully: {file_info['name']}")

    except Exception as e:
        error_text = (
            f"❌ **Upload Failed**\n\n"
            f"**Error:** {str(e)}\n\n"
            f"Please try again or check if the bot has admin rights in the storage channel."
        )
        await processing_message.edit_text(error_text)
        logger.error(f"Failed to store file: {e}", exc_info=True)


# --- Error Handler ---
@app.on_errors()
async def error_handler(client: Client, error: Exception, update):
    """Global error handler"""
    logger.error(f"Error in update: {error}", exc_info=True)


# --- Main Execution ---
async def main():
    """Main function to start the bot"""
    logger.info(f"Starting {config.BOT_NAME}...")
    
    # Test channel access
    try:
        chat = await app.get_chat(config.STORAGE_CHANNEL_ID)
        logger.info(f"Storage channel: {chat.title} (ID: {config.STORAGE_CHANNEL_ID})")
    except Exception as e:
        logger.error(f"Cannot access storage channel: {e}")
        return
    
    # Start the bot
    await app.start()
    
    # Get bot info
    bot_info = await app.get_me()
    logger.info(f"Bot @{bot_info.username} is now running!")
    
    # Display bot information
    logger.info(f"Bot Name: {config.BOT_NAME}")
    logger.info(f"Owner ID: {config.OWNER_ID}")
    logger.info(f"Storage Channel: {config.STORAGE_CHANNEL_ID}")
    logger.info(f"Max File Size: {config.MAX_FILE_SIZE / (1024**3)}GB")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'production')}")
    
    # Keep the bot running
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")
    finally:
        logger.info("Bot has stopped.")
