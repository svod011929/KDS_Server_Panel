# KDS Server Panel Bot

![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![Aiogram Version](https://img.shields.io/badge/aiogram-3.x-green.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)
![Status](https://img.shields.io/badge/status-stable-brightgreen)

Мощный и безопасный Telegram-бот для управления вашими Linux-серверами по SSH. Позволяет выполнять команды, управлять файлами, отслеживать нагрузку на систему, а также включает в себя полнофункциональную админ-панель и систему платных подписок.

## 🚀 Основные возможности

### Для Пользователей
-   **Управление серверами:** Добавляйте, переименовывайте и удаляйте неограниченное количество серверов.
-   **Интерактивный SSH-терминал:** Выполняйте команды на вашем сервере в режиме реального времени.
-   **Мониторинг:** Получайте актуальную информацию о статусе сервера, времени его работы (Uptime), а также о нагрузке на CPU, RAM и дисковое пространство.
-   **Управление питанием:** Безопасно перезагружайте (`reboot`) и выключайте (`shutdown`) ваш сервер.
-   **Встроенный файловый менеджер:**
    -   Просматривайте файлы и папки на сервере.
    -   Скачивайте файлы с сервера прямо в чат Telegram (до 50 МБ).
    -   Загружайте файлы с компьютера или телефона на сервер (до 20 МБ).
-   **Безопасность:** Смена пароля от сервера прямо из меню настроек.
-   **VIP-подписка:** Покупайте VIP-статус для получения расширенных возможностей через **ЮKassa** или **CryptoBot (USDT)**.

### 🛠️ Для Администратора
-   **Комплексная Админ-панель:** Полноценная панель управления ботом.
-   **Массовая рассылка:** Отправляйте информационные сообщения всем пользователям бота (поддерживается любой тип контента).
-   **Управление пользователями:**
    -   Находите любого пользователя по его Telegram ID.
    -   Просматривайте подробную информацию о пользователе (статус VIP, количество серверов).
    -   Выдавайте и отзывайте VIP-статус вручную.
    -   Отправляйте личные сообщения любому пользователю.
-   **Управление серверами:**
    -   Находите любой сервер в базе данных по его ID.
    -   Просматривайте информацию о сервере и его владельце.
    -   Удаляйте любой сервер из системы.
-   **VIP-управление:**
    -   Просматривайте постраничный список всех активных VIP-пользователей с датами окончания подписки.
-   **Динамическое управление контентом:**
    -   Изменяйте ключевые тексты бота (приветствие, информация о VIP, текст поддержки) прямо из админ-панели без перезапуска.
-   **Экспорт данных:**
    -   Выгружайте полные бэкапы таблиц `users` и `servers` в CSV-формате.

## 💻 Стек технологий

-   **Язык:** Python 3.10+
-   **Telegram Framework:** Aiogram 3.x
-   **Веб-сервер:** Aiohttp (для обработки вебхуков Telegram и платежных систем)
-   **База данных:** PostgreSQL
-   **Взаимодействие с БД:** Asyncpg
-   **SSH/SFTP:** AsyncSSH
-   **Шифрование:** Cryptography (Fernet)
-   **Оркестрация:** Docker & Docker Compose

## ⚙️ Установка и запуск

Проект полностью упакован в Docker, что делает его запуск максимально простым и изолированным.

### 1. Предварительные требования
Убедитесь, что на вашем сервере установлены:
-   `git`
-   `docker`
-   `docker-compose`

### 2. Клонирование репозитория
```bash
git clone https://github.com/svod011929/KDS_Server_Panel.git
cd KDS_Server_Panel
```

### 3. Создание файла конфигурации
В проекте используется `.env` файл для хранения всех секретных данных. Скопируйте пример, чтобы создать свой файл конфигурации.

```bash
cp .env.example .env
```
> **ВНИМАНИЕ:** Файл `.env` содержит чувствительные данные. Убедитесь, что он добавлен в `.gitignore` и никогда не попадет в публичный репозиторий!

### 4. Настройка переменных окружения
Откройте файл `.env` любым текстовым редактором (например, `nano .env`) и заполните все переменные. Подробное описание каждой переменной находится ниже.

### 5. Запуск проекта
Просто выполните команду в корневой папке проекта:
```bash
sudo docker-compose up --build -d
```
-   `--build` — флаг для пересборки контейнеров, если вы вносили изменения в код.
-   `-d` — флаг для запуска в фоновом (detached) режиме.

### Полезные команды Docker
-   **Просмотр логов бота в реальном времени:**
    ```bash
    sudo docker-compose logs -f bot
    ```
-   **Остановка проекта:**
    ```bash
    sudo docker-compose down
    ```

## 🔑 Переменные окружения (`.env`)

Это самый важный шаг конфигурации.

| Переменная          | Описание                                                                                                                  | Пример                                |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| `BOT_TOKEN`         | Токен вашего бота. Получить у [@BotFather](https://t.me/BotFather).                                                        | `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` |
| `ADMIN_ID`          | Telegram ID главного администратора. Получить у [@userinfobot](https://t.me/userinfobot).                                   | `123456789`                           |
| `SUPPORT_USERNAME`  | Юзернейм для связи с поддержкой. Будет показан пользователям.                                                              | `@your_support_username`              |
| `ENCRYPTION_KEY`    | **(Критически важно!)** Ключ для шифрования паролей. **Сгенерируйте один раз и никогда не меняйте!**                            | `...` (см. инструкцию ниже)         |
| `POSTGRES_USER`     | Имя пользователя для базы данных.                                                                                         | `myuser`                              |
| `POSTGRES_PASSWORD` | Пароль для пользователя базы данных.                                                                                      | `mystrongpassword`                    |
| `POSTGRES_DB`       | Название базы данных.                                                                                                     | `kds_panel`                           |
| `DB_HOST`           | Хост для подключения к БД из контейнера бота. **Оставьте `db`**.                                                              | `db`                                  |
| `DB_PORT`           | Порт базы данных. **Оставьте `5432`**.                                                                                      | `5432`                                |
| `YK_SHOP_ID`        | ID вашего магазина в ЮKassa.                                                                                              | `...`                                 |
| `YK_SECRET_KEY`     | Секретный ключ вашего магазина в ЮKassa.                                                                                  | `...`                                 |
| `CRYPTO_PAY_TOKEN`  | Токен вашего приложения в CryptoBot.                                                                                        | `...`                                 |

#### Как сгенерировать `ENCRYPTION_KEY`
Этот ключ используется для шифрования паролей от серверов в базе данных. Если вы его поменяете, доступ ко всем ранее добавленным серверам будет утерян.

Выполните эту команду на машине с Python, чтобы получить ключ, и вставьте его в `.env` файл:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 📂 Структура проекта
```
KDS_Server_Panel/
├── app/                  # Основной код приложения
│   ├── keyboards/        # Модули для создания клавиатур
│   │   └── inline.py
│   ├── utils/            # Вспомогательные утилиты
│   │   ├── crypto.py     # Шифрование паролей
│   │   └── ssh.py        # Вся логика SSH и SFTP
│   └── app.py            # Главный файл бота: хендлеры, FSM, запуск
├── .env                  # (Локальный) Файл с секретными переменными
├── .env.example          # Пример файла .env для репозитория
├── .gitignore            # Файл с исключениями для Git
├── create_tables.sql     # SQL-схема для инициализации таблиц
├── docker-compose.yml    # Файл для оркестрации Docker-контейнеров
└── Dockerfile            # Инструкция по сборке Docker-образа для бота
```
## 📄 Лицензия
Проект распространяется под лицензией MIT. Подробности в файле `LICENSE`.

## 🌟 Поддержка и сотрудничество

<div align="center">
  
### ✨ Свяжитесь со мной

[![Telegram Contact](https://img.shields.io/badge/Telegram-@KodoDrive-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/KodoDrive)
[![Email](https://img.shields.io/badge/Email-business@example.com-7B68EE?style=for-the-badge&logo=gmail&logoColor=white)](mailto:bussines@kododrive-devl.ru)

</div>

<div align="center">
  <table>
    <tr>
      <td align="center" width="140">
        <img src="https://api.iconify.design/fluent-emoji-flat:sparkles.svg?width=60&height=60" alt="Sparkles">
        <br><strong>Поддержка</strong>
      </td>
      <td align="center" width="140">
        <img src="https://api.iconify.design/fluent-emoji-flat:briefcase.svg?width=60&height=60" alt="Briefcase">
        <br><strong>Сотрудничество</strong>
      </td>
      <td align="center" width="140">
        <img src="https://api.iconify.design/fluent-emoji-flat:gear.svg?width=60&height=60" alt="Gear">
        <br><strong>Настройка</strong>
      </td>
    </tr>
  </table>
</div>

<div align="center" style="margin-top: 20px; font-size: 1.2rem;">

📬 **Telegram:** [@KodoDrive](https://t.me/KodoDrive)  
⏳ Отвечаю в течение 24 часов  
💼 Деловые предложения: bussines@kododrive-devl.ru

</div>

<p align="center">
  <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&pause=1000&color=7B1FA2&center=true&vCenter=true&width=500&lines=%D0%93%D0%BE%D1%82%D0%BE%D0%B2+%D0%BA+%D1%81%D0%BE%D1%82%D1%80%D1%83%D0%B4%D0%BD%D0%B8%D1%87%D0%B5%D1%81%D1%82%D0%B2%D1%83%21;%D0%9F%D0%B8%D1%88%D0%B8+%D0%B2+Telegram+%F0%9F%93%A7;%D0%9E%D1%82%D0%B2%D0%B5%D1%87%D0%B0%D1%8E+%D0%B2+%D1%82%D0%B5%D1%87%D0%B5%D0%BD%D0%B8%D0%B5+24+%D1%87%D0%B0%D1%81%D0%BE%D0%B2+%F0%9F%95%92" alt="Typing SVG">
</p>

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=svod011929&repo=KDS_Server_Panel&label=Просмотры+репозитория&color=7b1fa2&style=for-the-badge&labelColor=5d4037" width="400" height="50" alt="Repository views">
</p>

<!-- kododrive-projects-block -->

## Проекты KodoDrive

Другие проекты автора: [профиль @svod011929](https://github.com/svod011929) · [сайт](https://kododrive.ru) · [Telegram](https://t.me/KodoDrive)

### VPN и инфраструктура

- [BuryatVPN — VPN-сервис + Telegram](https://github.com/svod011929/buryatvpn)
- [VPN Server Installer — VLESS + TLS](https://github.com/svod011929/vpn-server-installer)
- [3X-UI Auto Installer](https://github.com/svod011929/3x-ui-auto-installer)
- [AWG Bot Installer — AmneziaWG](https://github.com/svod011929/awg-bot-installer)
- [RemnaShop Installer](https://github.com/svod011929/remnashop-installer)
- [VPN Auto Installer — панели](https://github.com/svod011929/vpn-auto-installer)
- [VPNHubBot — Telegram VPN-бот](https://github.com/svod011929/VPNHubBot)

### Telegram и автоматизация

- **KDS Server Panel — SSH из Telegram** ← ты здесь
- [Telegram → VK Poster](https://github.com/svod011929/telegram-to-vk-poster)
- [KDS Parser CryptoBot](https://github.com/svod011929/kds_parser_cryptobot)
- [Auction Bot](https://github.com/svod011929/auction-bot)
- [Invest Bot](https://github.com/svod011929/invest-bot)
- [Crypto Check Bot](https://github.com/svod011929/crypto-check-bot)
- [KodoRefStarsBot](https://github.com/svod011929/KodoRefStarsBot)

### Магазины и финансы

- [KodoCashFlow](https://github.com/svod011929/KodoCashFlow)
- [Telegram Crypto Shop](https://github.com/svod011929/telegram-crypto-shop)
- [TalkProfit](https://github.com/svod011929/talkprofit)

### Сайты

- [KodoDrive Portfolio](https://github.com/svod011929/kododrive-portfolio)
- [kododrive.github.io](https://github.com/svod011929/kododrive.github.io)

<!-- /kododrive-projects-block -->
