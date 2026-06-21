#!/bin/bash
set -euo pipefail

# Only run in remote (web) sessions
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo '{"async": true, "asyncTimeout": 300000}'

# Install Python backend dependencies, skipping unavailable private packages
grep -v "emergentintegrations" "$CLAUDE_PROJECT_DIR/backend/requirements.txt" \
  | pip install -r /dev/stdin --quiet --ignore-installed

# Create a stub for the proprietary emergentintegrations package so imports succeed
SITE_PKG=$(python3 -c "import site; print(site.getsitepackages()[0])")
mkdir -p "$SITE_PKG/emergentintegrations/llm"
touch "$SITE_PKG/emergentintegrations/__init__.py"
touch "$SITE_PKG/emergentintegrations/llm/__init__.py"
cat > "$SITE_PKG/emergentintegrations/llm/chat.py" << 'PYEOF'
class UserMessage:
    def __init__(self, text: str = "", **kwargs):
        self.text = text

class ImageContent:
    def __init__(self, url: str = "", **kwargs):
        self.url = url

class LlmChat:
    def __init__(self, api_key: str = "", session_id: str = "", system_message: str = "", **kwargs):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message

    def with_model(self, provider: str, model: str):
        return self

    async def send_message(self, message):
        raise RuntimeError("emergentintegrations stub — AI chat requires the proprietary package.")
PYEOF

# Install frontend dependencies using yarn
cd "$CLAUDE_PROJECT_DIR/frontend" && yarn install
