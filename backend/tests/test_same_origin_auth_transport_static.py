from pathlib import Path


BACKEND_BASE = Path('/app/frontend/src/utils/backendBase.js').read_text(encoding='utf-8')
AUTH_TOKEN = Path('/app/frontend/src/utils/authToken.js').read_text(encoding='utf-8')
API_CLIENT = Path('/app/frontend/src/services/api.js').read_text(encoding='utf-8')
SIDEBAR = Path('/app/frontend/src/components/Sidebar.jsx').read_text(encoding='utf-8')


def test_browser_resolver_prefers_same_origin_api_transport():
    assert "window.location?.origin" in BACKEND_BASE
    assert "return '';" in BACKEND_BASE
    assert "export const API_BASE = `${resolveBackendBase()}/api`;" in BACKEND_BASE


def test_auth_requests_are_cookie_backed_no_omit_fallback():
    assert "credentials: 'include'" in AUTH_TOKEN
    assert "credentials: 'omit'" not in AUTH_TOKEN
    assert "REACT_APP_BACKEND_URL || ''" not in AUTH_TOKEN


def test_shared_axios_client_sends_credentials():
    assert "axios.defaults.withCredentials = true;" in API_CLIENT
    assert "withCredentials: true" in API_CLIENT


def test_logout_uses_same_origin_resolver():
    assert "resolveBackendBase()}/api/auth/logout" in SIDEBAR
    assert "process.env.REACT_APP_BACKEND_URL || ''}/api/auth/logout" not in SIDEBAR