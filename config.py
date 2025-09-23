import os
import logging
from dotenv import load_dotenv
from typing import List, Optional

# Load environment variables
load_dotenv()

class Config:
    """Configuration class for the File Store Bot"""
    
    # Telegram API Configuration
    API_ID: int = int(os.getenv("API_ID", 0))
    API_HASH: str = os.getenv("API_HASH", "")
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # Bot Configuration
    OWNER_ID: int = int(os.getenv("OWNER_ID", 0))
    STORAGE_CHANNEL_ID: int = int(os.getenv("STORAGE_CHANNEL_ID", 0))
    
    # Bot Settings
    BOT_NAME: str = os.getenv("BOT_NAME", "File Store Bot")
    MAX_FILE_SIZE: int = 4 * 1024 * 1024 * 1024  # 4GB in bytes
    SUPPORTED_FORMATS: List[str] = [
        "document", "video", "audio", "photo", "voice", "sticker", "animation"
    ]
    
    # Feature Flags
    ENABLE_STATS: bool = True
    ENABLE_BROADCAST: bool = False  # Disabled by default for security
    ENABLE_FILE_PREVIEW: bool = True
    
    # Message Templates
    WELCOME_MESSAGE: str = """
👋 **Welcome, {user_name}!**

📁 **{bot_name}** - Your personal cloud storage

**Features:**
• Store files up to {max_size}GB
• Support for all file types
• Direct download links
• File information tracking
• Secure private storage

**Commands:**
• /start - Show this message
• /stats - Get storage statistics
• /help - Show help information
• /settings - Configure bot settings (coming soon)

Simply send me any file to get started!
"""
    
    HELP_MESSAGE: str = """
📖 **Help Guide**

**How to use:**
1. Send any file (document, video, audio, photo)
2. The bot will store it in your private channel
3. You'll receive a direct download link

**Supported file types:**
• Documents (PDF, ZIP, EXE, etc.)
• Videos (MP4, MKV, AVI, etc.)
• Audio files (MP3, WAV, etc.)
• Photos (JPEG, PNG, etc.)
• Voice messages
• Stickers
• Animations (GIFs)

**File limits:**
• Maximum file size: {max_size}GB
• No limit on total storage

Need help? This bot is maintained exclusively for you!
"""
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate that all required configuration is present"""
        required_vars = {
            "API_ID": cls.API_ID,
            "API_HASH": cls.API_HASH,
            "BOT_TOKEN": cls.BOT_TOKEN,
            "OWNER_ID": cls.OWNER_ID,
            "STORAGE_CHANNEL_ID": cls.STORAGE_CHANNEL_ID
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        
        if missing_vars:
            logging.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            return False
        
        # Additional validation
        if cls.STORAGE_CHANNEL_ID > 0:
            logging.error("STORAGE_CHANNEL_ID must be negative (channel ID should start with -100)")
            return False
            
        if cls.MAX_FILE_SIZE > 4 * 1024 * 1024 * 1024:
            logging.warning("MAX_FILE_SIZE exceeds Telegram's 4GB limit, setting to 4GB")
            cls.MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024
        
        logging.info("Configuration validated successfully")
        return True
    
    @classmethod
    def get_supported_media_filters(cls):
        """Get Pyrogram filters for supported media types"""
        from pyrogram import filters
        
        filter_list = []
        media_mapping = {
            "document": filters.document,
            "video": filters.video,
            "audio": filters.audio,
            "photo": filters.photo,
            "voice": filters.voice,
            "sticker": filters.sticker,
            "animation": filters.animation
        }
        
        for media_type in cls.SUPPORTED_FORMATS:
            if media_type in media_mapping:
                filter_list.append(media_mapping[media_type])
        
        return filters.create(lambda _, __, m: any(f(m) for f in filter_list))
    
    @classmethod
    def get_bot_info(cls) -> dict:
        """Get bot information for display"""
        return {
            "name": cls.BOT_NAME,
            "max_file_size_gb": cls.MAX_FILE_SIZE / (1024 * 1024 * 1024),
            "supported_formats": cls.SUPPORTED_FORMATS,
            "owner_id": cls.OWNER_ID,
            "storage_channel_id": cls.STORAGE_CHANNEL_ID,
            "features": {
                "stats": cls.ENABLE_STATS,
                "broadcast": cls.ENABLE_BROADCAST,
                "file_preview": cls.ENABLE_FILE_PREVIEW
            }
        }


class DevelopmentConfig(Config):
    """Development-specific configuration"""
    def __init__(self):
        self.ENABLE_DEBUG_LOGGING = True
        self.LOG_LEVEL = logging.DEBUG
        self.ENABLE_BROADCAST = True  # Enable in development for testing


class ProductionConfig(Config):
    """Production-specific configuration"""
    def __init__(self):
        self.ENABLE_DEBUG_LOGGING = False
        self.LOG_LEVEL = logging.INFO
        self.ENABLE_BROADCAST = False  # Disable in production for security


def get_config(env: str = os.getenv("ENVIRONMENT", "production")) -> Config:
    """Get configuration based on environment"""
    if env.lower() == "development":
        return DevelopmentConfig()
    else:
        return ProductionConfig()


# Global config instance
config = get_config()
# In config.py, update the get_supported_media_filters method:

@classmethod
def get_supported_media_filters(cls):
    """Get Pyrogram filters for supported media types"""
    from pyrogram import filters
    
    # Create individual filters for each supported media type
    media_filters = []
    
    if "document" in cls.SUPPORTED_FORMATS:
        media_filters.append(filters.document)
    if "video" in cls.SUPPORTED_FORMATS:
        media_filters.append(filters.video)
    if "audio" in cls.SUPPORTED_FORMATS:
        media_filters.append(filters.audio)
    if "photo" in cls.SUPPORTED_FORMATS:
        media_filters.append(filters.photo)
    if "voice" in cls.SUPPORTED_FORMATS:
        media_filters.append(filters.voice)
    if "sticker" in cls.SUPPORTED_FORMATS:
        media_filters.append(filters.sticker)
    if "animation" in cls.SUPPORTED_FORMATS:
        media_filters.append(filters.animation)
    
    # Combine all filters with OR logic
    if media_filters:
        return filters.create(lambda _, __, m: any(f(m) for f in media_filters))
    else:
        return filters.create(lambda _, __, m: False)
