import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
import json


class ClimateAnalytics:
    def __init__(self):
        self.scaler = StandardScaler()

    def prepare_data(self, sensor_data):
        """Подготовка данных для анализа"""
        if not sensor_data:
            return None

        df = pd.DataFrame(sensor_data)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.sort_values('datetime')

        # Добавляем временные признаки
        df['hour'] = df['datetime'].dt.hour
        df['day_of_week'] = df['datetime'].dt.dayofweek
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)

        return df

    def predict_trends(self, sensor_data, hours_ahead=6):
        """Предсказание тенденций на следующие N часов"""
        try:
            df = self.prepare_data(sensor_data)
            if df is None or len(df) < 10:
                return {"error": "Недостаточно данных для прогноза"}

            # Подготовка данных для прогноза температуры
            X = np.array(range(len(df))).reshape(-1, 1)
            y_temp = df['temp'].values

            # Обучаем модель линейной регрессии
            model_temp = LinearRegression()
            model_temp.fit(X, y_temp)

            # Прогноз на следующие hours_ahead периодов
            future_X = np.array(range(len(df), len(df) + hours_ahead)).reshape(-1, 1)
            future_temp = model_temp.predict(future_X)

            # Анализ тренда
            current_trend = "стабильный"
            if len(future_temp) > 1:
                trend_slope = future_temp[-1] - future_temp[0]
                if abs(trend_slope) < 0.5:
                    current_trend = "стабильный"
                elif trend_slope > 0:
                    current_trend = "рост"
                else:
                    current_trend = "падение"

            return {
                "trend": current_trend,
                "predicted_temp": round(float(future_temp[-1]), 1),
                "confidence": "высокая" if len(df) > 50 else "средняя",
                "next_hours": [
                    {
                        "hour": i + 1,
                        "temp": round(float(temp), 1)
                    }
                    for i, temp in enumerate(future_temp)
                ]
            }

        except Exception as e:
            return {"error": f"Ошибка прогнозирования: {str(e)}"}

    def analyze_correlations(self, sensor_data):
        """Анализ корреляций между параметрами"""
        try:
            df = self.prepare_data(sensor_data)
            if df is None or len(df) < 10:
                return {"error": "Недостаточно данных для анализа"}

            # Вычисляем корреляции
            correlations = df[['temp', 'hum', 'lux']].corr()

            temp_hum_corr = correlations.loc['temp', 'hum']
            temp_lux_corr = correlations.loc['temp', 'lux']
            hum_lux_corr = correlations.loc['hum', 'lux']

            # Интерпретация корреляций
            def interpret_correlation(corr):
                abs_corr = abs(corr)
                if abs_corr < 0.3:
                    return "слабая", "нет значимой связи"
                elif abs_corr < 0.7:
                    return "умеренная", "заметная взаимосвязь"
                else:
                    return "сильная", "тесная взаимосвязь"

            temp_hum_strength, temp_hum_meaning = interpret_correlation(temp_hum_corr)
            temp_lux_strength, temp_lux_meaning = interpret_correlation(temp_lux_corr)
            hum_lux_strength, hum_lux_meaning = interpret_correlation(hum_lux_corr)

            return {
                "correlations": {
                    "temp_hum": {
                        "value": round(temp_hum_corr, 3),
                        "strength": temp_hum_strength,
                        "meaning": temp_hum_meaning,
                        "interpretation": "рост температуры → снижение влажности" if temp_hum_corr < 0 else "рост температуры → рост влажности"
                    },
                    "temp_lux": {
                        "value": round(temp_lux_corr, 3),
                        "strength": temp_lux_strength,
                        "meaning": temp_lux_meaning,
                        "interpretation": "освещенность влияет на температуру" if abs(
                            temp_lux_corr) > 0.3 else "связь не обнаружена"
                    },
                    "hum_lux": {
                        "value": round(hum_lux_corr, 3),
                        "strength": hum_lux_strength,
                        "meaning": hum_lux_meaning
                    }
                },
                "insights": self.generate_insights(df, temp_hum_corr, temp_lux_corr)
            }

        except Exception as e:
            return {"error": f"Ошибка анализа корреляций: {str(e)}"}

    def generate_insights(self, df, temp_hum_corr, temp_lux_corr):
        """Генерация инсайтов на основе данных"""
        insights = []

        # Анализ суточных колебаний
        daily_avg = df.groupby('hour').agg({
            'temp': ['mean', 'std'],
            'hum': ['mean', 'std']
        }).round(2)

        max_temp_hour = daily_avg[('temp', 'mean')].idxmax()
        min_temp_hour = daily_avg[('temp', 'mean')].idxmin()

        insights.append(f"📈 Пик температуры обычно в {max_temp_hour}:00")
        insights.append(f"📉 Минимум температуры обычно в {min_temp_hour}:00")

        # Анализ стабильности
        temp_std = df['temp'].std()
        if temp_std < 1.0:
            insights.append("🌡️ Температура очень стабильна")
        elif temp_std > 3.0:
            insights.append("🌡️ Заметны значительные колебания температуры")

        # Корреляционные инсайты
        if temp_hum_corr < -0.5:
            insights.append("🔁 Сильная обратная связь: температура ↑ → влажность ↓")
        elif temp_lux_corr > 0.5:
            insights.append("💡 Освещенность значительно влияет на температуру")

        return insights

    def detect_anomalies(self, sensor_data):
        """Обнаружение аномалий в данных"""
        try:
            df = self.prepare_data(sensor_data)
            if df is None or len(df) < 20:
                return {"error": "Недостаточно данных для обнаружения аномалий"}

            # Подготовка признаков для обнаружения аномалий
            features = df[['temp', 'hum', 'lux']].copy()

            # Масштабирование данных
            scaled_features = self.scaler.fit_transform(features)

            # Обучение модели обнаружения аномалий
            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            anomalies = iso_forest.fit_predict(scaled_features)

            # Помечаем аномалии (-1 - аномалия, 1 - норма)
            df['is_anomaly'] = anomalies
            df['anomaly_score'] = iso_forest.decision_function(scaled_features)

            # Получаем аномальные точки
            anomaly_points = df[df['is_anomaly'] == -1]

            # Анализ типов аномалий
            anomaly_analysis = []
            for _, row in anomaly_points.iterrows():
                anomaly_type = self.classify_anomaly(row)
                anomaly_analysis.append({
                    "timestamp": int(row['timestamp']),
                    "datetime": row['datetime'].strftime('%Y-%m-%d %H:%M'),
                    "temp": round(row['temp'], 1),
                    "hum": round(row['hum'], 1),
                    "lux": int(row['lux']),
                    "type": anomaly_type,
                    "score": round(row['anomaly_score'], 3)
                })

            return {
                "total_anomalies": len(anomaly_points),
                "anomaly_rate": round(len(anomaly_points) / len(df) * 100, 1),
                "anomalies": anomaly_analysis,
                "summary": self.anomaly_summary(anomaly_analysis)
            }

        except Exception as e:
            return {"error": f"Ошибка обнаружения аномалий: {str(e)}"}

    def classify_anomaly(self, row):
        """Классификация типа аномалии"""
        conditions = []

        if row['temp'] > 28:
            conditions.append("высокая температура")
        elif row['temp'] < 15:
            conditions.append("низкая температура")

        if row['hum'] > 75:
            conditions.append("высокая влажность")
        elif row['hum'] < 30:
            conditions.append("низкая влажность")

        if row['lux'] > 1500:
            conditions.append("яркое освещение")
        elif row['lux'] < 50:
            conditions.append("темнота")

        return ", ".join(conditions) if conditions else "необычное сочетание параметров"

    def anomaly_summary(self, anomalies):
        """Сводка по аномалиям"""
        if not anomalies:
            return "Аномалий не обнаружено"

        types = {}
        for anomaly in anomalies:
            for anomaly_type in anomaly['type'].split(', '):
                types[anomaly_type] = types.get(anomaly_type, 0) + 1

        summary_parts = []
        for anomaly_type, count in types.items():
            summary_parts.append(f"{count}× {anomaly_type}")

        return "; ".join(summary_parts)


# Глобальный экземпляр аналитики
analytics_engine = ClimateAnalytics()