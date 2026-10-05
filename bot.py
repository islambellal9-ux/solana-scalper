import os
import logging
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==========================================
# 1. خادم الصحة لإرضاء Render (Port Binding)
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Solana Scalper Bot is Live!")

    def log_message(self, format, *args):
        return

def run_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_health_check_server, daemon=True).start()

# ==========================================
# 2. إعدادات التلجرام والـ Logging
# ==========================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8963061526:AAHVEWLqQC6A-Onn9D-UxjjGRyk7LiGHwNQ")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# ==========================================
# 3. وظائف التحليل المحدثة (اختيار المجمع الأكبر)
# ==========================================
def analyze_token(mint_address: str) -> dict:
    result = {
        "score": 0,
        "risks": [],
        "dex_data": {}
    }
    
    # 1. فحص DexScreener وترتيب المجمعات حسب السيولة
    try:
        dex_url = f"https://api.dexscreener.com/latest/dex/tokens/{mint_address}"
        dex_res = requests.get(dex_url, headers=HEADERS, timeout=10).json()
        pairs = dex_res.get("pairs")
        if pairs:
            # اختيار المجمع صاحب أعلى سيولة لتفادي المجمعات الميتة
            best_pair = max(pairs, key=lambda x: x.get("liquidity", {}).get("usd", 0) or 0)
            
            result["dex_data"] = {
                "name": best_pair.get("baseToken", {}).get("name", "N/A"),
                "symbol": best_pair.get("baseToken", {}).get("symbol", "N/A"),
                "price": best_pair.get("priceUsd", "0"),
                "liquidity": best_pair.get("liquidity", {}).get("usd", 0) or 0,
                "mcap": best_pair.get("fdv", 0) or 0,
                "volume5m": best_pair.get("volume", {}).get("m5", 0) or 0,
                "priceChange5m": best_pair.get("priceChange", {}).get("m5", 0) or 0
            }
    except Exception as e:
        logger.error(f"DexScreener Error: {e}")

    # 2. فحص RugCheck
    try:
        rug_url = f"https://api.rugcheck.xyz/v1/tokens/{mint_address}/report/summary"
        rug_res = requests.get(rug_url, headers=HEADERS, timeout=10).json()
        result["score"] = rug_res.get("score", 0)
        
        for risk in rug_res.get("risks", []):
            result["risks"].append(f"• {risk.get('name')}: {risk.get('description')}")
    except Exception as e:
        logger.error(f"RugCheck Error: {e}")

    return result

# ==========================================
# 4. أوامر البوت
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Solana Scalper Bot**\n\n"
        "أرسل عقد العملة (Mint Address) للحصول على أحدث بيانات السيولة والتحليل الحقيقي."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mint_address = update.message.text.strip()
    
    if len(mint_address) < 32 or len(mint_address) > 44:
        await update.message.reply_text("⚠️ يرجى إرسال عقد سولانا صحيح (Contract Address).")
        return

    await update.message.reply_text("🔎 جاري فحص العقد المحدث...")
    
    data = analyze_token(mint_address)
    dex = data["dex_data"]
    score = data["score"]
    
    liquidity = dex.get("liquidity", 0)
    
    # تقييم ديناميكي واقعي
    if liquidity < 5000:
        status = "🔴 سيولة منخفضة جداً"
    elif score > 2000:
        status = "🔴 مخاطرة عالية (Rug Risk)"
    else:
        status = "🟢 نشط وحي"

    msg = (
        f"📊 **تقرير فحص العملة:** {dex.get('name', 'N/A')} ({dex.get('symbol', 'N/A')})\n\n"
        f"💵 **السعر:** ${dex.get('price', '0')}\n"
        f"💧 **السيولة (Liquidity):** ${liquidity:,.2f}\n"
        f"📊 **القيمة السوقية (FDV):** ${dex.get('mcap', 0):,.2f}\n"
        f"📈 **التغير (5 دقائق):** {dex.get('priceChange5m', 0)}%\n"
        f"💸 **الفوليوم (5 دقائق):** ${dex.get('volume5m', 0):,.2f}\n\n"
        f"🛡 **فحص الأمان (RugCheck):** `{score}` ({status})\n"
    )
    
    if data["risks"]:
        msg += "\n⚠️ **المخاطر المكتشفة:**\n" + "\n".join(data["risks"][:5])
        
    await update.message.reply_text(msg, parse_mode="Markdown")

# ==========================================
# 5. تشغيل البوت
# ==========================================
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot started polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
