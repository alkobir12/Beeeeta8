from pathlib import Path


LOGIN = Path('/app/frontend/src/pages/Login.jsx').read_text(encoding='utf-8')
BACKEND_BASE = Path('/app/frontend/src/utils/backendBase.js').read_text(encoding='utf-8')
AUTH_TOKEN = Path('/app/frontend/src/utils/authToken.js').read_text(encoding='utf-8')


def test_login_defaults_to_password_not_stale_pin():
    assert "const [showPassword, setShowPassword] = useState(true);" in LOGIN
    assert "const [pinMode, setPinMode] = useState(false);" in LOGIN


def test_pin_toggle_keeps_password_and_pin_modes_exclusive():
    assert "const nextPinMode = !pinMode;" in LOGIN
    assert "setPinMode(nextPinMode);" in LOGIN
    assert "setShowPassword(!nextPinMode);" in LOGIN


def test_browser_api_base_is_same_origin_relative():
    assert "window.location?.origin" in BACKEND_BASE
    assert "return '';" in BACKEND_BASE
    assert "export const API_BASE = `${resolveBackendBase()}/api`;" in BACKEND_BASE


def test_auth_fetches_include_credentials_without_omit_fallback():
    assert "credentials: 'include'" in AUTH_TOKEN
    assert "credentials: 'omit'" not in AUTH_TOKEN
    assert "REACT_APP_BACKEND_URL || ''" not in AUTH_TOKEN