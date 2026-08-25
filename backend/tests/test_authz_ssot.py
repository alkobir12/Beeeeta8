"""Security regression tests for the Authorization SSOT (core/authz).
Pure unit tests on the policy engine + user-guard helpers — no HTTP, no DB, no mutation.
Run: python tests/test_authz_ssot.py"""
import sys, os
sys.path.insert(0, '/app/backend')
os.chdir('/app/backend')
from core import authz
from routes_users import _actor_is_admin, _grants_privileged_perms
from core.rbac import Actor, get_role_permissions

def _ev(path, method, role):
    return authz.evaluate(path, method, {"sub": "u", "role": role})

FAILS = []
def check(cond, label):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: FAILS.append(label)

# 1) P0-SEC-USERS: privilege escalation blocked
check(_ev("/api/users/9", "DELETE", "technician") is not None, "technician cannot DELETE users")
check(_ev("/api/users/9", "PUT", "technician") is not None, "technician cannot PUT users")
check(_ev("/api/users", "POST", "reception") is not None, "reception cannot create users")
check(_ev("/api/users", "GET", "accountant") is not None, "accountant cannot list users (users.view=false)")
check(_ev("/api/users", "GET", "manager") is None, "manager can list users (users.view=true)")
check(_ev("/api/users/9", "DELETE", "admin") is None, "admin can manage users")
# critical fail-closed when role missing
check(authz.evaluate("/api/users/9", "DELETE", {"sub": "u"}) is not None, "no-role → users management denied (fail-closed)")

# 2) destructive admin-only
check(_ev("/api/financial-reset/run", "POST", "technician") is not None, "technician cannot run financial-reset")
check(_ev("/api/financial-reset/run", "POST", "accountant") is not None, "accountant cannot run financial-reset")
check(_ev("/api/financial-reset/run", "POST", "admin") is None, "admin can run financial-reset")

# 3) ledger/finance mutations grounded in journal_entries perm
check(_ev("/api/finance/post-x", "POST", "accountant") is None, "accountant can write ledger (journal_entries.edit)")
check(_ev("/api/finance/post-x", "POST", "technician") is not None, "technician cannot write ledger")
check(_ev("/api/finance/post-x", "DELETE", "accountant") is not None, "accountant cannot DELETE ledger (delete=admin only)")
check(_ev("/api/finance/post-x", "DELETE", "admin") is None, "admin can DELETE ledger")

# 4) operations mutations
check(_ev("/api/operations/5", "PUT", "reception") is None, "reception can edit operations")
check(_ev("/api/operations/5", "DELETE", "reception") is not None, "reception cannot delete operations")
check(_ev("/api/operations/5", "PUT", "storekeeper") is not None, "storekeeper cannot edit operations")

# 5) invoices/settings
check(_ev("/api/invoices", "POST", "accountant") is None, "accountant can create invoices")
check(_ev("/api/invoices", "POST", "storekeeper") is not None, "storekeeper cannot create invoices")
check(_ev("/api/settings/x", "PUT", "manager") is not None, "manager cannot edit settings (settings.edit=false)")
check(_ev("/api/settings/x", "PUT", "admin") is None, "admin can edit settings")

# 6) financial-control mutations → approver roles
check(_ev("/api/financial-control/findings/scan", "POST", "accountant") is None, "accountant (approver) can scan findings")
check(_ev("/api/financial-control/findings/scan", "POST", "technician") is not None, "technician cannot scan findings")

# 7) NO BLIND AUTHORIZATION: unlisted / read endpoints unaffected
check(_ev("/api/vehicles", "GET", "technician") is None, "unlisted GET vehicles allowed (no breakage)")
check(_ev("/api/operations/5", "GET", "technician") is None, "GET operations allowed (mutation-only policy)")
check(_ev("/api/dashboard/kpis", "GET", "technician") is None, "dashboard GET allowed")

# 8) object-level user-guard helpers (mass-assignment / privilege)
admin = Actor(user_id="a", name="a", role="admin", permissions=get_role_permissions("admin"), found=True)
tech = Actor(user_id="t", name="t", role="technician", permissions=get_role_permissions("technician"), found=True)
check(_actor_is_admin(admin) is True, "admin recognized as admin")
check(_actor_is_admin(tech) is False, "technician not admin")
check(_grants_privileged_perms({"users": {"edit": True}}) is True, "granting users.edit is privileged")
check(_grants_privileged_perms({"settings": {"edit": True}}) is True, "granting settings.edit is privileged")
check(_grants_privileged_perms({"vehicles": {"edit": True}}) is False, "granting vehicles.edit not privileged")

print("\n" + ("ALL PASS" if not FAILS else f"{len(FAILS)} FAILURES: {FAILS}"))
sys.exit(1 if FAILS else 0)
