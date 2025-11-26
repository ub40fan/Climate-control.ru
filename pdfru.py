import os
import json
import csv
import io
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import numpy as np
import tempfile

# --- НОВЫЕ ИМПОРТЫ ДЛЯ ГРАФИКОВ И АНАЛИТИКИ ---
try:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.font_manager import FontProperties
    import pandas as pd
    from scipy import stats
    from sklearn.linear_model import LinearRegression
except ImportError:
    print("Warning: matplotlib and/or pandas not found. Charts and advanced analytics will fail.")
    plt = None
    pd = None


class PDFReportGeneratorRU:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_fonts()
        self.setup_styles()

        # Mapping для параметров
        self.param_names = {
            'temp': ('Температура', '°C'),
            'hum': ('Влажность', '%'),
            'lux': ('Освещенность', 'лк')
        }

    def setup_fonts(self):
        """Настройка шрифтов с поддержкой кириллицы для reportlab и matplotlib"""
        self.default_font = 'Helvetica'
        font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/Library/Fonts/Arial.ttf',
            'C:/Windows/Fonts/arial.ttf',
            './DejaVuSans.ttf'
        ]
        self.mpl_font = None

        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
                    self.default_font = 'DejaVuSans'
                    if plt:
                        self.mpl_font = FontProperties(fname=font_path, size=10)
                    break
                except:
                    pass
        if self.default_font == 'Helvetica':
            print("Шрифт с кириллицей не найден. Используется Helvetica.")

    def setup_styles(self):
        """Настройка стилей для русского PDF с поддержкой кириллицы"""
        self.title_style = ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontName=self.default_font,
            fontSize=18,
            spaceAfter=30,
            alignment=1,
            textColor=colors.HexColor('#4361ee')
        )

        self.heading_style = ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontName=self.default_font,
            fontSize=14,
            spaceAfter=12,
            textColor=colors.HexColor('#4361ee')
        )

        self.subheading_style = ParagraphStyle(
            name='CustomSubHeading',
            parent=self.styles['Heading3'],
            fontName=self.default_font,
            fontSize=12,
            spaceAfter=8,
            textColor=colors.HexColor('#6c757d')
        )

        self.normal_style = ParagraphStyle(
            name='CustomNormal',
            parent=self.styles['Normal'],
            fontName=self.default_font,
            fontSize=10,
            spaceAfter=6,
            encoding='utf-8'
        )

    # --- ОСНОВНОЙ ГРАФИК БЕЗ ПРОГНОЗА ---
    def _create_time_series_chart(self, data, param, unit):
        """Генерирует основной график временного ряда без прогноза"""
        if plt is None:
            return Paragraph("Не удалось построить график: не найдена библиотека Matplotlib.", self.normal_style)

        try:
            # Подготовка данных
            df = pd.DataFrame(data)
            if 'timestamp' in df.columns:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            else:
                df['datetime'] = pd.date_range(start=datetime.now() - timedelta(days=len(df)),
                                               periods=len(df), freq='H')

            # Создаем фигуру с двумя subplots (основной график + прогноз)
            fig = plt.figure(figsize=(10, 6))  # Увеличили ширину для лучшего отображения
            gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.6)  # Увеличили расстояние между графиками
            ax_main = fig.add_subplot(gs[0])
            ax_forecast = fig.add_subplot(gs[1])

            # --- ОСНОВНОЙ ГРАФИК ---
            # Основные данные
            ax_main.plot(df['datetime'], df[param],
                         label=f'Измерения {self.param_names[param][0]}',
                         color='#4361ee', linewidth=1.5, marker='o', markersize=2)

            # Добавляем вертикальные линии разделения дней
            self._add_day_separators(ax_main, df['datetime'])

            # Настройки основного графика
            ax_main.set_title(f'Динамика {self.param_names[param][0]}', fontsize=14, pad=25)
            ax_main.set_ylabel(f'{self.param_names[param][0]} ({unit})', fontsize=10)
            ax_main.grid(True, linestyle=':', alpha=0.6)
            ax_main.legend(loc='upper left', fontsize=9)

            # Форматирование оси X для основного графика - ТОЛЬКО ВРЕМЯ
            self._format_time_axis(ax_main, df['datetime'])

            # --- ГРАФИК ПРОГНОЗА ---
            # Создаем прогноз на 3 часа
            forecast_data = self._create_forecast_data(df, param, unit)
            if forecast_data:
                times_forecast = forecast_data['times']
                values_forecast = forecast_data['values']

                ax_forecast.plot(times_forecast, values_forecast,
                                 label='Прогноз на 3 часа',
                                 color='#ef233c', linewidth=1.5, linestyle='--', marker='s', markersize=3)

                ax_forecast.set_title('Прогноз на ближайшие 3 часа', fontsize=11, pad=15)
                ax_forecast.set_ylabel(f'{unit}', fontsize=9)
                ax_forecast.grid(True, linestyle=':', alpha=0.4)
                ax_forecast.legend(loc='upper left', fontsize=8)

                # Форматирование оси X для прогноза
                ax_forecast.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax_forecast.xaxis.set_major_locator(mdates.HourLocator(interval=1))
                plt.setp(ax_forecast.xaxis.get_majorticklabels(), rotation=45, fontsize=8)

            # Общие настройки - используем constrained_layout вместо tight_layout
            plt.subplots_adjust(hspace=0.6)  # Ручная настройка расстояния

            # Сохранение графика в буфер памяти
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', pad_inches=0.5)
            plt.close(fig)

            # Создание объекта Image для reportlab
            buf.seek(0)
            img = Image(buf, width=550, height=400)  # Увеличили размер для лучшего отображения
            return img

        except Exception as e:
            print(f"Ошибка при создании графика Matplotlib для {param}: {e}")
            if plt:
                plt.close('all')
            return Paragraph(f"Не удалось построить график: {e}", self.normal_style)

    def _add_day_separators(self, ax, datetimes):
        """Добавляет вертикальные пунктирные линии разделения дней"""
        try:
            # Находим уникальные дни в данных
            unique_days = sorted(set(dt.date() for dt in datetimes))

            # Получаем текущие пределы оси Y
            ylim = ax.get_ylim()
            y_range = ylim[1] - ylim[0]

            for day in unique_days[1:]:  # Пропускаем первый день
                midnight = datetime.combine(day, datetime.min.time())
                ax.axvline(x=midnight, color='gray', linestyle=':', alpha=0.7, linewidth=1)

                # Добавляем подпись даты над графиком (выше максимального значения)
                label_y = ylim[1] + y_range * 0.02  # Немного выше максимального значения
                ax.text(midnight, label_y, day.strftime('%d.%m.%Y'),
                        ha='center', va='bottom', fontsize=8, alpha=0.8,
                        bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))

        except Exception as e:
            print(f"Ошибка добавления разделителей дней: {e}")

    def _format_time_axis(self, ax, datetimes):
        """Форматирует ось времени - показывает только время (00:00, 03:00, и т.д.)"""
        try:
            if len(datetimes) == 0:
                return

            time_range = datetimes.max() - datetimes.min()

            if time_range <= timedelta(days=1):
                # Для периода до 1 дня: метки каждые 3 часа
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            elif time_range <= timedelta(days=2):
                # Для периода до 2 дней: метки каждые 6 часов
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M\n%d.%m'))
            elif time_range <= timedelta(days=7):
                # Для периода до 1 недели: метки каждый день
                ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))
            else:
                # Для периодов больше недели: метки каждые 3 дня
                ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))

            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=8)

        except Exception as e:
            print(f"Ошибка форматирования оси времени: {e}")

    def _create_forecast_data(self, df, param, unit):
        """Создает данные для прогноза на 3 часа"""
        try:
            if len(df) < 5:
                return None

            values = df[param].dropna().values
            if len(values) < 5:
                return None

            # Простая линейная регрессия для прогноза
            X = np.arange(len(values)).reshape(-1, 1)
            y = values
            model = LinearRegression()
            model.fit(X, y)

            # Прогноз на 3 часа вперед
            steps = 3
            future_X = np.arange(len(values), len(values) + steps).reshape(-1, 1)
            predictions = model.predict(future_X)

            # Создаем временные метки для прогноза
            last_time = df['datetime'].iloc[-1]
            forecast_times = [last_time + timedelta(hours=i + 1) for i in range(steps)]

            return {
                'times': forecast_times,
                'values': predictions
            }

        except Exception as e:
            print(f"Ошибка создания прогноза: {e}")
            return None

    # --- ОСТАЛЬНЫЕ МЕТОДЫ БЕЗ ИЗМЕНЕНИЙ ---
    # (predict_trends, analyze_correlations, detect_anomalies, _create_anomalies_table,
    # create_summary_table, create_detailed_analysis_text, _analyze_temperature,
    # _analyze_humidity, _analyze_illuminance, generate_report, create_detailed_analysis,
    # get_title_text, get_period_text)

    def predict_trends(self, data, steps=3):
        """Прогнозирование трендов на следующие steps шагов"""
        predictions = {'temp': [], 'hum': [], 'lux': []}

        try:
            df = pd.DataFrame(data)
            if 'timestamp' not in df.columns:
                return predictions

            df = df.sort_values('timestamp')

            for param in ['temp', 'hum', 'lux']:
                if param in df.columns:
                    values = df[param].dropna().values
                    if len(values) > 5:
                        X = np.arange(len(values)).reshape(-1, 1)
                        y = values
                        model = LinearRegression()
                        model.fit(X, y)

                        future_X = np.arange(len(values), len(values) + steps).reshape(-1, 1)
                        pred = model.predict(future_X)
                        predictions[param] = pred.tolist()

        except Exception as e:
            print(f"Ошибка прогнозирования: {e}")

        return predictions

    def analyze_correlations(self, data):
        """Анализ корреляций между параметрами"""
        try:
            df = pd.DataFrame(data)
            numeric_cols = [col for col in ['temp', 'hum', 'lux'] if col in df.columns]

            if len(numeric_cols) < 2:
                return {'summary': 'Недостаточно параметров для анализа корреляций.'}

            corr_matrix = df[numeric_cols].corr()

            correlations = []
            for i in range(len(numeric_cols)):
                for j in range(i + 1, len(numeric_cols)):
                    corr = corr_matrix.iloc[i, j]
                    param1 = self.param_names[numeric_cols[i]][0]
                    param2 = self.param_names[numeric_cols[j]][0]

                    if abs(corr) > 0.7:
                        relation = "сильная положительная" if corr > 0 else "сильная отрицательная"
                        correlations.append(f"{param1} и {param2}: {relation} связь (r={corr:.2f})")
                    elif abs(corr) > 0.3:
                        relation = "умеренная положительная" if corr > 0 else "умеренная отрицательная"
                        correlations.append(f"{param1} и {param2}: {relation} связь (r={corr:.2f})")

            if correlations:
                summary = "Обнаружены следующие значимые корреляции:\n• " + "\n• ".join(correlations)
            else:
                summary = "Сильных корреляций между параметрами не обнаружено."

            return {'summary': summary, 'matrix': corr_matrix}

        except Exception as e:
            return {'summary': f'Ошибка анализа корреляций: {e}'}

    def detect_anomalies(self, data):
        """Обнаружение аномалий в данных"""
        anomalies = []

        try:
            df = pd.DataFrame(data)

            for param in ['temp', 'hum', 'lux']:
                if param in df.columns:
                    values = df[param].dropna()
                    if len(values) > 5:
                        Q1 = values.quantile(0.25)
                        Q3 = values.quantile(0.75)
                        IQR = Q3 - Q1
                        lower_bound = Q1 - 1.5 * IQR
                        upper_bound = Q3 + 1.5 * IQR

                        param_anomalies = values[(values < lower_bound) | (values > upper_bound)]

                        for idx in param_anomalies.index:
                            anomaly_data = df.iloc[idx].to_dict()
                            anomaly_data['type'] = f'Аномалия {self.param_names[param][0]}'
                            anomalies.append(anomaly_data)

        except Exception as e:
            print(f"Ошибка детекции аномалий: {e}")

        return {'anomalies': anomalies, 'count': len(anomalies)}

    def _create_anomalies_table(self, anomalies):
        """Создает таблицу для отображения аномалий"""
        if not anomalies:
            return [Paragraph("Серьезные аномалии в данных не обнаружены.", self.normal_style)]

        table_data = [
            ['Время', 'Темп (°C)', 'Влаж. (%)', 'Освещ. (лк)', 'Тип аномалии']
        ]

        for anomaly in anomalies[:10]:
            time_str = anomaly.get('timestamp', 'N/A')
            if isinstance(time_str, (int, float)):
                time_str = datetime.fromtimestamp(time_str).strftime('%Y-%m-%d %H:%M')

            table_data.append([
                str(time_str),
                f"{anomaly.get('temp', 0):.1f}",
                f"{anomaly.get('hum', 0):.1f}",
                f"{anomaly.get('lux', 0):.0f}",
                anomaly.get('type', 'Неизвестно')
            ])

        table = Table(table_data, colWidths=[100, 70, 70, 70, 190])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.red),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), self.default_font),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))

        story = [
            Paragraph(f"Обнаружено <b>{len(anomalies)}</b> аномалий (показаны первые {len(anomalies[:10])}):",
                      self.normal_style),
            Spacer(0, 5),
            table
        ]
        return story

    def create_summary_table(self, data, param):
        """Создает сводную таблицу статистики для одного параметра."""
        values = [d.get(param, 0) for d in data if param in d]
        if not values:
            return Paragraph(f"Нет данных для параметра {param}", self.normal_style)

        name, unit = self.param_names.get(param, ('Параметр', ''))

        summary_data = [
            ['Статистика', f'{name} ({unit})'],
            ['Среднее', f'{np.mean(values):.1f}'],
            ['Минимальное', f'{min(values):.1f}'],
            ['Максимальное', f'{max(values):.1f}'],
            ['Станд. отклонение', f'{np.std(values):.2f}'],
            ['Кол-во измерений', f'{len(values)}']
        ]

        table = Table(summary_data, colWidths=[120, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4361ee')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), self.default_font),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        return table

    def create_detailed_analysis_text(self, data, param):
        """Максимально подробный детальный анализ для одного параметра."""
        try:
            values = [d.get(param, 0) for d in data if param in d]
            if not values:
                return [Paragraph("Нет данных для анализа.", self.normal_style)]

            avg_value = np.mean(values)
            std_dev = np.std(values)
            min_value = min(values)
            max_value = max(values)
            name, unit = self.param_names[param]

            analysis = []
            analysis.append(Paragraph(f"<b>{name}: Детальный анализ</b>", self.subheading_style))

            analysis.append(Paragraph(
                f"Среднее значение <b>{name}</b> за период составило <b>{avg_value:.1f} {unit}</b>. Диапазон колебаний: от {min_value:.1f} {unit} до {max_value:.1f} {unit}.",
                self.normal_style))
            analysis.append(
                Paragraph(f"Стандартное отклонение <b>(изменчивость)</b> составляет <b>{std_dev:.2f} {unit}</b>.",
                          self.normal_style))

            if param == 'temp':
                analysis.append(
                    Paragraph(self._analyze_temperature(avg_value, std_dev, min_value, max_value), self.normal_style))
            elif param == 'hum':
                analysis.append(
                    Paragraph(self._analyze_humidity(avg_value, std_dev, min_value, max_value), self.normal_style))
            elif param == 'lux':
                analysis.append(
                    Paragraph(self._analyze_illuminance(avg_value, std_dev, min_value, max_value), self.normal_style))

            analysis.append(Spacer(0, 6))
            return analysis

        except Exception as e:
            return [Paragraph(f"Ошибка при детальном анализе: {e}", self.normal_style)]

    def _analyze_temperature(self, avg, std, min_val, max_val):
        """Анализ температурного режима"""
        if avg < 18:
            status = "Холодный."
            rec = "Средняя температура ниже комфортной зоны (18-24°C). Необходимо увеличить обогрев."
        elif avg > 26:
            status = "Жаркий."
            rec = "Средняя температура превышает комфортную зону. Рекомендуется активное охлаждение или проветривание."
        else:
            status = "Комфортный."
            rec = "Средняя температура находится в оптимальном диапазоне (18-24°C)."

        stability = ""
        if std > 2.5:
            stability = "Зафиксированы значительные перепады температуры. Проверьте стабильность системы."
        else:
            stability = "Температурный режим достаточно стабилен."

        return f"<b>Оценка:</b> {status} {rec} <b>Стабильность:</b> {stability}"

    def _analyze_humidity(self, avg, std, min_val, max_val):
        """Анализ влажности"""
        if avg < 40:
            status = "Низкая."
            rec = "Влажность ниже оптимальной зоны (40-60%). Рекомендуется использовать увлажнитель."
        elif avg > 65:
            status = "Высокая."
            rec = "Влажность выше нормы, создается риск плесени. Необходимо усилить вентиляцию."
        else:
            status = "Оптимальная."
            rec = "Влажность находится в оптимальном диапазоне (40-60%)."

        stability = ""
        if std > 10:
            stability = "Наблюдается высокая нестабильность влажности. Это может быть связано с эпизодическим проветриванием."
        else:
            stability = "Уровень влажности стабилен."

        return f"<b>Оценка:</b> {status} {rec} <b>Стабильность:</b> {stability}"

    def _analyze_illuminance(self, avg, std, min_val, max_val):
        """Анализ освещенности"""
        if avg < 150:
            status = "Низкая."
            rec = "Освещенность недостаточна для комфортной работы (минимум 300 лк). Рекомендуется добавить источники света."
        elif avg > 800:
            status = "Избыточная."
            rec = "Уровень освещенности очень высок, что может привести к утомлению глаз. Рекомендуется использовать затемнение."
        else:
            status = "Удовлетворительная."
            rec = "Уровень освещенности находится в приемлемых пределах."

        peak_analysis = ""
        if max_val > 1500:
            peak_analysis = f" Зафиксированы кратковременные пики (до {max_val:.0f} лк), возможно, связанные с прямым солнечным светом."

        stability = ""
        if std > 200:
            stability = "Освещенность крайне нестабильна, что характерно для естественного освещения или частого переключения."
        else:
            stability = "Освещенность умеренно стабильна."

        return f"<b>Оценка:</b> {status} {rec} <b>Стабильность:</b> {stability} {peak_analysis}"

    def generate_report(self, device_id, data, param, period, output_path):
        """Генерация максимально подробного PDF отчета"""
        if not data:
            with open(output_path, 'w') as f:
                f.write("Нет данных для генерации отчета.")
            return None

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=30,
            bottomMargin=30
        )
        story = []

        # --- ШАГ 1: АНАЛИЗ ДАННЫХ ---
        predictions = self.predict_trends(data)
        correlations = self.analyze_correlations(data)
        anomalies = self.detect_anomalies(data)

        # --- ШАГ 2: ЗАГОЛОВОК И ОБЩАЯ ИНФОРМАЦИЯ ---
        title_text = self.get_title_text(param, period)
        story.append(Paragraph(title_text, self.title_style))

        generated_date = datetime.now().strftime('%d.%m.%Y %H:%M')
        info_text = f"Устройство: <b>{device_id}</b> | Период: <b>{self.get_period_text(period)}</b> | Сгенерирован: <b>{generated_date}</b>"
        story.append(Paragraph(info_text, self.normal_style))
        story.append(Spacer(0, 15))

        # --- ШАГ 3: АНАЛИЗ ПО ПАРАМЕТРАМ ---
        parameters_to_analyze = []
        if param == 'all':
            parameters_to_analyze = [p for p in ['temp', 'hum', 'lux'] if any(p in d for d in data)]
        else:
            parameters_to_analyze = [param] if any(param in d for d in data) else []

        for param_name in parameters_to_analyze:
            name, unit = self.param_names[param_name]

            # 3.1. Заголовок раздела
            story.append(Paragraph(f"Анализ {name.lower()}", self.heading_style))
            story.append(Spacer(0, 5))

            # 3.2. Сводка статистики
            story.append(Paragraph(f"<b>Сводка статистики</b>", self.subheading_style))
            story.append(self.create_summary_table(data, param_name))
            story.append(Spacer(0, 10))

            # 3.3. График отображения
            story.append(Paragraph(f"<b>График динамики</b>", self.subheading_style))
            chart_image = self._create_time_series_chart(data, param_name, unit)
            story.append(chart_image)
            story.append(Spacer(0, 10))

            # 3.4. Детальный анализ
            story.append(Paragraph(f"<b>Детальный анализ</b>", self.subheading_style))
            story.extend(self.create_detailed_analysis_text(data, param_name))
            story.append(Spacer(0, 10))

            # 3.5. Рекомендации
            story.append(Paragraph(f"<b>Рекомендации по {name.lower()}</b>", self.subheading_style))

            values = [d.get(param_name, 0) for d in data if param_name in d]
            avg_value = np.mean(values) if values else 0
            std_value = np.std(values) if len(values) > 1 else 0
            min_value = min(values) if values else 0
            max_value = max(values) if values else 0

            if param_name == 'temp':
                rec_text = self._analyze_temperature(avg_value, std_value, min_value, max_value)
            elif param_name == 'hum':
                rec_text = self._analyze_humidity(avg_value, std_value, min_value, max_value)
            else:
                rec_text = self._analyze_illuminance(avg_value, std_value, min_value, max_value)

            rec_text = rec_text.replace('<b>', '').replace('</b>', '').replace('Оценка: ', '').replace('Стабильность: ',
                                                                                                       '').strip()

            recommendations_list = []
            for rec in rec_text.split('. '):
                if rec.strip() and not rec.startswith('Зафиксированы'):
                    recommendations_list.append(Paragraph(f"• {rec.strip()}.", self.normal_style))

            if not recommendations_list:
                recommendations_list.append(Paragraph("• Параметры в оптимальных пределах.", self.normal_style))

            story.extend(recommendations_list)
            story.append(Spacer(0, 25))

        # --- ШАГ 4: ОБЩИЙ АНАЛИЗ ---
        if param == 'all':
            story.append(Paragraph("Общий Анализ и Корреляции", self.heading_style))
            story.append(Spacer(0, 10))

            # 4.1. Анализ Корреляций
            story.append(Paragraph("Анализ Корреляций", self.subheading_style))
            corr_result = correlations.get('summary', 'Недостаточно данных для анализа корреляций.')
            story.append(Paragraph(corr_result, self.normal_style))
            story.append(Spacer(0, 10))

            # 4.2. Обнаружение Аномалий
            story.append(Paragraph("Обнаружение Аномалий", self.subheading_style))
            anomalies_list = anomalies.get('anomalies', [])
            story.extend(self._create_anomalies_table(anomalies_list))
            story.append(Spacer(0, 10))

            # 4.3. Прогноз Тренда
            story.append(Paragraph("Прогноз Тренда", self.subheading_style))
            if any(predictions.values()):
                prediction_data = [
                    ['Параметр'] + [f'Шаг {i + 1}' for i in range(len(next(iter(predictions.values()))))]]

                for param_name in ['temp', 'hum', 'lux']:
                    if predictions[param_name]:
                        name, unit = self.param_names[param_name]
                        row = [f'{name} ({unit})']
                        row.extend([f'{val:.1f}' for val in predictions[param_name]])
                        prediction_data.append(row)

                table = Table(prediction_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c757d')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), self.default_font),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                ]))
                story.append(table)
            else:
                story.append(Paragraph("Недостаточно данных для построения прогноза.", self.normal_style))

        story.append(Spacer(0, 20))

        # --- ШАГ 5: КОНТАКТНАЯ ИНФОРМАЦИЯ ---
        story.append(Paragraph("Контактная информация", self.subheading_style))
        story.append(Paragraph("По вопросам отчета и анализа данных обращайтесь:", self.normal_style))
        story.append(Paragraph("Email: <b>denisnovikorazr@gmail.com</b>", self.normal_style))

        # --- ШАГ 6: ПОСТРОЕНИЕ ДОКУМЕНТА ---
        try:
            doc.build(story)
        except Exception as e:
            print(f"Ошибка при построении PDF: {e}")
            return None

        try:
            with open(output_path, 'rb') as f:
                pdf_content = f.read()
            return pdf_content
        except Exception as e:
            print(f"Ошибка при чтении PDF: {e}")
            return None

    def create_detailed_analysis(self, analysis_data):
        """Совместимость со старым методом"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                output_path = tmp_file.name

            pdf_content = self.generate_report(
                device_id=analysis_data.get('device_id', 'Unknown'),
                data=analysis_data.get('data', []),
                param=analysis_data.get('parameter', 'all'),
                period=analysis_data.get('period', 'all'),
                output_path=output_path
            )

            try:
                os.unlink(output_path)
            except:
                pass

            return pdf_content

        except Exception as e:
            print(f"Ошибка в create_detailed_analysis: {e}")
            return None

    def get_title_text(self, param, period):
        """Получение заголовка отчета"""
        param_titles = {
            'temp': "Анализ температурного режима",
            'hum': "Анализ уровня влажности",
            'lux': "Анализ освещенности",
            'all': "Комплексный анализ микроклимата"
        }
        return param_titles.get(param, "Анализ данных")

    def get_period_text(self, period):
        """Текстовое описание периода"""
        period_names = {
            'day': "За сегодня",
            'week': "За неделю",
            'month': "За месяц",
            'all': "За весь период"
        }
        return period_names.get(period, period)


# Глобальный экземпляр для русского языка
pdf_generator_ru = PDFReportGeneratorRU()