"""
🤝 Shared Partner Financials — Re-export module.

Hosts the partner-financial-map helpers used by both customers/* and suppliers/*
domains. Right now these still live inside server.py for historical reasons,
so this module simply provides a stable import surface. Future refactors will
move the actual logic here.

Usage:
    from shared.partner_financials import (
        build_partner_financial_map,
        get_customer_file_number_map,
        safe_sync_partner_subaccounts,
        partner_summary_template,
    )
"""

# Late imports to avoid circular dependency (server.py imports domains/*, and
# we'd otherwise import server.py back).
def build_partner_financial_map(*args, **kwargs):
    from server import _build_partner_financial_map  # noqa: WPS433
    return _build_partner_financial_map(*args, **kwargs)


def get_customer_file_number_map(*args, **kwargs):
    from server import _get_customer_file_number_map  # noqa: WPS433
    return _get_customer_file_number_map(*args, **kwargs)


def safe_sync_partner_subaccounts(*args, **kwargs):
    from server import _safe_sync_partner_subaccounts  # noqa: WPS433
    return _safe_sync_partner_subaccounts(*args, **kwargs)


def partner_summary_template():
    from server import _partner_summary_template  # noqa: WPS433
    return _partner_summary_template()
