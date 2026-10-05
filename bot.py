import os
import logging
import requests
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# التوكن الكامل والصحيح
TELEGRAM_BOT_TOKEN = "8963061526:AAGm3uYv93lvKSPo7GkT2g1sXRdskJlFIYY"

# سيرفر صغير باش Render يعرف بلي البوت شغال وما يعطيش Deploy Failed
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)

def analyze_token(ca: str) -> str:
    url = f"https://api.dexscreener.com/latest/dex/tokens/{ca}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if not data.get("pairs"):
            return "❌ **خطأ:** العقد غير موجود أو لا توجد له سيولة على DEXScreener."
        
        pair = data["pairs"][0]
        base_token = pair.get("baseToken", {}).get("symbol", "UNKNOWN")
        fdv = float(pair.get("fdv", 0)) or float(pair.get("marketCap", 0))
        liquidity = float(pair.get("liquidity", {}).get("usd", 0))
        volume_5m = float(pair.get("volume", {}).get("m5", 0))
        price_change_5m = float(pair.get("priceChange", {}).get("m5", 0))
        
        score = 0
        reasons = []
        
        # 1. السيولة بالنسبة للماركت كاب
        liq_mc_ratio = (liquidity / fdv * 100) if fdv > 0 else 0
        if liq_mc_ratio >= 15:
            score += 35
            reasons.append("✅ سيولة ممتازة بالنسبة للماركت كاب")
        elif liq_mc_ratio >= 8:
            score += 20
            reasons.append("⚠️ سيولة متوسطة")
        else:
            reasons.append("🚨 سيولة ضعيفة جداً (مخاطرة RugPull)")
            
        # 2. فوليوم 5 دقائق
        if fdv > 0 and (volume_5m / fdv) > 0.10:
            score += 35
            reasons.append("🚀 دخول فوليوم قوي في آخر 5 دقائق")
        elif volume_5m > 5000:
            score += 20
            reasons.append("📈 فوليوم مقبول في 5 دقائق")
            
        # 3. حركة السعر
        if price_change_5m > 0:
            score += 30
            reasons.append(f"🟢 السعر صاعد (+{price_change_5m:.1f}% في 5m)")
        else:
            reasons.append(f"🔴 السعر نازل ({price_change_5m:.1f}% في 5m)")
            
        if score >= 75:
            verdict = "🚀 **STRONG BUY / FLY POTENTIAL**"
        elif score >= 50:
            verdict = "⚠️️ **SPECULATIVE / WATCH CLOSELY**"
        else:
            verdict = "🛑 **AVOID / HIGH RISK**"
            
        report = (
            f"🪙 **العملة:** {base_token}\n"
            f"📌 **العقد:** `{ca}`\n\n"
            f"📊 **القرار:** {verdict}\n"
            f"🎯 **النقاط:** `{score} / 100`\n\n"
            f"💰 **Market Cap:** ${fdv:,.0f}\n"
            f"💧 **Liquidity:** ${liquidity:,.0f} ({liq_mc_ratio:.1f}%)\n"
            f"⚡ **Volume (5m):** ${volume_5m:,.0f}\n\n"
            f"🔍 **ملاحظات التحليل:**\n" + "\n".join(reasons)
        )
        return report
        
    except Exception as e:
        return f"❌ حدوث خطأ أثناء جلب البيانات: {str(e)}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) >= 32 and not text.startswith("/"):
        await update.message.reply_text("🔎 جاري جلب البيانات وتحليل المومنتوم...")
        result = analyze_token(text)
        await update.message.reply_text(result, parse_mode="Markdown")
    else:
        await update.message.reply_text("أرسل عنوان عقد العملة (CA) الخاص بـ Solana لكتشاف المومنتوم.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً إسلام! ابعثلي العقد (CA) تاع العملة وراح نعطيك قرار فوري.")

if __name__ == '__main__':
    Thread(target=run_flask).start()
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 البوت يعمل الآن بنجاح...")
    app.run_polling()
