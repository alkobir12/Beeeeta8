#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مولد عروض الأسعار العربية المحمول
Portable Arabic Quotation Generator

استخدام:
python arabic_quotation.py

المميزات:
- مولد عروض أسعار عربية احترافية
- قوالب متعددة الألوان والأساليب
- واجهة سهلة الاستخدام
- لا يحتاج مكتبات خارجية
- ملف واحد فقط
"""

import os
import webbrowser
import tempfile
from datetime import datetime, timedelta
from typing import Dict


class ArabicQuotationBuilder:
    """بناء عروض الأسعار العربية"""

    def __init__(self):
        self.reset_quotation()
        self.themes = {
            "أزرق": {"primary": "#3b82f6", "secondary": "#1e40af", "accent": "#dbeafe"},
            "أخضر": {"primary": "#10b981", "secondary": "#059669", "accent": "#d1fae5"},
            "بنفسجي": {
                "primary": "#8b5cf6",
                "secondary": "#7c3aed",
                "accent": "#e9d5ff",
            },
            "برتقالي": {
                "primary": "#f59e0b",
                "secondary": "#d97706",
                "accent": "#fef3c7",
            },
            "أحمر": {"primary": "#ef4444", "secondary": "#dc2626", "accent": "#fee2e2"},
            "تركوازي": {
                "primary": "#14b8a6",
                "secondary": "#0d9488",
                "accent": "#ccfbf1",
            },
            "ذهبي": {"primary": "#d97706", "secondary": "#92400e", "accent": "#fef3c7"},
            "رمادي": {
                "primary": "#6b7280",
                "secondary": "#374151",
                "accent": "#f3f4f6",
            },
        }

    def reset_quotation(self):
        """إعادة تعيين بيانات العرض"""
        # 🆕 CR-4: reset the escape guard so a reused generator re-escapes fresh data.
        self._html_escaped = False
        self.company = {
            "name": "شركة الإبداع التقني",
            "name_en": "Creative Tech Solutions",
            "address": "الرياض - المملكة العربية السعودية",
            "phone": "+966 11 123 4567",
            "email": "info@company.sa",
            "website": "www.company.sa",
            "tax_number": "300012345600003",
            "logo": "",
        }

        self.quotation = {
            "number": self._generate_number(),
            "date": datetime.now().strftime("%Y/%m/%d"),
            "valid_until": (datetime.now() + timedelta(days=30)).strftime("%Y/%m/%d"),
            "doc_type": "quote",
            "doc_title": "عرض سعر",
            "client": {
                "name": "العميل المحترم",
                "company": "الشركة المحترمة",
                "address": "العنوان",
                "phone": "+966 XX XXX XXXX",
                "email": "client@email.com",
            },
            "project_description": "وصف مفصل للمشروع أو الخدمة المطلوبة",
            "items": [],
            "subtotal": 0,
            "discount": 0,
            "tax_rate": 0,
            "tax_amount": 0,
            "total": 0,
            "terms": [
                "هذا العرض صالح لمدة 30 يوماً من تاريخ الإصدار",
                "يتطلب دفع 50% مقدماً لبدء العمل",
                "المدة المتوقعة للتسليم حسب نطاق المشروع",
                "الأسعار لا تشمل التعديلات الإضافية غير المذكورة",
                "جميع الأسعار بالريال السعودي",
            ],
        }

    def _generate_number(self) -> str:
        """توليد رقم عرض سعر"""
        now = datetime.now()
        return (
            f"Q-{now.year}-{now.month:02d}{now.day:02d}-{now.hour:02d}{now.minute:02d}"
        )

    def set_company(self, **kwargs):
        """تحديث بيانات الشركة"""
        self.company.update(kwargs)
        return self

    def set_client(self, **kwargs):
        """تحديث بيانات العميل"""
        self.quotation["client"].update(kwargs)
        return self

    def set_project(self, description: str):
        """تحديد وصف المشروع"""
        self.quotation["project_description"] = description
        return self

    def add_item(
        self, description: str, quantity: float, unit_price: float, discount: float = 0
    ):
        """إضافة بند للعرض"""
        total = (quantity * unit_price) - discount
        self.quotation["items"].append(
            {
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "discount": discount,
                "total": total,
            }
        )
        self._calculate_totals()
        return self

    def _calculate_totals(self):
        """حساب المجاميع"""
        subtotal = sum(item["total"] for item in self.quotation["items"])
        total_discount = sum(item["discount"] for item in self.quotation["items"])

        self.quotation["subtotal"] = subtotal + total_discount
        self.quotation["discount"] = total_discount

        taxable_amount = subtotal
        self.quotation["tax_amount"] = taxable_amount * (
            self.quotation["tax_rate"] / 100
        )
        self.quotation["total"] = subtotal + self.quotation["tax_amount"]

    def _render_approval_block(self) -> str:
        # حسب طلب الورشة: لا نعرض QR/Barcode أو أي بيانات موافقة داخل المستندات المطبوعة.
        # تبقى بيانات الاعتماد داخل النظام فقط (ملف العميل/الزيارة).
        return ""

    def _render_if_value(self, value: str, label: str) -> str:
        """عرض الحقل فقط إذا كان له قيمة"""
        if value and str(value).strip():
            return f"""
                        <div class="info-item">
                            <span class="label">{label}:</span>
                            <span class="value">{value}</span>
                        </div>"""
        return ""

    def _render_logo(self) -> str:
        """عرض الشعار إذا كان موجوداً"""
        logo_url = self.company.get("logo", "")
        if logo_url and str(logo_url).strip():
            return f"""<div class="logo">
                        <img src="{logo_url}" alt="شعار الورشة" style="width: 100%; height: 100%; object-fit: contain; border-radius: 50%;" />
                    </div>"""
        else:
            return """<div class="logo">
                        <div class="logo-text">الشعار</div>
                    </div>"""

    def add_term(self, term: str):
        """إضافة شرط"""
        self.quotation["terms"].append(term)
        return self

    def generate_html(self, theme: str = "أزرق", style: str = "حديث") -> str:
        """إنشاء HTML"""
        colors = self.themes.get(theme, self.themes["أزرق"])

        # 🔐 SEC-001: تهريب (escape) كل الحقول القابلة للتحكم من المستخدم قبل الحقن في
        # HTML — يمنع XSS المخزَّن (اسم عميل/وصف بند فيه <script>/<img onerror> يسرق
        # التوكن عند الطباعة). نهرّب مرة واحدة فقط (علم حماية من التهريب المزدوج)،
        # والحقول الرقمية تبقى كما هي.
        if not getattr(self, "_html_escaped", False):
            import html as _html

            def _esc(v):
                return _html.escape(str(v), quote=True) if isinstance(v, str) else v

            for _it in self.quotation.get("items", []):
                if isinstance(_it, dict) and isinstance(_it.get("description"), str):
                    _it["description"] = _esc(_it["description"])
            _cli = self.quotation.get("client") or {}
            for _k in ("name", "company", "address", "phone", "email"):
                if isinstance(_cli.get(_k), str):
                    _cli[_k] = _esc(_cli[_k])
            for _k in ("project_description", "number", "doc_title", "date"):
                if isinstance(self.quotation.get(_k), str):
                    self.quotation[_k] = _esc(self.quotation[_k])
            self.quotation["terms"] = [_esc(_t) for _t in self.quotation.get("terms", [])]
            for _k in ("name", "name_en", "slogan", "address", "phone", "email",
                       "website", "commercial_register"):
                if isinstance(self.company.get(_k), str):
                    self.company[_k] = _esc(self.company[_k])
            self._html_escaped = True

        # إنشاء صفوف البنود
        items_html = ""
        for i, item in enumerate(self.quotation["items"], 1):
            items_html += f"""
            <tr>
                <td>{i}</td>
                <td class="text-right">{item['description']}</td>
                <td>{item['quantity']}</td>
                <td>{item['unit_price']:,.2f}</td>
                <td>{item['discount']:,.2f}</td>
                <td>{item['total']:,.2f}</td>
            </tr>
            """

        # إنشاء تذييل الجدول (الإجماليات)
        table_footer = f"""
        <tfoot>
            <tr class="total-row-table">
                <td colspan="5" class="text-left font-bold">المجموع الكلي</td>
                <td class="font-bold">{self.quotation['total']:,.2f}</td>
            </tr>
        </tfoot>
        """

        # إنشاء قائمة الشروط
        terms_html = ""
        for term in self.quotation["terms"]:
            terms_html += f"<li>{term}</li>"

        # اختيار نمط CSS
        if style == "كلاسيكي":
            css_style = self._get_classic_style(colors)
        elif style == "فاخر":
            css_style = self._get_luxury_style(colors)
        else:
            css_style = self._get_modern_style(colors)

        return f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.quotation['doc_title']} - {self.quotation['number']}</title>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&display=swap" rel="stylesheet">
    <style>
        {css_style}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <div class="header-content">
                <div class="company-section">
                    {self._render_logo()}
                    <div class="company-info">
                        <h1>{self.company['name']}</h1>
                        <p class="company-name-en">{self.company['name_en']}</p>
                        {f'<p class="company-slogan">{self.company.get("slogan", "")}</p>' if self.company.get('slogan') else ''}
                        <p class="company-address">{self.company['address']}</p>
                    </div>
                </div>
                <div class="quote-section">
                    <h2 class="quote-title">{self.quotation['doc_title']}</h2>
                    <p class="quote-number">{self.quotation['number']}</p>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="content">
            <!-- Details Grid -->
            <div class="details-section">
                <div class="client-info">
                    <h3 class="section-title">بيانات العميل</h3>
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="label">الاسم:</span>
                            <span class="value">{self.quotation['client']['name']}</span>
                        </div>
                        {self._render_if_value(self.quotation['client']['company'], 'الشركة')}
                        {self._render_if_value(self.quotation['client']['address'], 'العنوان')}
                        <div class="info-item">
                            <span class="label">الهاتف:</span>
                            <span class="value">{self.quotation['client']['phone']}</span>
                        </div>
                        {self._render_if_value(self.quotation['client']['email'], 'البريد')}
                        {self._render_if_value(self.quotation.get('project_description', ''), 'وصف الخدمة/المشروع')}
                    </div>
                </div>
                
                <div class="quote-info">
                    <h3 class="section-title">بيانات الورشة</h3>
                    <div class="info-grid">
                        {self._render_if_value(self.company.get('commercial_register', ''), 'السجل التجاري')}
                        {self._render_if_value(self.company.get('phone', ''), 'رقم الجوال')}
                        {self._render_if_value(self.company.get('address', ''), 'عنوان الورشة')}
                        <div class="info-item">
                            <span class="label">التاريخ:</span>
                            <span class="value">{self.quotation['date']}</span>
                        </div>

                    </div>
                </div>
            </div>



            <!-- Items Table -->
            <div class="items-section">
                <h3 class="section-title">تفاصيل البنود</h3>
                <div class="table-container">
                    <table class="items-table">
                        <thead>
                            <tr>
                                <th>م</th>
                                <th>الوصف</th>
                                <th>الكمية</th>
                                <th>سعر الوحدة</th>
                                <th>الخصم</th>
                                <th>المجموع</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                        {table_footer}
                    </table>
                </div>
            </div>



            <!-- Signatures -->
            <div class="signatures-section">
                <div class="signature-box">
                    <h4>توقيع العميل</h4>
                    <div class="signature-line"></div>
                    <p>الاسم والتوقيع والتاريخ</p>
                </div>
                <div class="signature-box">
                    <h4>توقيع الورشة</h4>
                    <div class="signature-line"></div>
                    <p>الاسم والتوقيع والتاريخ</p>
                </div>
            </div>
        </main>

        <!-- Footer -->
        <footer class="footer">
            <div class="footer-content">
                <div class="contact-info">
                    <span>البريد: {self.company['email']}</span>
                    <span>الجوال: {self.company['phone']}</span>
                    <span>الموقع: {self.company['website']}</span>
                </div>
                <p>&copy; 2024 {self.company['name']} - جميع الحقوق محفوظة</p>
            </div>
        </footer>
    </div>

    <script>
        // وظائف الطباعة والتصدير
        function printQuote() {{
            window.print();
        }}
        
        // تحسين العرض
        document.addEventListener('DOMContentLoaded', function() {{
            // تطبيق تأثيرات بصرية
            const tables = document.querySelectorAll('.items-table tr');
            tables.forEach(row => {{
                row.addEventListener('mouseenter', function() {{
                    this.style.transform = 'scale(1.01)';
                    this.style.transition = 'all 0.2s ease';
                }});
                row.addEventListener('mouseleave', function() {{
                    this.style.transform = 'scale(1)';
                }});
            }});
        }});
    </script>
</body>
</html>
        """

    def _get_modern_style(self, colors: Dict) -> str:
        """نمط حديث - محسّن لحجم A4"""
        return f"""
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Tajawal', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            direction: rtl;
            background: #ffffff;
            color: #0f172a;
            line-height: 1.5;
            font-size: 12px;
            text-rendering: geometricPrecision;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}
        
        .container {{
            width: 210mm;
            min-height: 297mm;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 0;
            box-shadow: none;
            overflow: hidden;
            border: 1px solid #e5e7eb;
            padding: 0;
        }}
        
        /* تحسينات الطباعة لحجم A4 */
        @media print {{
            * {{
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}

            body {{
                background: white;
                margin: 0;
                padding: 0;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            
            .container {{
                width: 100%;
                min-height: 100%;
                max-width: none;
                margin: 0;
                border-radius: 0;
                box-shadow: none;
                border: none;
                page-break-after: avoid;
            }}
            
            @page {{
                size: A4 portrait;
                margin: 10mm;
            }}
        }}
        
        .header {{
            background: linear-gradient(135deg, {colors['primary']} 0%, {colors['secondary']} 100%);
            color: white;
            padding: 1.1rem 1.4rem;
            position: relative;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 100%;
            height: 100%;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="20" cy="20" r="0.8" fill="white" opacity="0.1"/><circle cx="80" cy="30" r="0.6" fill="white" opacity="0.1"/><circle cx="40" cy="70" r="0.5" fill="white" opacity="0.1"/><circle cx="90" cy="80" r="0.7" fill="white" opacity="0.1"/></svg>');
        }}
        
        .header-content {{
            position: relative;
            z-index: 2;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .company-section {{
            display: flex;
            align-items: center;
            gap: 0.9rem;
        }}
        
        .logo {{
            width: 64px;
            height: 64px;
            background: rgba(255,255,255,0.15);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 3px solid rgba(255,255,255,0.4);
            backdrop-filter: blur(10px);
            flex-shrink: 0;
        }}
        
        .logo img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            border-radius: 50%;
        }}
        
        .logo-text {{
            font-weight: bold;
            font-size: 1rem;
            color: white;
        }}
        
        .company-info h1 {{
            font-size: 1.3rem;
            font-weight: 800;
            margin-bottom: 0.2rem;
            text-shadow: 1px 1px 3px rgba(0,0,0,0.25);
            line-height: 1.2;
        }}
        
        .company-name-en {{
            font-size: 0.78rem;
            opacity: 0.95;
            margin-bottom: 0.15rem;
            font-weight: 500;
        }}

        .company-slogan {{
            font-size: 0.78rem;
            opacity: 0.95;
            margin-bottom: 0.15rem;
            font-weight: 600;
        }}

        
        .company-address {{
            font-size: 0.72rem;
            opacity: 0.92;
            line-height: 1.2;
        }}
        
        .quote-section {{
            text-align: left;
            background: rgba(255,255,255,0.15);
            padding: 0.75rem 0.95rem;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }}
        
        .quote-title {{
            font-size: 1.6rem;
            font-weight: 900;
            margin-bottom: 0.2rem;
            text-shadow: 1px 1px 4px rgba(0,0,0,0.25);
            letter-spacing: 0.5px;
        }}
        
        .quote-number {{
            font-size: 0.9rem;
            opacity: 0.95;
            font-weight: 600;
        }}
        
        .content {{
            padding: 0.9rem 1.1rem;
        }}
        
        .section-title {{
            font-size: 0.82rem;
            font-weight: 800;
            color: {colors['primary']};
            margin-bottom: 0.55rem;
            padding: 0.3rem 0;
            border-bottom: 2px solid {colors['primary']};
            position: relative;
        }}
        
        .section-title::after {{
            content: '';
            position: absolute;
            bottom: -2px;
            right: 0;
            width: 40px;
            height: 2px;
            background: {colors['secondary']};
        }}
        
        .details-section {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}
        
        .client-info, .quote-info {{
            background: {colors['accent']};
            padding: 0.6rem 0.7rem;
            border-radius: 8px;
            border: 1px solid rgba(0,0,0,0.05);
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }}
        
        .info-grid {{
            display: flex;
            flex-direction: column;
            gap: 0.3rem;
        }}
        
        .info-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.25rem 0.45rem;
            background: white;
            border-radius: 6px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }}
        
        .label {{
            font-weight: 600;
            color: {colors['secondary']};
            font-size: 0.7rem;
        }}
        
        .value {{
            font-weight: 500;
            color: #1e293b;
            font-size: 0.7rem;
        }}
        
        .project-section {{
            margin-bottom: 1.2rem;
        }}
        
        .project-description {{
            background: linear-gradient(135deg, #fef7cd 0%, #fef3c7 100%);
            padding: 0.8rem 1rem;
            border-radius: 8px;
            border-right: 3px solid #f59e0b;
            font-size: 0.75rem;
            line-height: 1.5;
            box-shadow: 0 2px 6px rgba(245,158,11,0.1);
        }}
        
        .items-section {{
            margin-bottom: 1.2rem;
        }}
        
        .table-container {{
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 3px 10px rgba(0,0,0,0.08);
            border: 1px solid rgba(0,0,0,0.05);
        }}
        
        .items-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        .items-table th {{
            background: {colors['primary']};
            color: white;
            padding: 0.5rem 0.6rem;
            text-align: center;
            font-weight: 700;
            font-size: 0.7rem;
        }}
        
        .items-table td {{
            padding: 0.5rem 0.6rem;
            text-align: center;
            border-bottom: 1px solid #f1f5f9;
            vertical-align: middle;
            font-size: 0.7rem;
        }}
        
        .items-table tr:nth-child(even) {{
            background: #f8fafc;
        }}
        
        .items-table tr:hover {{
            background: {colors['accent']};
        }}

        .items-table tfoot td {{
            padding: 0.5rem;
            border-top: 1px solid #e2e8f0;
            background: #f8fafc;
            font-size: 0.7rem;
        }}

        .items-table .total-row-table td {{
            background: {colors['accent']};
            color: {colors['primary']};
            font-size: 0.8rem;
            border-top: 2px solid {colors['primary']};
            font-weight: 700;
        }}
        
        .text-right {{
            text-align: right !important;
            padding-right: 0.8rem;
        }}
        

        
        .signatures-section {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-bottom: 1rem;
        }}
        
        .signature-box {{
            background: white;
            padding: 0.8rem 1rem;
            border-radius: 8px;
            text-align: center;
            border: 1px dashed #cbd5e1;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }}
        
        .signature-box h4 {{
            font-size: 0.8rem;
            font-weight: 600;
            color: {colors['secondary']};
            margin-bottom: 0.8rem;
        }}
        
        .signature-line {{
            width: 100%;
            height: 1px;
            background: #cbd5e1;
            margin: 1rem 0 0.5rem;
        }}
        
        .signature-box p {{
            font-size: 0.65rem;
            color: #64748b;
        }}
        
        .footer {{
            background: #1e293b;
            color: white;
            padding: 0.8rem 1rem;
            text-align: center;
        }}
        
        .footer-content {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}
        
        .footer-content p {{
            font-size: 0.65rem;
        }}
        
        .contact-info {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }}
        
        .contact-info span {{
            font-size: 0.65rem;
        }}
        
        @media print {{
            .footer {{
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
            }}
        }}
        
        @media (max-width: 768px) {{
            .container {{
                margin: 10px;
                border-radius: 12px;
            }}
            
            .header {{
                padding: 2rem 1.5rem;
            }}
            
            .header-content {{
                flex-direction: column;
                text-align: center;
                gap: 2rem;
            }}
            
            .quote-title {{
                font-size: 2.5rem;
            }}
            
            .content {{
                padding: 2rem 1.5rem;
            }}
            
            .details-section {{
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }}
            
            .signatures-section {{
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }}
            
            .footer-content {{
                flex-direction: column;
                text-align: center;
            }}
            
            .contact-info {{
                flex-direction: column;
                gap: 0.5rem;
            }}
        }}

        /* ===========================================
           طباعة A4 — تتفوق على قواعد الموبايل
           (مهمة عند الطباعة من جوال: يجب أن تكون A4)
           =========================================== */
        @media print {{
            html, body {{
                background: white !important;
                margin: 0 !important;
                padding: 0 !important;
                font-size: 11px !important;
            }}
            .container {{
                width: 100% !important;
                max-width: 100% !important;
                min-height: 100% !important;
                margin: 0 !important;
                padding: 0 !important;
                border: none !important;
                border-radius: 0 !important;
                box-shadow: none !important;
            }}
            @page {{
                size: A4 portrait;
                margin: 8mm 7mm;
            }}

            /* هيدر مدمج للطباعة */
            .header {{
                padding: 0.55rem 0.8rem !important;
            }}
            .header-content {{
                flex-direction: row !important;
                text-align: right !important;
                gap: 0.7rem !important;
                align-items: center !important;
            }}
            .company-section {{
                gap: 0.6rem !important;
            }}
            .logo {{
                width: 44px !important;
                height: 44px !important;
                border-width: 2px !important;
            }}
            .company-info h1 {{
                font-size: 0.95rem !important;
                margin-bottom: 0.1rem !important;
                line-height: 1.15 !important;
            }}
            .company-name-en,
            .company-slogan {{
                font-size: 0.62rem !important;
                margin-bottom: 0.1rem !important;
            }}
            .company-address {{
                font-size: 0.58rem !important;
                line-height: 1.15 !important;
            }}
            .quote-section {{
                padding: 0.4rem 0.6rem !important;
            }}
            .quote-title {{
                font-size: 1.1rem !important;
            }}
            .content {{
                padding: 0.6rem 0.9rem !important;
            }}
            .details-section {{
                grid-template-columns: 1fr 1fr !important;
                gap: 0.5rem !important;
                margin: 0.4rem 0 !important;
            }}

            /* التوقيعات: قسمين متجاورين (عميل يمين، ورشة يسار في RTL) */
            .signatures-section {{
                grid-template-columns: 1fr 1fr !important;
                gap: 0.6rem !important;
                margin: 0.5rem 0 !important;
                page-break-inside: avoid !important;
            }}
            .signature-box {{
                padding: 0.5rem 0.6rem !important;
                box-shadow: none !important;
            }}
            .signature-box h4 {{
                font-size: 0.7rem !important;
                margin-bottom: 0.5rem !important;
            }}
            .signature-line {{
                margin: 0.6rem 0 0.3rem !important;
            }}

            /* الجدول مدمج لاستيعاب بنود أكثر */
            table {{
                font-size: 10px !important;
                page-break-inside: auto !important;
            }}
            table th, table td {{
                padding: 0.35rem 0.45rem !important;
            }}
            tr {{
                page-break-inside: avoid !important;
                page-break-after: auto !important;
            }}

            /* footer مدمج وفي أسفل الصفحة */
            .footer {{
                padding: 0.4rem 0.7rem !important;
                font-size: 0.6rem !important;
            }}
            .footer-content {{
                flex-direction: row !important;
                text-align: center !important;
                gap: 0.4rem !important;
            }}
            .contact-info {{
                flex-direction: row !important;
                gap: 0.6rem !important;
            }}
            .footer-content p,
            .contact-info span {{
                font-size: 0.58rem !important;
            }}
        }}
        """

    def _get_classic_style(self, colors: Dict) -> str:
        """نمط كلاسيكي"""
        return f"""
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Noto Sans Arabic', serif;
            direction: rtl;
            background: #f9fafb;
            color: #374151;
            line-height: 1.8;
            font-size: 14px;
        }}
        
        .container {{
            max-width: 850px;
            margin: 30px auto;
            background: white;
            border: 2px solid #d1d5db;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        
        .header {{
            background: {colors['primary']};
            color: white;
            padding: 2rem;
            border-bottom: 4px solid {colors['secondary']};
        }}
        
        .header-content {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .company-section {{
            display: flex;
            align-items: center;
            gap: 0.9rem;
        }}
        
        .logo {{
            width: 80px;
            height: 80px;
            background: rgba(255,255,255,0.2);
            border: 2px solid white;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .company-info h1 {{
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}
        
        .quote-section {{
            text-align: left;
            border: 2px solid white;
            padding: 1rem;
        }}
        
        .quote-title {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}
        
        .content {{
            padding: 2rem;
        }}
        
        .section-title {{
            font-size: 1.3rem;
            font-weight: 600;
            color: {colors['secondary']};
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid {colors['primary']};
        }}
        
        .details-section {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
            padding: 1.5rem;
            background: {colors['accent']};
            border: 1px solid #d1d5db;
        }}
        
        .client-info, .quote-info {{
            background: white;
            padding: 1.5rem;
            border: 1px solid #d1d5db;
        }}
        
        .info-grid {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        
        .info-item {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem;
            border-bottom: 1px dotted #d1d5db;
        }}
        
        .label {{
            font-weight: 600;
            color: {colors['secondary']};
        }}
        
        .project-section {{
            margin-bottom: 2rem;
        }}
        
        .project-description {{
            background: {colors['accent']};
            padding: 1.0rem;
            border: 1px solid #d1d5db;
            border-right: 4px solid {colors['primary']};
        }}
        
        .table-container {{
            border: 2px solid {colors['primary']};
            margin-bottom: 2rem;
        }}
        
        .items-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        .items-table th {{
            background: {colors['primary']};
            color: white;
            padding: 1rem;
            text-align: center;
            font-weight: 600;
            border-right: 1px solid white;
        }}
        
        .items-table td {{
            padding: 1rem;
            text-align: center;
            border-bottom: 1px solid #d1d5db;
            border-right: 1px solid #d1d5db;
        }}
        
        .text-right {{
            text-align: right !important;
        }}
        

        
        .signatures-section {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
        }}
        
        .signature-box {{
            background: {colors['accent']};
            padding: 2rem;
            text-align: center;
            border: 2px solid {colors['primary']};
        }}
        
        .signature-box h4 {{
            font-weight: 600;
            color: {colors['secondary']};
            margin-bottom: 2rem;
        }}
        
        .signature-line {{
            width: 100%;
            height: 1px;
            background: #374151;
            margin: 3rem 0 1rem;
        }}
        
        .footer {{
            background: {colors['secondary']};
            color: white;
            padding: 1.5rem;
            text-align: center;
            border-top: 4px solid {colors['primary']};
        }}
        
        .footer-content {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .contact-info {{
            display: flex;
            gap: 2rem;
        }}
        
        @media (max-width: 768px) {{
            .container {{
                margin: 15px;
            }}
            
            .details-section {{
                grid-template-columns: 1fr;
            }}
            
            .signatures-section {{
                grid-template-columns: 1fr;
            }}
            
            .header-content {{
                flex-direction: column;
                gap: 1rem;
            }}
            
            .footer-content {{
                flex-direction: column;
                gap: 1rem;
            }}
            
            .contact-info {{
                flex-direction: column;
                gap: 0.5rem;
            }}
        }}
        """

    def _get_luxury_style(self, colors: Dict) -> str:
        """نمط فاخر"""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Noto Sans Arabic', 'Times New Roman', serif;
            direction: rtl;
            background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
            color: #1f2937;
            line-height: 1.7;
            font-size: 14px;
            min-height: 100vh;
            padding: 20px 0;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: linear-gradient(135deg, #ffffff 0%, #f9fafb 100%);
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
            border: 1px solid rgba(212,175,55,0.3);
        }
        
        .header {
            background: linear-gradient(135deg, #1f2937 0%, #111827 50%, #0f172a 100%);
            color: #d4af37;
            padding: 3rem 2rem;
            position: relative;
            overflow: hidden;
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: -50%;
            right: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(212,175,55,0.1) 0%, transparent 70%);
            animation: shimmer 15s infinite linear;
        }
        
        @keyframes shimmer {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .header-content {
            position: relative;
            z-index: 2;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .company-section {
            display: flex;
            align-items: center;
            gap: 2rem;
        }
        
        .logo {
            width: 100px;
            height: 100px;
            background: linear-gradient(135deg, #d4af37 0%, #b8860b 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 3px solid #ffd700;
            box-shadow: 0 10px 30px rgba(212,175,55,0.4);
        }
        
        .logo-text {
            font-weight: bold;
            font-size: 1.2rem;
            color: #1f2937;
        }
        
        .company-info h1 {
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #d4af37 0%, #ffd700 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .company-name-en {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .company-address {
            font-size: 0.95rem;
            opacity: 0.8;
        }
        
        .quote-section {
            text-align: left;
            background: rgba(212,175,55,0.1);
            padding: 2rem;
            border-radius: 15px;
            border: 1px solid rgba(212,175,55,0.3);
        }
        
        .quote-title {
            font-size: 3.5rem;
            font-weight: 900;
            background: linear-gradient(135deg, #d4af37 0%, #ffd700 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .quote-number {
            font-size: 1.3rem;
            opacity: 0.9;
        }
        
        .content {
            padding: 3rem;
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        }
        
        .section-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: #1f2937;
            margin-bottom: 2rem;
            padding: 1rem 0;
            border-bottom: 3px solid #d4af37;
        }
        
        .details-section {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2.5rem;
            margin-bottom: 3rem;
        }
        
        .client-info, .quote-info {
            background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
            padding: 2.5rem;
            border-radius: 15px;
            border: 1px solid rgba(212,175,55,0.2);
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
        }
        
        .info-grid {
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }
        
        .info-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
        
        .label {
            font-weight: 700;
            color: #1f2937;
        }
        
        .value {
            font-weight: 600;
            color: #374151;
        }
        
        .project-section {
            margin-bottom: 3rem;
        }
        
        .project-description {
            background: linear-gradient(135deg, #fef7cd 0%, #fef3c7 100%);
            padding: 2.5rem;
            border-radius: 15px;
            border-right: 6px solid #d97706;
            font-size: 1.15rem;
            line-height: 1.9;
        }
        
        .items-section {
            margin-bottom: 3rem;
        }
        
        .table-container {
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 15px 40px rgba(0,0,0,0.1);
        }
        
        .items-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .items-table th {
            background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
            color: #d4af37;
            padding: 1.5rem;
            text-align: center;
            font-weight: 700;
        }
        
        .items-table td {
            padding: 1.5rem;
            text-align: center;
            border-bottom: 1px solid rgba(0,0,0,0.05);
        }
        
        .items-table tr:nth-child(even) {
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        }
        
        .items-table tr:hover {
            background: linear-gradient(135deg, #fef7cd 0%, #fef3c7 100%);
        }
        
        .text-right {
            text-align: right !important;
        }
        
        .summary-section {
            margin-bottom: 3rem;
        }
        
        .summary-box {
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            padding: 2.5rem;
            border-radius: 15px;
            border: 1px solid #0ea5e9;
        }
        
        .summary-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.25rem 0;
            border-bottom: 1px solid rgba(14,165,233,0.2);
            font-size: 1.15rem;
            font-weight: 600;
        }
        
        .total-row {
            border-bottom: none;
            border-top: 3px solid #d4af37;
            background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
            color: #d4af37;
            margin: 1.5rem -2.5rem -2.5rem;
            padding: 2rem 2.5rem;
            font-weight: 900;
            font-size: 1.6rem;
            border-radius: 0 0 15px 15px;
        }
        
        .terms-section {
            margin-bottom: 3rem;
        }
        
        .terms-list {
            background: linear-gradient(135deg, #fef3c7 0%, #fef7cd 100%);
            padding: 2.5rem;
            border-radius: 15px;
            border-right: 6px solid #d97706;
            list-style: none;
        }
        
        .terms-list li {
            margin-bottom: 1.25rem;
            padding-right: 2rem;
            position: relative;
            line-height: 1.8;
        }
        
        .terms-list li::before {
            content: '◆';
            position: absolute;
            right: 0;
            color: #d97706;
        }
        
        .signatures-section {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2.5rem;
            margin-bottom: 2rem;
        }
        
        .signature-box {
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            padding: 2.5rem;
            border-radius: 15px;
            text-align: center;
            border: 2px solid #d4af37;
        }
        
        .signature-box h4 {
            font-size: 1.3rem;
            font-weight: 700;
            color: #1f2937;
            margin-bottom: 2.5rem;
        }
        
        .signature-line {
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, #d4af37, #ffd700);
            margin: 3rem 0 1.5rem;
        }
        
        .footer {
            background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
            color: #d4af37;
            padding: 2.5rem;
            text-align: center;
        }
        
        .footer-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1.5rem;
        }
        
        .contact-info {
            display: flex;
            gap: 2.5rem;
            flex-wrap: wrap;
        }
        
        @media (max-width: 768px) {
            .container {
                margin: 10px;
            }
            
            .header-content {
                flex-direction: column;
                text-align: center;
                gap: 2rem;
            }
            
            .details-section {
                grid-template-columns: 1fr;
            }
            
            .signatures-section {
                grid-template-columns: 1fr;
            }
            
            .footer-content {
                flex-direction: column;
            }
            
            .contact-info {
                flex-direction: column;
                gap: 1rem;
            }
        }
        
        @media print {
            body {
                background: white;
            }
            
            .container {
                box-shadow: none;
                margin: 0;
            }
        }
        """

    def save_and_open(
        self, filename: str = None, theme: str = "أزرق", style: str = "حديث"
    ) -> str:
        """حفظ الملف وفتحه في المتصفح"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"quotation_{self.quotation['number']}_{timestamp}.html"

        temp_dir = tempfile.gettempdir()
        full_path = os.path.join(temp_dir, filename)

        html_content = self.generate_html(theme=theme, style=style)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        webbrowser.open(f"file://{full_path}")

        return full_path

    def to_dict(self) -> Dict:
        """تحويل العرض لقاموس"""
        return {"company": self.company, "quotation": self.quotation}

    def from_dict(self, data: Dict):
        """استيراد من قاموس"""
        if "company" in data:
            self.company.update(data["company"])
        if "quotation" in data:
            self.quotation.update(data["quotation"])
        return self


# FastAPI Integration
def create_quotation_routes(router):
    """إنشاء مسارات API لعروض الأسعار"""
    from fastapi import HTTPException
    from pydantic import BaseModel
    from typing import List, Optional

    class QuotationItem(BaseModel):
        description: str
        quantity: float
        unit_price: float
        discount: float = 0

    class QuotationClient(BaseModel):
        name: str
        company: Optional[str] = ""
        address: Optional[str] = ""
        phone: Optional[str] = ""
        email: Optional[str] = ""

    class QuotationCompany(BaseModel):
        name: Optional[str] = None
        name_en: Optional[str] = None
        address: Optional[str] = None
        phone: Optional[str] = None
        email: Optional[str] = None
        website: Optional[str] = None
        commercial_register: Optional[str] = None

    class QuotationRequest(BaseModel):
        company: Optional[QuotationCompany] = None
        client: QuotationClient
        project_description: str
        items: List[QuotationItem]
        terms: Optional[List[str]] = None
        theme: Optional[str] = "أزرق"
        style: Optional[str] = "حديث"

    @router.post("/quotations/generate")
    async def generate_quotation(request: QuotationRequest):
        """توليد عرض سعر جديد"""
        try:
            builder = ArabicQuotationBuilder()

            # تعيين بيانات الشركة
            if request.company:
                company_data = {
                    k: v for k, v in request.company.dict().items() if v is not None
                }
                builder.set_company(**company_data)

            # تعيين بيانات العميل
            builder.set_client(**request.client.dict())

            # تعيين وصف المشروع
            builder.set_project(request.project_description)

            # الضرائب غير مستخدمة
            builder.quotation["tax_rate"] = 0

            # إضافة البنود
            for item in request.items:
                builder.add_item(
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    discount=item.discount,
                )

            # إضافة الشروط المخصصة
            if request.terms:
                builder.quotation["terms"] = request.terms

            # توليد HTML
            html_content = builder.generate_html(
                theme=request.theme or "أزرق", style=request.style or "حديث"
            )

            return {
                "success": True,
                "quotation_number": builder.quotation["number"],
                "html": html_content,
                "data": builder.to_dict(),
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/quotations/themes")
    async def get_themes():
        """الحصول على قائمة الألوان والأنماط المتاحة"""
        builder = ArabicQuotationBuilder()
        return {
            "themes": list(builder.themes.keys()),
            "styles": ["حديث", "كلاسيكي", "فاخر"],
        }

    return router


if __name__ == "__main__":
    # اختبار سريع
    builder = ArabicQuotationBuilder()
    builder.set_client(
        name="أحمد محمد", company="شركة التقنية", phone="+966 50 123 4567"
    )
    builder.set_project("تطوير نظام إدارة الورش")
    builder.add_item("تصميم النظام", 1, 5000)
    builder.add_item("التطوير والبرمجة", 1, 15000, 1000)
    builder.add_item("الاختبار والتدريب", 1, 3000)

    html = builder.generate_html(theme="أزرق", style="حديث")
    print(f"✅ تم توليد عرض سعر رقم: {builder.quotation['number']}")
    print(f"المجموع: {builder.quotation['total']:,.2f} ر.س")
