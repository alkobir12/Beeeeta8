from pathlib import Path


LOGIN = Path('/app/frontend/src/pages/Login.jsx').read_text(encoding='utf-8')


def test_login_defaults_to_password_not_stale_pin():
    assert "const [showPassword, setShowPassword] = useState(true);" in LOGIN
    assert "const [pinMode, setPinMode] = useState(false);" in LOGIN


def test_pin_toggle_keeps_password_and_pin_modes_exclusive():
    assert "const nextPinMode = !pinMode;" in LOGIN
    assert "setPinMode(nextPinMode);" in LOGIN
    assert "setShowPassword(!nextPinMode);" in LOGIN