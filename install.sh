#!/bin/bash
# CypherPulse installer - supports Ubuntu/Debian and macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/tibor-ai/cypherpulse/main/install.sh | bash

set -e

REPO_URL="https://github.com/tibor-ai/cypherpulse.git"
INSTALL_DIR="$HOME/cypherpulse"

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
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
ok "Repository ready"

# ---------- virtualenv + deps ----------
msg ""
msg "Setting up Python environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
ok "Dependencies installed"

# ---------- config ----------
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/config.example.env" "$INSTALL_DIR/.env"
    ok "Config created: $INSTALL_DIR/.env"
    msg ""
    msg "  Edit $INSTALL_DIR/.env and set:"
    msg "    TWITTER_API_KEY    -> get one at https://twitterapi.io/?ref=quenosai"
    msg "    TWITTER_USERNAME   -> your handle (without @)"
    msg ""
else
    ok ".env already exists"
fi

# ---------- optional PATH symlink ----------
msg ""
ask "Add 'cypherpulse' to /usr/local/bin? [y/N]:"
case "$REPLY" in
    [Yy]*)
        if [ -w "/usr/local/bin" ]; then
            ln -sf "$INSTALL_DIR/venv/bin/cypherpulse" /usr/local/bin/cypherpulse
            ok "cypherpulse added to /usr/local/bin"
        else
            sudo ln -sf "$INSTALL_DIR/venv/bin/cypherpulse" /usr/local/bin/cypherpulse \
                && ok "cypherpulse added to /usr/local/bin" \
                || warn "Could not add to PATH. Run: $INSTALL_DIR/venv/bin/cypherpulse"
        fi
        ;;
esac

# ---------- optional scheduling ----------
msg ""
msg "--------------------------------------------------"
msg "  Automated data collection"
msg "--------------------------------------------------"
ask "Schedule CypherPulse to run automatically? [Y/n]:"
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
            ask "Enter cron expression:"
            CRON_EXPR="$REPLY"
            FREQ_DESC="custom"
            ;;
        *) CRON_EXPR="0 9 * * *";   FREQ_DESC="daily at 9am" ;;
    esac

    CRON_CMD="cd $INSTALL_DIR && source venv/bin/activate && cypherpulse scan && cypherpulse collect >> $INSTALL_DIR/cypherpulse.log 2>&1"
    ( crontab -l 2>/dev/null; echo "$CRON_EXPR $CRON_CMD" ) | crontab -
    ok "Cron job added ($FREQ_DESC)"
else
    msg "Skipped. To set up later: crontab -e"
fi

# ---------- done ----------
msg ""
msg "=================================================="
msg "  Done!"
msg "=================================================="
msg ""
msg "Next steps:"
msg "  1. Edit $INSTALL_DIR/.env  (add API key + username)"
msg "  2. cd $INSTALL_DIR && source venv/bin/activate"
msg "  3. cypherpulse scan      # fetch recent tweets"
msg "  4. cypherpulse collect   # snapshot metrics"
msg "  5. cypherpulse serve     # open dashboard"
msg ""
msg "API key: https://twitterapi.io/?ref=quenosai"
msg ""
