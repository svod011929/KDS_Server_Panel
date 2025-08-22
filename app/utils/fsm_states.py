from aiogram.fsm.state import State, StatesGroup

class AddServer(StatesGroup):
    name = State()          # Состояние ожидания ввода названия сервера
    ip = State()            # Состояние ожидания ввода IP
    port = State()          # Состояние ожидания ввода порта
    login_user = State()    # Состояние ожидания ввода логина
    password = State()      # Состояние ожидания ввода пароля
