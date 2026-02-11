# Stock TUI

The definitive terminal UI for viewing stocks, markets, commodities, ETFs, and more!

Complete with modular indicators, high resolution charts, multiple time frames and intervals, and chart types!

## Prerequisites

- **Rust**: Ensure you have Rust and Cargo installed.
- **Python 3**: The data fetching and charting logic requires Python 3.
- **Python Dependencies**:
  ```bash
  pip3 install yfinance matplotlib pandas
  ```
- **A compatible terminal**: Your terminal must work with ratatui_image, so it is recommended that it support the high-resolution kitty image protocol. Try Wezterm, Kitty, or Ghostty.

## Build and Run

To run the application locally:

```bash
cargo run -- [TICKER]
```
Example:
```bash
cargo run -- NVDA
```

## Installation

### Automatic Install (Recommended)

Run the installation script to build and set up `stock-tui`:

```bash
chmod +x install.sh
./install.sh
```

This will:
1.  Verify dependencies (Python 3, Rust/Cargo).
2.  Install required Python packages if missing.
3.  Build the release binary.
4.  Install the application to `~/.local/share/stock-tui`.
5.  Create a wrapper script `stock-tui` in `~/.local/bin`.

Wait for the "Installation Complete!" message. Ensure `~/.local/bin` is in your `PATH`.

### Manual Install

If you prefer to install manually:

1.  **Build the release binary**:
    ```bash
    cargo build --release
    ```

2.  **Create Installation Directory**:
    Create a folder to hold the application and its resources (e.g., `~/.local/share/stock-tui`):
    ```bash
    mkdir -p ~/.local/share/stock-tui
    ```

3.  **Copy Files**:
    Copy the binary, Python script, and data files to the installation directory:
    ```bash
    cp target/release/tmp2 ~/.local/share/stock-tui/stock-tui-bin
    cp fetch_stock.py ~/.local/share/stock-tui/
    cp top-tickers.csv ~/.local/share/stock-tui/
    cp -r indicators ~/.local/share/stock-tui/
    ```

4.  **Create Wrapper Script**:
    Create a script named `stock-tui` in your `PATH` (e.g., `~/.local/bin/stock-tui`) with the following content:
    ```bash
    #!/bin/bash
    cd ~/.local/share/stock-tui
    ./stock-tui-bin "$@"
    ```
    Make it executable:
    ```bash
    chmod +x ~/.local/bin/stock-tui
    ```

## Usage

```bash
stock-tui [TICKER]
```

- **[TICKER]**: Optional. The stock symbol to query (e.g., TSLA, AMD, SPY). Defaults to "AAPL".
- **Controls**:
    - `q` or `Esc`: Quit the application.
    - `Ctrl + o`: Open a ticker
    - `Ctrl + s`: Settings menu
