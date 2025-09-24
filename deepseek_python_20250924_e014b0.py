# Add this simple version at the end as an alternative
def run_simple():
    """Simple version that just runs polling on port 5000"""
    bot = URLShortenerBot(config.BOT_TOKEN)
    
    # Start a simple HTTP server in background to occupy port 5000
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running")
        
        def log_message(self, format, *args):
            pass  # Disable logging
    
    def start_http_server():
        server = HTTPServer(('0.0.0.0', 5000), HealthHandler)
        server.serve_forever()
    
    # Start HTTP server in background thread
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    print("🚀 Bot running on port 5000...")
    bot.run_polling()

# Use this instead of main() if you want the simple approach
# if __name__ == '__main__':
#     run_simple()