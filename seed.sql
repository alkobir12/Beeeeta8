INSERT OR REPLACE INTO settings (key, value) VALUES 
('company_name', 'شركة المستقبل للتقنية'),
('company_address', 'شارع الملك فهد، الرياض، المملكة العربية السعودية\nهاتف: 01122334455'),
('company_email', 'contact@futuretech.sa'),
('theme_color', '#2563eb'),
('font_family', 'Tajawal'),
('logo_url', ''),
('header_layout', 'right');

INSERT INTO invoices (invoice_number, date, due_date, status, client_name, client_email, client_address, subtotal, tax_rate, tax_amount, total_amount, notes) VALUES 
('INV-1001', '2025-11-20', '2025-11-27', 'paid', 'مؤسسة النور', 'info@alnoor.com', 'جدة، حي الروضة', 1500, 15, 225, 1725, 'تم استلام المبلغ شيك رقم 123'),
('INV-1002', '2025-11-25', '2025-12-05', 'sent', 'شركة الأفق', 'contact@horizon.com', 'الدمام، حي الشاطئ', 5000, 15, 750, 5750, 'يرجى السداد قبل الموعد المحدد');

INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total) VALUES 
(1, 'تصميم شعار', 1, 1000, 1000),
(1, 'تصميم كرت شخصي', 2, 250, 500),
(2, 'تطوير موقع إلكتروني', 1, 5000, 5000);
