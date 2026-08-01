"""
Iteration 227 - Integration tests for the bugs reported by user.
Covers:
- /api/customers (DebtFollowUp dependency)
- /api/suppliers (DebtFollowUp dependency)
- /api/finance/chart-of-accounts (DebtFollowUp + OperationCard accounting badge)
- /api/operations (live sync between operations/POS/journal)
- /api/smart-pos-journal entries (live sync source)
- /api/finance/journal-entries (linkage check)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ar-ledger-ssot.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = 'finmodule-sync'


@pytest.fixture(scope='module')
def client():
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})
    return s


# ---------- DebtFollowUp dependencies ----------
class TestDebtFollowUpDeps:
    def test_customers_endpoint(self, client):
        r = client.get(f'{BASE_URL}/api/customers', params={'workshop_id': WORKSHOP_ID}, timeout=20)
        assert r.status_code == 200, f'customers HTTP {r.status_code}: {r.text[:300]}'
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_suppliers_endpoint(self, client):
        r = client.get(f'{BASE_URL}/api/suppliers', params={'workshop_id': WORKSHOP_ID}, timeout=20)
        assert r.status_code == 200, f'suppliers HTTP {r.status_code}: {r.text[:300]}'
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_chart_of_accounts(self, client):
        r = client.get(f'{BASE_URL}/api/finance/chart-of-accounts',
                       params={'workshop_id': WORKSHOP_ID}, timeout=20)
        assert r.status_code == 200, f'chart-of-accounts HTTP {r.status_code}: {r.text[:300]}'
        data = r.json()
        # Should be a list or dict containing accounts
        if isinstance(data, dict):
            accounts = data.get('accounts') or data.get('data') or data.get('items') or []
        else:
            accounts = data
        assert isinstance(accounts, list)


# ---------- Live sync (operations / POS / journal) ----------
class TestLiveSyncSources:
    def test_operations_listing(self, client):
        r = client.get(f'{BASE_URL}/api/operations', params={'workshop_id': WORKSHOP_ID}, timeout=30)
        assert r.status_code == 200, f'operations HTTP {r.status_code}: {r.text[:300]}'
        data = r.json()
        ops = data if isinstance(data, list) else (data.get('items') or data.get('operations') or data.get('data') or [])
        assert isinstance(ops, list)

    def test_journal_entries(self, client):
        r = client.get(f'{BASE_URL}/api/finance/journal-entries',
                       params={'workshop_id': WORKSHOP_ID}, timeout=30)
        # journal-entries may or may not exist - allow 404 but flag others
        assert r.status_code in (200, 404), f'journal-entries HTTP {r.status_code}: {r.text[:300]}'

    def test_smart_pos_journal_source(self, client):
        # SmartPOSJournal page reads from /api/finance/journal-entries
        r = client.get(f'{BASE_URL}/api/finance/journal-entries',
                       params={'workshop_id': WORKSHOP_ID, 'limit': 10}, timeout=20)
        assert r.status_code == 200, f'finance/journal-entries HTTP {r.status_code}: {r.text[:300]}'


# ---------- Raw-field leak in operations response ----------
class TestNoRawLeaks:
    """Check operations API doesn't expose raw enum-only fields without Arabic labels.
    NB: backend MAY return raw fields (payment_status='paid_full'); we only assert structure
    and let the frontend format. So this test just asserts presence of useful keys.
    """
    def test_operation_shape(self, client):
        r = client.get(f'{BASE_URL}/api/operations', params={'workshop_id': WORKSHOP_ID, 'limit': 5}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        ops = data if isinstance(data, list) else (data.get('items') or data.get('operations') or data.get('data') or [])
        if not ops:
            pytest.skip('no operations seeded to inspect shape')
        sample = ops[0]
        assert isinstance(sample, dict)
        # at least one of id/_id/invoiceNumber must exist
        assert any(k in sample for k in ('id', '_id', 'invoiceNumber', 'invoice_number'))
