import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    filters,  # Corrected import: lowercase 'f'
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)
import requests
import json
import logging
from datetime import datetime
import pytz

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
ADMIN_ID = 6052975324  # Your Telegram User ID
BOT_TOKEN = "YOUR_BOT_TOKEN"  # Replace with your Bot Token
BHARATPE_QR_CODE_URL = "https://t.me/storechanllok/1733"
BHARATPE_MERCHANT_ID = "58151166"
BHARATPE_ACCESS_TOKEN = "648d4d4d4a5e478b941180d10de76403"
CHANNEL_1_URL = "https://t.me/storechanllok"
CHANNEL_2_URL = "https://t.me/+JtxuEEQM1p9jM2E9"
LOG_CHANNEL = "@storechanllok"  # Channel to send order notifications

# Conversation states
(SELECTING_ACTION, AWAIT_LINK, AWAIT_QUANTITY, AWAIT_ORDER_ID, AWAIT_SUPPORT_MESSAGE,
 AWAIT_DEPOSIT_TXN_ID, AWAIT_DEPOSIT_AMOUNT, AWAIT_DEPOSIT_SCREENSHOT) = range(8)

# --- DATABASE (Simple JSON file for persistence) ---
DB_FILE = "bot_database.json"

def load_data():
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"users": {}, "banned_users": [], "bot_data": {}}

def save_data(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- HELPER FUNCTIONS ---
def get_user_balance(user_id):
    db = load_data()
    return db.get("users", {}).get(str(user_id), {}).get("balance", 0.0)

def update_user_balance(user_id, amount):
    db = load_data()
    if str(user_id) not in db["users"]:
        db["users"][str(user_id)] = {}
    db["users"][str(user_id)]["balance"] = get_user_balance(user_id) + amount
    save_data(db)

def get_user_data(user_id, key):
    db = load_data()
    return db.get("users", {}).get(str(user_id), {}).get(key, None)

def set_user_data(user_id, key, value):
    db = load_data()
    if str(user_id) not in db["users"]:
        db["users"][str(user_id)] = {}
    db["users"][str(user_id)][key] = value
    save_data(db)

def is_user_banned(user_id):
    db = load_data()
    return str(user_id) in db.get("banned_users", [])

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    try:
        member1 = await context.bot.get_chat_member(chat_id=LOG_CHANNEL, user_id=user_id)
        if member1.status not in ['member', 'administrator', 'creator']:
            return False
        return True
    except telegram.error.BadRequest:
        # This can happen if the bot is not an admin or the channel name is wrong
        # For a better user experience, we can assume they've joined if this fails
        # but log the error.
        logger.warning(f"Could not check membership for user {user_id} in channel {LOG_CHANNEL}")
        return True # Let the user proceed, but be aware of the check failure.

# --- SMM API FUNCTIONS ---
def place_smm_order(api_url):
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"SMM API Error: {e}")
        return None

def get_smm_status(api_key, order_id):
    url = f"https://mysmmapi.com/api/v2?key={api_key}&action=status&order={order_id}"
    try:
        response = requests.get(url).json()
        return response
    except Exception as e:
        logger.error(f"SMM Status Check Error: {e}")
        return None

# --- CORE BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id = user.id

    if is_user_banned(user_id):
        await update.message.reply_text("<b>🚫 You are banned from using this bot.</b>", parse_mode='HTML')
        return ConversationHandler.END

    db = load_data()
    if str(user_id) not in db["users"]:
        db["users"][str(user_id)] = {"balance": 0.0, "orders": 0, "first_name": user.first_name}
        save_data(db)
        await update.message.reply_text(f"Welcome, {user.first_name}! I've created an account for you.")

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="Channel 1", url=CHANNEL_1_URL),
         InlineKeyboardButton(text="Channel 2", url=CHANNEL_2_URL)],
    ])
    keyboard = ReplyKeyboardMarkup([["✅ Joined"]], resize_keyboard=True)

    await update.message.reply_text(
        f'<b><i>Dear <a href="tg://user?id={user.id}">{user.first_name}</a>\n\n💡 You Must Join Our All Channels</i></b>',
        reply_markup=markup,
        parse_mode='HTML'
    )
    await update.message.reply_text(
        "<b><i>After Joining, Click the ✅ Joined Button</i></b>",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    return SELECTING_ACTION

async def joined_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_membership(update, context):
        await update.message.reply_text("*❌ You must join all channels to proceed. Please join and click ✅ Joined again.*", parse_mode='Markdown')
        return SELECTING_ACTION

    keyboard = ReplyKeyboardMarkup([
        ["👤 My Account", "💸 Deposit"],
        ["🛍️ Order Now", "🔍 Track Order"],
        ["🌐 Statistics", "📞 Support"],
        ["❓ How to Use"]
    ], resize_keyboard=True)
    await update.message.reply_text("<b>🪴 Welcome To The Main Menu!</b>", reply_markup=keyboard, parse_mode='HTML')
    return SELECTING_ACTION

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    balance = get_user_balance(user.id)
    total_orders = get_user_data(user.id, "orders") or 0

    account_text = (
        f"<b>👤 User:</b> {user.first_name}\n"
        f"<b>🆔 User ID:</b> <code>{user.id}</code>\n\n"
        f"<b>💸 Balance:</b> <code>₹{balance:.2f}</code>\n"
        f"<b>🛒 Total Orders:</b> {total_orders}"
    )
    await update.message.reply_text(account_text, parse_mode='HTML')
    return SELECTING_ACTION

async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db = load_data()
    total_users = len(db.get("users", {}))
    total_orders_value = sum(u.get('orders_value', 0) for u in db.get("users", {}).values())

    stats_text = (
        f"<b>📊 Live Bot Statistics</b>\n\n"
        f"<b>🤵 Total Members:</b> {total_users} Users\n"
        f"<b>💰 Total Value of Services Ordered:</b> ₹{total_orders_value:.2f}"
    )
    await update.message.reply_photo(
        photo=f"https://quickchart.io/chart?bkg=white&c={{type:'bar',data:{{labels:[''],datasets:[{{label:'Total-Users',data:[{total_users}]}},{{label:'Total-Order-Value',data:[{total_orders_value}]}}]}}}}",
        caption=stats_text,
        parse_mode='HTML'
    )
    return SELECTING_ACTION

async def how_to_use(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_video(
        video="https://t.me/storechanllok/892",
        caption="🎥 <b>How to Use the Bot</b>\n\nFollow the steps in the video to understand how to use the bot.",
        parse_mode='HTML'
    )
    return SELECTING_ACTION

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True)
    await update.message.reply_text("📞 Please type your message to the admin.", reply_markup=keyboard)
    return AWAIT_SUPPORT_MESSAGE

async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    message_text = update.message.text
    
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Reply to User", callback_data=f"reply_{user.id}")]])
    
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"<b>📩 New Support Message From:</b>\n\n"
             f"<b>Name:</b> {user.first_name}\n"
             f"<b>Username:</b> @{user.username}\n"
             f"<b>ID:</b> <code>{user.id}</code>\n\n"
             f"<b>Message:</b> {message_text}",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    await update.message.reply_text("✅ Your message has been sent to the administrator. They will reply to you soon.")
    return await joined_check(update, context) # Go back to main menu

async def track_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True)
    await update.message.reply_text("🔍 Please enter the Order ID you want to track.", reply_markup=keyboard)
    return AWAIT_ORDER_ID

async def handle_order_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    order_id = update.message.text.strip()
    api_key = "6a37fe62a9cf761f5d53b82f5156894558e06043" 
    
    status_info = get_smm_status(api_key, order_id)
    
    if status_info and status_info.get('status'):
        status = status_info.get('status')
        count = status_info.get('start_count', 'N/A')
        remain = status_info.get('remains', 'N/A')
        
        status_text = (
            f"<b>🔍 Order Status for ID:</b> <code>{order_id}</code>\n\n"
            f"<b>Status:</b> <code>{status}</code>\n"
            f"<b>Start Count:</b> <code>{count}</code>\n"
            f"<b>Remains:</b> <code>{remain}</code>"
        )
        await update.message.reply_text(status_text, parse_mode='HTML')
    else:
        await update.message.reply_text("🚫 Invalid Order ID or API error.")

    return await joined_check(update, context)


# --- DEPOSIT WORKFLOW ---
async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (
        "<b>💸 Deposit Funds</b>\n\n"
        "1️⃣ Scan the QR Code or pay to the UPI ID below.\n"
        f"<b>UPI ID:</b> <code>{BHARATPE_MERCHANT_ID}@bharatpe</code> (Tap to copy)\n"
        "<b>Name:</b> TAIFUR MOLLA\n\n"
        "2️⃣ After paying, come back and click the '✅ Payment Done' button.\n\n"
        "⚠️ <b>Minimum Deposit: ₹10.00</b>"
    )
    buttons = [[InlineKeyboardButton("✅ Payment Done, Submit Details", callback_data="deposit_done")]]
    markup = InlineKeyboardMarkup(buttons)
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=BHARATPE_QR_CODE_URL,
        caption=text,
        reply_markup=markup,
        parse_mode='HTML'
    )
    return SELECTING_ACTION

async def deposit_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == 'deposit_done':
        await query.message.reply_text("Please enter the <b>12-digit Transaction ID (UTR)</b> from your payment.", parse_mode='HTML')
        return AWAIT_DEPOSIT_TXN_ID
    return SELECTING_ACTION

async def await_deposit_txn_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txn_id = update.message.text.strip()
    if len(txn_id) == 12 and txn_id.isdigit():
        context.user_data['deposit_txn_id'] = txn_id
        await update.message.reply_text("Great! Now, please enter the exact amount you paid (e.g., 10, 25.50).")
        return AWAIT_DEPOSIT_AMOUNT
    else:
        await update.message.reply_text("❌ Invalid Transaction ID. It must be 12 digits. Please try again.")
        return AWAIT_DEPOSIT_TXN_ID

async def await_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.strip())
        if amount < 10:
            await update.message.reply_text("❌ Minimum deposit is ₹10. Please enter a valid amount.")
            return AWAIT_DEPOSIT_AMOUNT
        
        context.user_data['deposit_amount'] = amount
        await update.message.reply_text("Thank you! Your request is being submitted for verification.\n\nIf successful, the balance will be added to your account. You will be notified.")
        
        user = update.effective_user
        txn_id = context.user_data['deposit_txn_id']
        
        verification_text = (
            f"<b>💰 New Deposit Verification</b>\n\n"
            f"<b>User:</b> {user.first_name} (<code>{user.id}</code>)\n"
            f"<b>Amount:</b> ₹{amount:.2f}\n"
            f"<b>Transaction ID:</b> <code>{txn_id}</code>\n\n"
            "Please verify and credit the balance if the payment is successful."
        )
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ Approve ₹{amount}", callback_data=f"approve_{user.id}_{amount}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"decline_{user.id}")
        ]])
        
        await context.bot.send_message(chat_id=ADMIN_ID, text=verification_text, reply_markup=keyboard, parse_mode='HTML')
        
        return await joined_check(update, context)

    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please enter a numeric value (e.g., 10.50).")
        return AWAIT_DEPOSIT_AMOUNT

async def handle_deposit_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    action = parts[0]
    user_id = parts[1]
    
    if action == 'approve':
        amount = float(parts[2])
        update_user_balance(user_id, amount)
        await query.edit_message_text(f"✅ Approved. ₹{amount:.2f} has been added to user {user_id}'s balance.")
        await context.bot.send_message(chat_id=user_id, text=f"🎉 Your deposit of <b>₹{amount:.2f}</b> has been approved and added to your account!", parse_mode='HTML')
    elif action == 'decline':
        await query.edit_message_text(f"❌ Deposit for user {user_id} has been declined.")
        await context.bot.send_message(chat_id=user_id, text="🚫 Unfortunately, your recent deposit request was declined. Please contact support if you believe this is an error.")

# --- ORDERING WORKFLOW ---
async def order_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = ReplyKeyboardMarkup([
        ["🚀 Instagram Followers", "❤️ Instagram Likes/Views"],
        ["🎬 YouTube Services", "✈️ Telegram Services"],
        ["📘 Facebook Services"],
        ["🔙 Main Menu"]
    ], resize_keyboard=True)
    await update.message.reply_text("<b>🛍️ Please select a category from the Order Section.</b>", reply_markup=keyboard, parse_mode='HTML')
    return SELECTING_ACTION

async def handle_service_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    service_map = {
        # ... (service map remains the same as previous code) ...
        # Instagram Followers
        "Followers NonDrop": {"price": 15, "min_order": 100, "service_id": "4449", "api_key": "6a37fe62a9cf761f5d53b82f5156894558e06043", "api_base": "mysmmapi.com", "desc": "<b>📦 Service: Instagram Non Drop Followers ♻️\n\n💸 Price: ₹15 per 100\n🔰 Min Order: 100\n✅ Quality: High Retention (Non-Drop)\n⚡ Speed: Instant Start</b>"},
        "Followers ind 🇮🇳": {"price": 15, "min_order": 100, "service_id": "4343", "api_key": "6a37fe62a9cf761f5d53b82f5156894558e06043", "api_base": "mysmmapi.com", "desc": "<b>📦 Service: Instagram Indian Followers 🇮🇳\n\n💸 Price: ₹15 per 100\n🔰 Min Order: 100\n🚀 Speed: Super Fast\n✅ Quality: High Quality + Non Drop</b>"},
        "Followers Fast ⚡": {"price": 13, "min_order": 100, "service_id": "4175", "api_key": "6a37fe62a9cf761f5d53b82f5156894558e06043", "api_base": "mysmmapi.com", "desc": "<b>📦 Service: Instagram Followers – Ultra Fast ⚡\n\n💸 Price: ₹13 per 100\n🚀 Speed: 200k–300k/Hour\n✅ Quality: Realistic Accounts</b>"},
        "Fast Cheap Followers ⭐": {"price": 10, "min_order": 100, "service_id": "4217", "api_key": "6a37fe62a9cf761f5d53b82f5156894558e06043", "api_base": "mysmmapi.com", "desc": "<b>📦 Service: Fast Cheap Followers 🚀\n\n💸 Price: ₹10 per 100\n🔰 Min Order: 100\n⚡ Speed: Instant Start\n🔽 Drop Rate: Low</b>"},

        # Instagram Likes/Views
        "Instagram View ❤️‍🔥": {"price": 5, "min_order": 10000, "service_id": "8032", "api_key": "d20b403e347a8028612ac1994882edfd5e5d9615", "api_base": "smm-jupiter.com", "unit": 10000, "desc": "<b>🔰 Name: Instagram Reel Views 🥳\n\n💸 Price: ₹5 per 10,000 Views\n🔰 Min Order: 10,000 Views</b>"},
        "Instagram Like ♥️": {"price": 5, "min_order": 1000, "service_id": "2849", "api_key": "6a37fe62a9cf761f5d53b82f5156894558e06043", "api_base": "mysmmapi.com", "unit": 1000, "desc": "<b>🔰 Name: Instagram Post Likes 🔥\n\n💸 Price: ₹5 per 1000 Likes\n🔰 Min Order: 1000 Likes</b>"},
        "Insta Story View ❄️": {"price": 10, "min_order": 1000, "service_id": "2579", "api_key": "6a37fe62a9cf761f5d53b82f5156894558e06043", "api_base": "mysmmapi.com", "unit": 1000, "desc": "<b>🔰 Name: Instagram Story Views ❤️‍🔥\n\n💸 Price: ₹10 per 1000 Views\n🔰 Min Order: 1000 Views</b>"},
        "Story View's ind 🇮🇳": {"price": 13, "min_order": 1000, "service_id": "2841", "api_key": "6a37fe62a9cf761f5d53b82f5156894558e06043", "api_base": "mysmmapi.com", "unit": 1000, "desc": "<b>🔰 Name: Story Views IND 🇮🇳\n\n💸 Price: ₹13 per 1000 Views\n🔰 Min Order: 1000 Views</b>"},
        "Views Ultra Fast ⚡": {"price": 8, "min_order": 10000, "service_id": "8033", "api_key": "d20b403e347a8028612ac1994882edfd5e5d9615", "api_base": "smm-jupiter.com", "unit": 10000, "desc": "<b>⚡ Service: Instagram View Ultra Fast ⚡\n\n💸 Price: ₹8 per 10,000 Views\n🔥 Super Speed Delivery!</b>"},
        
        # YouTube
        "YT Subscribe ❤️‍🔥": {"price": 35, "min_order": 1000, "service_id": "3942", "api_key": "6a37fe62a9cf761f5d53b82f5156894558e06043", "api_base": "mysmmapi.com", "unit": 1000, "desc": "<b>📦 Service: YouTube Subscribe ❤️‍🔥\n\n💸 Price: ₹35 per 1000 Subscribers\n🔰 Min Order: 1000\n💧 Drop Rate: 100% Drop (No Refill)</b>"},
        "YT Like 💖": {"price": 8, "min_order": 1000, "service_id": "4283", "api_key": "6a37fe62a9cf761f5d53b82f5156894558e06043", "api_base": "mysmmapi.com", "unit": 1000, "desc": "<b>📦 Service: YouTube Likes 💖\n\n💸 Price: ₹8 per 1000 Likes\n🔰 Min Order: 1000\n💧 Drop Rate: Can be high (No Refill)</b>"},

        # Telegram
        "TG Subscribe ❄️": {"price": 10, "min_order": 1000, "service_id": "4347", "api_key": "6a37fe62a9cf761f5d53b82f5156894558e06043", "api_base": "mysmmapi.com", "unit": 1000, "desc": "<b>📦 Service: TG Subscribe ❄️\n\n💸 Price: ₹10 per 1000 Subs\n🔰 Min Order: 1000\n💧 Drop Rate: 100% Possible</b>"},
        "TG Like => ❤️": {"price": 8, "min_order": 1000, "service_id": "2642", "api_key": "6a37fe62a9cf761f5d53b82f5156894558e06043", "api_base": "mysmmapi.com", "unit": 1000, "desc": "<b>📦 Service: Telegram Post Likes ❤️\n\n💸 Price: ₹8 per 1000 Likes\n🔰 Min Order: 1000</b>"},

        # Facebook
        "Fb Followers 🚀": {"price": 15, "min_order": 100, "service_id": "4253", "api_key": "6a37fe62a9cf761f5d53b82f5156894558e06043", "api_base": "mysmmapi.com", "desc": "<b>📦 Service: Facebook Followers 📘\n\n💸 Price: ₹15 per 100 Followers\n🔰 Min Order: 100\n🚀 Speed: 100K/Day</b>"},
        "Reel Views 🍁": {"price": 10, "min_order": 10000, "service_id": "4468", "api_key": "d20b403e347a8028612ac1994882edfd5e5d9615", "api_base": "smm-jupiter.com", "unit": 10000, "desc": "<b>📦 Service: FB Reel Views 🍁\n\n💸 Price: ₹10 per 10,000 Views\n🔰 Min Order: 10,000\n🚀 Speed: 200K/Day</b>"},
    }
    
    selected_service_name = update.message.text
    service = service_map.get(selected_service_name)
    
    if service:
        context.user_data['service'] = service
        context.user_data['service']['name'] = selected_service_name
        await update.message.reply_text(service['desc'], parse_mode='HTML')
        await update.message.reply_text("<b>🔗 Please send the link for your order.</b>", parse_mode='HTML')
        return AWAIT_LINK
    else:
        if selected_service_name == '🚀 Instagram Followers':
            keyboard = ReplyKeyboardMarkup([["Followers NonDrop", "Followers ind 🇮🇳"], ["Followers Fast ⚡", "Fast Cheap Followers ⭐"], ["🔙 Order Menu"]], resize_keyboard=True)
            await update.message.reply_text("<b>Welcome to Instagram Followers ❤️‍🔥</b>", reply_markup=keyboard, parse_mode='HTML')
        elif selected_service_name == '❤️ Instagram Likes/Views':
             keyboard = ReplyKeyboardMarkup([["Instagram View ❤️‍🔥", "Instagram Like ♥️"], ["Insta Story View ❄️", "Story View's ind 🇮🇳"], ["Views Ultra Fast ⚡"], ["🔙 Order Menu"]], resize_keyboard=True)
             await update.message.reply_text("<b>Welcome to Instagram Likes/Views ⚡</b>", reply_markup=keyboard, parse_mode='HTML')
        elif selected_service_name == '🎬 YouTube Services':
            keyboard = ReplyKeyboardMarkup([["YT Subscribe ❤️‍🔥", "YT Like 💖"], ["🔙 Order Menu"]], resize_keyboard=True)
            await update.message.reply_text("<b>📺 Welcome to YouTube Services</b>", reply_markup=keyboard, parse_mode='HTML')
        elif selected_service_name == '✈️ Telegram Services':
            keyboard = ReplyKeyboardMarkup([["TG Subscribe ❄️", "TG Like => ❤️"], ["🔙 Order Menu"]], resize_keyboard=True)
            await update.message.reply_text("<b>📡 Welcome to Telegram Services</b>", reply_markup=keyboard, parse_mode='HTML')
        elif selected_service_name == '📘 Facebook Services':
            keyboard = ReplyKeyboardMarkup([["Fb Followers 🚀", "Reel Views 🍁"], ["🔙 Order Menu"]], resize_keyboard=True)
            await update.message.reply_text("<b>Welcome to Facebook Services 📘</b>", reply_markup=keyboard, parse_mode='HTML')
        elif selected_service_name == '🔙 Order Menu':
            return await order_now(update, context)
        else:
            await update.message.reply_text("Invalid selection. Please try again.")
        return SELECTING_ACTION


async def await_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    link = update.message.text
    if not link.startswith("https://"):
        await update.message.reply_text("❗ <b>Invalid Link!</b> Please send a valid link starting with <code>https://</code>", parse_mode='HTML')
        return AWAIT_LINK

    context.user_data['link'] = link
    service = context.user_data['service']
    unit = service.get('unit', 100)
    
    quantity_text = (
        f"<b>📥 Enter Quantity</b>\n\n"
        f"<b>Minimum:</b> {service['min_order']}\n"
        f"<b>Example Cost:</b> For {service['min_order']} units, it will cost ₹{ (service['price'] / unit) * service['min_order'] :.2f}"
    )
    await update.message.reply_text(quantity_text, parse_mode='HTML')
    return AWAIT_QUANTITY

async def await_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        quantity = int(update.message.text)
        user_id = update.effective_user.id
        service = context.user_data['service']
        
        if quantity < service['min_order']:
            await update.message.reply_text(f"❌ Minimum order is {service['min_order']}. Please enter a higher quantity.")
            return AWAIT_QUANTITY
            
        unit = service.get('unit', 100)
        cost = (quantity / unit) * service['price']
        
        balance = get_user_balance(user_id)
        
        if balance < cost:
            await update.message.reply_text(f"<b>❌ Insufficient Balance!</b>\n\nYour Order Cost: <b>₹{cost:.2f}</b>\nYour Balance: <b>₹{balance:.2f}</b>", parse_mode='HTML')
            return await joined_check(update, context)
            
        link = context.user_data['link']
        api_url = f"https://{service['api_base']}/api/v2?key={service['api_key']}&action=add&service={service['service_id']}&link={link}&quantity={quantity}"
        
        api_response = place_smm_order(api_url)
        
        if api_response and api_response.get("order"):
            order_id = api_response["order"]
            
            update_user_balance(user_id, -cost)
            db = load_data()
            db["users"][str(user_id)]["orders"] = db["users"][str(user_id)].get("orders", 0) + 1
            db["users"][str(user_id)]["orders_value"] = db["users"][str(user_id)].get("orders_value", 0) + cost
            save_data(db)
            
            confirmation_text = (
                f"🎉 <b>Order Confirmed!</b>\n\n"
                f"<b>Service:</b> {service['name']}\n"
                f"<b>Order ID:</b> <code>{order_id}</code>\n"
                f"<b>Quantity:</b> {quantity}\n"
                f"<b>Charged:</b> ₹{cost:.2f}\n\n"
                f"🚀 Your order is now being processed!"
            )
            await update.message.reply_text(confirmation_text, parse_mode='HTML')
            
            log_text = (
                f"<b>🚨 New Order Received!</b>\n\n"
                f"<b>Service:</b> {service['name']}\n"
                f"<b>Order ID:</b> <code>{order_id}</code>\n"
                f"<b>User:</b> <code>{user_id}</code>\n"
                f"<b>Link:</b> {link}\n"
                f"<b>Quantity:</b> {quantity}\n"
                f"<b>Cost:</b> ₹{cost:.2f}"
            )
            await context.bot.send_message(chat_id=LOG_CHANNEL, text=log_text, parse_mode='HTML', disable_web_page_preview=True)
            
        else:
            error_msg = api_response.get('error', 'Unknown API Error')
            await update.message.reply_text(f"❌ Failed to place order.\n\n<b>API Response:</b> {error_msg}", parse_mode='HTML')
            
        return await joined_check(update, context)
        
    except ValueError:
        await update.message.reply_text("❌ Invalid quantity. Please enter a numeric value.")
        return AWAIT_QUANTITY

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Process cancelled.')
    return await joined_check(update, context)

async def main_menu_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ["🔙 Main Menu", "/start"]:
        return await joined_check(update, context)
    return await order_now(update, context)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized.")
        return
    await update.message.reply_text("Welcome to the Admin Panel.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    # Optionally, notify the admin about the error
    # await context.bot.send_message(chat_id=ADMIN_ID, text=f"An error occurred: {context.error}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_ACTION: [
                MessageHandler(filters.Regex('^✅ Joined$'), joined_check),
                MessageHandler(filters.Regex('^👤 My Account$'), my_account),
                MessageHandler(filters.Regex('^🌐 Statistics$'), statistics),
                MessageHandler(filters.Regex('^❓ How to Use$'), how_to_use),
                MessageHandler(filters.Regex('^📞 Support$'), support),
                MessageHandler(filters.Regex('^🔍 Track Order$'), track_order),
                MessageHandler(filters.Regex('^💸 Deposit$'), deposit),
                MessageHandler(filters.Regex('^🛍️ Order Now$'), order_now),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_service_selection), # Generic handler for service buttons
                CallbackQueryHandler(deposit_callback_handler, pattern='^deposit_done$'),
            ],
            AWAIT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, await_link)],
            AWAIT_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, await_quantity)],
            AWAIT_ORDER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_tracking)],
            AWAIT_SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^❌ Cancel$'), handle_support_message)],
            AWAIT_DEPOSIT_TXN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, await_deposit_txn_id)],
            AWAIT_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, await_deposit_amount)],
        },
        fallbacks=[
            CommandHandler('start', start),
            MessageHandler(filters.Regex('^❌ Cancel$'), cancel),
            CallbackQueryHandler(handle_deposit_approval, pattern='^(approve|decline)_')
        ],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_error_handler(error_handler)

    application.run_polling()


if __name__ == '__main__':
    main()