import os
import json
import csv
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import numpy as np

class PDFReportGeneratorEN:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_styles()
    
    def setup_styles(self):
        """Setup styles for English PDF"""
        self.title_style = ParagraphStyle(
            name='CustomTitleEN',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1,
            textColor=colors.HexColor('#4361ee')
        )
        
        self.heading_style = ParagraphStyle(
            name='CustomHeadingEN',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=colors.HexColor('#4361ee')
        )
        
        self.normal_style = self.styles['Normal']
        self.normal_style.fontSize = 10
        self.normal_style.spaceAfter = 6
    
    def generate_report(self, device_id, data, param, period, output_path):
        """Generate PDF report in English"""
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        story = []
        
        # Report title
        title_text = self.get_title_text(param, period)
        story.append(Paragraph(title_text, self.title_style))
        
        # Device information
        device_info = f"Device: {device_id} | Period: {self.get_period_text(period)}"
        story.append(Paragraph(device_info, self.normal_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", self.normal_style))
        story.append(Spacer(1, 20))
        
        # Summary statistics
        story.append(Paragraph("Summary Statistics", self.heading_style))
        summary_table = self.create_summary_table(data, param)
        if summary_table:
            story.append(summary_table)
            story.append(Spacer(1, 15))
        
        # Detailed analysis
        story.append(Paragraph("Detailed Analysis", self.heading_style))
        analysis_content = self.create_detailed_analysis(data, param)
        story.extend(analysis_content)
        
        # Recommendations
        story.append(Paragraph("Recommendations", self.heading_style))
        recommendations = self.generate_recommendations(data, param)
        for rec in recommendations:
            story.append(Paragraph(f"• {rec}", self.normal_style))
            story.append(Spacer(1, 3))
        
        doc.build(story)
    
    def get_title_text(self, param, period):
        """Get report title based on parameter"""
        param_titles = {
            'temp': "Temperature Analysis Report",
            'hum': "Humidity Analysis Report",
            'lux': "Illuminance Analysis Report", 
            'all': "Comprehensive Climate Analysis Report"
        }
        return param_titles.get(param, "Data Analysis Report")
    
    def get_period_text(self, period):
        """Text description of period"""
        period_names = {
            'day': "Last 24 hours",
            'week': "Last week", 
            'month': "Last month",
            'all': "All time"
        }
        return period_names.get(period, period)
    
    def create_summary_table(self, data, param):
        """Create summary statistics table"""
        if not data:
            return None
        
        try:
            if param == 'all':
                temps = [d['temp'] for d in data]
                hums = [d['hum'] for d in data]
                luxs = [d['lux'] for d in data]
                
                summary_data = [
                    ['Parameter', 'Temperature (°C)', 'Humidity (%)', 'Illuminance (lux)'],
                    ['Average', f'{np.mean(temps):.1f}', f'{np.mean(hums):.1f}', f'{np.mean(luxs):.0f}'],
                    ['Min', f'{min(temps):.1f}', f'{min(hums):.1f}', f'{min(luxs):.0f}'],
                    ['Max', f'{max(temps):.1f}', f'{max(hums):.1f}', f'{max(luxs):.0f}'],
                    ['Std Dev', f'{np.std(temps):.2f}', f'{np.std(hums):.2f}', f'{np.std(luxs):.2f}']
                ]
                
                table = Table(summary_data, colWidths=[90, 75, 75, 85])
                
            else:
                values = [d[param] for d in data]
                param_names = {
                    'temp': ('Temperature', '°C'),
                    'hum': ('Humidity', '%'),
                    'lux': ('Illuminance', 'lux')
                }
                name, unit = param_names.get(param, ('Parameter', ''))
                
                summary_data = [
                    ['Statistic', f'{name} ({unit})'],
                    ['Average', f'{np.mean(values):.1f}'],
                    ['Minimum', f'{min(values):.1f}'],
                    ['Maximum', f'{max(values):.1f}'],
                    ['Std Deviation', f'{np.std(values):.2f}'],
                    ['Measurements', f'{len(values)}']
                ]
                
                table = Table(summary_data, colWidths=[110, 80])
            
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4361ee')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 9)
            ]))
            
            return table
            
        except Exception as e:
            print(f"Table creation error: {e}")
            return None

    def create_detailed_analysis(self, data, param):
        """Create detailed analysis content"""
        content = []
        
        if not data:
            return [Paragraph("Insufficient data for analysis", self.normal_style)]
        
        try:
            if param == 'all':
                temps = [d['temp'] for d in data]
                hums = [d['hum'] for d in data]
                luxs = [d['lux'] for d in data]
                
                # Temperature analysis
                temp_analysis = self.analyze_temperature(temps)
                content.append(Paragraph("<b>Temperature Analysis:</b>", self.normal_style))
                for item in temp_analysis:
                    content.append(Paragraph(f"• {item}", self.normal_style))
                    content.append(Spacer(1, 2))
                
                content.append(Spacer(1, 10))
                
                # Humidity analysis
                hum_analysis = self.analyze_humidity(hums)
                content.append(Paragraph("<b>Humidity Analysis:</b>", self.normal_style))
                for item in hum_analysis:
                    content.append(Paragraph(f"• {item}", self.normal_style))
                    content.append(Spacer(1, 2))
                
                content.append(Spacer(1, 10))
                
                # Illuminance analysis
                lux_analysis = self.analyze_illuminance(luxs)
                content.append(Paragraph("<b>Illuminance Analysis:</b>", self.normal_style))
                for item in lux_analysis:
                    content.append(Paragraph(f"• {item}", self.normal_style))
                    content.append(Spacer(1, 2))
                    
            else:
                values = [d[param] for d in data]
                
                if param == 'temp':
                    analysis = self.analyze_temperature(values)
                    content.append(Paragraph("<b>Detailed Temperature Analysis:</b>", self.normal_style))
                elif param == 'hum':
                    analysis = self.analyze_humidity(values)
                    content.append(Paragraph("<b>Detailed Humidity Analysis:</b>", self.normal_style))
                elif param == 'lux':
                    analysis = self.analyze_illuminance(values)
                    content.append(Paragraph("<b>Detailed Illuminance Analysis:</b>", self.normal_style))
                else:
                    analysis = ["Basic statistical analysis completed"]
                    content.append(Paragraph("<b>Data Analysis:</b>", self.normal_style))
                
                for item in analysis:
                    content.append(Paragraph(f"• {item}", self.normal_style))
                    content.append(Spacer(1, 2))
            
            return content
            
        except Exception as e:
            print(f"Analysis error: {e}")
            return [Paragraph("Error in data analysis", self.normal_style)]

    def analyze_temperature(self, temps):
        """Analyze temperature data"""
        analysis = []
        
        avg_temp = np.mean(temps)
        temp_std = np.std(temps)
        
        analysis.append(f"Average temperature: {avg_temp:.1f}°C")
        
        if avg_temp < 18:
            analysis.append("Temperature below comfortable range (18-24°C)")
        elif avg_temp > 24:
            analysis.append("Temperature above comfortable range (18-24°C)")
        else:
            analysis.append("Temperature within comfortable range")
        
        if temp_std < 1.0:
            analysis.append("Very stable temperature regime")
        elif temp_std > 3.0:
            analysis.append("Significant temperature fluctuations detected")
        else:
            analysis.append("Moderately stable temperature regime")
        
        if max(temps) > 28:
            analysis.append(f"High temperatures detected (up to {max(temps):.1f}°C)")
        if min(temps) < 15:
            analysis.append(f"Low temperatures detected (down to {min(temps):.1f}°C)")
        
        return analysis

    def analyze_humidity(self, hums):
        """Analyze humidity data"""
        analysis = []
        
        avg_hum = np.mean(hums)
        hum_std = np.std(hums)
        
        analysis.append(f"Average humidity: {avg_hum:.1f}%")
        
        if avg_hum < 40:
            analysis.append("Humidity below comfortable range (40-60%)")
        elif avg_hum > 60:
            analysis.append("Humidity above comfortable range (40-60%)")
        else:
            analysis.append("Humidity within comfortable range")
        
        if hum_std < 5.0:
            analysis.append("Very stable humidity level")
        elif hum_std > 15.0:
            analysis.append("Significant humidity fluctuations detected")
        else:
            analysis.append("Moderately stable humidity level")
        
        return analysis

    def analyze_illuminance(self, luxs):
        """Analyze illuminance data"""
        analysis = []
        
        avg_lux = np.mean(luxs)
        
        analysis.append(f"Average illuminance: {avg_lux:.0f} lux")
        
        if avg_lux < 100:
            analysis.append("Very low illuminance (recommended 300-500 lux)")
        elif avg_lux < 300:
            analysis.append("Illuminance below recommended level (300-500 lux)")
        elif avg_lux > 1000:
            analysis.append("Illuminance above recommended level")
        else:
            analysis.append("Illuminance within optimal range")
        
        if max(luxs) > 2000:
            analysis.append("Periods of very bright illumination detected")
        if min(luxs) < 50:
            analysis.append("Periods of very dim illumination detected")
        
        return analysis

    def generate_recommendations(self, data, param):
        """Generate recommendations based on analysis"""
        recommendations = []
        
        if not data:
            return ["Insufficient data for recommendations"]
        
        try:
            if param == 'all':
                temps = [d['temp'] for d in data]
                hums = [d['hum'] for d in data]
                luxs = [d['lux'] for d in data]
                
                # Temperature recommendations
                avg_temp = np.mean(temps)
                if avg_temp < 18:
                    recommendations.append("Increase room temperature to 20-22°C")
                elif avg_temp > 24:
                    recommendations.append("Decrease room temperature to 20-22°C")
                
                # Humidity recommendations
                avg_hum = np.mean(hums)
                if avg_hum < 40:
                    recommendations.append("Use a humidifier to increase humidity")
                elif avg_hum > 60:
                    recommendations.append("Increase ventilation or use a dehumidifier")
                
                # Illuminance recommendations
                avg_lux = np.mean(luxs)
                if avg_lux < 300:
                    recommendations.append("Add artificial lighting to workspace")
                elif avg_lux > 1000:
                    recommendations.append("Use blinds or curtains to reduce illuminance")
                    
            else:
                values = [d[param] for d in data]
                avg_value = np.mean(values)
                
                if param == 'temp':
                    if avg_value < 18:
                        recommendations.append("Increase room temperature to comfortable 20-22°C")
                    elif avg_value > 24:
                        recommendations.append("Decrease room temperature to comfortable 20-22°C")
                    else:
                        recommendations.append("Maintain current temperature regime")
                        
                elif param == 'hum':
                    if avg_value < 40:
                        recommendations.append("Use humidifier to increase humidity level")
                    elif avg_value > 60:
                        recommendations.append("Increase ventilation or use dehumidifier")
                    else:
                        recommendations.append("Current humidity level is optimal")
                        
                elif param == 'lux':
                    if avg_value < 300:
                        recommendations.append("Add artificial light sources")
                    elif avg_value > 1000:
                        recommendations.append("Use protection from excessive light")
                    else:
                        recommendations.append("Illuminance level meets standards")
            
            # General recommendations
            if len(data) < 100:
                recommendations.append("Collect more data for more accurate analysis")
            
            if not recommendations:
                recommendations.append("Climate parameters are within optimal ranges")
                
            return recommendations
            
        except Exception as e:
            print(f"Recommendations error: {e}")
            return ["Recommendations cannot be generated due to analysis error"]

# Global instance for English
pdf_generator_en = PDFReportGeneratorEN()