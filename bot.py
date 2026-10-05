import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

def check_rugcheck_security(mint_address: str):
    """فحص أمان العقد عبر RugCheck API مع الترويسات لتفادي الحظر"""
    url = f"https://api.rugcheck.xyz/v1/tokens/{mint_address}/report/summary"
    headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'}
    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json()
            score = data.get("score", 0)
            risks = data.get("risks", [])
            
            risk_list = [f"• {r.get('name', 'Risk')}: {r.get('level', 'Warning')}" for r in risks]
            is_safe = score < 1500
            return is_safe, score, risk_list
    except Exception as e:
        print(f"RugCheck Error: {e}")
    return True, 0, ["تعذر جلب بيانات الأمان من RugCheck"]

def analyze_solana_token(mint_address: str):
    """تحليل العقد عبر DexScreener و RugCheck"""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{mint_address}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return "❌ تعذر الاتصال بخوادم التحليل."
        
        data = response.json()
        pairs = data.get("pairs")
        if not pairs:
            return "❌ العقد غير موجود أو لا توجد له سيولة متداولة حالياً."
        
        pair = pairs[0]
        base_token = pair.get("baseToken", {}).get("name", "Unknown")
        symbol = pair.get("baseToken", {}).get("symbol", "TOKEN")
        price_usd = float(pair.get("priceUsd", 0))
        liquidity = float(pair.get("liquidity", {}).get("usd", 0))
        fdv = float(pair.get("fdv", 0))
        volume_m5 = float(pair.get("volume", {}).get("m5", 0))
        price_change_m5 = float(pair.get("priceChange", {}).get("m5", 0))

        # 1. فحص الأمان
        is_safe, rug_score, risk_list = check_rugcheck_security(mint_address)

        # 2. تقييم المخاطر
        score = 50
        warnings = []
        status_flag = "🟢 فرصة محتملة"

        liq_ratio = (liquidity / fdv * 100) if fdv > 0 else 0
        if liq_ratio < 2.0 and fdv > 100000:
            score -= 30
            warnings.append("⚠️ **تنبيه قمة وهمية:** السيولة ضعيفة جداً مقارنة بالمحتوى (احتمال تصريف).")
            status_flag = "🔴 خطر قمة (Top Trap)"

        if price_change_m5 > 80 and volume_m5 > liquidity:
            score -= 20
            warnings.append("⚠️ **انتبه:** صعود حاد جداً، الدخول الآن يعتبر FOMO عالي المخاطر.")
            status_flag = "🟠 دخول متأخر"

        if liquidity > 30000:
            score += 20
        elif liquidity < 5000:
            score -= 25
            warnings.append("⚠️ السيولة منخفضة جداً (أقل من 5,000$).")

        if is_safe:
            score += 15
        else:
            score -= 40
            status_flag = "🚨 HIGH RUG RISK"

        final_score = max(0, min(100, score))

        risks_text = "\n".join(risk_list[:3]) if risk_list else "لا توجد مخاطر حرجة مجدولة."
        warnings_text = "\n".join(warnings) if warnings else "لا توجد تحذيرات هيكلية حادة."

        report = (
            f"🔍 **تقرير فحص العملة:** `{symbol}` ({base_token})\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 **التقييم العام:** `{final_score}/100` | {status_flag}\n\n"
            f"💵 **السعر:** `${price_usd:.8f}`\n"
            f"💧 **السيولة (Liquidity):** `${liquidity:,.0f}`\n"
            f"📊 **القيمة السوقية (FDV):** `${fdv:,.0f}`\n"
            f"📈 **التغير (5 دقائق):** `{price_change_m5}%`\n"
            f"💸 **الفوليوم (5 دقائق):** `${volume_m5:,.0f}`\n\n"
            f"🛡️ **فحص الأمان (RugCheck):**\n"
            f"{risks_text}\n\n"
            f"⚠️️ **التحليل والاستراتيجية:**\n"
            f"{warnings_text}\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        return report

    except Exception as e:
        return f"❌ حدث خطأ أثناء تحليل العقد: {str(e)}"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "مرحباً بك في **Solana Scalper Bot v2.0** 🚀\n\n"
        "أرسل لي **عقد العملة (CA)** لتحليله وفحصه تلقائياً."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) >= 32 and len(text) <= 44 and not text.startswith("/"):
        await update.message.reply_text("⏳ جاري الفحص المتقدم للأمان والسيولة...")
        report = analyze_solana_token(text)
        await update.message.reply_text(report, parse_mode="Markdown")
    else:
        await update.message.reply_text("يرجى إرسال عقد سولانا صحيح (CA).")

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is not set!")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
