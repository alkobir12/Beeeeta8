document.addEventListener('alpine:init', () => {
    Alpine.data('invoiceApp', () => ({
        view: 'dashboard', // dashboard, editor, settings, preview
        subView: 'general', // general, design (for settings)
        invoices: [],
        currentInvoice: {
            id: null,
            invoice_number: '',
            date: new Date().toISOString().slice(0, 10),
            due_date: '',
            status: 'draft',
            client_name: '',
            client_email: '',
            client_address: '',
            items: [{ description: '', quantity: 1, unit_price: 0, total: 0 }],
            notes: '',
            subtotal: 0,
            tax_rate: 0,
            tax_amount: 0,
            total_amount: 0
        },
        settings: {
            company_name: '',
            company_address: '',
            company_email: '',
            theme_color: '#2563eb',
            font_family: 'Tajawal',
            logo_url: '',
            header_layout: 'right'
        },
        fonts: [
            { name: 'تجوال (Tajawal)', value: 'Tajawal' },
            { name: 'كايرو (Cairo)', value: 'Cairo' },
            { name: 'المرعي (Almarai)', value: 'Almarai' },
            { name: 'آي بي إم بليكس (IBM Plex Sans Arabic)', value: 'IBM Plex Sans Arabic' }
        ],
        isLoading: false,
        isEmbedded: false, // New flag for embedded mode

        async init() {
            // Check if embedded (via URL param or iframe detection)
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('mode') === 'embedded' || window.self !== window.top) {
                this.isEmbedded = true;
                this.view = 'editor'; // Start directly in editor
            }

            await this.loadSettings();
            
            // Auto-create invoice if data is passed via URL
            if (urlParams.has('client_name') || urlParams.has('amount')) {
                this.createInvoiceFromUrl(urlParams);
            } else {
                await this.loadInvoices();
            }

            // Listen for messages from parent window (Integration)
            window.addEventListener('message', (event) => {
                if (event.data && event.data.type === 'CREATE_INVOICE') {
                    this.createInvoiceFromData(event.data.payload);
                }
            });
        },

        createInvoiceFromUrl(params) {
            this.newInvoice();
            // Override with passed data
            if (params.get('client_name')) this.currentInvoice.client_name = params.get('client_name');
            if (params.get('client_email')) this.currentInvoice.client_email = params.get('client_email');
            
            // Handle Items
            const description = params.get('description') || 'خدمة جديدة';
            const price = parseFloat(params.get('amount')) || 0;
            
            this.currentInvoice.items = [{
                description: description,
                quantity: 1,
                unit_price: price,
                total: price
            }];
            
            this.calculateTotals();
            this.view = 'editor';
        },

        createInvoiceFromData(data) {
            this.newInvoice();
            // Smart merge of data
            this.currentInvoice.client_name = data.clientName || '';
            this.currentInvoice.client_email = data.clientEmail || '';
            this.currentInvoice.client_address = data.clientAddress || '';
            this.currentInvoice.notes = data.notes || '';
            
            if (data.items && Array.isArray(data.items)) {
                this.currentInvoice.items = data.items.map(i => ({
                    description: i.description || 'خدمة',
                    quantity: i.quantity || 1,
                    unit_price: i.price || 0,
                    total: (i.quantity || 1) * (i.price || 0)
                }));
            } else if (data.amount) {
                this.currentInvoice.items = [{
                    description: data.description || 'خدمة عامة',
                    quantity: 1,
                    unit_price: parseFloat(data.amount),
                    total: parseFloat(data.amount)
                }];
            }
            
            this.calculateTotals();
            this.view = 'editor';
        },

        async loadInvoices() {
            this.isLoading = true;
            try {
                const res = await fetch('/api/invoices');
                this.invoices = await res.json();
            } catch (e) {
                console.error(e);
                alert('حدث خطأ أثناء تحميل الفواتير');
            }
            this.isLoading = false;
        },

        async loadSettings() {
            try {
                const res = await fetch('/api/settings');
                const data = await res.json();
                // Merge with defaults to handle missing keys
                this.settings = { ...this.settings, ...data };
            } catch (e) {
                console.error(e);
            }
        },

        async saveSettings() {
            try {
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.settings)
                });
                alert('تم حفظ الإعدادات بنجاح');
            } catch (e) {
                alert('فشل حفظ الإعدادات');
            }
        },

        newInvoice() {
            this.currentInvoice = {
                id: null,
                invoice_number: 'INV-' + Date.now(),
                date: new Date().toISOString().slice(0, 10),
                due_date: '',
                status: 'draft',
                client_name: '',
                client_email: '',
                client_address: '',
                items: [{ description: 'خدمة تصميم', quantity: 1, unit_price: 100, total: 100 }],
                notes: '',
                subtotal: 100,
                tax_rate: 0,
                tax_amount: 0,
                total_amount: 100
            };
            this.view = 'editor';
        },

        async editInvoice(id) {
            this.isLoading = true;
            try {
                const res = await fetch(`/api/invoices/${id}`);
                this.currentInvoice = await res.json();
                this.calculateTotals(); // Ensure totals are correct
                this.view = 'editor';
            } catch (e) {
                alert('فشل تحميل الفاتورة');
            }
            this.isLoading = false;
        },

        addItem() {
            this.currentInvoice.items.push({ description: '', quantity: 1, unit_price: 0, total: 0 });
        },

        removeItem(index) {
            this.currentInvoice.items.splice(index, 1);
            this.calculateTotals();
        },

        calculateItemTotal(item) {
            item.total = item.quantity * item.unit_price;
            this.calculateTotals();
        },

        calculateTotals() {
            this.currentInvoice.subtotal = this.currentInvoice.items.reduce((sum, item) => sum + item.total, 0);
            this.currentInvoice.tax_amount = this.currentInvoice.subtotal * (this.currentInvoice.tax_rate / 100);
            this.currentInvoice.total_amount = this.currentInvoice.subtotal + this.currentInvoice.tax_amount;
        },

        async saveInvoice() {
            const method = this.currentInvoice.id ? 'PUT' : 'POST';
            const url = this.currentInvoice.id ? `/api/invoices/${this.currentInvoice.id}` : '/api/invoices';

            try {
                const res = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.currentInvoice)
                });

                if (res.ok) {
                    // Notify Parent Window (If embedded)
                    if (this.isEmbedded) {
                        window.parent.postMessage({
                            type: 'INVOICE_SAVED',
                            invoiceId: this.currentInvoice.id || (await res.clone().json()).id,
                            total: this.currentInvoice.total_amount,
                            status: 'success'
                        }, '*');
                    }

                    alert('تم حفظ الفاتورة بنجاح');
                    await this.loadInvoices();
                    
                    // If embedded, maybe stay on editor or show success?
                    // For now, go to dashboard only if not strictly embedded for single creation
                    if (!this.isEmbedded) {
                        this.view = 'dashboard';
                    }
                } else {
                    throw new Error('Save failed');
                }
            } catch (e) {
                alert('حدث خطأ أثناء الحفظ');
            }
        },

        async deleteInvoice(id) {
            if (!confirm('هل أنت متأكد من حذف هذه الفاتورة؟')) return;
            try {
                await fetch(`/api/invoices/${id}`, { method: 'DELETE' });
                await this.loadInvoices();
            } catch (e) {
                alert('فشل الحذف');
            }
        },

        printInvoice(invoice = null) {
            if (invoice) {
                // If viewing from dashboard list
                this.editInvoice(invoice.id).then(() => {
                     this.view = 'preview';
                     setTimeout(() => window.print(), 500);
                });
            } else {
                // If currently editing
                this.view = 'preview';
                setTimeout(() => window.print(), 500);
            }
        },

        exportToWord() {
            const filename = `invoice-${this.currentInvoice.invoice_number || 'draft'}.doc`;
            
            // Create a Word-friendly HTML structure (using tables for layout as Word prefers them over Flexbox)
            const content = `
                <html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
                <head>
                    <meta charset='utf-8'>
                    <title>Invoice</title>
                    <style>
                        body { font-family: 'Arial', sans-serif; direction: rtl; text-align: right; }
                        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                        td, th { padding: 8px; vertical-align: top; }
                        .header-table td { border: none; }
                        .items-table { border: 1px solid #000; }
                        .items-table th { background-color: #f0f0f0; border: 1px solid #000; font-weight: bold; }
                        .items-table td { border: 1px solid #000; }
                        .total-table td { border: none; }
                        .title { font-size: 24px; font-weight: bold; color: ${this.settings.theme_color}; }
                        .company-name { font-size: 18px; font-weight: bold; color: ${this.settings.theme_color}; }
                    </style>
                </head>
                <body dir="rtl">
                    <!-- Header Section -->
                    <table class="header-table">
                        <tr>
                            <td width="60%">
                                ${this.settings.logo_url ? `<img src="${this.settings.logo_url}" height="60" style="margin-bottom:10px"><br>` : ''}
                                <div class="company-name">${this.settings.company_name}</div>
                                <div>${this.settings.company_address.replace(/\n/g, '<br>')}</div>
                                <div>${this.settings.company_email}</div>
                            </td>
                            <td width="40%" style="text-align: left;">
                                <div class="title">فاتورة</div>
                                <div><strong>رقم الفاتورة:</strong> ${this.currentInvoice.invoice_number}</div>
                                <div><strong>التاريخ:</strong> ${this.currentInvoice.date}</div>
                                ${this.currentInvoice.due_date ? `<div><strong>تاريخ الاستحقاق:</strong> ${this.currentInvoice.due_date}</div>` : ''}
                            </td>
                        </tr>
                    </table>

                    <br><hr><br>

                    <!-- Bill To Section -->
                    <table class="header-table">
                        <tr>
                            <td>
                                <strong>فاتورة إلى:</strong><br>
                                <span style="font-size: 16px; font-weight: bold;">${this.currentInvoice.client_name}</span><br>
                                ${this.currentInvoice.client_address}<br>
                                ${this.currentInvoice.client_email}
                            </td>
                        </tr>
                    </table>

                    <br>

                    <!-- Items Table -->
                    <table class="items-table">
                        <thead>
                            <tr>
                                <th width="50%">الوصف</th>
                                <th width="15%" style="text-align: center;">الكمية</th>
                                <th width="15%" style="text-align: center;">السعر</th>
                                <th width="20%" style="text-align: center;">الإجمالي</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${this.currentInvoice.items.map(item => `
                                <tr>
                                    <td>${item.description}</td>
                                    <td style="text-align: center;">${item.quantity}</td>
                                    <td style="text-align: center;">${item.unit_price.toFixed(2)}</td>
                                    <td style="text-align: center;"><b>${item.total.toFixed(2)}</b></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>

                    <br>

                    <!-- Totals Section -->
                    <table class="total-table">
                        <tr>
                            <td width="60%"></td>
                            <td width="40%">
                                <table width="100%">
                                    <tr>
                                        <td style="text-align: left;">المجموع الفرعي:</td>
                                        <td style="text-align: left;"><b>${this.currentInvoice.subtotal.toFixed(2)}</b></td>
                                    </tr>
                                    ${this.currentInvoice.tax_amount > 0 ? `
                                    <tr>
                                        <td style="text-align: left;">الضريبة (${this.currentInvoice.tax_rate}%):</td>
                                        <td style="text-align: left;">${this.currentInvoice.tax_amount.toFixed(2)}</td>
                                    </tr>
                                    ` : ''}
                                    <tr>
                                        <td style="text-align: left; font-size: 16px; color: ${this.settings.theme_color};"><strong>الإجمالي الكلي:</strong></td>
                                        <td style="text-align: left; font-size: 16px;"><strong>${this.currentInvoice.total_amount.toFixed(2)}</strong></td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>

                    <br>

                    <!-- Notes Section -->
                    ${this.currentInvoice.notes ? `
                    <div style="border-top: 1px solid #ccc; padding-top: 10px;">
                        <strong>ملاحظات وشروط:</strong><br>
                        ${this.currentInvoice.notes.replace(/\n/g, '<br>')}
                    </div>
                    ` : ''}

                    <br><br>
                    <div style="text-align: center; font-size: 12px; color: #666;">شكراً لتعاملكم معنا</div>
                </body>
                </html>
            `;

            const blob = new Blob(['\ufeff', content], {
                type: 'application/msword'
            });
            
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        },
        
        setView(v) {
            this.view = v;
        }
    }));
});
