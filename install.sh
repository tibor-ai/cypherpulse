#!/usr/bin/env bash
set -e

# CypherPulse Installation Script
# Supports: Ubuntu/Debian and macOS

REPO_URL="https://github.com/tibor-ai/cypherpulse.git"
INSTALL_DIR="$HOME/cypherpulse"
MIN_PYTHON_VERSION="3.9"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "════════════════════════════════════════════════════"
echo "   CypherPulse Installation"
echo "════════════════════════════════════════════════════"
echo ""

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo "✓ Detected OS: Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "✓ Detected OS: macOS"
else
    echo -e "${RED}✗ Unsupported OS: $OSTYPE${NC}"
    echo "This script supports Ubuntu/Debian and macOS only."
    exit 1
fi

echo ""

# Check Python version
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 9 ]; then
            echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠ Python $PYTHON_VERSION found (need 3.9+)${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠ Python 3 not found${NC}"
        return 1
    fi
}

# Install Python if needed
if ! check_python; then
    echo ""
    echo "Python 3.9+ is required but not found."
    echo ""
    
    if [ "$OS" == "linux" ]; then
        echo "Installing Python..."
        
        if sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv; then
            echo -e "${GREEN}✓ Python installed successfully${NC}"
            
            # Re-check Python version
            if check_python; then
                echo -e "${GREEN}✓ Python is now ready${NC}"
            else
                echo -e "${RED}✗ Python installed but version is too old${NC}"
                echo "Please upgrade Python manually to version 3.9 or higher."
                exit 1
            fi
        else
            echo -e "${RED}✗ Failed to install Python${NC}"
            exit 1
        fi
        
    elif [ "$OS" == "macos" ]; then
        if command -v brew &> /dev/null; then
            echo "Installing Python via Homebrew..."
            
            if brew install python3; then
                echo -e "${GREEN}✓ Python installed successfully${NC}"
                
                # Re-check Python version
                if check_python; then
                    echo -e "${GREEN}✓ Python is now ready${NC}"
                else
                    echo -e "${RED}✗ Python installed but not available in PATH${NC}"
                    echo "You may need to restart your terminal and run this script again."
                    exit 1
                fi
            else
                echo -e "${RED}✗ Homebrew installation failed${NC}"
                exit 1
            fi
        else
            echo "Installing Homebrew and Python (this may take a few minutes)..."
            
            # Install Homebrew
            if /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; then
                echo -e "${GREEN}✓ Homebrew installed successfully${NC}"
                
                # Install Python
                echo "Installing Python..."
                if brew install python3; then
                    echo -e "${GREEN}✓ Python installed successfully${NC}"
                    
                    # Re-check Python version
                    if check_python; then
                        echo -e "${GREEN}✓ Python is now ready${NC}"
                    else
                        echo -e "${RED}✗ Python installed but not available in PATH${NC}"
                        echo "You may need to restart your terminal and run this script again."
                        exit 1
                    fi
                else
                    echo -e "${RED}✗ Python installation failed${NC}"
                    exit 1
                fi
            else
                echo -e "${RED}✗ Homebrew installation failed${NC}"
                exit 1
            fi
        fi
    fi
fi

echo ""

# Clone or update repository
if [ -d "$INSTALL_DIR" ]; then
    echo "📁 CypherPulse directory already exists at $INSTALL_DIR"
    read -p "Update existing installation? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Updating repository..."
        cd "$INSTALL_DIR"
        git pull origin main || {
            echo -e "${YELLOW}⚠ Git pull failed, skipping update${NC}"
        }
    else
        echo "Skipping repository update"
    fi
else
    echo "📦 Cloning repository to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR" || {
        echo -e "${RED}✗ Git clone failed${NC}"
        exit 1
    }
fi

cd "$INSTALL_DIR"
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv || {
        echo -e "${RED}✗ Failed to create virtual environment${NC}"
        exit 1
    }
else
    echo "✓ Virtual environment already exists"
fi

# Activate and install dependencies
echo "📚 Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip > /dev/null
pip install -r requirements.txt || {
    echo -e "${RED}✗ Failed to install dependencies${NC}"
    exit 1
}

# Install package in development mode
pip install -e . > /dev/null || {
    echo -e "${YELLOW}⚠ Failed to install package (continuing anyway)${NC}"
}

echo ""

# Copy config file if needed
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file from template..."
    cp config.example.env .env
    echo -e "${GREEN}✓ .env file created${NC}"
else
    echo "✓ .env file already exists (not overwriting)"
fi

echo ""

# Optional: Add CLI to PATH
read -p "Add 'cypherpulse' command to your PATH? (requires sudo) (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -w "/usr/local/bin" ]; then
        ln -sf "$INSTALL_DIR/venv/bin/cypherpulse" /usr/local/bin/cypherpulse
        echo -e "${GREEN}✓ cypherpulse added to /usr/local/bin${NC}"
    else
        sudo ln -sf "$INSTALL_DIR/venv/bin/cypherpulse" /usr/local/bin/cypherpulse && \
            echo -e "${GREEN}✓ cypherpulse added to /usr/local/bin${NC}" || \
            echo -e "${YELLOW}⚠ Failed to add to PATH (you can still use it from $INSTALL_DIR/venv/bin/cypherpulse)${NC}"
    fi
fi

echo ""
echo "════════════════════════════════════════════════════"
echo -e "${GREEN}✓ Installation complete!${NC}"
echo "════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo ""
echo "1. Get your API key from https://twitterapi.io/"
echo ""
echo "2. Edit your configuration:"
echo -e "   ${YELLOW}nano $INSTALL_DIR/.env${NC}"
echo ""
echo "   Add your credentials:"
echo "   TWITTER_API_KEY=your_api_key_here"
echo "   TWITTER_USERNAME=your_twitter_username"
echo ""
echo "3. Start the dashboard:"
echo -e "   ${YELLOW}cd $INSTALL_DIR${NC}"
echo -e "   ${YELLOW}source venv/bin/activate${NC}"
echo -e "   ${YELLOW}cypherpulse serve${NC}"
echo ""
echo "   Then open: http://localhost:8080"
echo ""
echo "════════════════════════════════════════════════════"
