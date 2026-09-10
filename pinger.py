import time
import requests

# Yeh link wahi hai jise aap active rakhna chahte hain
URL = "https://tfqdeadlox636-my-telegram-bot.hf.space"

while True:
    try:
        requests.get(URL)
        print(f"Pinged {URL} successfully!")
    except Exception as e:
        print(f"Error pinging: {e}")
    time.sleep(300) # 5 minute
    