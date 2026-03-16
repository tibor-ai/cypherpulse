#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/tibor-ai/cypherpulse.git"
INSTALL_DIR="$HOME/cypherpulse"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=9

# Colors (ASCII safe)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo "=================================================="
echo "  CypherPulse Installer"
echo "=================================================="
echo ""

# --- Detect OS ---
case "$OSTYPE" in
  linux-gnu*) OS="linux" ;;
  darwin*)    OS="macos" ;;
  *)          err "Unsupported OS: $OSTYPE. Supports Ubuntu/Debian and macOS." ;;
esac
ok "Detected OS: $OS"

# --- Python check / install ---
install_python_linux() {
    echo "Installing Python 3..."
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-pip python3-venv
}

install_python_macos() {
    if command -v brew &>/dev/null; then
        echo "Installing Python via Homebrew..."
        brew install python3
    else
        echo "Installing Homebrew (this may take a few minutes)..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        echo "Installing Python via Homebrew..."
        brew install python3
    fi
}

check_python() {
    if ! command -v python3 &>/dev/null; then return 1; fi
    local ver
    ver=$(python3 -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null)
    local major minor
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    [ "$major" -ge "$MIN_PYTHON_MAJOR" ] && [ "$minor" -ge "$MIN_PYTHON_MINOR" ]
}

if check_python; then
    PYTHON_VER=$(python3 -c "import sys; print('%d.%d' % sys.version_info[:2])")
    ok "Python $PYTHON_VER found"
else
    warn "Python 3.9+ not found. Installing..."
    if [ "$OS" = "linux" ]; then
        install_python_linux
    else
        install_python_macos
    fi
    check_python || err "Python install failed. Please install Python 3.9+ manually from https://www.python.org/downloads/"
    ok "Python installed successfully"
fi

# --- Git check ---
if ! command -v git &>/dev/null; then
    warn "Git not found. Installing..."
    if [ "$OS" = "linux" ]; then
        sudo apt-get install -y git
    else
        err "Please install Git from https://git-scm.com/ and re-run this script."
    fi
fi

# --- Clone or update repo ---
echo ""
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating existing CypherPulse installation..."
    cd "$INSTALL_DIR" && git pull --ff-only
else
    echo "Cloning CypherPulse to $INSTALL_DIR ..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
ok "Repository ready"

# --- Virtualenv + dependencies ---
cd "$INSTALL_DIR"
echo ""
echo "Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Dependencies installed"

# --- Config ---
if [ ! -f ".env" ]; then
    cp config.example.env .env
    ok "Config file created: $INSTALL_DIR/.env"
    echo ""
    echo "  --> Edit $INSTALL_DIR/.env and add:"
    echo "      TWITTER_API_KEY   (get yours at https://twitterapi.io/?ref=quenosai)"
    echo "      TWITTER_USERNAME  (your X/Twitter handle, without @)"
    echo ""
else
    ok ".env already exists, skipping"
fi

# --- Optional PATH symlink ---
echo ""
read -p "Add 'cypherpulse' command to PATH? (requires sudo on some systems) [y/N]: " -r PATHREPLY
if [[ "$PATHREPLY" =~ ^[Yy]$ ]]; then
    if [ -w "/usr/local/bin" ]; then
        ln -sf "$INSTALL_DIR/venv/bin/cypherpulse" /usr/local/bin/cypherpulse
        ok "cypherpulse added to /usr/local/bin"
    else
        sudo ln -sf "$INSTALL_DIR/venv/bin/cypherpulse" /usr/local/bin/cypherpulse && \
            ok "cypherpulse added to /usr/local/bin" || \
            warn "Could not add to PATH. Run from: $INSTALL_DIR/venv/bin/cypherpulse"
    fi
fi

# --- Optional scheduling ---
echo ""
echo "--------------------------------------------------"
echo "  Automated data collection (recommended)"
echo "--------------------------------------------------"
read -p "Run CypherPulse automatically on a schedule? [Y/n]: " -r SCHEDREPLY
if [[ ! "$SCHEDREPLY" =~ ^[Nn]$ ]]; then
    echo ""
    echo "How often?"
    echo "  1) Hourly"
    echo "  2) Every 6 hours"
    echo "  3) Daily at 9am (recommended)"
    echo "  4) Custom cron expression"
    echo ""
    read -p "Choice [1-4, default 3]: " -r FREQ
    FREQ="${FREQ:-3}"

    case "$FREQ" in
        1) CRON_EXPR="0 * * * *";    FREQ_DESC="hourly" ;;
        2) CRON_EXPR="0 */6 * * *";  FREQ_DESC="every 6 hours" ;;
        3) CRON_EXPR="0 9 * * *";    FREQ_DESC="daily at 9am" ;;
        4)
            read -p "Enter cron expression: " -r CRON_EXPR
            FREQ_DESC="custom schedule"
            ;;
        *) CRON_EXPR="0 9 * * *";    FREQ_DESC="daily at 9am" ;;
    esac

    CRON_CMD="cd $INSTALL_DIR && source venv/bin/activate && cypherpulse scan && cypherpulse collect >> $INSTALL_DIR/cypherpulse.log 2>&1"
    (crontab -l 2>/dev/null; echo "$CRON_EXPR $CRON_CMD") | crontab -
    ok "Cron job added ($FREQ_DESC)"
else
    echo "Skipped. To set up later: crontab -e"
fi

# --- Done ---
echo ""
echo "=================================================="
echo "  Installation complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Edit $INSTALL_DIR/.env with your API key and username"
echo "  2. cd $INSTALL_DIR && source venv/bin/activate"
echo "  3. cypherpulse scan     # fetch your recent tweets"
echo "  4. cypherpulse collect  # snapshot engagement metrics"
echo "  5. cypherpulse serve    # open dashboard in browser"
echo ""
echo "Get your twitterapi.io key: https://twitterapi.io/?ref=quenosai"
echo ""
