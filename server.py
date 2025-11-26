import os
import json
import csv
import time
import socket
import requests
import numpy as np
import tempfile
import base64
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from analytics import analytics_engine
from pdfru import pdf_generator_ru
from pdfen import pdf_generator_en

# === Настройка путей ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
DATA_DIR = os.path.join(BASE_DIR, 'data')
DEVICES_DIR = os.path.join(BASE_DIR, 'devices')

# Создаём папки, если их нет
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DEVICES_DIR, exist_ok=True)

# Файл пользователей
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f)

app = Flask(__name__, static_folder=STATIC_FOLDER)

# === НАСТРОЙКИ TELEGRAM ===
TELEGRAM_BOT_TOKEN = "8468881082:AAGCN5mKa0u80yUwhQHzHOthamKlas0Gfd0"  # Замени на настоящий токен


def send_telegram_message(chat_id, message):
    """Отправка сообщения в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Ошибка отправки Telegram: {e}")
        return False


# === Вспомогательные функции ===

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def load_users():
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def get_device_file(device_id):
    return os.path.join(DEVICES_DIR, f"{device_id}.csv")


def get_settings_file(device_id):
    return os.path.join(DEVICES_DIR, f"{device_id}.settings.json")


def ensure_device_file(device_id):
    file_path = get_device_file(device_id)
    if not os.path.exists(file_path):
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'temp', 'hum', 'lux'])


def ensure_settings_file(device_id):
    settings_file = get_settings_file(device_id)
    if not os.path.exists(settings_file):
        default = {'target_temp': 20.0, 'target_hum': 50.0, 'log_interval': 30}
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(default, f, indent=2)


# === Проверка условий и отправка уведомлений ===

def check_alerts(device_id, temp, hum, lux):
    """Проверяет условия и отправляет уведомления при необходимости"""
    try:
        settings_file = os.path.join(DEVICES_DIR, f"{device_id}.notifications.json")
        if not os.path.exists(settings_file):
            return

        with open(settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)

        if not settings.get('telegram_enabled') or not settings.get('telegram_chat_id'):
            return

        alerts = settings.get('alerts', {})
        chat_id = settings['telegram_chat_id']
        messages = []

        # Проверка температуры
        if settings.get('notify_temp', True):
            if temp < alerts.get('temp_min', 18):
                messages.append(f"🌡️ Температура НИЗКАЯ: {temp:.1f}°C (мин: {alerts['temp_min']}°C)")
            elif temp > alerts.get('temp_max', 25):
                messages.append(f"🌡️ Температура ВЫСОКАЯ: {temp:.1f}°C (макс: {alerts['temp_max']}°C)")

        # Проверка влажности
        if settings.get('notify_hum', True):
            if hum < alerts.get('hum_min', 40):
                messages.append(f"💧 Влажность НИЗКАЯ: {hum:.1f}% (мин: {alerts['hum_min']}%)")
            elif hum > alerts.get('hum_max', 60):
                messages.append(f"💧 Влажность ВЫСОКАЯ: {hum:.1f}% (макс: {alerts['hum_max']}%)")

        # Проверка освещенности
        if settings.get('notify_lux', False):
            if lux < alerts.get('lux_min', 100):
                messages.append(f"☀️ Освещенность НИЗКАЯ: {lux} лк (мин: {alerts['lux_min']} лк)")
            elif lux > alerts.get('lux_max', 1000):
                messages.append(f"☀️ Освещенность ВЫСОКАЯ: {lux} лк (макс: {alerts['lux_max']} лк)")

        # Отправка сообщений
        if messages:
            message = f"🚨 <b>Устройство {device_id}</b>\n" + "\n".join(messages)
            send_telegram_message(chat_id, message)

    except Exception as e:
        print(f"❌ Ошибка проверки алертов: {e}")


# === API: Регистрация и вход ===

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    if not email or len(password) < 6:
        return jsonify({'error': 'Некорректные данные'}), 400

    users = load_users()
    if email in users:
        return jsonify({'error': 'Пользователь уже существует'}), 409

    users[email] = {'password': password, 'devices': []}
    save_users(users)
    return jsonify({'success': True})


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    users = load_users()
    user = users.get(email)
    if user and user['password'] == password:
        return jsonify({'success': True})
    return jsonify({'error': 'Неверный email или пароль'}), 401


# === API: Устройства ===

@app.route('/api/devices', methods=['GET'])
def api_get_devices():
    email = request.args.get('email', '').strip().lower()
    users = load_users()
    if email in users:
        return jsonify({'devices': users[email]['devices']})
    return jsonify({'devices': []})


@app.route('/api/devices', methods=['POST'])
def api_add_device():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    device_id = data.get('device_id', '').strip().upper()
    name = data.get('name', '').strip()

    if not email or not device_id or not name:
        return jsonify({'error': 'Недостаточно данных'}), 400

    users = load_users()
    if email not in users:
        return jsonify({'error': 'Пользователь не найден'}), 404

    # Проверяем, занято ли устройство
    for u in users.values():
        if device_id in u['devices']:
            return jsonify({'error': 'Устройство уже используется'}), 409

    if device_id not in users[email]['devices']:
        users[email]['devices'].append(device_id)
        save_users(users)
        ensure_device_file(device_id)
        ensure_settings_file(device_id)

    return jsonify({'success': True})


@app.route('/api/devices/<device_id>', methods=['DELETE'])
def api_remove_device(device_id):
    email = request.args.get('email', '').strip().lower()
    users = load_users()
    if email in users and device_id in users[email]['devices']:
        users[email]['devices'].remove(device_id)
        save_users(users)
        # Удаляем файлы
        for f in [get_device_file(device_id), get_settings_file(device_id)]:
            if os.path.exists(f):
                os.remove(f)
        return jsonify({'success': True})
    return jsonify({'error': 'Устройство не найдено'}), 404


# === API: Настройки устройства ===

@app.route('/api/device/<device_id>/settings', methods=['GET'])
def get_device_settings(device_id):
    settings_file = get_settings_file(device_id)
    if os.path.exists(settings_file):
        with open(settings_file, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({'target_temp': 20.0, 'target_hum': 50.0, 'log_interval': 30})


@app.route('/api/device/<device_id>/settings', methods=['POST'])
def save_device_settings(device_id):
    data = request.get_json()
    settings = {
        'target_temp': float(data.get('target_temp', 20.0)),
        'target_hum': float(data.get('target_hum', 50.0)),
        'log_interval': int(data.get('log_interval', 30))
    }
    settings_file = get_settings_file(device_id)
    with open(settings_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    return jsonify({'status': 'ok'})


# === API: Настройки уведомлений ===

@app.route('/api/device/<device_id>/notification-settings', methods=['GET'])
def get_notification_settings(device_id):
    settings_file = os.path.join(DEVICES_DIR, f"{device_id}.notifications.json")
    default_settings = {
        'telegram_enabled': False,
        'telegram_chat_id': '',
        'alerts': {
            'temp_min': 18.0,
            'temp_max': 25.0,
            'hum_min': 40.0,
            'hum_max': 60.0,
            'lux_min': 100,
            'lux_max': 1000
        },
        'notify_temp': True,
        'notify_hum': True,
        'notify_lux': False
    }

    if os.path.exists(settings_file):
        with open(settings_file, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify(default_settings)


@app.route('/api/device/<device_id>/notification-settings', methods=['POST'])
def save_notification_settings(device_id):
    data = request.get_json()
    settings_file = os.path.join(DEVICES_DIR, f"{device_id}.notifications.json")

    with open(settings_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return jsonify({'status': 'ok'})


# === API: Тестовое Telegram уведомление ===

@app.route('/api/test-telegram', methods=['GET'])
def test_telegram_notification():
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({'error': 'Chat ID не указан'}), 400

    message = (
        "✅ <b>Тестовое уведомление</b>\n"
        "Система мониторинга микроклимата\n"
        "Это тестовое сообщение подтверждает, что уведомления работают корректно!\n"
        f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    if send_telegram_message(chat_id, message):
        return jsonify({'status': 'ok', 'message': 'Тестовое уведомление отправлено'})
    else:
        return jsonify({'error': 'Не удалось отправить сообщение'}), 500


# === API: Расширенная аналитика ===

@app.route('/api/device/<device_id>/analytics/trends')
def get_trend_analysis(device_id):
    """Анализ тенденций и прогнозирование"""
    try:
        # Загружаем данные устройства
        file_path = get_device_file(device_id)
        if not os.path.exists(file_path):
            return jsonify({'error': 'Данные не найдены'}), 404

        data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append({
                    'timestamp': int(row['timestamp']),
                    'temp': float(row['temp']),
                    'hum': float(row['hum']),
                    'lux': float(row['lux'])
                })

        # Получаем прогноз
        hours_ahead = request.args.get('hours', default=6, type=int)
        trends = analytics_engine.predict_trends(data, hours_ahead)
        return jsonify(trends)

    except Exception as e:
        return jsonify({'error': f'Ошибка анализа трендов: {str(e)}'}), 500


@app.route('/api/device/<device_id>/analytics/correlations')
def get_correlation_analysis(device_id):
    """Анализ корреляций между параметрами"""
    try:
        file_path = get_device_file(device_id)
        if not os.path.exists(file_path):
            return jsonify({'error': 'Данные не найдены'}), 404

        data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append({
                    'timestamp': int(row['timestamp']),
                    'temp': float(row['temp']),
                    'hum': float(row['hum']),
                    'lux': float(row['lux'])
                })

        correlations = analytics_engine.analyze_correlations(data)
        return jsonify(correlations)

    except Exception as e:
        return jsonify({'error': f'Ошибка анализа корреляций: {str(e)}'}), 500


@app.route('/api/device/<device_id>/analytics/anomalies')
def get_anomaly_analysis(device_id):
    """Обнаружение аномалий в данных"""
    try:
        file_path = get_device_file(device_id)
        if not os.path.exists(file_path):
            return jsonify({'error': 'Данные не найдены'}), 404

        data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append({
                    'timestamp': int(row['timestamp']),
                    'temp': float(row['temp']),
                    'hum': float(row['hum']),
                    'lux': float(row['lux'])
                })

        anomalies = analytics_engine.detect_anomalies(data)
        return jsonify(anomalies)

    except Exception as e:
        return jsonify({'error': f'Ошибка обнаружения аномалий: {str(e)}'}), 500


@app.route('/api/device/<device_id>/analytics/summary')
def get_analytics_summary(device_id):
    """Сводная аналитика по всем аспектам"""
    try:
        file_path = get_device_file(device_id)
        if not os.path.exists(file_path):
            return jsonify({'error': 'Данные не найдены'}), 404

        data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append({
                    'timestamp': int(row['timestamp']),
                    'temp': float(row['temp']),
                    'hum': float(row['hum']),
                    'lux': float(row['lux'])
                })

        # Получаем все виды аналитики
        trends = analytics_engine.predict_trends(data, 6)
        correlations = analytics_engine.analyze_correlations(data)
        anomalies = analytics_engine.detect_anomalies(data)

        summary = {
            "device_id": device_id,
            "data_points": len(data),
            "period": {
                "start": datetime.fromtimestamp(data[0]['timestamp']).strftime('%Y-%m-%d'),
                "end": datetime.fromtimestamp(data[-1]['timestamp']).strftime('%Y-%m-%d'),
                "days": (data[-1]['timestamp'] - data[0]['timestamp']) / 86400
            },
            "trends": trends,
            "correlations": correlations,
            "anomalies": anomalies
        }

        return jsonify(summary)

    except Exception as e:
        return jsonify({'error': f'Ошибка сводной аналитики: {str(e)}'}), 500


# === API: Приём данных с ESP32 ===

@app.route('/api/sensor_data', methods=['POST'])
def receive_sensor_data():
    """Прием одиночных данных с датчиков"""
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        temp = data.get('temp')
        hum = data.get('hum')
        lux = data.get('lux')
        timestamp = data.get('timestamp', int(time.time()))

        if not device_id or temp is None or hum is None or lux is None:
            print("❌ Ошибка: недостаточно данных в запросе")
            return jsonify({'error': 'Недостаточно данных'}), 400

        # Убедимся, что файлы существуют
        ensure_device_file(device_id)
        file_path = get_device_file(device_id)

        # Записываем данные
        with open(file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, temp, hum, lux])

        # Проверяем алерты
        check_alerts(device_id, temp, hum, lux)

        print(f"✅ Приняты данные от {device_id}: T={temp}°C, H={hum}%, L={lux} лк")
        return jsonify({'status': 'ok', 'received': 1})

    except Exception as e:
        print(f"❌ Ошибка приема данных: {e}")
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


# === API: Приём пачек данных с ESP32 ===

@app.route('/api/sensor_batch', methods=['POST'])
def receive_sensor_batch():
    """Прием пачек данных с датчиков"""
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        batch_data = data.get('data', [])

        if not device_id or not batch_data:
            print("❌ Ошибка: недостаточно данных в запросе")
            return jsonify({'error': 'Недостаточно данных'}), 400

        if not isinstance(batch_data, list):
            return jsonify({'error': 'Данные должны быть массивом'}), 400

        # Убедимся, что файлы существуют
        ensure_device_file(device_id)
        file_path = get_device_file(device_id)

        # Записываем данные пачкой
        records_written = 0
        with open(file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            for record in batch_data:
                temp = record.get('temp')
                hum = record.get('hum')
                lux = record.get('lux')
                timestamp = record.get('timestamp', int(time.time()))

                if temp is not None and hum is not None and lux is not None:
                    writer.writerow([timestamp, temp, hum, lux])
                    records_written += 1

                    # Проверяем алерты для каждой записи
                    check_alerts(device_id, temp, hum, lux)

        print(f"✅ Принята пачка от {device_id}: {records_written} записей")
        return jsonify({'status': 'ok', 'received': records_written})

    except Exception as e:
        print(f"❌ Ошибка приема пачки данных: {e}")
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


@app.route('/api/sensor_array', methods=['POST'])
def receive_sensor_array():
    """Прием данных в формате массива (более компактный)"""
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        count = data.get('count', 0)
        array_data = data.get('data', [])

        if not device_id or not array_data:
            return jsonify({'error': 'Недостаточно данных'}), 400

        # Убедимся, что файлы существуют
        ensure_device_file(device_id)
        file_path = get_device_file(device_id)

        # Записываем данные
        records_written = 0
        with open(file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            for record in array_data:
                if len(record) >= 4:  # [timestamp, temp, hum, lux]
                    timestamp, temp, hum, lux = record[0], record[1], record[2], record[3]
                    writer.writerow([timestamp, temp, hum, lux])
                    records_written += 1

                    # Проверяем алерты
                    check_alerts(device_id, temp, hum, lux)

        print(f"✅ Принят массив от {device_id}: {records_written} записей")
        return jsonify({'status': 'ok', 'received': records_written})

    except Exception as e:
        print(f"❌ Ошибка приема массива данных: {e}")
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


# === API: Генерация отчетов ===

@app.route('/api/device/<device_id>/report/generate', methods=['POST'])
def generate_report(device_id):
    """Генерация PDF отчета"""
    try:
        data = request.get_json()
        period = data.get('period', 'week')
        report_type = data.get('type', 'summary')

        # Загружаем данные устройства
        file_path = get_device_file(device_id)
        if not os.path.exists(file_path):
            return jsonify({'error': 'Данные не найдены'}), 404

        sensor_data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sensor_data.append({
                    'timestamp': int(row['timestamp']),
                    'temp': float(row['temp']),
                    'hum': float(row['hum']),
                    'lux': float(row['lux'])
                })

        # Фильтруем данные по периоду
        filtered_data = filter_data_by_period(sensor_data, period)

        if not filtered_data:
            return jsonify({'error': 'Нет данных за выбранный период'}), 400

        # Создаем временный файл для PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            pdf_path = temp_file.name

        # Генерируем PDF отчет
        report_generator.generate_pdf_report(device_id, filtered_data, period, pdf_path)

        # Читаем PDF и кодируем в base64
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()

        # Удаляем временный файл
        os.unlink(pdf_path)

        # Возвращаем PDF как base64
        return jsonify({
            'status': 'ok',
            'pdf_data': base64.b64encode(pdf_data).decode('utf-8'),
            'filename': f'report_{device_id}_{period}_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
        })

    except Exception as e:
        print(f"❌ Ошибка генерации отчета: {e}")
        return jsonify({'error': f'Ошибка генерации отчета: {str(e)}'}), 500


@app.route('/api/device/<device_id>/report/compare', methods=['POST'])
def compare_periods(device_id):
    """Сравнение двух периодов"""
    try:
        data = request.get_json()
        period1 = data.get('period1', 'week')
        period2 = data.get('period2', 'month')

        # Загружаем данные
        file_path = get_device_file(device_id)
        if not os.path.exists(file_path):
            return jsonify({'error': 'Данные не найдены'}), 404

        sensor_data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sensor_data.append({
                    'timestamp': int(row['timestamp']),
                    'temp': float(row['temp']),
                    'hum': float(row['hum']),
                    'lux': float(row['lux'])
                })

        # Фильтруем данные для двух периодов
        data1 = filter_data_by_period(sensor_data, period1)
        data2 = filter_data_by_period(sensor_data, period2)

        if not data1 or not data2:
            return jsonify({'error': 'Недостаточно данных для сравнения'}), 400

        # Анализируем оба периода
        comparison = analyze_period_comparison(data1, data2, period1, period2)

        return jsonify(comparison)

    except Exception as e:
        print(f"❌ Ошибка сравнения периодов: {e}")
        return jsonify({'error': f'Ошибка сравнения периодов: {str(e)}'}), 500


@app.route('/api/device/<device_id>/report/hourly-stats')
def get_hourly_statistics(device_id):
    """Статистика по времени суток"""
    try:
        period = request.args.get('period', 'all')

        # Загружаем данные
        file_path = get_device_file(device_id)
        if not os.path.exists(file_path):
            return jsonify({'error': 'Данные не найдены'}), 404

        sensor_data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sensor_data.append({
                    'timestamp': int(row['timestamp']),
                    'temp': float(row['temp']),
                    'hum': float(row['hum']),
                    'lux': float(row['lux'])
                })

        # Фильтруем данные
        filtered_data = filter_data_by_period(sensor_data, period)

        if not filtered_data:
            return jsonify({'error': 'Нет данных за выбранный период'}), 400

        # Анализируем почасовую статистику
        hourly_stats = analyze_hourly_data(filtered_data)

        return jsonify({
            'period': period,
            'hourly_stats': hourly_stats,
            'summary': summarize_hourly_stats(hourly_stats)
        })

    except Exception as e:
        print(f"❌ Ошибка получения почасовой статистики: {e}")
        return jsonify({'error': f'Ошибка получения статистики: {str(e)}'}), 500


def analyze_period_comparison(data1, data2, period1_name, period2_name):
    """Анализ сравнения двух периодов"""

    def calculate_stats(data):
        temps = [d['temp'] for d in data]
        hums = [d['hum'] for d in data]
        luxs = [d['lux'] for d in data]

        return {
            'temp_mean': np.mean(temps),
            'temp_std': np.std(temps),
            'hum_mean': np.mean(hums),
            'hum_std': np.std(hums),
            'lux_mean': np.mean(luxs),
            'lux_std': np.std(luxs),
            'count': len(data)
        }

    stats1 = calculate_stats(data1)
    stats2 = calculate_stats(data2)

    # Вычисляем изменения
    changes = {}
    for key in ['temp_mean', 'hum_mean', 'lux_mean']:
        value1 = stats1[key]
        value2 = stats2[key]
        change = ((value2 - value1) / value1 * 100) if value1 != 0 else 0
        changes[key] = {
            'absolute': round(value2 - value1, 2),
            'percent': round(change, 1),
            'trend': 'up' if change > 0 else 'down' if change < 0 else 'stable'
        }

    return {
        'periods': {
            period1_name: stats1,
            period2_name: stats2
        },
        'changes': changes,
        'insights': generate_comparison_insights(stats1, stats2, changes)
    }


def analyze_hourly_data(data):
    """Анализ почасовой статистики"""
    hourly_stats = {}

    for record in data:
        dt = datetime.fromtimestamp(record['timestamp'])
        hour = dt.hour

        if hour not in hourly_stats:
            hourly_stats[hour] = {
                'temp_values': [],
                'hum_values': [],
                'lux_values': [],
                'count': 0
            }

        hourly_stats[hour]['temp_values'].append(record['temp'])
        hourly_stats[hour]['hum_values'].append(record['hum'])
        hourly_stats[hour]['lux_values'].append(record['lux'])
        hourly_stats[hour]['count'] += 1

    # Форматируем результат
    result = []
    for hour in sorted(hourly_stats.keys()):
        stats = hourly_stats[hour]
        result.append({
            'hour': hour,
            'temp_avg': np.mean(stats['temp_values']),
            'temp_min': np.min(stats['temp_values']),
            'temp_max': np.max(stats['temp_values']),
            'hum_avg': np.mean(stats['hum_values']),
            'hum_min': np.min(stats['hum_values']),
            'hum_max': np.max(stats['hum_values']),
            'lux_avg': np.mean(stats['lux_values']),
            'count': stats['count']
        })

    return result


def summarize_hourly_stats(hourly_stats):
    """Сводка по почасовой статистике"""
    if not hourly_stats:
        return {}

    max_temp_hour = max(hourly_stats, key=lambda x: x['temp_avg'])
    min_temp_hour = min(hourly_stats, key=lambda x: x['temp_avg'])
    max_hum_hour = max(hourly_stats, key=lambda x: x['hum_avg'])
    min_hum_hour = min(hourly_stats, key=lambda x: x['hum_avg'])

    return {
        'hottest_hour': f"{max_temp_hour['hour']:02d}:00 ({max_temp_hour['temp_avg']:.1f}°C)",
        'coldest_hour': f"{min_temp_hour['hour']:02d}:00 ({min_temp_hour['temp_avg']:.1f}°C)",
        'most_humid_hour': f"{max_hum_hour['hour']:02d}:00 ({max_hum_hour['hum_avg']:.1f}%)",
        'least_humid_hour': f"{min_hum_hour['hour']:02d}:00 ({min_hum_hour['hum_avg']:.1f}%)",
        'temp_variation': round(max_temp_hour['temp_avg'] - min_temp_hour['temp_avg'], 1)
    }


def generate_comparison_insights(stats1, stats2, changes):
    """Генерация инсайтов при сравнении периодов"""
    insights = []

    temp_change = changes['temp_mean']
    hum_change = changes['hum_mean']

    if abs(temp_change['percent']) > 10:
        direction = "повысилась" if temp_change['percent'] > 0 else "понизилась"
        insights.append(f"Температура значительно {direction} на {abs(temp_change['percent'])}%")

    if abs(hum_change['percent']) > 15:
        direction = "повысилась" if hum_change['percent'] > 0 else "понизилась"
        insights.append(f"Влажность значительно {direction} на {abs(hum_change['percent'])}%")

    if stats2['temp_std'] < stats1['temp_std']:
        insights.append("Температурный режим стал более стабильным")
    elif stats2['temp_std'] > stats1['temp_std']:
        insights.append("Увеличились колебания температуры")

    return insights


# === API: Очистка данных SD-карты ===

@app.route('/api/device/<device_id>/clear-sd', methods=['POST'])
def clear_sd_card_data(device_id):
    try:
        # Получаем email из параметров запроса (для проверки прав)
        email = request.args.get('email', '').strip().lower()
        if not email:
            return jsonify({'error': 'Email не указан'}), 400

        # Проверяем, что устройство принадлежит пользователю
        users = load_users()
        if email not in users or device_id not in users[email]['devices']:
            return jsonify({'error': 'Доступ запрещен'}), 403

        # Очищаем файл данных устройства
        device_file = get_device_file(device_id)
        if os.path.exists(device_file):
            # Создаем backup старого файла
            backup_file = f"{device_file}.backup.{int(time.time())}"
            os.rename(device_file, backup_file)

            # Создаем новый пустой файл с заголовком
            with open(device_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'temp', 'hum', 'lux'])

        print(f"✅ Данные SD-карты очищены для устройства {device_id}")
        return jsonify({'status': 'ok', 'message': 'Данные успешно удалены'})

    except Exception as e:
        print(f"❌ Ошибка очистки SD-карты: {e}")
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


# === API: Получение данных для графиков ===

@app.route('/api/device/<device_id>/data')
def get_device_data(device_id):
    file_path = get_device_file(device_id)
    if not os.path.exists(file_path):
        return jsonify({'error': 'Устройство не найдено'}), 404

    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append({
                'timestamp': int(row['timestamp']),
                'temp': float(row['temp']),
                'hum': float(row['hum']),
                'lux': float(row['lux'])
            })
    return jsonify(data[-100000:])  # Возвращаем последние 1000 записей


# === API: Скачивание данных ===

@app.route('/api/device/<device_id>/download')
def download_device_data(device_id):
    file_path = get_device_file(device_id)
    if not os.path.exists(file_path):
        return jsonify({'error': 'Данные не найдены'}), 404

    # Параметры запроса
    param = request.args.get('param', 'all')
    period = request.args.get('period', 'all')

    # Фильтрация по периоду
    now = int(time.time())
    period_seconds = {
        'day': 24 * 3600,
        'week': 7 * 24 * 3600,
        'month': 30 * 24 * 3600,
        'all': 0
    }

    start_time = now - period_seconds.get(period, 0) if period != 'all' else 0

    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = int(row['timestamp'])
            if timestamp >= start_time:
                data.append({
                    'timestamp': timestamp,
                    'temp': float(row['temp']),
                    'hum': float(row['hum']),
                    'lux': float(row['lux'])
                })

    return jsonify(data)


# === API: Генерация PDF отчетов с выбором параметров ===

@app.route('/api/device/<device_id>/report/generate-pdf', methods=['POST'])
def generate_pdf_report_custom(device_id):
    """Генерация PDF отчета с выбранными параметрами"""
    try:
        data = request.get_json()
        period = data.get('period', 'week')
        param = data.get('param', 'all')
        language = data.get('language', 'ru')  # ru или en

        # Загружаем данные устройства
        file_path = get_device_file(device_id)
        if not os.path.exists(file_path):
            return jsonify({'error': 'Данные не найдены'}), 404

        sensor_data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sensor_data.append({
                    'timestamp': int(row['timestamp']),
                    'temp': float(row['temp']),
                    'hum': float(row['hum']),
                    'lux': float(row['lux'])
                })

        # Фильтруем данные по периоду
        filtered_data = filter_data_by_period(sensor_data, period)

        if not filtered_data:
            return jsonify({'error': 'Нет данных за выбранный период'}), 400

        # Создаем временный файл для PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            pdf_path = temp_file.name

        # Выбираем генератор по языку
        if language == 'en':
            pdf_generator_en.generate_report(device_id, filtered_data, param, period, pdf_path)
            filename = f"climate_report_{param}_{period}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        else:
            pdf_generator_ru.generate_report(device_id, filtered_data, param, period, pdf_path)
            filename = f"отчет_климат_{param}_{period}_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf"

        # Читаем PDF и кодируем в base64
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()

        # Удаляем временный файл
        os.unlink(pdf_path)

        # Возвращаем PDF как base64
        return jsonify({
            'status': 'ok',
            'pdf_data': base64.b64encode(pdf_data).decode('utf-8'),
            'filename': filename
        })

    except Exception as e:
        print(f"❌ Ошибка генерации PDF отчета: {e}")
        return jsonify({'error': f'Ошибка генерации отчета: {str(e)}'}), 500


# Вспомогательная функция фильтрации данных
def filter_data_by_period(data, period):
    """Фильтрация данных по периоду"""
    if not data:
        return []

    now = datetime.now().timestamp()
    period_seconds = {
        'day': 24 * 3600,
        'week': 7 * 24 * 3600,
        'month': 30 * 24 * 3600,
        'all': 0
    }

    cutoff_time = now - period_seconds.get(period, 0) if period != 'all' else 0
    return [d for d in data if d['timestamp'] >= cutoff_time]


# === Отдача статических файлов ===

@app.route('/')
def index():
    return send_from_directory(STATIC_FOLDER, 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    path = os.path.join(STATIC_FOLDER, filename)
    if os.path.exists(path):
        return send_from_directory(STATIC_FOLDER, filename)
    return "Файл не найден", 404


# === Запуск сервера ===

if __name__ == '__main__':
    print("✅ Сервер запущен")
    print(f"🌐 Локальный адрес: http://localhost:5000")
    print(f"🌐 В локальной сети: http://{get_local_ip()}:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)