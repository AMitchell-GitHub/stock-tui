#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Starting Stock TUI Installation...${NC}"

# 1. Check Prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

if ! command -v cargo &> /dev/null; then
    echo -e "${RED}Error: Cargo (Rust) is not installed.${NC}"
    echo "Please install Rust: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed.${NC}"
    exit 1
fi

# 2. Build Release Binary
echo -e "${BLUE}Building release binary...${NC}"
cargo build --release

# 3. Create Installation Directory
INSTALL_DIR="$HOME/.local/share/stock-tui"
BIN_DIR="$HOME/.local/bin"

echo -e "${BLUE}Installing to $INSTALL_DIR...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# 4. Copy Files
echo -e "${BLUE}Copying application files...${NC}"
# Binary - assumed to be 'tmp2' based on Cargo.toml. Renaming to stock-tui-bin
if [ -f "target/release/tmp2" ]; then
    cp "target/release/tmp2" "$INSTALL_DIR/stock-tui-bin"
elif [ -f "target/release/stock-tui" ]; then
    cp "target/release/stock-tui" "$INSTALL_DIR/stock-tui-bin"
else
    echo -e "${RED}Error: Could not find compiled binary in target/release/${NC}"
    exit 1
fi

# Python Script
cp fetch_stock.py "$INSTALL_DIR/"

# Logic Resources
cp top-tickers.csv "$INSTALL_DIR/"
cp -r indicators "$INSTALL_DIR/"

# 5. Create Wrapper Script
echo -e "${BLUE}Creating wrapper script in $BIN_DIR/stock-tui...${NC}"
cat > "$BIN_DIR/stock-tui" << 'EOF'
#!/bin/bash
# Wrapper for Stock TUI to run from installation directory
INSTALL_DIR="$HOME/.local/share/stock-tui"
if [ -d "$INSTALL_DIR" ]; then
    cd "$INSTALL_DIR"
    ./stock-tui-bin "$@"
else
    echo "Error: Stock TUI installation not found at $INSTALL_DIR"
    exit 1
fi
EOF

chmod +x "$BIN_DIR/stock-tui"

# 6. Python Dependencies Check
echo -e "${BLUE}Checking Python dependencies...${NC}"
if ! python3 -c "import yfinance, matplotlib, pandas" &> /dev/null; then
    echo -e "${RED}Warning: Python dependencies missing.${NC}"
    echo "Attempting to install: yfinance matplotlib pandas"
    pip3 install yfinance matplotlib pandas --user
else
    echo -e "${GREEN}Python dependencies found.${NC}"
fi

echo -e "${GREEN}Installation Complete!${NC}"
echo -e "You can now run the application with: ${GREEN}stock-tui [TICKER]${NC}"
echo -e "Note: Ensure '$BIN_DIR' is in your PATH."
