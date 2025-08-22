import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

# Локальные импорты
from utils.fsm_states import AddServer
from keyboards.inline import cancel_fsm_keyboard, servers_menu_keyboard

# Создаем новый "Router" для этого файла. Позже мы подключим его к основному приложению.
router = Router()

# ------ Обработка отмены FSM ------
@router.callback_query(F.data == "cancel_fsm")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info(f"Cancelling state {current_state}")
    await state.clear()
    await callback.message.edit_text(
        "Действие отменено.",
        reply_markup=servers_menu_keyboard()
    )

# ------ Начало сценария добавления сервера ------
@router.callback_query(F.data == "add_server")
async def start_add_server(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddServer.name)
    await callback.message.edit_text(
        "<b>Шаг 1/5: Название сервера</b>\n\n"
        "Введите название для вашего сервера. Например, 'Мой веб-сайт' или 'Домашний сервер'.",
        reply_markup=cancel_fsm_keyboard()
    )

# ------ Шаг 2: Получение названия и запрос IP ------
@router.message(AddServer.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddServer.ip)
    await message.answer(
        "<b>Шаг 2/5: IP-адрес</b>\n\n"
        "Отлично! Теперь введите IP-адрес вашего сервера.",
        reply_markup=cancel_fsm_keyboard()
    )

# ------ Шаг 3: Получение IP и запрос порта ------
@router.message(AddServer.ip)
async def process_ip(message: types.Message, state: FSMContext):
    # Здесь нужна валидация IP, но пока для простоты опустим ее
    await state.update_data(ip=message.text)
    await state.set_state(AddServer.port)
    await message.answer(
        "<b>Шаг 3/5: SSH Порт</b>\n\n"
        "Введите порт для SSH-подключения. Обычно это порт 22.",
        reply_markup=cancel_fsm_keyboard()
    )

# ------ Шаг 4: Получение порта и запрос логина ------
@router.message(AddServer.port)
async def process_port(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Порт должен быть числом. Попробуйте еще раз.", reply_markup=cancel_fsm_keyboard())
        return

    await state.update_data(port=int(message.text))
    await state.set_state(AddServer.login_user)
    await message.answer(
        "<b>Шаг 4/5: Логин</b>\n\n"
        "Введите имя пользователя для подключения (например, 'root' или 'ubuntu').",
        reply_markup=cancel_fsm_keyboard()
    )

# ------ Шаг 5: Получение логина и запрос пароля ------
@router.message(AddServer.login_user)
async def process_login(message: types.Message, state: FSMContext):
    await state.update_data(login_user=message.text)
    await state.set_state(AddServer.password)
    await message.answer(
        "<b>Шаг 5/5: Пароль</b>\n\n"
        "Введите пароль для подключения. Ваше сообщение будет автоматически удалено для безопасности.",
        reply_markup=cancel_fsm_keyboard()
    )

# ------ Финальный шаг: Получение пароля и сохранение ------
@router.message(AddServer.password)
async def process_password(message: types.Message, state: FSMContext):
    # Получаем все данные из FSM
    data = await state.update_data(password=message.text)
    # Очищаем состояние
    await state.clear()

    # Удаляем сообщение с паролем для безопасности
    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение с паролем: {e}")

    #
    # === ЗДЕСЬ БУДЕТ ВАЖНЫЙ КОД ===
    # 1. Шифрование пароля (AES-256), data['password']
    # 2. Проверка SSH подключения с полученными данными
    # 3. Сохранение данных в базу
    #

    await message.answer(
        f"✅ <b>Сервер '{data['name']}' успешно добавлен!</b>\n\n"
        "Теперь вы можете найти его в списке своих серверов и управлять им.",
        reply_markup=servers_menu_keyboard()
    )
    # Временно выведем данные для проверки
    logging.info(f"Добавлен новый сервер: {data}")
