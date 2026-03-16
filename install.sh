#!/bin/bash
# CypherPulse installer - supports Ubuntu/Debian and macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/tibor-ai/cypherpulse/main/install.sh | bash

set -e

REPO_URL="https://github.com/tibor-ai/cypherpulse.git"
DEFAULT_DIR="$(pwd)"

# ---------- helpers ----------
msg()  { printf '%s\n' "$1"; }
ok()   { printf '[OK]  %s\n' "$1"; }
warn() { printf '[!]   %s\n' "$1"; }
die()  { printf '[ERR] %s\n' "$1" >&2; exit 1; }

# read from /dev/tty so it works when stdin is a pipe (curl | bash)
ask() {
    printf '%s ' "$1"
    read -r REPLY </dev/tty
}

ask_silent() {
    printf '%s ' "$1"
    read -rs REPLY </dev/tty
    printf '\n'
}

msg ""
msg "=================================================="
msg "  CypherPulse Installer"
msg "=================================================="
msg ""

# ---------- detect OS ----------
case "$OSTYPE" in
    linux-gnu*) OS="linux" ;;
    darwin*)    OS="macos" ;;
    *) die "Unsupported OS: $OSTYPE. Supports Ubuntu/Debian and macOS only." ;;
esac
ok "Detected OS: $OS"

# ---------- install location ----------
msg ""
ask "Install directory [default: $DEFAULT_DIR]:"
if [ -n "$REPLY" ]; then
    INSTALL_DIR="$REPLY"
else
    INSTALL_DIR="$DEFAULT_DIR"
fi
msg "Installing to: $INSTALL_DIR"

# ---------- python ----------
python_version_ok() {
    command -v python3 >/dev/null 2>&1 || return 1
    python3 -c "import sys; exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null
}

if python_version_ok; then
    PY_VER=$(python3 -c "import sys; print('%d.%d' % sys.version_info[:2])")
    ok "Python $PY_VER found"
else
    warn "Python 3.9+ not found. Installing..."
    if [ "$OS" = "linux" ]; then
        sudo apt-get update -qq
        sudo apt-get install -y python3 python3-pip python3-venv
    else
        if command -v brew >/dev/null 2>&1; then
            msg "Installing Python via Homebrew..."
            brew install python3
        else
            msg "Installing Homebrew then Python (this may take a few minutes)..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            msg "Installing Python..."
            brew install python3
        fi
    fi
    python_version_ok || die "Python install failed. Install Python 3.9+ from https://www.python.org/downloads/ and re-run."
    ok "Python installed"
fi

# ---------- git ----------
if ! command -v git >/dev/null 2>&1; then
    warn "Git not found. Installing..."
    if [ "$OS" = "linux" ]; then
        sudo apt-get install -y git
    else
        die "Install Git from https://git-scm.com/ then re-run this script."
    fi
fi

# ---------- clone / update ----------
msg ""
if [ -d "$INSTALL_DIR/.git" ]; then
    msg "Updating existing install at $INSTALL_DIR ..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    msg "Cloning to $INSTALL_DIR ..."
    # Clone into a temp dir then move, so it works whether $INSTALL_DIR exists or not
    TMP_CLONE="$(mktemp -d)"
    git clone "$REPO_URL" "$TMP_CLONE/cypherpulse"
    mkdir -p "$INSTALL_DIR"
    cp -r "$TMP_CLONE/cypherpulse/." "$INSTALL_DIR/"
    rm -rf "$TMP_CLONE"
fi
ok "Repository ready"

# ---------- virtualenv + deps ----------
msg ""
msg "Setting up Python environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
ok "Dependencies installed"

# ---------- config: collect API key inline ----------
msg ""
msg "=================================================="
msg "  Setup"
msg "=================================================="

# Check if .env already has values set
ENV_FILE="$INSTALL_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "$INSTALL_DIR/config.example.env" "$ENV_FILE"
fi

# Read existing values if present
EXISTING_KEY=$(grep -E "^TWITTER_API_KEY=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
EXISTING_USER=$(grep -E "^TWITTER_USERNAME=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")

# Prompt for API key
if [ -n "$EXISTING_KEY" ] && [ "$EXISTING_KEY" != "your_api_key_here" ]; then
    ok "API key already set"
    API_KEY="$EXISTING_KEY"
else
    msg ""
    msg "Get your free API key at: https://twitterapi.io/?ref=quenosai"
    ask_silent "twitterapi.io API key:"
    API_KEY="$REPLY"
fi

# Prompt for username
if [ -n "$EXISTING_USER" ] && [ "$EXISTING_USER" != "your_twitter_username" ]; then
    ok "Username already set: $EXISTING_USER"
    TWITTER_USER="$EXISTING_USER"
else
    msg ""
    ask "Your X/Twitter username (without @):"
    TWITTER_USER="$REPLY"
fi

# Write to .env using sed (no heredoc, safe for curl|bash)
if grep -q "^TWITTER_API_KEY=" "$ENV_FILE"; then
    sed -i.bak "s|^TWITTER_API_KEY=.*|TWITTER_API_KEY=$API_KEY|" "$ENV_FILE"
else
    printf '\nTWITTER_API_KEY=%s\n' "$API_KEY" >> "$ENV_FILE"
fi
if grep -q "^TWITTER_USERNAME=" "$ENV_FILE"; then
    sed -i.bak "s|^TWITTER_USERNAME=.*|TWITTER_USERNAME=$TWITTER_USER|" "$ENV_FILE"
else
    printf '\nTWITTER_USERNAME=%s\n' "$TWITTER_USER" >> "$ENV_FILE"
fi
rm -f "$ENV_FILE.bak"

ok "Config saved"

# ---------- optional PATH symlink ----------
msg ""
ask "Add 'cypherpulse' command to /usr/local/bin? [y/N]:"
case "$REPLY" in
    [Yy]*)
        if [ -w "/usr/local/bin" ]; then
            ln -sf "$INSTALL_DIR/venv/bin/cypherpulse" /usr/local/bin/cypherpulse
            ok "cypherpulse added to /usr/local/bin"
        else
            sudo ln -sf "$INSTALL_DIR/venv/bin/cypherpulse" /usr/local/bin/cypherpulse \
                && ok "cypherpulse added to /usr/local/bin" \
                || warn "Could not add to PATH. Run directly: $INSTALL_DIR/venv/bin/cypherpulse"
        fi
        ;;
esac

# ---------- optional scheduling ----------
msg ""
msg "--------------------------------------------------"
msg "  Automated data collection"
msg "--------------------------------------------------"
ask "Schedule automatic data collection? [Y/n]:"
case "$REPLY" in
    [Nn]*) SCHED=no ;;
    *)     SCHED=yes ;;
esac

if [ "$SCHED" = "yes" ]; then
    msg ""
    msg "How often?"
    msg "  1) Hourly"
    msg "  2) Every 6 hours"
    msg "  3) Daily at 9am (recommended)"
    msg "  4) Custom cron expression"
    msg ""
    ask "Choice [1-4, default 3]:"
    FREQ="${REPLY:-3}"

    case "$FREQ" in
        1) CRON_EXPR="0 * * * *";   FREQ_DESC="hourly" ;;
        2) CRON_EXPR="0 */6 * * *"; FREQ_DESC="every 6 hours" ;;
        4)
            ask "Enter cron expression (e.g. 0 9 * * *):"
            CRON_EXPR="$REPLY"
            FREQ_DESC="custom"
            ;;
        *) CRON_EXPR="0 9 * * *";   FREQ_DESC="daily at 9am" ;;
    esac

    CRON_CMD="cd $INSTALL_DIR && source venv/bin/activate && cypherpulse scan && cypherpulse collect >> $INSTALL_DIR/cypherpulse.log 2>&1"
    ( crontab -l 2>/dev/null; echo "$CRON_EXPR $CRON_CMD" ) | crontab -
    ok "Cron job added ($FREQ_DESC)"
else
    msg "Skipped. To add later: crontab -e"
fi

# ---------- initial data collection ----------
msg ""
msg "=================================================="
msg "  Fetching your initial data..."
msg "=================================================="
msg ""

cd "$INSTALL_DIR"
source venv/bin/activate

msg "Scanning your recent tweets..."
cypherpulse scan && ok "Scan complete"

msg ""
msg "Collecting engagement metrics..."
cypherpulse collect && ok "Metrics collected"

# ---------- launch dashboard ----------
msg ""
ask "Open the dashboard now in your browser? [Y/n]:"
case "$REPLY" in
    [Nn]*) ;;
    *)
        msg "Starting dashboard at http://localhost:8080 ..."
        msg "(Press Ctrl+C to stop)"
        msg ""
        cypherpulse serve
        ;;
esac

# ---------- done ----------
msg ""
msg "=================================================="
msg "  CypherPulse is ready!"
msg "=================================================="
msg ""
msg "To run manually:"
msg "  cd $INSTALL_DIR && source venv/bin/activate"
msg "  cypherpulse scan      # fetch new tweets"
msg "  cypherpulse collect   # snapshot metrics"
msg "  cypherpulse serve     # open dashboard"
msg ""
