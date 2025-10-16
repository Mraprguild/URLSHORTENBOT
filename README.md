# 🔗 URL Shorten Bot
A simple and fast **Telegram URL Shortener Bot** built with **Python** and **Pyrogram**. This bot shortens long URLs using multiple shortener APIs and returns a compact link instantly.

## 🚀 Features
- Shorten any long URL instantly
- Supports multiple shortening services
- Inline query support
- Fast and lightweight
- Easy to deploy on Render, Railway, Heroku, or VPS

## 🧩 Requirements
- Python 3.9+
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Optional: API keys for custom URL shortener services

## ⚙️ Environment Variables
| Variable | Description |
|-----------|--------------|
| `API_ID` | Your Telegram API ID |
| `API_HASH` | Your Telegram API Hash |
| `BOT_TOKEN` | Telegram Bot Token from @BotFather |
| `SHORTENER_API` | (Optional) Your URL shortener API key |

## 🛠️ Installation
```bash
git clone https://github.com/Mraprguild/URLSHORTENBOT.git
cd URLSHORTENBOT
pip install -r requirements.txt
python bot.py
