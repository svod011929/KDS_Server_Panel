import os
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

def main_menu_keyboard(is_admin: bool = False):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🖥️ Мои серверы", callback_data="list_servers"))
    b.button(text="👑 VIP-подписка", callback_data="vip_subscription")
    b.button(text="🆘 Поддержка", callback_data="support")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"))
    if is_admin:
        b.row(InlineKeyboardButton(text="🛠️ Админ-панель", callback_data="admin_panel"))
    return b.as_markup()

def admin_main_keyboard():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast"))
    b.button(text="👥 Пользователи", callback_data="admin_users_menu")
    b.button(text="🖥️ Серверы", callback_data="admin_servers_menu")
    b.adjust(2)
    b.button(text="💎 VIP-управление", callback_data="admin_vip_menu")
    b.button(text="📝 Контент", callback_data="admin_content_menu")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="📤 Экспорт данных", callback_data="admin_export_data"))
    b.row(InlineKeyboardButton(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu"))
    return b.as_markup()

def confirm_broadcast_keyboard():
    b = InlineKeyboardBuilder()
    b.button(text="✅ Начать рассылку", callback_data="start_broadcast")
    b.button(text="❌ Отмена", callback_data="admin_panel")
    return b.as_markup()

# --- Раздел "Управление пользователями" ---
def admin_users_keyboard():
    b = InlineKeyboardBuilder()
    b.button(text="🔍 Найти пользователя по ID", callback_data="admin_find_user")
    b.button(text="📊 Статистика (в разработке)", callback_data="dev_placeholder")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel"))
    return b.as_markup()

def admin_user_details_keyboard(servers: list, user_tg_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="👑 Выдать VIP", callback_data=f"admin_give_vip:{user_tg_id}")
    b.button(text="🗑 Забрать VIP", callback_data=f"admin_revoke_vip:{user_tg_id}")
    b.button(text="✍️ Написать сообщение", callback_data=f"admin_message_user:{user_tg_id}")
    b.adjust(2)
    for server in servers:
        b.row(InlineKeyboardButton(text=f"🖥️ {server['name']}", callback_data=f"admin_view_server:{server['id']}"),
              InlineKeyboardButton(text="❌", callback_data=f"admin_delete_server_confirm:{server['id']}:{user_tg_id}"))
    b.row(InlineKeyboardButton(text="⬅️ Назад к управлению пользователями", callback_data="admin_users_menu"))
    return b.as_markup()

def admin_confirm_delete_server_keyboard(server_id: int, user_tg_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, удалить", callback_data=f"admin_delete_server_run:{server_id}:{user_tg_id}")
    b.button(text="❌ Нет, отмена", callback_data=f"admin_find_user_return:{user_tg_id}")
    b.adjust(2)
    return b.as_markup()

def admin_cancel_message_keyboard(user_tg_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data=f"admin_find_user_return:{user_tg_id}")
    return b.as_markup()

# --- Раздел "Управление серверами" ---
def admin_servers_menu_keyboard():
    b = InlineKeyboardBuilder()
    b.button(text="🔍 Найти сервер по ID", callback_data="admin_find_server_by_id")
    b.button(text="📊 Статистика (в разработке)", callback_data="dev_placeholder")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel"))
    return b.as_markup()

def admin_server_details_keyboard(server_id: int, owner_tg_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="👤 Перейти к владельцу", callback_data=f"admin_find_user_return:{owner_tg_id}")
    b.button(text="🗑 Удалить этот сервер", callback_data=f"admin_server_delete_confirm:{server_id}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="⬅️ Назад к управлению серверами", callback_data="admin_servers_menu"))
    return b.as_markup()

def admin_server_confirm_delete_keyboard(server_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, я уверен", callback_data=f"admin_server_delete_run:{server_id}")
    b.button(text="❌ Отмена", callback_data="admin_servers_menu")
    b.adjust(2)
    return b.as_markup()

# --- Раздел "VIP-управление" ---
def admin_vip_menu_keyboard():
    b = InlineKeyboardBuilder()
    b.button(text="📋 Список VIP-пользователей", callback_data="admin_list_vips:0")
    b.button(text="➕ Массовая выдача (в разработке)", callback_data="dev_placeholder")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel"))
    return b.as_markup()

def admin_vips_list_keyboard(current_page: int, total_pages: int):
    b = InlineKeyboardBuilder()
    buttons = []
    if current_page > 0:
        buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_list_vips:{current_page - 1}"))
    if total_pages > 1:
        buttons.append(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="dev_placeholder"))
    if current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"admin_list_vips:{current_page + 1}"))
    if buttons:
        b.row(*buttons)
    b.row(InlineKeyboardButton(text="⬅️ В меню VIP-управления", callback_data="admin_vip_menu"))
    return b.as_markup()

# --- Раздел "Управление контентом" ---
def admin_content_menu_keyboard():
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Приветствие (/start)", callback_data="admin_edit_content:welcome_message")
    b.button(text="✏️ Инфо о VIP", callback_data="admin_edit_content:vip_info")
    b.button(text="✏️ Текст поддержки", callback_data="admin_edit_content:support_info")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel"))
    return b.as_markup()

def admin_cancel_content_edit_keyboard():
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data="admin_content_menu")
    return b.as_markup()

# --- Основные клавиатуры пользователя ---
def servers_list_keyboard(servers: list):
    b = InlineKeyboardBuilder()
    for s in servers:
        b.row(InlineKeyboardButton(text=f"🖥️ {s['name']}", callback_data=f"manage_server:{s['id']}"))
    b.row(InlineKeyboardButton(text="➕ Добавить сервер", callback_data="add_server"))
    b.row(InlineKeyboardButton(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu"))
    return b.as_markup()

def server_management_keyboard(server_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="🖥️ Информация", callback_data=f"server_info:{server_id}"); b.button(text="📊 Нагрузка", callback_data=f"server_load:{server_id}")
    b.adjust(2)
    b.button(text="💻 Терминал", callback_data=f"terminal:{server_id}"); b.button(text="📁 Файлы", callback_data=f"fm_enter:{server_id}:/root")
    b.adjust(2)
    b.button(text="⚙️ Настройки", callback_data=f"server_settings:{server_id}"); b.button(text="🗑️ Удалить", callback_data=f"delete_server_confirm:{server_id}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="list_servers"))
    return b.as_markup()

def get_back_to_manage_keyboard(server_id: int):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="⬅️ Назад к управлению", callback_data=f"manage_server:{server_id}"))
    return b.as_markup()

def get_load_keyboard(server_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Обновить", callback_data=f"server_load:{server_id}")
    b.button(text="⬅️ Назад", callback_data=f"manage_server:{server_id}")
    return b.as_markup()

def server_settings_keyboard(server_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Переименовать", callback_data=f"rename_server:{server_id}"); b.button(text="🔑 Изменить пароль", callback_data=f"change_password:{server_id}")
    b.adjust(2)
    b.button(text="🔄 Перезагрузка", callback_data=f"reboot_server_confirm:{server_id}"); b.button(text="🔌 Выключение", callback_data=f"shutdown_server_confirm:{server_id}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="⬅️ Назад к управлению", callback_data=f"manage_server:{server_id}"))
    return b.as_markup()

def confirm_action_keyboard(action: str, server_id: int):
    b = InlineKeyboardBuilder()
    b.button(text=f"✅ Да, {action.lower()}", callback_data=f"{action.lower()}_server_run:{server_id}")
    b.button(text="❌ Нет, отмена", callback_data=f"server_settings:{server_id}")
    b.adjust(2)
    return b.as_markup()

def confirm_delete_keyboard(server_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, удалить", callback_data=f"delete_server_run:{server_id}")
    b.button(text="❌ Нет, отмена", callback_data=f"manage_server:{server_id}")
    b.adjust(2)
    return b.as_markup()

def file_manager_keyboard(server_id: int, current_path: str, items: list):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📤 Загрузить сюда", callback_data=f"fm_upload_here:{server_id}:{current_path}"))
    parent_path = os.path.dirname(current_path)
    if current_path != parent_path:
        b.row(InlineKeyboardButton(text="⬆️ На уровень выше", callback_data=f"fm_nav:{server_id}:{parent_path}"))
    for item in items:
        icon = "📁" if item['type'] == 'dir' else "📄"
        action = "fm_nav" if item['type'] == 'dir' else "fm_info"
        full_path = os.path.join(current_path, item['name'])
        b.row(InlineKeyboardButton(text=f"{icon} {item['name']}", callback_data=f"{action}:{server_id}:{full_path}"))
    b.row(InlineKeyboardButton(text="⬅️ Выход из Файл-менеджера", callback_data=f"manage_server:{server_id}"))
    return b.as_markup()

def vip_menu_keyboard():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💳 Купить VIP", callback_data="buy_vip"))
    b.row(InlineKeyboardButton(text="ℹ️ Мой статус", callback_data="my_vip_status"))
    b.row(InlineKeyboardButton(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu"))
    return b.as_markup()

def choose_tariff_keyboard():
    b = InlineKeyboardBuilder()
    b.button(text="1 месяц - 49₽", callback_data="choose_tariff:30:0.5"); b.button(text="3 месяца - 129₽", callback_data="choose_tariff:90:1.3")
    b.adjust(2)
    b.button(text="6 месяцев - 199₽", callback_data="choose_tariff:180:2.0"); b.button(text="12 месяцев - 349₽", callback_data="choose_tariff:365:3.5")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="vip_subscription"))
    return b.as_markup()

def choose_payment_method_keyboard(days: int, amount: float):
    b = InlineKeyboardBuilder()
    b.button(text="🤖 CryptoBot", callback_data=f"pay:cryptobot:{days}:{amount}")
    b.button(text="🥝 ЮKassa", callback_data=f"pay:yookassa:{days}:{amount}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="⬅️ Назад к тарифам", callback_data="buy_vip"))
    return b.as_markup()

def payment_keyboard(pay_url: str, payment_system: str, invoice_id: str):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="➡️ Перейти к оплате", url=pay_url))
    b.row(InlineKeyboardButton(text="✅ Проверить платеж", callback_data=f"check_payment:{payment_system}:{invoice_id}"))
    b.row(InlineKeyboardButton(text="⬅️ Отмена", callback_data="vip_subscription"))
    return b.as_markup()