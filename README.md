# Stock TUI

A terminal-based interface for viewing live stock data and intraday charts.

## Prerequisites

- **Rust**: Ensure you have Rust and Cargo installed.
- **Python 3**: The data fetching and charting logic requires Python 3.
- **Python Dependencies**:
  ```bash
  pip3 install yfinance matplotlib pandas
  ```

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

To install the application so you can run it from anywhere:

1.  **Build the release binary**:
    ```bash
    cargo build --release
    ```

2.  **Copy the binary and the Python script**:
    The application relies on `fetch_stock.py` being in the same directory or accessible.
    
    A simple way to install is to create a directory in your local bin path:

    ```bash
    mkdir -p ~/.local/bin/stock-tui-app
    cp target/release/tmp2 ~/.local/bin/stock-tui-app/stock-tui
    cp fetch_stock.py ~/.local/bin/stock-tui-app/
    ```

    *Note: The current implementation looks for `fetch_stock.py` in the current working directory. For a global install, you might need to wrap it in a shell script or modify the Rust code to look for the python script in a specific location.*

    **Recommended (Alias method):**
    
    Keep the project in a folder (e.g., `~/tools/stock-tui`) and add an alias to your shell configuration (`.bashrc` or `.zshrc`):

    ```bash
    alias stock="cd /path/to/stock-tui && cargo run --release --quiet --"
    ```
    
    Or if you want to use the compiled binary:
    
    1. Move the folder to a permanent location (e.g., `~/.local/share/stock-tui`).
    2. Create a wrapper script in `~/.local/bin/stock`:
    
    ```bash
    #!/bin/bash
    cd ~/.local/share/stock-tui
    ./target/release/tmp2 "$@"
    ```
    
    3. Make it executable:
    ```bash
    chmod +x ~/.local/bin/stock
    ```

## Usage

```bash
stock [TICKER]
```

- **[TICKER]**: Optional. The stock symbol to query (e.g., TSLA, AMD, SPY). Defaults to "AAPL".
- **Controls**:
    - `q` or `Esc`: Quit the application.
