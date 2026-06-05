#!/usr/bin/env python3
"""
Enhanced Arabic Approval Backend Analysis
Provides detailed HTML analysis with specific snippets showing forbidden content locations
"""

import requests
import json
import re
from datetime import datetime

class DetailedHTMLAnalyzer:
    def __init__(self):
        self.base_url = "https://workshop-helper-7.preview.emergentagent.com"
        self.api_url = f"{self.base_url}/api"
        self.session = requests.Session()
        
        self.session.headers.update({
            'User-Agent': 'Detailed-HTML-Analyzer/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def generate_test_invoice(self):
        """Generate test invoice and return HTML"""
        payload = {
            "doc_type": "invoice",
            "customer": {
                "name": "أحمد محمد العميل",
                "phone": "0551234567",
                "email": "ahmed@example.com"
            },
            "vehicle": {
                "plateNumber": "ت س ت 1234",
                "brand": "تويوتا",
                "model": "كامري",
                "year": 2024
            },
            "workshop": {
                "name": "ورشة الاختبار",
                "commercialRegister": "1010123456",
                "phone": "0553280100",
                "address": "الرياض، المملكة العربية السعودية"
            },
            "items": [
                {
                    "name": "خدمة صيانة شاملة",
                    "description": "خدمة صيانة شاملة",
                    "quantity": 1,
                    "price": 500,
                    "unit_price": 500
                }
            ],
            "settings": {
                "approval_token": "APV-TEST-2026-001",
                "approval_info": {
                    "token": "APV-TEST-2026-001",
                    "status": "approved",
                    "responderName": "أحمد محمد العميل",
                    "responderPhone": "0551234567",
                    "respondedAt": "2026-02-08T10:30:00Z",
                    "clientIp": "192.168.1.100",
                    "userAgent": "Mozilla/5.0 Test Browser"
                },
                "approval_vehicle_id": "f3422cc1-dd9c-4e69-8205-0aa50b3795a1",
                "document_number": "INV-TEST-20260208",
                "date": "2026-02-08"
            }
        }
        
        try:
            response = self.session.post(f"{self.api_url}/documents/generate", json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'html' in data:
                    return data['html']
            
            print(f"❌ Failed to generate invoice: {response.status_code} - {response.text[:200]}")
            return None
            
        except Exception as e:
            print(f"❌ Error generating invoice: {e}")
            return None
    
    def analyze_forbidden_content(self, html):
        """Detailed analysis of forbidden content"""
        print("🔍 DETAILED FORBIDDEN CONTENT ANALYSIS")
        print("=" * 60)
        
        forbidden_words = ['موافقة العميل', 'QR', 'barcode', 'token']
        
        for word in forbidden_words:
            print(f"\n🔎 Searching for: '{word}'")
            
            if word in ['QR', 'barcode', 'token']:
                pattern = re.compile(re.escape(word), re.IGNORECASE)
            else:
                pattern = re.compile(re.escape(word))
            
            matches = []
            for match in pattern.finditer(html):
                start = max(0, match.start() - 150)
                end = min(len(html), match.end() + 150)
                context = html[start:end]
                
                matches.append({
                    'position': match.start(),
                    'context': context,
                    'match': match.group()
                })
            
            if matches:
                print(f"❌ Found {len(matches)} occurrences:")
                for i, match in enumerate(matches[:5]):  # Show first 5 matches
                    print(f"  {i+1}. Position {match['position']}: '{match['match']}'")
                    print(f"     Context: ...{match['context']}...")
                    print()
            else:
                print(f"✅ Not found")
    
    def analyze_styling_improvements(self, html):
        """Detailed analysis of styling improvements"""
        print("\n🎨 DETAILED STYLING IMPROVEMENTS ANALYSIS")
        print("=" * 60)
        
        # Check for padding improvements
        print("\n🔎 Checking for padding: 0.6rem 0.7rem")
        padding_patterns = [
            r'padding:\s*0\.6rem\s+0\.7rem',
            r'padding:\s*0\.6rem\s*0\.7rem'
        ]
        
        padding_found = False
        for pattern in padding_patterns:
            matches = list(re.finditer(pattern, html, re.IGNORECASE))
            if matches:
                padding_found = True
                print(f"✅ Found {len(matches)} padding improvements:")
                for i, match in enumerate(matches[:3]):
                    start = max(0, match.start() - 100)
                    end = min(len(html), match.end() + 100)
                    context = html[start:end]
                    print(f"  {i+1}. {match.group()}")
                    print(f"     Context: ...{context}...")
                break
        
        if not padding_found:
            print("❌ Padding improvements not found")
        
        # Check for font-size improvements
        print("\n🔎 Checking for font-size: 0.7rem")
        font_patterns = [
            r'font-size:\s*0\.7rem',
            r'font-size:\s*\.7rem'
        ]
        
        font_found = False
        for pattern in font_patterns:
            matches = list(re.finditer(pattern, html, re.IGNORECASE))
            if matches:
                font_found = True
                print(f"✅ Found {len(matches)} font-size improvements:")
                for i, match in enumerate(matches[:3]):
                    start = max(0, match.start() - 100)
                    end = min(len(html), match.end() + 100)
                    context = html[start:end]
                    print(f"  {i+1}. {match.group()}")
                    print(f"     Context: ...{context}...")
                break
        
        if not font_found:
            print("❌ Font-size improvements not found")
        
        # Check for customer/workshop sections
        print("\n🔎 Checking for customer/workshop data sections")
        section_patterns = [
            r'بيانات\s*العميل',
            r'بيانات\s*الورشة'
        ]
        
        for pattern in section_patterns:
            matches = list(re.finditer(pattern, html, re.IGNORECASE))
            if matches:
                print(f"✅ Found '{pattern}' sections: {len(matches)}")
                for i, match in enumerate(matches[:2]):
                    start = max(0, match.start() - 100)
                    end = min(len(html), match.end() + 100)
                    context = html[start:end]
                    print(f"  {i+1}. {match.group()}")
                    print(f"     Context: ...{context}...")
            else:
                print(f"❌ '{pattern}' sections not found")
    
    def extract_html_sections(self, html):
        """Extract key HTML sections for analysis"""
        print("\n📄 KEY HTML SECTIONS ANALYSIS")
        print("=" * 60)
        
        # Extract style section
        style_match = re.search(r'<style>(.*?)</style>', html, re.DOTALL)
        if style_match:
            style_content = style_match.group(1)
            print(f"\n📝 CSS Styles (first 500 chars):")
            print(style_content[:500] + "..." if len(style_content) > 500 else style_content)
        
        # Extract signature section
        signature_match = re.search(r'<div class="signatures-section">(.*?)</div>', html, re.DOTALL)
        if signature_match:
            signature_content = signature_match.group(1)
            print(f"\n✍️ Signatures Section:")
            print(signature_content[:300] + "..." if len(signature_content) > 300 else signature_content)
        
        # Extract customer data section
        customer_match = re.search(r'بيانات العميل(.*?)(?=<div|$)', html, re.DOTALL)
        if customer_match:
            customer_content = customer_match.group(0)
            print(f"\n👤 Customer Data Section:")
            print(customer_content[:300] + "..." if len(customer_content) > 300 else customer_content)
        
        # Extract workshop data section
        workshop_match = re.search(r'بيانات الورشة(.*?)(?=<div|$)', html, re.DOTALL)
        if workshop_match:
            workshop_content = workshop_match.group(0)
            print(f"\n🏪 Workshop Data Section:")
            print(workshop_content[:300] + "..." if len(workshop_content) > 300 else workshop_content)
    
    def run_analysis(self):
        """Run complete analysis"""
        print("🚀 Starting Enhanced Arabic Approval HTML Analysis")
        print("=" * 60)
        
        # Generate test invoice
        print("📋 Generating test invoice...")
        html = self.generate_test_invoice()
        
        if not html:
            print("❌ Failed to generate HTML for analysis")
            return
        
        print(f"✅ Generated HTML successfully ({len(html)} characters)")
        
        # Run detailed analyses
        self.analyze_forbidden_content(html)
        self.analyze_styling_improvements(html)
        self.extract_html_sections(html)
        
        # Save full HTML for manual inspection
        try:
            with open('/app/generated_invoice_analysis.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"\n💾 Full HTML saved to: /app/generated_invoice_analysis.html")
        except Exception as e:
            print(f"⚠️ Could not save HTML file: {e}")
        
        print("\n🎯 ANALYSIS COMPLETE")

def main():
    analyzer = DetailedHTMLAnalyzer()
    analyzer.run_analysis()

if __name__ == "__main__":
    main()