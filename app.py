import os
import json
import requests
from fastapi import FastAPI, Request, Response
import uvicorn

# ---------- CONFIGURATION ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
user_states = {}

# ---------- LIVE DATA FETCH FUNCTION ----------
def fetch_api_data(chat_id, text):
    """Bina kisi background task ke, live data fetch karne ka function"""
    cleaned = "".join([c for c in text if c.isdigit()])
    if len(cleaned) < 10:
        return "⚠️ Kam se kam 10-digit ka number bhejo bhai!"

    final_number = cleaned[-10:]
    selected_api = user_states.get(chat_id, "api1")

    # URL Selection
    if selected_api == "api1":
        url = f"https://tfqdeadlo-inddataapi.hf.space/search?mobile={final_number}"
    elif selected_api == "api2":
        url = f"https://tfqdeadlo-850crfastsearch.hf.space/search/{final_number}"
    else:
        url = f"https://tfqdeadlo-1-78bapi.hf.space/search?mobile={final_number}"

    bt = "```"
    try:
        # Live hit to your API (Hugging Face to Hugging Face is very fast)
        response = requests.get(url, timeout=12)
        if response.status_code == 200:
            try:
                data = response.json()
                formatted_json = json.dumps(data, indent=2, ensure_ascii=False)
                return f"✅ **Data Found!**\n\n{bt}json\n{formatted_json}\n{bt}"
            except:
                return f"✅ **Data Found!**\n\n{bt}\n{response.text}\n{bt}"
        else:
            return f"❌ API Error Code: {response.status_code}"
    except Exception as e:
        return f"💥 API Fetch Error: {str(e)}"

# ---------- FASTAPI ENGINE ----------
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "Super Synchronous Bot Engine is Running", "secured": bool(BOT_TOKEN)}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        payload = await request.json()
        
        if "message" not in payload or "text" not in payload["message"]:
            return Response(content=json.dumps({"status": "ignored"}), status_code=200)

        message = payload["message"]
        chat_id = message["chat"]["id"]
        text = message["text"].strip()
        
        reply_payload = {"method": "sendMessage", "chat_id": chat_id}

        # 1. Handle /start Command
        if text == "/start":
            reply_payload.update({
                "text": "👋 Welcome Bhai! Niche keyboard me se koi ek API select karo:",
                "reply_markup": {
                    "keyboard": [[{"text": "1st API"}, {"text": "2nd API"}, {"text": "3rd API"}]],
                    "one_time_keyboard": True,
                    "resize_keyboard": True
                }
            })
            return Response(content=json.dumps(reply_payload), media_type="application/json", status_code=200)

        # 2. Handle API Selection
        elif text in ["1st API", "2nd API", "3rd API"]:
            if text == "1st API":
                user_states[chat_id] = "api1"
            elif text == "2nd API":
                user_states[chat_id] = "api2"
            else:
                user_states[chat_id] = "api3"
                
            reply_payload.update({
                "text": f"Selected: *{text}*\n\n📝 Ab mujhe mobile number bhejo.",
                "parse_mode": "Markdown",
                "reply_markup": {"remove_keyboard": True}
            })
            return Response(content=json.dumps(reply_payload), media_type="application/json", status_code=200)

        # 3. Handle Number Search (Live Synchronous Reply)
        else:
            # Turant live data nikalenge bina kisi external Telegram network call ke
            result_message = fetch_api_data(chat_id, text)
            
            # State clear karenge taaki next time firse selection ho sake
            if chat_id in user_states:
                del user_states[chat_id]
                
            # Direct data response me wrap karke bhej rahe hain
            reply_payload.update({
                "text": result_message,
                "parse_mode": "Markdown",
                "reply_markup": {
                    "keyboard": [[{"text": "1st API"}, {"text": "2nd API"}, {"text": "3rd API"}]],
                    "one_time_keyboard": True,
                    "resize_keyboard": True
                }
            })
            return Response(content=json.dumps(reply_payload), media_type="application/json", status_code=200)

    except Exception as e:
        print(f"🔴 Webhook Fatal Error: {e}")
        return Response(content=json.dumps({"status": "error"}), status_code=200)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
    