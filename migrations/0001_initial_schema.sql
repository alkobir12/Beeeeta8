-- Migration number: 0001 	 2024-11-26T00:00:00.000Z
-- Invoices table
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL,
    date TEXT NOT NULL,
    due_date TEXT,
    status TEXT DEFAULT 'draft', -- draft, sent, paid, overdue
    
    -- Client Details
    client_name TEXT NOT NULL,
    client_email TEXT,
    client_address TEXT,
    
    -- Totals
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    total_amount REAL DEFAULT 0,
    
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Invoice Items table
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    quantity REAL DEFAULT 1,
    unit_price REAL DEFAULT 0,
    total REAL DEFAULT 0,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);

-- Settings/Profile table (optional, for sender details)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Insert default settings if they don't exist
INSERT OR IGNORE INTO settings (key, value) VALUES 
('company_name', 'شركتي'),
('company_address', 'العنوان هنا'),
('company_email', 'info@example.com');
