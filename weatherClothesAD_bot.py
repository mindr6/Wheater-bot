import logging
import telebot
import requests
from datetime import time
from apscheduler.schedulers.background import BackgroundScheduler
import matplotlib.pyplot as plt
import io


# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API ключи (рекомендую вынести в переменные окружения!)
API_KEY = 'ваш_api_от_openweather'
BOT_TOKEN = 'ващ_токен_телеграм_бота'

# Словарь
weather_descriptions = {
    'clear sky': 'ясное небо',
    'few clouds': 'небольшая облачность',
    'scattered clouds': 'рассеянные облака',
    'broken clouds': 'облачно с прояснениями',
    'shower rain': 'ливень',
    'rain': 'дождь',
    'light rain': 'небольшой дождь',
    'moderate rain': 'умеренный дождь',
    'heavy intensity rain': 'сильный дождь',
    'thunderstorm': 'гроза',
    'snow': 'снег',
    'light snow': 'небольшой снег',
    'mist': 'туман',
    'overcast clouds': 'пасмурные облака',
    'haze': 'дымка',
    'fog': 'туман',
    'drizzle': 'морось'
}

# Советы по одежде
clothing_advice = {
    'ясное небо': 'Сегодня ясно! Наденьте легкую одежду и солнцезащитные очки. ☀️',
    'небольшая облачность': 'Небольшая облачность. Легкая куртка или свитер будут кстати. 🌥️',
    'рассеянные облака': 'Рассеянные облака. Удобная одежда и возможно легкая куртка. ⛅',
    'облачно с прояснениями': 'Облачно с прояснениями. Куртка или свитер подойдут. 🌤️',
    'ливень': 'Ливень на улице! Захватите зонт и водонепроницаемую одежду. ☔',
    'дождь': 'Дождь. Возьмите зонт и накиньте водонепроницаемую куртку. 🌧️',
    'небольшой дождь': 'Небольшой дождь. Зонтик не помешает. 🌦️',
    'умеренный дождь': 'Умеренный дождь. Возьмите зонт и водонепроницаемую куртку. 🌧️',
    'сильный дождь': 'Сильный дождь! Водонепроницаемая одежда обязательна. ⛈️',
    'гроза': 'Гроза! Безопасность прежде всего, оставайтесь в помещении. 🌩️',
    'снег': 'Идет снег. Наденьте теплую одежду и зимнюю обувь. ❄️',
    'небольшой снег': 'Небольшой снег. Теплая одежда и зимняя обувь. 🌨️',
    'туман': 'Туманно. Одевайтесь теплее и будьте осторожны на дорогах. 🌫️',
    'пасмурные облака': 'Пасмурно. Легкая куртка или свитер будут уместны. ☁️',
    'дымка': 'Дымка. Легкая куртка будет кстати. 🌫️',
    'морось': 'Морось. Зонтик может пригодиться. 🌦️'
}

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Словари для хранения данных пользователей
user_notification_times = {}
user_cities = {}
user_locations = {}  # Для геолокаций

# Инициализация планировщика задач
scheduler = BackgroundScheduler()
scheduler.start()


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Главное меню бота"""
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(
        '🌆 Отправить город',
        callback_data='city'
    ))
    keyboard.add(telebot.types.InlineKeyboardButton(
        '📍 Отправить геолокацию',
        callback_data='location'
    ))
    keyboard.add(telebot.types.InlineKeyboardButton(
        '🔔 Установить время уведомлений',
        callback_data='set_time'
    ))
    
    welcome_text = (
        '👋 Привет! Я бот прогноза погоды!\n\n'
        '🌤️ Я могу показать текущую погоду и прогноз на 5 дней\n\n'
        'Доступные команды:\n'
        '/start - Главное меню\n'
        '/help - Справка\n\n'
        'Выберите опцию ниже:'
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data in ['city', 'location', 'set_time'])
def callback_worker(call):
    """Обработчик кнопок меню"""
    if call.data == 'city':
        bot.send_message(
            call.message.chat.id,
            '📝 Отправьте название города (на русском или английском):'
        )
        bot.register_next_step_handler(call.message, handle_city)
        
    elif call.data == 'location':
        markup = telebot.types.ReplyKeyboardMarkup(
            one_time_keyboard=True,
            resize_keyboard=True
        )
        button = telebot.types.KeyboardButton(
            text='📍 Отправить геолокацию',
            request_location=True
        )
        markup.add(button)
        
        bot.send_message(
            call.message.chat.id,
            '📍 Нажмите кнопку ниже, чтобы отправить свою геолокацию:',
            reply_markup=markup
        )
        bot.register_next_step_handler(call.message, handle_location)
        
    elif call.data == 'set_time':
        if call.message.chat.id not in user_cities and call.message.chat.id not in user_locations:
            bot.send_message(
                call.message.chat.id,
                '⚠️ Сначала выберите город или отправьте геолокацию через /start'
            )
            return
            
        bot.send_message(
            call.message.chat.id,
            '🕰️ Отправьте время для ежедневных уведомлений в формате ЧЧ:ММ\n'
            'Например: 09:00'
        )
        bot.register_next_step_handler(call.message, set_notification_time)


def handle_city(message):
    """Обработка названия города"""
    if not message.text:
        bot.send_message(message.chat.id, '⚠️ Пожалуйста, отправьте текст с названием города.')
        return
    
    city = message.text.strip()
    
    # Сохраняем город пользователя
    user_cities[message.chat.id] = city
    
    # Убираем геолокацию если была
    if message.chat.id in user_locations:
        del user_locations[message.chat.id]
    
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(
        '✅ Получить прогноз',
        callback_data=f'weather_city_{city}'
    ))
    
    bot.send_message(
        message.chat.id,
        f'🏙️ Город: {city}\nНажмите кнопку для получения прогноза:',
        reply_markup=keyboard
    )


def handle_location(message):
    """Обработка геолокации"""
    if not message.location:
        bot.send_message(
            message.chat.id,
            '⚠️ Пожалуйста, отправьте геолокацию через кнопку.'
        )
        return

    location = message.location
    latitude = location.latitude
    longitude = location.longitude
    
    # Сохраняем координаты
    user_locations[message.chat.id] = (latitude, longitude)
    
    # Убираем город если был
    if message.chat.id in user_cities:
        del user_cities[message.chat.id]
    
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(
        '✅ Получить прогноз',
        callback_data=f'weather_location_{latitude}_{longitude}'
    ))
    
    bot.send_message(
        message.chat.id,
        '📍 Геолокация получена!\nНажмите кнопку для получения прогноза:',
        reply_markup=keyboard
    )

def plot_weekly_weather(forecast_data):
    """Создание графика прогноза температуры"""
    dates = []
    temperatures = []
    
    # Берем одну точку в день (в 12:00)
    for forecast in forecast_data['list']:
        if '12:00:00' in forecast['dt_txt']:
            date = forecast['dt_txt'].split()[0]
            # Форматируем дату
            day, month = date.split('-')[2], date.split('-')[1]
            dates.append(f'{day}.{month}')
            temperatures.append(forecast['main']['temp'])
    
    # Если нет данных на 12:00, берем каждую 8-ю запись (раз в сутки)
    if not dates:
        for i in range(0, min(40, len(forecast_data['list'])), 8):
            forecast = forecast_data['list'][i]
            date = forecast['dt_txt'].split()[0]
            day, month = date.split('-')[2], date.split('-')[1]
            dates.append(f'{day}.{month}')
            temperatures.append(forecast['main']['temp'])
    
    plt.figure(figsize=(10, 5))
    plt.plot(dates, temperatures, marker='o', linewidth=2, markersize=8, color='#FF6B35')
    plt.xlabel('Дата', fontsize=12)
    plt.ylabel('Температура (°C)', fontsize=12)
    plt.title('Прогноз температуры на 5 дней', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()

    # Сохраняем в буфер
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close()
    
    return buf


def get_weather(city=None, latitude=None, longitude=None):
    """Получение текущей погоды"""
    try:
        if city:
            url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&lang=ru'
        else:
            url = f'http://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&appid={API_KEY}&units=metric&lang=ru'
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('cod') != 200:
            logger.error(f"API returned error code: {data.get('cod')}")
            return None
        
        # Переводим описание
        description = data['weather'][0]['description']
        data['weather'][0]['description_ru'] = weather_descriptions.get(
            description,
            description
        )
        
        return data
        
    except requests.exceptions.Timeout:
        logger.error("Request timeout")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"API error: {e}")
        return None
    except (KeyError, IndexError) as e:
        logger.error(f"Data parsing error: {e}")
        return None


def get_forecast(city=None, latitude=None, longitude=None):
    """Получение прогноза на 5 дней"""
    try:
        if city:
            url = f'http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric&lang=ru'
        else:
            url = f'http://api.openweathermap.org/data/2.5/forecast?lat={latitude}&lon={longitude}&appid={API_KEY}&units=metric&lang=ru'
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('cod') != '200':
            logger.error(f"Forecast API returned error code: {data.get('cod')}")
            return None
        
        # Переводим описание для каждой записи
        for entry in data['list']:
            description = entry['weather'][0]['description']
            entry['weather'][0]['description_ru'] = weather_descriptions.get(
                description,
                description
            )
        
        return data
        
    except requests.exceptions.Timeout:
        logger.error("Forecast request timeout")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Forecast API error: {e}")
        return None
    except (KeyError, IndexError) as e:
        logger.error(f"Forecast data parsing error: {e}")
        return None


def get_clothing_advice_text(description):
    """Получение совета по одежде"""
    return clothing_advice.get(
        description,
        'Одевайтесь по погоде! 👔'
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('weather_'))
def send_weather(call):
    """Отправка прогноза погоды"""
    try:
        data_parts = call.data.split('_')
        
        # Определяем тип запроса
        if data_parts[1] == 'city':
            city = '_'.join(data_parts[2:])  # Города могут содержать _
            weather_data = get_weather(city=city)
            forecast_data = get_forecast(city=city)
            location_name = city
        else:  # location
            latitude = float(data_parts[2])
            longitude = float(data_parts[3])
            weather_data = get_weather(latitude=latitude, longitude=longitude)
            forecast_data = get_forecast(latitude=latitude, longitude=longitude)
            location_name = f"координаты ({latitude:.2f}, {longitude:.2f})"

        # Проверка на ошибки
        if not weather_data:
            bot.send_message(
                call.message.chat.id,
                '❌ Не удалось получить данные о погоде.\n'
                'Проверьте название города или попробуйте позже.'
            )
            return

        # Извлекаем данные
        description = weather_data['weather'][0].get('description_ru', weather_data['weather'][0]['description'])
        temp = weather_data['main']['temp']
        feels_like = weather_data['main']['feels_like']
        humidity = weather_data['main']['humidity']
        pressure = weather_data['main']['pressure']
        wind_speed = weather_data['wind']['speed']
        
        # Получаем иконку от OpenWeather
        icon_code = weather_data['weather'][0]['icon']
        weather_icon_url = f'https://openweathermap.org/img/wn/{icon_code}@4x.png'

        # Получаем совет по одежде
        advice = get_clothing_advice_text(description)

        # Формируем текст
        text = (
            f"🌍 Погода: {location_name}\n\n"
            f"🌦️ {description.capitalize()}\n"
            f"🌡️ Температура: {temp}°C\n"
            f"🌡️ Ощущается как: {feels_like}°C\n"
            f"💧 Влажность: {humidity}%\n"
            f"🔽 Давление: {pressure} гПа\n"
            f"💨 Ветер: {wind_speed} м/с\n\n"
            f"👕 Совет по одежде:\n{advice}"
        )

        # Отправляем текущую погоду с иконкой
        bot.send_photo(call.message.chat.id, weather_icon_url, caption=text)
        
        # Отправляем график и прогноз если доступны
        if forecast_data and len(forecast_data['list']) > 0:
            # График температуры
            try:
                graph_buf = plot_weekly_weather(forecast_data)
                bot.send_photo(
                    call.message.chat.id,
                    graph_buf,
                    caption='📊 График прогноза температуры на 5 дней'
                )
            except Exception as e:
                logger.error(f"Error creating graph: {e}")

            # Прогноз на ближайшие часы
            next_hours = forecast_data['list'][:4]  # 12 часов вперед
            forecast_text = "📅 Прогноз на ближайшие часы:\n\n"
            
            for forecast in next_hours:
                forecast_time = forecast['dt_txt']
                forecast_desc = forecast['weather'][0].get('description_ru', forecast['weather'][0]['description'])
                forecast_temp = forecast['main']['temp']
                forecast_feels = forecast['main']['feels_like']
                forecast_wind = forecast['wind']['speed']

                forecast_text += (
                    f"🕒 {forecast_time}\n"
                    f"   🌦️ {forecast_desc.capitalize()}\n"
                    f"   🌡️ {forecast_temp}°C (ощущается {forecast_feels}°C)\n"
                    f"   💨 {forecast_wind} м/с\n\n"
                )

            bot.send_message(call.message.chat.id, forecast_text)
        else:
            bot.send_message(
                call.message.chat.id,
                '⚠️ Прогноз на ближайшие дни временно недоступен.'
            )
            
    except Exception as e:
        logger.error(f"Error in send_weather: {e}")
        bot.send_message(
            call.message.chat.id,
            '❌ Произошла ошибка при обработке запроса. Попробуйте позже.'
        )


def set_notification_time(message):
    """Установка времени ежедневных уведомлений"""
    try:
        time_str = message.text.strip()
        
        if ':' not in time_str:
            raise ValueError("Invalid format")
        
        parts = time_str.split(':')
        if len(parts) != 2:
            raise ValueError("Invalid format")
            
        hour, minute = int(parts[0]), int(parts[1])
        
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Invalid time range")
        
        # Проверяем наличие города или координат
        if message.chat.id not in user_cities and message.chat.id not in user_locations:
            bot.send_message(
                message.chat.id,
                '⚠️ Сначала выберите город или отправьте геолокацию через /start'
            )
            return
        
        # Сохраняем время
        user_notification_times[message.chat.id] = time(hour, minute)

        # Удаляем старое задание если существует
        job_id = f'weather_{message.chat.id}'
        existing_jobs = [job for job in scheduler.get_jobs() if job.id == job_id]
        for job in existing_jobs:
            scheduler.remove_job(job.id)

        # Создаем новое задание
        scheduler.add_job(
            send_daily_weather,
            'cron',
            hour=hour,
            minute=minute,
            args=[message.chat.id],
            id=job_id,
            replace_existing=True
        )
        
        location_info = user_cities.get(message.chat.id, 'по вашим координатам')
        
        bot.send_message(
            message.chat.id,
            f'🔔 Уведомления установлены!\n\n'
            f'⏰ Время: {time_str} (МСК)\n'
            f'📍 Локация: {location_info}\n\n'
            f'Каждый день в это время я буду присылать прогноз погоды.'
        )
        
        logger.info(f"Notification set for user {message.chat.id} at {time_str}")

    except ValueError as e:
        bot.send_message(
            message.chat.id,
            '⚠️ Некорректный формат времени!\n\n'
            'Используйте формат ЧЧ:ММ\n'
            'Примеры: 09:00, 14:30, 20:15'
        )
    except Exception as e:
        logger.error(f"Error setting notification: {e}")
        bot.send_message(
            message.chat.id,
            '❌ Ошибка при установке уведомлений. Попробуйте позже.'
        )


def send_daily_weather(chat_id):
    """Отправка ежедневного прогноза погоды"""
    try:
        # Определяем источник данных
        if chat_id in user_cities:
            city = user_cities[chat_id]
            weather_data = get_weather(city=city)
            location_name = city
        elif chat_id in user_locations:
            lat, lon = user_locations[chat_id]
            weather_data = get_weather(latitude=lat, longitude=lon)
            location_name = "вашей локации"
        else:
            logger.error(f"No location data for user {chat_id}")
            return
        
        if not weather_data:
            bot.send_message(
                chat_id,
                '❌ Не удалось получить прогноз погоды. Попробую позже.'
            )
            return
        
        # Извлекаем данные
        description = weather_data['weather'][0].get('description_ru', weather_data['weather'][0]['description'])
        temp = weather_data['main']['temp']
        feels_like = weather_data['main']['feels_like']
        wind_speed = weather_data['wind']['speed']
        humidity = weather_data['main']['humidity']
        
        # Получаем иконку
        icon_code = weather_data['weather'][0]['icon']
        weather_icon_url = f'https://openweathermap.org/img/wn/{icon_code}@4x.png'
        
        # Получаем совет
        advice = get_clothing_advice_text(description)
        
        # Формируем сообщение
        text = (
            f"🌅 Доброе утро!\n"
            f"Погода в {location_name}:\n\n"
            f"🌦️ {description.capitalize()}\n"
            f"🌡️ Температура: {temp}°C\n"
            f"🌡️ Ощущается как: {feels_like}°C\n"
            f"💧 Влажность: {humidity}%\n"
            f"💨 Ветер: {wind_speed} м/с\n\n"
            f"👕 {advice}\n\n"
            f"Хорошего дня! ☀️"
        )
        
        bot.send_photo(chat_id, weather_icon_url, caption=text)
        logger.info(f"Daily weather sent to user {chat_id}")
        
    except Exception as e:
        logger.error(f"Error in send_daily_weather for {chat_id}: {e}")


@bot.message_handler(func=lambda message: True)
def unknown_command(message):
    """Обработчик неизвестных команд"""
    bot.send_message(
        message.chat.id,
        '🤔 Не понял эту команду.\n'
        'Используйте /start для главного меню.'
    )


if __name__ == '__main__':
    logger.info("Weather bot started successfully")
    logger.info(f"Scheduler running: {scheduler.running}")
    
    try:
        bot.polling(none_stop=True, interval=0, timeout=20)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        scheduler.shutdown()
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        scheduler.shutdown()
