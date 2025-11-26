// profile.js - Общие функции для всех страниц

// ==================== АУТЕНТИФИКАЦИЯ ====================

// Регистрация пользователя
async function registerUser(email, password) {
    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password })
        });

        if (response.ok) {
            return true;
        } else {
            const error = await response.json();
            alert(error.error || 'Ошибка регистрации');
            return false;
        }
    } catch (error) {
        console.error('Ошибка регистрации:', error);
        alert('Ошибка соединения с сервером');
        return false;
    }
}

// Вход пользователя
async function loginUser(email, password) {
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password })
        });

        if (response.ok) {
            localStorage.setItem('userEmail', email);
            return true;
        } else {
            const error = await response.json();
            alert(error.error || 'Ошибка входа');
            return false;
        }
    } catch (error) {
        console.error('Ошибка входа:', error);
        alert('Ошибка соединения с сервером');
        return false;
    }
}

// Выход из системы
function logout() {
    localStorage.removeItem('userEmail');
    window.location.href = 'login.html';
}

// Проверка авторизации
function isUserLoggedIn() {
    return localStorage.getItem('userEmail') !== null;
}

// Получение текущего email пользователя
function getCurrentUserEmail() {
    return localStorage.getItem('userEmail');
}

// ==================== УСТРОЙСТВА ====================

// Получение списка устройств пользователя
async function getUserDevices() {
    const email = getCurrentUserEmail();
    if (!email) return [];

    try {
        const response = await fetch(`/api/devices?email=${encodeURIComponent(email)}`);
        if (!response.ok) throw new Error('Ошибка загрузки устройств');
        const data = await response.json();

        // Преобразуем массив ID устройств в массив объектов
        return (data.devices || []).map(code => ({
            code: code,
            name: code
        }));
    } catch (error) {
        console.error('Ошибка загрузки устройств:', error);
        return [];
    }
}

// Добавление устройства к аккаунту
async function addDeviceToAccount(deviceCode, deviceName) {
    const email = getCurrentUserEmail();
    if (!email) return false;

    try {
        const response = await fetch('/api/devices', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email: email,
                device_id: deviceCode,
                name: deviceName
            })
        });

        if (response.ok) {
            return true;
        } else {
            const error = await response.json();
            alert(error.error || 'Ошибка добавления устройства');
            return false;
        }
    } catch (error) {
        console.error('Ошибка добавления устройства:', error);
        alert('Ошибка соединения с сервером');
        return false;
    }
}

// Удаление устройства из аккаунта
async function removeDeviceFromAccount(deviceCode) {
    const email = getCurrentUserEmail();
    if (!email) return false;

    try {
        const response = await fetch(`/api/devices/${deviceCode}?email=${encodeURIComponent(email)}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            return true;
        } else {
            const error = await response.json();
            alert(error.error || 'Ошибка удаления устройства');
            return false;
        }
    } catch (error) {
        console.error('Ошибка удаления устройства:', error);
        alert('Ошибка соединения с сервером');
        return false;
    }
}

// ==================== ДАННЫЕ ДАТЧИКОВ ====================

// Загрузка данных устройства
async function loadDeviceData(deviceId) {
    try {
        const response = await fetch(`/api/device/${deviceId}/data`);
        if (!response.ok) throw new Error('Ошибка загрузки данных');
        return await response.json();
    } catch (error) {
        console.error('Ошибка загрузки данных:', error);
        return [];
    }
}

// Загрузка настроек устройства
async function loadDeviceSettings(deviceId) {
    try {
        const response = await fetch(`/api/device/${deviceId}/settings`);
        if (response.ok) {
            return await response.json();
        } else {
            return { target_temp: 20.0, target_hum: 50.0, log_interval: 30 };
        }
    } catch (error) {
        console.error('Ошибка загрузки настроек:', error);
        return { target_temp: 20.0, target_hum: 50.0, log_interval: 30 };
    }
}

// Сохранение настроек устройства
async function saveDeviceSettings(deviceId, settings) {
    try {
        const response = await fetch(`/api/device/${deviceId}/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            return true;
        } else {
            alert('Ошибка сохранения настроек');
            return false;
        }
    } catch (error) {
        console.error('Ошибка сохранения настроек:', error);
        alert('Ошибка соединения с сервером');
        return false;
    }
}

// ==================== УТИЛИТЫ ====================

// Проверка авторизации при загрузке страницы
function checkAuth() {
    if (!isUserLoggedIn()) {
        window.location.href = 'login.html';
        return false;
    }
    return true;
}

// Форматирование даты
function formatDateTime(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('ru-RU');
}

// Форматирование времени
function formatTime(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Определение зоны комфорта
function getZoneForValue(value, param, settings) {
    if (!settings) return 'danger';

    if (param === 'lux') {
        if (value >= 300 && value <= 750) return 'comfort';
        if (value >= 150 && value <= 1000) return 'warning';
        return 'danger';
    }

    let target = param === 'temp' ? settings.target_temp : settings.target_hum;
    let diff = Math.abs(value - target);

    if (param === 'temp') {
        if (diff <= 2) return 'comfort';
        if (diff <= 5) return 'warning';
        return 'danger';
    } else {
        if (diff <= 5) return 'comfort';
        if (diff <= 10) return 'warning';
        return 'danger';
    }
}

// Обновление класса метрики
function updateMetricClass(element, zone) {
    element.classList.remove('metric--comfort', 'metric--warning', 'metric--danger');
    element.classList.add(`metric--${zone}`);
}

// Показать уведомление
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        background: ${type === 'error' ? '#ef476f' : type === 'success' ? '#06d6a0' : '#4361ee'};
        color: white;
        border-radius: 8px;
        z-index: 1000;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        font-weight: 600;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 3000);
}