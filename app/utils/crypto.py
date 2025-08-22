import os
from cryptography.fernet import Fernet

# Загружаем ключ из переменных окружения
# .env файл загружается в основном app.py, поэтому os.getenv() здесь работает
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
fernet = Fernet(ENCRYPTION_KEY.encode())

def encrypt_password(password: str) -> str:
    """Шифрует пароль и возвращает его в виде строки."""
    encrypted_password = fernet.encrypt(password.encode())
    return encrypted_password.decode()

def decrypt_password(encrypted_password: str) -> str:
    """Расшифровывает пароль и возвращает его в виде строки."""
    decrypted_password = fernet.decrypt(encrypted_password.encode())
    return decrypted_password.decode()
