import asyncio
import os
import logging
from datetime import datetime, timedelta
import uuid

import asyncpg
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

from aiohttp import web
from aiocryptopay import AioCryptoPay, Networks
from yookassa import Configuration, Payment
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application


from keyboards.inline import *
from utils.crypto import *
from utils.ssh import *

# --- Конфигурация ---
load_dotenv('../.env')
logging.basicConfig(level=logging.INFO)
BOT_TOKEN, ADMIN_ID = os.getenv('BOT_TOKEN'), int(os.getenv('ADMIN_ID'))
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME')
DB_USER, DB_PASS, DB_NAME, DB_HOST, DB_PORT = os.getenv('POSTGRES_USER'), os.getenv('POSTGRES_PASSWORD'), os.getenv('POSTGRES_DB'), os.getenv('DB_HOST'), os.getenv('DB_PORT')
CRYPTO_PAY_TOKEN, YK_SHOP_ID, YK_SECRET_KEY = os.getenv('CRYPTO_PAY_TOKEN'), os.getenv('YK_SHOP_ID'), os.getenv('YK_SECRET_KEY')
BOT_VERSION, VIP_PRICE = "1.7.0-admin", "49₽/месяц" # Версия обновлена
WEB_SERVER_HOST, WEB_SERVER_PORT = "0.0.0.0", 8080

# --- ПУТИ ВЕБХУКОВ ---
WEBHOOK_BASE_URL = "/webhook"
WEBHOOK_TELEGRAM_PATH = f"{WEBHOOK_BASE_URL}/telegram"
WEBHOOK_CRYPTO_PAY_PATH = f"{WEBHOOK_BASE_URL}/cryptopay"
WEBHOOK_YOOKASSA_PATH = f"{WEBHOOK_BASE_URL}/yookassa"


# --- Инициализация ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
db_pool = None
cryptopay = AioCryptoPay(token=CRYPTO_PAY_TOKEN, network=Networks.MAIN_NET)
if YK_SHOP_ID and YK_SECRET_KEY:
    Configuration.configure(YK_SHOP_ID, YK_SECRET_KEY)

# --- FSM Состояния ---
class AddServer(StatesGroup): name,ip,port,login,password = State(),State(),State(),State(),State()
class TerminalSession(StatesGroup): active = State()
class FileManagerSession(StatesGroup): browsing=State(); uploading=State()
class RenameServer(StatesGroup): new_name = State()
class Broadcast(StatesGroup): message = State(); confirmation = State()
class AdminSearchUser(StatesGroup): by_id = State()


# --- Функции БД ---
async def create_db_pool():
    global db_pool
    for i in range(5):
        try:
            db_pool = await asyncpg.create_pool(user=DB_USER, password=DB_PASS, database=DB_NAME, host=DB_HOST, port=DB_PORT, timeout=10)
            logging.info("Пул подключений к базе данных успешно создан"); return
        except Exception as e:
            logging.error(f"Попытка {i+1}/5: Не удалось создать пул подключений к БД: {e}"); await asyncio.sleep(5)

async def get_or_create_user(telegram_id: int, username: str, first_name: str) -> asyncpg.Record:
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        if user: return user
        is_admin = (telegram_id == ADMIN_ID)
        vip_expires = (datetime.now() + timedelta(days=365*100)) if is_admin else None
        return await conn.fetchrow("INSERT INTO users (telegram_id, username, first_name, is_admin, is_vip, vip_expires) VALUES ($1, $2, $3, $4, $5, $6) RETURNING *", telegram_id, username, first_name, is_admin, is_admin, vip_expires)

async def get_db_user_id(telegram_id: int) -> int or None:
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", telegram_id)
        return user['id'] if user else None

async def add_server_to_db(user_id: int, data: dict) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute("INSERT INTO servers (user_id, name, ip, port, login_user, password_encrypted) VALUES ($1, $2, $3, $4, $5, $6)", user_id, data['name'], data['ip'], data['port'], data['login'], encrypt_password(data['password']))

async def get_user_servers(user_id: int) -> list:
    async with db_pool.acquire() as conn:
        return await conn.fetch("SELECT id, name FROM servers WHERE user_id = $1 ORDER BY name", user_id)

async def get_server_details(server_id: int, user_id: int) -> asyncpg.Record or None:
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM servers WHERE id = $1 AND user_id = $2", server_id, user_id)

async def delete_server_from_db(server_id: int, user_id: int) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM servers WHERE id = $1 AND user_id = $2", server_id, user_id)

async def update_server_name(server_id: int, user_id: int, new_name: str) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE servers SET name = $1 WHERE id = $2 AND user_id = $3", new_name, server_id, user_id)

async def get_total_users_count() -> int:
    async with db_pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")

async def get_total_servers_count() -> int:
    async with db_pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM servers")

async def create_subscription_record(user_id: int, amount: float, provider: str, invoice_id: str, days: int) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute("INSERT INTO subscriptions (user_id, amount, provider, payment_id, status, duration_days) VALUES ($1, $2, $3, $4, 'pending', $5)", user_id, amount, provider, invoice_id, days)

async def get_all_users_ids() -> list:
    async with db_pool.acquire() as conn:
        return await conn.fetch("SELECT telegram_id FROM users")

async def get_subscription_by_payment_id(payment_id: str) -> asyncpg.Record or None:
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM subscriptions WHERE payment_id = $1", payment_id)

async def mark_subscription_paid(payment_id: str) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE subscriptions SET status = 'paid' WHERE payment_id = $1", payment_id)

async def activate_vip_for_user(user_id: int, days_to_add: int) -> None:
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT is_vip, vip_expires FROM users WHERE id = $1", user_id)
        if not user: return
        start_date = datetime.now()
        if user['is_vip'] and user['vip_expires'] and user['vip_expires'] > start_date:
            start_date = user['vip_expires']
        new_expires_date = start_date + timedelta(days=days_to_add)
        await conn.execute("UPDATE users SET is_vip = TRUE, vip_expires = $1 WHERE id = $2", new_expires_date, user_id)

async def get_user_by_telegram_id(telegram_id: int) -> asyncpg.Record or None:
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)

async def admin_delete_server(server_id: int):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM servers WHERE id = $1", server_id)


# --- Хелперы ---
async def get_welcome_text(user_record: asyncpg.Record) -> str:
    user_name = user_record['username'] or user_record['first_name']
    vip_status = "Бесплатный"
    if user_record['is_vip']:
        expires_delta = (user_record['vip_expires'] - datetime.now()).days if user_record['vip_expires'] else 0
        if expires_delta > 365 * 50: vip_status = "Вечный 👑"
        else: vip_status = f"VIP до {user_record['vip_expires'].strftime('%d.%m.%Y')} 👑"
    rights = "Администратор 🛠️" if user_record['is_admin'] else "Пользователь"
    return (f"🚀 <b>Добро пожаловать в KDS Server Panel!</b>\n\nЭтот бот поможет вам управлять вашими серверами.\n\n"
            f"✅ Подключайте серверы\n✅ Выполняйте команды\n✅ Управляйте файлами\n\n"
            f"👤 <b>Пользователь:</b> {user_name}\n"
            f"🆔 <b>Ваш ID:</b> <code>{user_record['telegram_id']}</code>\n"
            f"🆓 <b>Статус:</b> {vip_status}\n"
            f"🔧 <b>Права:</b> {rights}\n\n"
            f"💬 <b>Поддержка:</b> {SUPPORT_USERNAME}")

async def get_status_message_text(user_record: asyncpg.Record, total_users: int, total_servers: int) -> str:
    now = datetime.now().strftime('%d.%m.%Y %H:%M:%S'); vip_status = "Бесплатный"
    if user_record and user_record['is_vip']:
        expires_delta = (user_record['vip_expires'] - datetime.now()).days if user_record['vip_expires'] else 0
        if expires_delta > 365*50: vip_status = "Вечный"
        else: vip_status = f"VIP до {user_record['vip_expires'].strftime('%d.%m.%Y')}"
    admin_status = "Да" if user_record and user_record['is_admin'] else "Нет"
    reg_date = user_record['created_at'].strftime('%d.%m.%Y %H:%M') if user_record else "н/д"
    return (f"🤖 <b>Статус бота</b>\n\n⏰ <b>Время:</b> {now}\n👥 <b>Пользователи:</b> {total_users}\n🖥️ <b>Серверы:</b> {total_servers}\n"
            f"👑 <b>VIP цена:</b> {VIP_PRICE}\n🎯 <b>Версия:</b> {BOT_VERSION}\n✅ <b>Статус:</b> Работает\n\n"
            f"📊 <b>Ваш профиль:</b>\n• <b>ID:</b> <code>{user_record['telegram_id'] if user_record else 'н/д'}</code>\n"
            f"• <b>Статус:</b> {vip_status}\n• <b>Администратор:</b> {admin_status}\n• <b>Регистрация:</b> {reg_date}")

async def show_found_user_info(message_or_callback, user_tg_id: int):
    user_record = await get_user_by_telegram_id(user_tg_id)
    if not user_record:
        if isinstance(message_or_callback, types.CallbackQuery):
             await message_or_callback.answer("❌ Пользователь с таким ID не найден.", show_alert=True)
             await message_or_callback.message.edit_text("Меню управления пользователями.", reply_markup=admin_users_keyboard())
        else:
             await message_or_callback.answer("❌ Пользователь с таким ID не найден.")
        return

    db_user_id = user_record['id']
    servers = await get_user_servers(db_user_id)

    expires_delta = (user_record['vip_expires'] - datetime.now()).days if user_record['vip_expires'] else 0
    if user_record['is_vip'] and expires_delta > 365 * 50:
        vip_status = "Вечный 👑"
    elif user_record['is_vip']:
        vip_status = f"VIP до {user_record['vip_expires'].strftime('%d.%m.%Y')}"
    else:
        vip_status = "Нет"

    text = (f"👤 <b>Информация о пользователе:</b>\n\n"
            f"<b>TG ID:</b> <code>{user_record['telegram_id']}</code>\n"
            f"<b>Username:</b> @{user_record['username']}\n"
            f"<b>Имя:</b> {user_record['first_name']}\n"
            f"<b>VIP Статус:</b> {vip_status}\n"
            f"<b>Админ:</b> {'Да' if user_record['is_admin'] else 'Нет'}\n"
            f"<b>Дата регистрации:</b> {user_record['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
            f"<b>Серверов добавлено:</b> {len(servers)}")

    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=admin_user_details_keyboard(servers, user_tg_id))
    else:
        await message_or_callback.message.edit_text(text, reply_markup=admin_user_details_keyboard(servers, user_tg_id))


# --- Вебхуки ---
async def yookassa_webhook_handler(request: web.Request) -> web.Response:
    try:
        event_json = await request.json()
        if event_json.get('event') == 'payment.succeeded':
            payment_object = event_json['object']
            sub = await get_subscription_by_payment_id(payment_object['id'])
            if sub and sub['status'] != 'paid':
                user_record = await get_user_by_telegram_id(int(payment_object['metadata']['telegram_id']))
                if user_record:
                    await activate_vip_for_user(sub['user_id'], sub['duration_days'])
                    await mark_subscription_paid(payment_object['id'])
                    await bot.send_message(user_record['telegram_id'], "✅ Оплата через ЮKassa прошла успешно! VIP активирован.")
        return web.Response(status=200)
    except Exception as e:
        logging.error(f"Ошибка в вебхуке ЮKassa: {e}"); return web.Response(status=500)

async def cryptopay_webhook_handler(request: web.Request) -> web.Response:
    try:
        update = await request.json()
        if update.get('update_type') == 'invoice_paid':
            invoice_id = str(update['payload']['invoice_id'])
            sub = await get_subscription_by_payment_id(invoice_id)
            if sub and sub['status'] != 'paid':
                user_telegram_id = await db_pool.fetchval("SELECT telegram_id FROM users WHERE id=$1", sub['user_id'])
                if user_telegram_id:
                    await activate_vip_for_user(sub['user_id'], sub['duration_days'])
                    await mark_subscription_paid(invoice_id)
                    await bot.send_message(user_telegram_id, "✅ Оплата через CryptoPay прошла успешно! VIP активирован.")
        return web.Response(status=200)
    except Exception as e:
        logging.error(f"Ошибка в вебхуке CryptoPay: {e}"); return web.Response(status=500)


# --- Основные обработчики команд и кнопок ---
@dp.message(CommandStart())
async def handle_start(message: types.Message, state: FSMContext):
    await state.clear()
    user = await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(await get_welcome_text(user), reply_markup=main_menu_keyboard(user['is_admin']))

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    total_users, total_servers = await get_total_users_count(), await get_total_servers_count()
    admin_record = await get_user_by_telegram_id(ADMIN_ID)
    if admin_record: await message.answer(await get_status_message_text(admin_record, total_users, total_servers))

@dp.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    if await state.get_state() is not None:
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu_keyboard(message.from_user.id == ADMIN_ID))

@dp.callback_query(F.data == "back_to_main_menu")
async def cq_back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    await callback.message.edit_text(await get_welcome_text(user), reply_markup=main_menu_keyboard(user['is_admin']))
    await callback.answer()

@dp.callback_query(F.data == "list_servers")
async def cq_list_servers(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    db_user_id = await get_db_user_id(callback.from_user.id)
    servers = await get_user_servers(db_user_id)
    await callback.message.edit_text("У вас нет серверов." if not servers else "🖥️ <b>Выберите сервер:</b>", reply_markup=servers_list_keyboard(servers))
    await callback.answer()

@dp.callback_query(F.data == "vip_subscription")
async def cq_vip_subscription(callback: types.CallbackQuery):
    await callback.message.edit_text("👑 <b>VIP-Подписка</b>\n\nVIP-статус открывает доступ к расширенным возможностям и снимает все ограничения.", reply_markup=vip_menu_keyboard())

@dp.callback_query(F.data == "my_vip_status")
async def cq_my_vip_status(callback: types.CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    expires = "никогда" if user['is_vip'] and (user['vip_expires'] - datetime.now()).days > 365*50 else user['vip_expires'].strftime('%d.%m.%Y') if user['is_vip'] else ""
    text = f"✅ Ваш VIP-статус активен.\nСрок окончания: <b>{expires}</b>" if user['is_vip'] else "❌ У вас нет активной VIP-подписки."
    await callback.answer(text, show_alert=True)

@dp.callback_query(F.data == "buy_vip")
async def cq_buy_vip(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите подходящий тариф:", reply_markup=choose_tariff_keyboard())

@dp.callback_query(F.data.startswith("choose_tariff:"))
async def cq_choose_tariff(callback: types.CallbackQuery):
    _, days_str, amount_str = callback.data.split(":")
    await callback.message.edit_text("Выберите удобный способ оплаты:", reply_markup=choose_payment_method_keyboard(int(days_str), float(amount_str)))

@dp.callback_query(F.data.startswith("pay:yookassa:"))
async def cq_pay_yookassa(callback: types.CallbackQuery):
    _, _, days_str, _ = callback.data.split(":")
    days, prices_rub = int(days_str), {30: 49, 90: 129, 180: 199, 365: 349}
    price_rub = prices_rub.get(days, 49)
    await callback.message.edit_text("⏳ Создаю счет в ЮKassa...")
    try:
        db_user_id = await get_db_user_id(callback.from_user.id)
        payment = Payment.create({"amount": {"value": f"{price_rub}.00", "currency": "RUB"}, "confirmation": {"type": "redirect", "return_url": f"https://t.me/{(await bot.get_me()).username}"}, "capture": True, "description": f"VIP подписка на {days} дней", "metadata": {'telegram_id': callback.from_user.id, 'user_id': db_user_id}}, str(uuid.uuid4()))
        await create_subscription_record(db_user_id, price_rub, 'yookassa', payment.id, days)
        await callback.message.edit_text(f"🥝 <b>Счет в ЮKassa создан</b>\n\n<b>Сумма:</b> {price_rub} RUB", reply_markup=payment_keyboard(payment.confirmation.confirmation_url, "yookassa", payment.id))
    except Exception as e:
        logging.error(f"Ошибка создания счета ЮKassa: {e}"); await callback.message.edit_text("❌ Не удалось создать счет.", reply_markup=vip_menu_keyboard())

@dp.callback_query(F.data.startswith("pay:cryptobot:"))
async def cq_pay_cryptobot(callback: types.CallbackQuery):
    _, _, days_str, amount_str = callback.data.split(":"); days, amount = int(days_str), float(amount_str)
    await callback.message.edit_text("⏳ Создаю счет в CryptoPay...")
    try:
        invoice = await cryptopay.create_invoice(asset='USDT', amount=amount, description=f"VIP на {days} дней", expires_in=900)
        db_user_id = await get_db_user_id(callback.from_user.id)
        await create_subscription_record(db_user_id, amount, 'cryptopay', str(invoice.invoice_id), days)
        await callback.message.edit_text(f"🤖 <b>Счет в CryptoPay создан</b>\n\n<b>Сумма:</b> {amount} USDT", reply_markup=payment_keyboard(invoice.bot_invoice_url, "cryptopay", str(invoice.invoice_id)))
    except Exception as e:
        logging.error(f"Ошибка создания счета CryptoPay: {e}"); await callback.message.edit_text("❌ Не удалось создать счет.", reply_markup=vip_menu_keyboard())

@dp.callback_query(F.data.startswith("check_payment:yookassa:"))
async def cq_check_yookassa_payment(callback: types.CallbackQuery):
    payment_id = callback.data.split(":")[2]
    try:
        payment_info = Payment.find_one(payment_id)
        if payment_info.status == 'succeeded':
            await callback.answer("✅ Оплата прошла успешно! VIP уже должен быть активирован через вебхук.", show_alert=True)
            await cq_vip_subscription(callback)
        else: await callback.answer(f"Статус платежа: {payment_info.status}", show_alert=True)
    except Exception as e:
        logging.error(f"Ошибка проверки платежа ЮKassa: {e}"); await callback.answer("Не удалось проверить платеж.", show_alert=True)

@dp.callback_query(F.data.startswith("check_payment:cryptopay:"))
async def cq_check_cryptopay_payment(callback: types.CallbackQuery):
    invoice_id_str = callback.data.split(":")[2]
    try: invoice_id_int = int(invoice_id_str)
    except ValueError: await callback.answer("Неверный формат ID счета.", show_alert=True); return
    invoices = await cryptopay.get_invoices(invoice_ids=[invoice_id_int])
    if invoices and invoices[0].status == 'paid':
        sub = await get_subscription_by_payment_id(invoice_id_str)
        if sub and sub['status'] != 'paid':
            await activate_vip_for_user(sub['user_id'], sub['duration_days']); await mark_subscription_paid(invoice_id_str)
            user = await get_user_by_telegram_id(callback.from_user.id)
            await bot.send_message(user['telegram_id'], "✅ Оплата прошла успешно! Ваш VIP-статус активирован."); await cq_vip_subscription(callback)
        else: await callback.answer("✅ Оплата уже была обработана.", show_alert=True)
    else: await callback.answer("Платеж еще не получен.", show_alert=True)

@dp.callback_query(F.data.startswith("add_server"))
async def cq_add_server(callback: types.CallbackQuery, state: FSMContext): await callback.message.edit_text("Начинаем...\nДля отмены в любой момент введите /cancel\n\n<b>Шаг 1: Название сервера</b>"); await state.set_state(AddServer.name)
@dp.message(AddServer.name)
async def process_name(m: types.Message, s: FSMContext): await s.update_data(name=m.text); await m.answer("<b>Шаг 2: IP-адрес</b>"); await s.set_state(AddServer.ip)
@dp.message(AddServer.ip)
async def process_ip(m: types.Message, s: FSMContext): await s.update_data(ip=m.text); await m.answer("<b>Шаг 3: SSH Порт (обычно 22)</b>"); await s.set_state(AddServer.port)
@dp.message(AddServer.port)
async def process_port(m: types.Message, s: FSMContext):
    if not m.text.isdigit(): await m.answer("Порт должен быть числом."); return
    await s.update_data(port=int(m.text)); await m.answer("<b>Шаг 4: Логин (например, root)</b>"); await s.set_state(AddServer.login)
@dp.message(AddServer.login)
async def process_login(m: types.Message, s: FSMContext): await s.update_data(login=m.text); await m.answer("<b>Шаг 5: Пароль (сообщение будет удалено)</b>"); await s.set_state(AddServer.password)
@dp.message(AddServer.password)
async def process_password(m: types.Message, s: FSMContext):
    data = await s.update_data(password=m.text); await m.delete(); msg = await m.answer("⏳ Проверяю SSH-подключение...")
    is_conn, status = await check_ssh_connection(data['ip'], data['port'], data['login'], data['password'])
    if not is_conn: await msg.edit_text(f"❌ <b>Ошибка подключения:</b> {status}.\n\nПроверьте данные и попробуйте добавить сервер заново."); await s.clear(); return
    try: user_id = await get_db_user_id(m.from_user.id); await add_server_to_db(user_id, data); servers = await get_user_servers(user_id); await msg.edit_text(f"✅ Сервер <b>'{data['name']}'</b> успешно добавлен!", reply_markup=servers_list_keyboard(servers))
    except Exception as e: logging.error(f"Ошибка сохранения сервера в БД: {e}"); await msg.edit_text("❌ Произошла ошибка при сохранении сервера в базу данных.")
    await s.clear()

@dp.callback_query(F.data.startswith("manage_server:"))
async def cq_manage_server(callback: types.CallbackQuery, state: FSMContext):
    await state.clear(); server_id = int(callback.data.split(":")[1]); db_user_id = await get_db_user_id(callback.from_user.id)
    if not db_user_id: await callback.answer("Ошибка: не удалось определить пользователя.", show_alert=True); return
    server = await get_server_details(server_id, db_user_id)
    if not server: await callback.answer("Сервер не найден или у вас нет к нему доступа.", show_alert=True); return
    await callback.message.edit_text(f"⏳ Получаю информацию о сервере <b>{server['name']}</b>...")
    try: password = decrypt_password(server['password_encrypted']); success, info = await get_system_info(server['ip'], server['port'], server['login_user'], password)
    except Exception as e: logging.error(f"Ошибка проверки статуса сервера {server_id}: {e}"); success, info = False, {'status': '🔴 Ошибка', 'uptime': 'н/д'}
    created_date = server['created_at'].strftime('%d.%m.%Y %H:%M')
    text = (f"<b>{server['name']}</b>\n\n<b>IP:</b> <code>{server['ip']}:{server['port']}</code>\n<b>Пользователь:</b> <code>{server['login_user']}</code>\n<b>Статус:</b> {info['status']} | <b>Uptime:</b> {info['uptime']}\n<b>Добавлен:</b> {created_date}")
    await callback.message.edit_text(text, reply_markup=server_management_keyboard(server_id)); await callback.answer()

@dp.callback_query(F.data.startswith("terminal:"))
async def cq_terminal(c: types.CallbackQuery, s: FSMContext): sid = int(c.data.split(":")[1]); await s.set_state(TerminalSession.active); await s.update_data(server_id=sid); await c.message.edit_text("🖥️ <b>Терминал.</b> Введите команду. Для выхода введите /exit"); await c.answer()

@dp.message(TerminalSession.active, Command("exit"))
async def terminal_exit(m: types.Message, s: FSMContext): await s.clear(); await m.answer("Выход из терминала.", reply_markup=main_menu_keyboard(m.from_user.id == ADMIN_ID))
@dp.message(TerminalSession.active)
async def terminal_command_handler(m: types.Message, s: FSMContext):
    cmd = m.text; COMMAND_BLACKLIST = ["reboot", "shutdown", "rm ", "mkfs", "dd ", "fdisk", "mv "];
    if any(b in cmd.lower() for b in COMMAND_BLACKLIST): await m.answer(f"❌ <b>Опасная команда!</b> Используйте кнопки в настройках сервера для перезагрузки/выключения."); return
    data = await s.get_data(); sid = data.get("server_id"); uid = await get_db_user_id(m.from_user.id)
    if not uid: await m.answer("Ошибка: не удалось определить пользователя."); return
    srv = await get_server_details(sid, uid)
    if not srv: await m.answer("Сервер не найден."); await s.clear(); return
    msg = await m.answer(f"⏳ Выполняю: <code>{cmd}</code>")
    try: password = decrypt_password(srv['password_encrypted'])
    except Exception: await msg.edit_text("❌ Ошибка расшифровки пароля."); await s.clear(); return
    success, output = await execute_command(srv['ip'], srv['port'], srv['login_user'], password, cmd)
    if len(output) > 4000: output = output[:4000] + "\n..."
    await msg.edit_text(f"<b>Результат:</b>\n<pre>{output}</pre>")

@dp.callback_query(F.data.startswith("fm_enter:"))
async def cq_fm_enter(c: types.CallbackQuery,s: FSMContext): _, sid, path = c.data.split(":", 2); await s.set_state(FileManagerSession.browsing); await s.update_data(server_id=int(sid), current_path=path); await show_files(c, int(sid), path)
@dp.callback_query(F.data.startswith("fm_nav:"))
async def cq_fm_nav(c: types.CallbackQuery,s: FSMContext): _, sid, path = c.data.split(":", 2); await s.update_data(current_path=path); await show_files(c, int(sid), path)

async def show_files(cb_or_msg: types.CallbackQuery | types.Message, server_id: int, path: str):
    is_msg = isinstance(cb_or_msg, types.Message); uid = cb_or_msg.from_user.id; edit_func = cb_or_msg.answer if is_msg else cb_or_msg.message.edit_text
    if not is_msg: await cb_or_msg.message.edit_text(f"⏳ Загружаю содержимое: <code>{path}</code>")
    db_uid = await get_db_user_id(uid)
    if not db_uid: await edit_func("Ошибка: не удалось определить пользователя."); return
    srv = await get_server_details(server_id, db_uid)
    if not srv: await edit_func("Ошибка: сервер не найден."); return
    try: password = decrypt_password(srv['password_encrypted'])
    except Exception: await edit_func("❌ Ошибка расшифровки пароля."); return
    success, result = await list_directory(srv['ip'], srv['port'], srv['login_user'], password, path)
    if not success: await edit_func(f"❌ Ошибка получения списка файлов: <code>{result}</code>", reply_markup=server_management_keyboard(server_id)); return
    await edit_func(f"<b>Содержимое каталога:</b> <code>{path}</code>", reply_markup=file_manager_keyboard(server_id, path, result))

@dp.callback_query(F.data.startswith("fm_info:"))
async def cq_fm_info(c: types.CallbackQuery,s: FSMContext):
    _, sid, path = c.data.split(":", 2); msg = await c.message.answer(f"⏳ Скачиваю файл <code>{os.path.basename(path)}</code>..."); await c.answer()
    uid = await get_db_user_id(c.from_user.id)
    if not uid: await msg.edit_text("Ошибка: не удалось определить пользователя."); return
    srv = await get_server_details(int(sid), uid)
    if not srv: await msg.edit_text("Ошибка: сервер не найден."); return
    try: password = decrypt_password(srv['password_encrypted'])
    except Exception: await msg.edit_text("❌ Ошибка расшифровки пароля."); return
    success, result = await download_file(srv['ip'], srv['port'], srv['login_user'], password, path)
    if not success: await msg.edit_text(f"❌ Не удалось скачать файл.\n<b>Причина:</b> {result}"); return
    file_to_send = BufferedInputFile(result, filename=os.path.basename(path))
    await bot.send_document(c.from_user.id, file_to_send, caption=f"✅ Файл <code>{os.path.basename(path)}</code> успешно скачан."); await msg.delete()

@dp.callback_query(F.data.startswith("fm_upload_here:"))
async def cq_fm_upload_here(c: types.CallbackQuery,s: FSMContext):
    _, sid, path = c.data.split(":", 2); await s.set_state(FileManagerSession.uploading); await s.update_data(server_id=int(sid), current_path=path)
    await c.message.edit_text(f"📤 <b>Загрузка в каталог</b>\n<code>{path}</code>\n\nПросто отправьте документ в этот чат."); await c.answer()

@dp.message(FileManagerSession.uploading, F.document)
async def handle_document_upload(m: types.Message,s: FSMContext):
    if m.document.file_size > 20*1024*1024: await m.answer("❌ Размер файла не должен превышать 20 МБ!"); return
    data = await s.get_data(); sid, cpath = data.get('server_id'), data.get('current_path')
    if not sid or not cpath: await m.answer("Ошибка сессии. Попробуйте снова."); await s.clear(); return
    msg = await m.answer(f"⏳ Скачиваю <code>{m.document.file_name}</code> с серверов Telegram...")
    f_io = await bot.download(m.document); f_content = f_io.read(); await msg.edit_text(f"⏳ Загружаю файл на ваш сервер...")
    uid = await get_db_user_id(m.from_user.id)
    if not uid: await msg.edit_text("Ошибка: не удалось определить пользователя."); return
    srv = await get_server_details(sid, uid)
    if not srv: await msg.edit_text("Ошибка: не удалось найти сервер."); await s.clear(); return
    try: pswd = decrypt_password(srv['password_encrypted'])
    except Exception: await msg.edit_text("❌ Ошибка расшифровки пароля."); await s.clear(); return
    rpath = os.path.join(cpath, m.document.file_name)
    success, res = await upload_file(srv['ip'], srv['port'], srv['login_user'], pswd, f_content, rpath)
    if not success: await msg.edit_text(f"❌ Не удалось загрузить файл.\n<b>Причина:</b> {res}"); await s.clear(); return
    await msg.delete(); await m.answer(f"✅ Файл успешно загружен в <code>{cpath}</code>")
    await s.set_state(FileManagerSession.browsing); await show_files(m, sid, cpath)

@dp.callback_query(F.data.startswith("delete_server_confirm:"))
async def cq_delete_server_confirm(c: types.CallbackQuery):
    sid = int(c.data.split(":")[1]); uid = await get_db_user_id(c.from_user.id)
    if not uid: await c.answer("Ошибка: не удалось определить пользователя.", show_alert=True); return
    srv = await get_server_details(sid, uid)
    if not srv: await c.answer("Сервер не найден.", show_alert=True); return
    await c.message.edit_text(f"❓ Вы уверены, что хотите удалить сервер <b>{srv['name']}</b> ({srv['ip']})?\n\n<b>Это действие необратимо!</b>", reply_markup=confirm_delete_keyboard(sid)); await c.answer()

@dp.callback_query(F.data.startswith("delete_server_run:"))
async def cq_delete_server_run(c: types.CallbackQuery,s: FSMContext): 
    sid = int(c.data.split(":")[1]); uid = await get_db_user_id(c.from_user.id)
    if not uid: await c.answer("Ошибка: не удалось определить пользователя.", show_alert=True); return
    await delete_server_from_db(sid, uid); await c.answer("✅ Сервер удален!", show_alert=True); await cq_list_servers(c,s)

@dp.callback_query(F.data.startswith("server_settings:"))
async def cq_server_settings(c: types.CallbackQuery): sid = int(c.data.split(":")[1]); await c.message.edit_text("⚙️ <b>Настройки сервера</b>", reply_markup=server_settings_keyboard(sid))

@dp.callback_query(F.data.startswith("rename_server:"))
async def cq_rename_server(c: types.CallbackQuery,s: FSMContext): sid = int(c.data.split(":")[1]); await s.set_state(RenameServer.new_name); await s.update_data(server_id=sid); await c.message.edit_text("✏️ Введите новое имя для сервера:"); await c.answer()

@dp.message(RenameServer.new_name)
async def process_rename_server(m: types.Message,s: FSMContext):
    data = await s.get_data(); sid = data.get("server_id"); uid = await get_db_user_id(m.from_user.id)
    if not uid: await m.answer("Ошибка: не удалось определить пользователя."); await s.clear(); return
    await update_server_name(sid, uid, m.text); await m.answer(f"✅ Имя сервера успешно изменено на: <b>{m.text}</b>"); await s.clear()
    cb_imitation = types.CallbackQuery(id=str(uuid.uuid4()), from_user=m.from_user, chat_instance="", data=f"manage_server:{sid}", message=m)
    await cq_manage_server(cb_imitation, s)

async def handle_power_command(c: types.CallbackQuery, f, a: str):
    sid = int(c.data.split(":")[1]); uid = await get_db_user_id(c.from_user.id)
    if not uid: await c.answer("Ошибка: не удалось определить пользователя.", show_alert=True); return
    srv = await get_server_details(sid, uid)
    if not srv: await c.answer("Сервер не найден.", show_alert=True); return
    await c.message.edit_text(f"⏳ Отправляю команду на {a}...")
    try: pswd = decrypt_password(srv['password_encrypted'])
    except Exception: await c.message.edit_text(f"❌ Ошибка расшифровки пароля.", reply_markup=server_settings_keyboard(sid)); return
    success, msg = await f(srv['ip'], srv['port'], srv['login_user'], pswd)
    await c.message.edit_text(f"✅ {msg}" if success else f"❌ {msg}", reply_markup=server_settings_keyboard(sid))

@dp.callback_query(F.data.startswith("reboot_server_confirm:"))
async def reboot_confirm(c: types.CallbackQuery): await c.message.edit_text("❓ Вы уверены, что хотите <b>перезагрузить</b> сервер?", reply_markup=confirm_action_keyboard("Reboot", int(c.data.split(":")[1])))
@dp.callback_query(F.data.startswith("shutdown_server_confirm:"))
async def shutdown_confirm(c: types.CallbackQuery): await c.message.edit_text("❓ Вы уверены, что хотите <b>выключить</b> сервер?", reply_markup=confirm_action_keyboard("Shutdown", int(c.data.split(":")[1])))

@dp.callback_query(F.data.startswith("reboot_server_run:"))
async def cq_reboot_run(c: types.CallbackQuery): await handle_power_command(c, reboot_server, "перезагрузку")
@dp.callback_query(F.data.startswith("shutdown_server_run:"))
async def cq_shutdown_run(c: types.CallbackQuery): await handle_power_command(c, shutdown_server, "выключение")

@dp.callback_query(F.data.startswith("change_password:"))
async def cq_change_password(c: types.CallbackQuery): await c.answer("Эта функция находится в разработке.", show_alert=True)

@dp.callback_query(F.data.startswith("server_info:"))
async def cq_server_info(c: types.CallbackQuery):
    sid = int(c.data.split(":")[1]); uid = await get_db_user_id(c.from_user.id)
    if not uid: await c.answer("Ошибка: не удалось определить пользователя.", show_alert=True); return
    srv = await get_server_details(sid, uid)
    if not srv: await c.answer("Сервер не найден.", show_alert=True); return
    await c.message.edit_text(f"⏳ Получаю подробную информацию о <b>{srv['name']}</b>...")
    try: pswd = decrypt_password(srv['password_encrypted']); success, info = await get_system_info(srv['ip'], srv['port'], srv['login_user'], pswd)
    except Exception as e: logging.error(f"Ошибка получения инфо о сервере: {e}"); success, info = False, {}
    if not success: text = "❌ Не удалось получить подробную информацию о сервере."
    else: text = f"<b>🖥️ Подробная информация</b>\n\n<b>Имя хоста:</b> <code>{info.get('hostname','н/д')}</code>\n<b>Операционная система:</b> {info.get('os','н/д')}\n<b>Версия ядра:</b> <code>{info.get('kernel','н/д')}</code>"
    await c.message.edit_text(text, reply_markup=get_back_to_manage_keyboard(sid)); await c.answer()

@dp.callback_query(F.data.startswith("server_load:"))
async def cq_server_load(c: types.CallbackQuery):
    sid = int(c.data.split(":")[1]); uid = await get_db_user_id(c.from_user.id)
    if not uid: await c.answer("Ошибка: не удалось определить пользователя.", show_alert=True); return
    srv = await get_server_details(sid, uid)
    if not srv: await c.answer("Сервер не найден.", show_alert=True); return
    await c.message.edit_text(f"⏳ Получаю данные о нагрузке на <b>{srv['name']}</b>...")
    try: pswd = decrypt_password(srv['password_encrypted']); success, info = await get_system_load(srv['ip'], srv['port'], srv['login_user'], pswd)
    except Exception as e: logging.error(f"Ошибка получения нагрузки: {e}"); success, info = False, "Критическая ошибка"
    if not success: text = f"❌ Не удалось получить данные о нагрузке.\n<b>Причина:</b> <code>{info}</code>"
    else: text = f"<b>📊 Нагрузка на систему</b>\n\n<b>CPU:</b> {info['cpu']}\n<b>RAM:</b> {info['ram']}\n<b>Диск (/):</b> {info['disk']}"
    await c.message.edit_text(text, reply_markup=get_load_keyboard(sid)); await c.answer()

@dp.callback_query(F.data == "support")
async def cq_support(c: types.CallbackQuery): await c.answer(f"🆘 Для связи с поддержкой пишите: {SUPPORT_USERNAME}", show_alert=True)
@dp.callback_query(F.data == "settings")
async def cq_settings(c: types.CallbackQuery): await c.answer("Настройки пока в разработке.", show_alert=True)


# ==========================================================
# ===                 АДМИН-ПАНЕЛЬ                       ===
# ==========================================================

@dp.callback_query(F.data == "admin_panel")
async def cq_admin_panel(callback: types.CallbackQuery):
    await callback.message.edit_text("🛠️ <b>Админ-панель</b>", reply_markup=admin_main_keyboard())

# --- Управление пользователями ---
@dp.callback_query(F.data == "admin_users_menu")
async def cq_admin_users_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("Меню управления пользователями.", reply_markup=admin_users_keyboard())

@dp.callback_query(F.data == "admin_find_user")
async def cq_admin_find_user(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminSearchUser.by_id)
    await callback.message.edit_text("Введите Telegram ID пользователя для поиска.")

@dp.message(AdminSearchUser.by_id)
async def admin_process_user_search(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен состоять только из цифр. Попробуйте еще раз.")
        return
    await state.clear()
    await show_found_user_info(message, int(message.text))

@dp.callback_query(F.data.startswith("admin_find_user_return:"))
async def cq_admin_find_user_return(callback: types.CallbackQuery):
    user_tg_id = int(callback.data.split(":")[1])
    await show_found_user_info(callback, user_tg_id)

@dp.callback_query(F.data.startswith("admin_delete_server_confirm:"))
async def cq_admin_delete_server_confirm(callback: types.CallbackQuery):
    _, server_id, user_tg_id = callback.data.split(":")
    await callback.message.edit_text(f"❓ Вы уверены, что хотите удалить этот сервер (ID: {server_id})?",
                                     reply_markup=admin_confirm_delete_server_keyboard(int(server_id), int(user_tg_id)))

@dp.callback_query(F.data.startswith("admin_delete_server_run:"))
async def cq_admin_delete_server_run(callback: types.CallbackQuery):
    _, server_id_str, user_tg_id_str = callback.data.split(":")
    await admin_delete_server(int(server_id_str))
    await callback.answer("✅ Сервер удален!", show_alert=True)
    await show_found_user_info(callback, int(user_tg_id_str))


# --- Заглушки для других разделов админки ---
@dp.callback_query(F.data.in_({"admin_servers_menu", "admin_vip_menu", "admin_content_menu", "admin_export_data", "dev_placeholder", "admin_give_vip", "admin_revoke_vip","admin_message_user", "admin_view_server"}))
async def cq_admin_dev_placeholder(callback: types.CallbackQuery):
    await callback.answer("Этот раздел находится в разработке.", show_alert=True)


# --- Рассылка ---
@dp.callback_query(F.data == "admin_broadcast")
async def cq_admin_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.message)
    await callback.message.edit_text("Введите сообщение для рассылки (текст, фото, видео). Для отмены: /cancel")
    await callback.answer()

@dp.message(Broadcast.message)
async def broadcast_message_handler(message: types.Message, state: FSMContext):
    await state.update_data(broadcast_message_id=message.message_id, broadcast_chat_id=message.chat.id)
    total_users = await get_total_users_count()
    await state.set_state(Broadcast.confirmation)
    await message.answer(f"Вы уверены, что хотите отправить это сообщение? Его получат примерно {total_users} пользователей.", reply_markup=confirm_broadcast_keyboard())

@dp.callback_query(F.data == "start_broadcast", Broadcast.confirmation)
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    message_id, chat_id = data.get("broadcast_message_id"), data.get("broadcast_chat_id")
    await state.clear()
    await callback.message.edit_text("✅ Рассылка начата...")
    users = await get_all_users_ids()
    success, error = 0, 0
    for user in users:
        try:
            await bot.copy_message(chat_id=user['telegram_id'], from_chat_id=chat_id, message_id=message_id)
            success += 1
        except Exception:
            error += 1
        await asyncio.sleep(0.1)
    await callback.message.answer(f"🏁 Рассылка завершена!\n\n✅ Успешно отправлено: {success}\n❌ Ошибок: {error}", reply_markup=admin_main_keyboard())


# --- Основная функция ---
async def main():
    await create_db_pool()
    if not db_pool:
        logging.critical("Не удалось подключиться к базе данных. Запуск отменен.")
        return

    WEBHOOK_BASE_DOMAIN = "https://pay.kododrive.ru"
    WEBHOOK_URL = f"{WEBHOOK_BASE_DOMAIN}{WEBHOOK_TELEGRAM_PATH}"

    app = web.Application()

    app.router.add_post(WEBHOOK_CRYPTO_PAY_PATH, cryptopay_webhook_handler)
    app.router.add_post(WEBHOOK_YOOKASSA_PATH, yookassa_webhook_handler)

    webhook_request_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_request_handler.register(app, path=WEBHOOK_TELEGRAM_PATH)
    setup_application(app, dp, bot=bot)

    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT)

    try:
        await site.start()
        logging.info(f"Веб-сервер запущен на http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT}")

        total_users, total_servers = await get_total_users_count(), await get_total_servers_count()
        admin_rec = await get_user_by_telegram_id(ADMIN_ID)
        if admin_rec:
            await bot.send_message(ADMIN_ID, await get_status_message_text(admin_rec, total_users, total_servers))

        logging.info("Бот запущен и работает в режиме вебхука по адресу: %s", WEBHOOK_URL)
        await asyncio.Event().wait()

    finally:
        await runner.cleanup()
        if db_pool:
            await db_pool.close()
        await bot.delete_webhook()
        logging.info("Бот и веб-сервер остановлены.")


if __name__ == "__main__":
    asyncio.run(main())