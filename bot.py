import os
import sqlite3
import requests
import re
from telebot import TeleBot, types
from telebot.util import quick_markup
from datetime import datetime

# Initialize bot
bot = TeleBot(os.environ['TELEGRAM_BOT_TOKEN'])
DB_NAME = "smm_bot.db"

# BharatPe credentials
BHARATPE_API_KEY = "648d4d4d4a5e478b941180d10de76403"
MERCHANT_ID = "58151166"
QR_CODE_URL = "https://t.me/storechanllok/1733"

# Service prices in INR
SERVICE_PRICES = {
    "instagram_views": 0.0008,  # per view
    "instagram_followers": 0.15,  # per follower
    "instagram_story_views": 0.001,  # per view
    "youtube_subscribers": 0.035,  # per subscriber
    "youtube_views": 0.0008,  # per view
    "telegram_members": 0.01,  # per member
    "telegram_likes": 0.0008,  # per like
    "facebook_followers": 0.15,  # per follower
    "facebook_views": 0.0008,  # per view
}

# Database setup
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, 
            balance REAL DEFAULT 0,
            orders INTEGER DEFAULT 0,
            deposits REAL DEFAULT 0,
            referrer_id INTEGER,
            banned BOOLEAN DEFAULT FALSE,
            last_order_service TEXT
        )''')
        
        # Orders table
        c.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service TEXT,
            quantity INTEGER,
            amount REAL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'PENDING'
        )''')
        
        # Transactions table
        c.execute('''CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'PENDING',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Service menu state
        c.execute('''CREATE TABLE IF NOT EXISTS user_state (
            user_id INTEGER PRIMARY KEY,
            current_menu TEXT,
            current_service TEXT,
            service_link TEXT
        )''')
        conn.commit()

# User management
def get_user(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return c.fetchone()

def create_user(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))

def update_balance(user_id, amount):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))

def is_banned(user_id):
    user = get_user(user_id)
    return user and user[5]  # banned field

# State management
def set_user_state(user_id, menu=None, service=None, link=None):
    with sqlite3.connect(DB_NAME) as conn:
        if menu or service or link:
            conn.execute('''INSERT OR REPLACE INTO user_state 
                         (user_id, current_menu, current_service, service_link) 
                         VALUES (?, ?, ?, ?)''',
                         (user_id, menu, service, link))
        else:
            conn.execute("DELETE FROM user_state WHERE user_id = ?", (user_id,))

def get_user_state(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM user_state WHERE user_id = ?", (user_id,))
        return c.fetchone()

# Payment verification
def verify_bharatpe_transaction(transaction_id, amount):
    url = f"https://api.bharatpe.com/verify/{transaction_id}"
    headers = {"Authorization": f"Bearer {BHARATPE_API_KEY}"}
    params = {"merchant_id": MERCHANT_ID, "amount": amount}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        return response.status_code == 200 and response.json().get("status") == "SUCCESS"
    except:
        return False

# =====================
# CORE BOT FUNCTIONALITY
# =====================

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    create_user(user_id)
    
    if is_banned(user_id):
        bot.send_message(user_id, "🚫 You are banned from using this bot")
        return
        
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Channel 1", url="https://t.me/storechanllok"),
        types.InlineKeyboardButton("Channel 2", url="https://t.me/+JtxuEEQM1p9jM2E9")
    )
    
    bot.send_message(
        user_id,
        f"<b>Dear {message.from_user.first_name}</b>\n\n💡 You must join our channels to use this bot:",
        reply_markup=markup,
        parse_mode="HTML"
    )
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("✅ Joined")
    bot.send_message(
        user_id,
        "After joining all channels, click the button below:",
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda msg: msg.text == "✅ Joined")
def joined_handler(message):
    user_id = message.from_user.id
    # In real bot, verify channel membership here
    show_main_menu(user_id)

def show_main_menu(user_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add("👤 My Account", "💸 Deposit")
    keyboard.add("🔍 Track Order", "🛍 Order Now")
    keyboard.add("🌐 Statistics", "📞 Support", "📽 How to Use")
    
    bot.send_message(
        user_id,
        "🪴 Welcome to the main menu. Choose an option:",
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda msg: msg.text == "👤 My Account")
def account_handler(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user:
        response = (
            f"👤 <b>Your Account</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"💰 Balance: ₹{user[1]:.2f}\n"
            f"📦 Total Orders: {user[2]}\n"
            f"💳 Total Deposits: ₹{user[3]:.2f}"
        )
        bot.send_message(user_id, response, parse_mode="HTML")

@bot.message_handler(func=lambda msg: msg.text == "💸 Deposit")
def deposit_handler(message):
    user_id = message.from_user.id
    text = (
        "<b>💸 Deposit Funds</b>\n\n"
        "1. Scan the QR code below or send to UPI ID: <code>7908817900@ibl</code>\n"
        "2. After payment, click 'I Paid' and provide:\n"
        "   - Transaction ID\n"
        "   - Amount sent\n\n"
        "💰 <b>Payment Options</b>\n"
        "▪️ ₹10 = ₹10.00 credit\n"
        "▪️ ₹25 = ₹25.00 credit\n"
        "▪️ ₹75 = ₹75.00 credit\n"
        "▪️ Custom amounts supported"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("I Paid ✅", callback_data="deposit_paid"))
    
    bot.send_photo(
        user_id,
        photo=QR_CODE_URL,
        caption=text,
        reply_markup=markup,
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: call.data == "deposit_paid")
def paid_handler(call):
    bot.send_message(
        call.message.chat.id,
        "🔢 Send your payment details in this format:\n<code>TXN123456 50.00</code>\n\n"
        "Replace with your actual Transaction ID and amount",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(call.message, process_payment)

def process_payment(message):
    user_id = message.from_user.id
    try:
        parts = message.text.split()
        if len(parts) < 2:
            raise ValueError
        
        transaction_id = parts[0]
        amount = float(parts[1])
        
        if verify_bharatpe_transaction(transaction_id, amount):
            update_balance(user_id, amount)
            
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(
                    "INSERT INTO transactions (id, user_id, amount, status) VALUES (?, ?, ?, 'COMPLETED')",
                    (transaction_id, user_id, amount)
                )
                conn.execute(
                    "UPDATE users SET deposits = deposits + ? WHERE id = ?",
                    (amount, user_id)
                )
            
            bot.send_message(
                user_id,
                f"✅ Deposit successful! ₹{amount:.2f} added to your account."
            )
            show_main_menu(user_id)
        else:
            bot.send_message(
                user_id,
                "❌ Payment verification failed. Please contact support."
            )
    except:
        bot.send_message(
            user_id,
            "❌ Invalid format. Please try again or contact support."
        )

@bot.message_handler(func=lambda msg: msg.text == "🛍 Order Now")
def order_now_handler(message):
    user_id = message.from_user.id
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add("🚀 Followers", "🔥 Instagram")
    keyboard.add("Facebook 💠", "Youtube✨")
    keyboard.add("Telegram 🍁", "🔙 Back")
    
    bot.send_message(
        user_id,
        "📡 Welcome to Order Section Services ⚡",
        reply_markup=keyboard
    )

# Instagram Services
@bot.message_handler(func=lambda msg: msg.text == "🔥 Instagram")
def instagram_handler(message):
    user_id = message.from_user.id
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add("Instagram View ❤️‍🔥", "Instagram Like ♥️")
    keyboard.add("Insta Story View ❄️", "Story View's ind 🇮🇳")
    keyboard.add("1 Lakh View's ♻️", "Views Ultra Fast ⚡")
    keyboard.add("🔙 Back")
    
    bot.send_message(
        user_id,
        "📺 Welcome to Instagram Services",
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda msg: msg.text == "Views Ultra Fast ⚡")
def insta_ultra_views(message):
    user_id = message.from_user.id
    set_user_state(user_id, service="insta_ultra_views")
    
    bot.send_message(
        user_id,
        "<b>⚡ Service: Instagram View Ultra Fast</b>\n\n"
        "💸 Price: ₹8 = 10,000 Views\n"
        "🔢 Min/Max: 10,000 • Unlimited\n\n"
        "📑 Description:\n"
        "🔥 Super Speed Delivery in Seconds\n"
        "🚀 100% Real & Instant Start\n"
        "⚙️ Fully Automated - One Click Order\n"
        "📈 Boost Your Reel/Post Views Instantly\n\n"
        "📞 Support: 7908817900",
        parse_mode="HTML"
    )
    
    bot.send_message(user_id, "<b>📎 Send Instagram Post Link</b>", parse_mode="HTML")

@bot.message_handler(func=lambda msg: get_user_state(msg.from_user.id) and 
                    get_user_state(msg.from_user.id)[3] == "insta_ultra_views" and
                    msg.text.startswith("http"))
def handle_insta_link(message):
    user_id = message.from_user.id
    link = message.text
    set_user_state(user_id, link=link)
    
    bot.send_message(
        user_id,
        "<b>📥 Enter Quantity (Min 10,000)</b>\n\n"
        "💡 Examples:\n"
        "• 10,000 = ₹8\n"
        "• 100,000 = ₹80",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda msg: get_user_state(msg.from_user.id) and 
                    get_user_state(msg.from_user.id)[3] == "insta_ultra_views" and
                    msg.text.isdigit())
def handle_insta_quantity(message):
    user_id = message.from_user.id
    quantity = int(message.text)
    state = get_user_state(user_id)
    link = state[4]  # service_link
    
    if quantity < 10000:
        bot.send_message(user_id, "❌ Minimum order is 10,000 views")
        return
        
    cost = (quantity / 10000) * 8
    user = get_user(user_id)
    
    if user[1] < cost:  # Check balance
        bot.send_message(
            user_id,
            f"❌ Insufficient balance. You need ₹{cost:.2f} but have ₹{user[1]:.2f}"
        )
        return
        
    # Place order (in a real bot, integrate with SMM API here)
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT INTO orders (user_id, service, quantity, amount) VALUES (?, ?, ?, ?)",
            (user_id, "Instagram Ultra Fast Views", quantity, cost)
        )
        conn.execute(
            "UPDATE users SET balance = balance - ?, orders = orders + 1 WHERE id = ?",
            (cost, user_id)
        )
    
    bot.send_message(
        user_id,
        f"🎉 Order confirmed!\n\n"
        f"👑 Service: Instagram Ultra Fast Views\n"
        f"🔗 Link: {link}\n"
        f"📦 Quantity: {quantity} views\n"
        f"💰 Charged: ₹{cost:.2f}\n\n"
        f"🚀 Your order is being processed",
        parse_mode="HTML"
    )
    set_user_state(user_id)  # Clear state
    show_main_menu(user_id)

# Repeat similar patterns for other services (YouTube, Telegram, Facebook, etc.)

# YouTube Services
@bot.message_handler(func=lambda msg: msg.text == "Youtube✨")
def youtube_handler(message):
    user_id = message.from_user.id
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add("YT Subscribe ❤️‍🔥", "YT Like 💖")
    keyboard.add("🔙 Back")
    
    bot.send_message(
        user_id,
        "📺 Welcome to YouTube Services",
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda msg: msg.text == "YT Subscribe ❤️‍🔥")
def yt_subscribe(message):
    user_id = message.from_user.id
    set_user_state(user_id, service="yt_subscribe")
    
    bot.send_message(
        user_id,
        "<b>📦 Service: YouTube Subscribe</b>\n\n"
        "💸 Price: ₹35 per 1000 Subscribers\n"
        "🔰 Minimum: 1000 Subs\n"
        "⚡ Speed: Instant - 10K/Hour\n"
        "💧 Drop Rate: 100% Possible\n"
        "📑 Note: Channel must be public\n\n"
        "📞 Support: 7908817900",
        parse_mode="HTML"
    )
    
    bot.send_message(user_id, "<b>🔗 Send YouTube Channel Link</b>", parse_mode="HTML")

# Telegram Services
@bot.message_handler(func=lambda msg: msg.text == "Telegram 🍁")
def telegram_handler(message):
    user_id = message.from_user.id
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add("TG Subscribe ❄️", "TG Like => ❤️")
    keyboard.add("🔙 Back")
    
    bot.send_message(
        user_id,
        "📡 Welcome to Telegram Services",
        reply_markup=keyboard
    )

# Facebook Services
@bot.message_handler(func=lambda msg: msg.text == "Facebook 💠")
def facebook_handler(message):
    user_id = message.from_user.id
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add("Fb Followers 🚀", "Reel Views 🍁")
    keyboard.add("🔙 Back")
    
    bot.send_message(
        user_id,
        "📘 Welcome to Facebook Services",
        reply_markup=keyboard
    )

# Back button handler
@bot.message_handler(func=lambda msg: msg.text == "🔙 Back")
def back_handler(message):
    show_main_menu(message.from_user.id)

# Track order handler
@bot.message_handler(func=lambda msg: msg.text == "🔍 Track Order")
def track_order(message):
    user_id = message.from_user.id
    bot.send_message(
        user_id,
        "🔍 Send your Order ID to check status:",
        reply_markup=types.ForceReply()
    )

@bot.message_handler(func=lambda msg: msg.reply_to_message and 
                    msg.reply_to_message.text == "🔍 Send your Order ID to check status:")
def handle_track_order(message):
    user_id = message.from_user.id
    order_id = message.text.strip()
    
    # In a real bot, fetch order status from database
    bot.send_message(
        user_id,
        f"🔄 Checking status for order: {order_id}\n\n"
        "✅ Status: Completed\n"
        "📦 Service: Instagram Followers\n"
        "🔢 Quantity: 1000\n"
        "📅 Date: 2023-08-15",
        parse_mode="HTML"
    )

# Support handler
@bot.message_handler(func=lambda msg: msg.text == "📞 Support")
def support_handler(message):
    user_id = message.from_user.id
    bot.send_message(
        user_id,
        "📞 Contact our support team at @mixy_ox or call 7908817900",
        reply_markup=types.ReplyKeyboardRemove()
    )

# How to use handler
@bot.message_handler(func=lambda msg: msg.text == "📽 How to Use")
def how_to_use_handler(message):
    user_id = message.from_user.id
    bot.send_video(
        user_id,
        video="https://t.me/storechanllok/892",
        caption="🎥 How to Use the Bot\n\nFollow the steps in the video to use all features",
        parse_mode="HTML"
    )

# Admin commands (for your user ID only)
@bot.message_handler(commands=['admin'], func=lambda msg: msg.from_user.id == 6052975324)
def admin_panel(message):
    markup = quick_markup({
        'Add Balance': {'callback_data': 'admin_add_balance'},
        'Ban User': {'callback_data': 'admin_ban_user'},
        'Unban User': {'callback_data': 'admin_unban_user'},
        'Broadcast': {'callback_data': 'admin_broadcast'}
    }, row_width=2)
    
    bot.send_message(message.chat.id, "👑 Admin Panel", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback(call):
    if call.data == 'admin_add_balance':
        bot.send_message(call.message.chat.id, "Send user ID and amount: <code>USERID AMOUNT</code>", parse_mode="HTML")
        bot.register_next_step_handler(call.message, admin_add_balance)
    elif call.data == 'admin_ban_user':
        bot.send_message(call.message.chat.id, "Send user ID to ban:")
        bot.register_next_step_handler(call.message, admin_ban_user)
    # Implement other admin functions similarly

def admin_add_balance(message):
    try:
        parts = message.text.split()
        user_id = int(parts[0])
        amount = float(parts[1])
        
        update_balance(user_id, amount)
        bot.send_message(
            message.chat.id,
            f"✅ Added ₹{amount:.2f} to user {user_id}'s balance"
        )
    except:
        bot.send_message(message.chat.id, "❌ Invalid format. Use: USERID AMOUNT")

def admin_ban_user(message):
    try:
        user_id = int(message.text)
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("UPDATE users SET banned = TRUE WHERE id = ?", (user_id,))
        bot.send_message(message.chat.id, f"✅ Banned user {user_id}")
    except:
        bot.send_message(message.chat.id, "❌ Invalid user ID")

# Run the bot
if __name__ == "__main__":
    init_db()
    print("SMM Bot started...")
    bot.infinity_polling()
