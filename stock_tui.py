import sys
import argparse
import time
import datetime
import pytz
import logging
import yfinance as yf
import plotext as plt
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.console import Console
from rich import box

# Silence yfinance spam
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

def fetch_data(ticker_symbol):
    """Fetches intraday data for the given ticker."""
    ticker = yf.Ticker(ticker_symbol)
    
    # Check if ticker is valid by trying to fetch simple info
    try:
        fast = ticker.fast_info
        current_price = fast['last_price']
        previous_close = fast['previous_close']
        open_price = fast['open']
        day_high = fast['day_high']
        day_low = fast['day_low']
        # Volume might need fallback
        # fast_info doesn't always have 'volume', it has 'last_volume' sometimes or we use history
        # Let's try to get it, or default to 0
        # actually 'last_volume' property usually exists
        try:
             volume = fast['last_volume']
        except:
             volume = 0
             
        change_percent = ((current_price - previous_close) / previous_close) * 100
    except Exception:
        current_price = 0.0
        change_percent = 0.0
        open_price = 0.0
        previous_close = 0.0
        day_high = 0.0
        day_low = 0.0
        volume = 0

    # Get intraday history for the chart (include pre/post market)
    try:
        # Request prepost=True to get 4:00 AM data
        history = ticker.history(period='1d', interval='1m', prepost=True)
        # If fast_info volume failed, try to sum history volume? 
        # Or just take last bar? No, we want day volume.
        if volume == 0 and history is not None and not history.empty:
            volume = history['Volume'].sum()
    except Exception:
        history = None

    return {
        'price': current_price,
        'change_percent': change_percent,
        'open_price': open_price,
        'day_high': day_high,
        'day_low': day_low,
        'volume': volume,
        'previous_close': previous_close,
        'history': history,
        'currency': ticker.fast_info.get('currency', 'USD'),
        'symbol': ticker_symbol.upper()
    }

def create_chart(history, previous_close, height, width=None):
    """Generates a plotext chart string."""
    if history is None or history.empty:
        return "No Data Available - Invalid Ticker or Market Closed"

    plt.clf()
    plt.plotsize(width, height)
    # Use 'clear' theme to remove background and match terminal
    plt.theme('clear')
    plt.title("Intraday Return % (vs Prev Close)")
    
    # Convert to US/Eastern
    try:
        if history.index.tz is None:
             history.index = history.index.tz_localize('UTC')
        history_eastern = history.index.tz_convert('US/Eastern')
    except Exception:
        history_eastern = history.index

    # X-axis: Minutes from midnight
    # 04:00 = 240
    # 09:30 = 570
    # 16:00 = 960
    x_values = [t.hour * 60 + t.minute for t in history_eastern]
    prices = history['Close'].tolist()
    
    # Calculate Percentage Change from Previous Close
    if previous_close == 0:
        # Fallback to first price if prev close missing?
        # But user explicitly asked for prev close.
        # If 0, avoid div by zero.
        pct_changes = [0.0] * len(prices)
    else:
        pct_changes = [((p - previous_close) / previous_close) * 100 for p in prices]
    
    # Determine color relative to 0% (which represents Previous Close)
    current_pct = pct_changes[-1] if pct_changes else 0.0
    line_color = "green" if current_pct >= 0 else "red"
    
    # Determine color relative to 0% (which represents Previous Close)
    current_pct = pct_changes[-1] if pct_changes else 0.0
    line_color = "green" if current_pct >= 0 else "red"
    
    # Plot baseline at 0% across the full width (04:00 to 16:00)
    # Using 2 points is sufficient for a straight line
    plt.plot([240, 960], [0.0, 0.0], marker=None, color="gray")
    
    # Plot percentage change line
    # Removing marker="." enables standard line mode which uses braille characters
    # This effectively increases resolution (2x4 sub-pixels per char)
    plt.plot(x_values, pct_changes, color=line_color) # No marker = High Res Line
    
    # Force Y-axis to include 0
    # Calculate current min/max
    if pct_changes:
        y_min = min(pct_changes)
        y_max = max(pct_changes)
        # Extend range to include 0
        y_min = min(y_min, 0)
        y_max = max(y_max, 0)
        # Apply ylim
        plt.ylim(y_min, y_max)
    
    # Enforce trading limits including pre-market (04:00 AM to 4:00 PM)
    plt.xlim(240, 960)
    
    # Ticks adjustment
    xticks = [240, 360, 480, 570, 660, 780, 900, 960]
    xlabels = ["04:00", "06:00", "08:00", "09:30", "11:00", "13:00", "15:00", "16:00"]
    plt.xticks(xticks, xlabels)
    
    return plt.build()

def make_layout(data, console_width, console_height):
    """Creates the Rich layout."""
    
    symbol = data['symbol']
    price = data['price']
    
    if price == 0 and (data['history'] is None or data['history'].empty):
        header_text = Text(f"{symbol}: Invalid Ticker or Data Unavailable", style="bold red")
        chart_content = Text("Please check the ticker symbol.", style="red")
    else:
        change = data['change_percent']
        color = "green" if change >= 0 else "red"
        icon = "▲" if change >= 0 else "▼"
        
        # Format Volume helper
        vol = data['volume']
        if vol >= 1_000_000:
            vol_str = f"{vol/1_000_000:.2f}M"
        elif vol >= 1_000:
            vol_str = f"{vol/1_000:.2f}K"
        else:
            vol_str = str(vol)
        
        header_text = Text()
        header_text.append(f"{symbol} ", style="bold white")
        header_text.append(f"{price:.2f} {data['currency']}", style="bold white")
        header_text.append(f" {icon} {abs(change):.2f}%", style=f"bold {color}")
        
        # Add OHLCV
        ohlcv_style = "dim white"
        header_text.append(" | ", style=ohlcv_style)
        header_text.append(f"O: {data['open_price']:.2f} ", style=ohlcv_style)
        header_text.append(f"H: {data['day_high']:.2f} ", style=ohlcv_style)
        header_text.append(f"L: {data['day_low']:.2f} ", style=ohlcv_style)
        header_text.append(f"Vol: {vol_str}", style=ohlcv_style)
        
        chart_height = console_height - 5
        if chart_height < 5:
            chart_height = 5
            
        chart_width = console_width - 4
        if chart_width < 20: 
            chart_width = 20
        
        baseline = data['previous_close'] if data['previous_close'] != 0 else data['open_price']
        
        chart_str = create_chart(data['history'], baseline, chart_height, width=chart_width)
        
        chart_content = Text.from_ansi(chart_str)

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body")
    )
    
    layout["header"].update(Panel(header_text, title="Stock Tracker", border_style="blue", box=box.ROUNDED))
    layout["body"].update(Panel(chart_content, title="Live Chart", border_style="blue", box=box.ROUNDED))
    
    return layout

def main():
    parser = argparse.ArgumentParser(description="Stock TUI Tracker")
    parser.add_argument("ticker", type=str, help="Stock ticker symbol (e.g., AAPL)")
    args = parser.parse_args()

    console = Console()
    console.show_cursor(False)
    
    # Refresh intervals
    FETCH_INTERVAL = 10 # Seconds between data fetches
    
    last_fetch_time = 0
    data = {"symbol": args.ticker.upper(), "price": 0, "change_percent": 0, "open_price": 0, "day_high": 0, "day_low": 0, "volume": 0, "previous_close": 0, "history": None, "currency": "USD"}
    
    try:
        with Live(console=console, screen=True, refresh_per_second=1) as live:
            while True:
                current_time = time.time()
                
                # Fetch data if interval passed
                if current_time - last_fetch_time >= FETCH_INTERVAL:
                    try:
                        new_data = fetch_data(args.ticker)
                        data = new_data
                        last_fetch_time = current_time
                    except Exception as e:
                        # Keep old data on transient error
                        pass
                
                # Render (no countdown needed)
                layout = make_layout(data, console.width, console.height)
                live.update(layout)
                
                time.sleep(1) # Fast UI refresh rate for responsiveness to resize
                
    except KeyboardInterrupt:
        pass
    finally:
        console.show_cursor(True)

if __name__ == "__main__":
    main()
