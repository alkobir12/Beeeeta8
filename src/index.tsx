import { Hono } from 'hono'
import { cors } from 'hono/cors'

type Bindings = {
  DB: D1Database
  ASSETS: { fetch: (request: Request) => Promise<Response> }
}

const app = new Hono<{ Bindings: Bindings }>()

app.use('/api/*', cors())

// API Routes

// Get all invoices
app.get('/api/invoices', async (c) => {
  const { results } = await c.env.DB.prepare(
    `SELECT * FROM invoices ORDER BY created_at DESC`
  ).all()
  return c.json(results)
})

// Get single invoice with items
app.get('/api/invoices/:id', async (c) => {
  const id = c.req.param('id')
  
  const invoice = await c.env.DB.prepare(
    `SELECT * FROM invoices WHERE id = ?`
  ).bind(id).first()
  
  if (!invoice) return c.json({ error: 'Invoice not found' }, 404)
  
  const { results: items } = await c.env.DB.prepare(
    `SELECT * FROM invoice_items WHERE invoice_id = ?`
  ).bind(id).all()
  
  return c.json({ ...invoice, items })
})

// Create invoice
app.post('/api/invoices', async (c) => {
  const body = await c.req.json()
  const { 
    invoice_number, date, due_date, client_name, client_email, client_address,
    notes, items, subtotal, tax_rate, tax_amount, total_amount
  } = body

  // Transaction to insert invoice and items
  try {
    const { success, meta } = await c.env.DB.prepare(
      `INSERT INTO invoices (invoice_number, date, due_date, client_name, client_email, client_address, notes, subtotal, tax_rate, tax_amount, total_amount)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
    ).bind(
      invoice_number, date, due_date, client_name, client_email, client_address,
      notes, subtotal, tax_rate, tax_amount, total_amount
    ).run()

    if (!success) throw new Error('Failed to create invoice')
    
    const invoiceId = meta.last_row_id

    if (items && items.length > 0) {
      const stmt = c.env.DB.prepare(
        `INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total) VALUES (?, ?, ?, ?, ?)`
      )
      const batch = items.map((item: any) => 
        stmt.bind(invoiceId, item.description, item.quantity, item.unit_price, item.total)
      )
      await c.env.DB.batch(batch)
    }

    return c.json({ id: invoiceId, message: 'Invoice created successfully' }, 201)
  } catch (e: any) {
    return c.json({ error: e.message }, 500)
  }
})

// Update invoice
app.put('/api/invoices/:id', async (c) => {
  const id = c.req.param('id')
  const body = await c.req.json()
  const { 
    invoice_number, date, due_date, status, client_name, client_email, client_address,
    notes, items, subtotal, tax_rate, tax_amount, total_amount
  } = body

  try {
    // Update invoice details
    await c.env.DB.prepare(
      `UPDATE invoices SET 
       invoice_number = ?, date = ?, due_date = ?, status = ?, 
       client_name = ?, client_email = ?, client_address = ?, 
       notes = ?, subtotal = ?, tax_rate = ?, tax_amount = ?, total_amount = ?, updated_at = CURRENT_TIMESTAMP
       WHERE id = ?`
    ).bind(
      invoice_number, date, due_date, status, client_name, client_email, client_address,
      notes, subtotal, tax_rate, tax_amount, total_amount, id
    ).run()

    // Update items: Delete all old items and re-insert (simplest strategy for this scale)
    await c.env.DB.prepare(`DELETE FROM invoice_items WHERE invoice_id = ?`).bind(id).run()

    if (items && items.length > 0) {
      const stmt = c.env.DB.prepare(
        `INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total) VALUES (?, ?, ?, ?, ?)`
      )
      const batch = items.map((item: any) => 
        stmt.bind(id, item.description, item.quantity, item.unit_price, item.total)
      )
      await c.env.DB.batch(batch)
    }

    return c.json({ message: 'Invoice updated successfully' })
  } catch (e: any) {
    return c.json({ error: e.message }, 500)
  }
})

// Delete invoice
app.delete('/api/invoices/:id', async (c) => {
  const id = c.req.param('id')
  await c.env.DB.prepare(`DELETE FROM invoices WHERE id = ?`).bind(id).run()
  return c.json({ message: 'Invoice deleted' })
})

// Get Settings
app.get('/api/settings', async (c) => {
  const { results } = await c.env.DB.prepare('SELECT * FROM settings').all()
  const settings: Record<string, string> = {}
  results.forEach((r: any) => settings[r.key] = r.value)
  return c.json(settings)
})

// Update Settings
app.post('/api/settings', async (c) => {
  const body = await c.req.json()
  const stmt = c.env.DB.prepare(`INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)`)
  const batch = Object.entries(body).map(([key, value]) => stmt.bind(key, value))
  await c.env.DB.batch(batch)
  return c.json({ message: 'Settings updated' })
})

// Fallback for SPA
app.get('*', async (c) => {
    if (c.env.ASSETS) {
        return await c.env.ASSETS.fetch(c.req.raw)
    }
    return c.text('Assets not found', 404)
})

export default app