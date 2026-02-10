import sys
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mtick
import json
import io
import base64
from datetime import datetime, time, timedelta
import pandas as pd

def fetch_and_plot(ticker_symbol, width=None, height=None):
    try:
        # Fetch data
        ticker = yf.Ticker(ticker_symbol)
        # Get history (1 day, 1 minute interval)
        hist = ticker.history(period="1d", interval="1m")
        
        if hist.empty:
            print(json.dumps({"error": "No data found"}))
            return

        # Timezone Conversion (Fix 14:30 -> 9:30 issue)
        # yfinance usually returns UTC. Convert to Eastern Time.
        if hist.index.tz is not None:
            hist.index = hist.index.tz_convert('America/New_York')
        else:
            hist.index = hist.index.tz_localize('UTC').tz_convert('America/New_York')

        # Determine Previous Close for % Change Calculation
        prev_close = ticker.info.get('previousClose')
        
        if prev_close is None:
            prev_close = hist.iloc[0]['Open']

        # Calculate Stats
        latest = hist.iloc[-1]
        current_price = latest['Close']
        change = current_price - prev_close
        pct_change = (change / prev_close) * 100
        
        stats = {
            "symbol": ticker_symbol.upper(),
            "price": round(current_price, 2),
            "open": round(hist.iloc[0]['Open'], 2),
            "high": round(hist['High'].max(), 2),
            "low": round(hist['Low'].min(), 2),
            "volume": int(hist['Volume'].sum()),
            "change": round(change, 2),
            "pct_change": round(pct_change, 2)
        }

        # Calculate % Change Series
        pct_series = ((hist['Close'] - prev_close) / prev_close) * 100

        # FIX: Convert to naive timestamps in ET to prevent matplotlib from reverting to UTC/System time
        # We assume hist.index has been converted to 'America/New_York' above.
        # Dropping tz info locks the "9:30" face value so plotting uses 9:30 not 14:30.
        hist.index = hist.index.tz_localize(None)

        # Determine Figure Size
        # Adjust heuristic to make chart "taller" and "lower res" feel
        # Using a slightly larger divisor for width/height with lower DPI makes elements relatively bigger
        w_in = 10
        h_in = 5
        if width and height:
            w_in = int(width) / 7.5   
            h_in = int(height) / 3.4  # Adjusted for wider aspect ratio
            
        # Generate Plot (Lower DPI for "smaller resolution" / chunky look)
        plt.figure(figsize=(w_in, h_in), dpi=80)
        
        # Transparent Background
        plt.gcf().patch.set_alpha(0.0)
        plt.gca().patch.set_alpha(0.0)
        
        # Plot Data (Thicker line)
        plt.plot(hist.index, pct_series, color='#4674d7', linewidth=2.5)
        
        # Baseline (Thicker dashed line)
        plt.axhline(0, color='#ABB2BF', linestyle='--', linewidth=2.0)

        # Set X-Axis Limits (9:30 - 16:00 ET)
        market_date = hist.index[0].date()
        
        start_time = datetime.combine(market_date, time(9, 30))
        end_time = datetime.combine(market_date, time(16, 0))
        
        # Ensure limits are also naive
        # start_time/end_time are already naive from datetime.combine

        plt.xlim(start_time, end_time)

        # Style - Remove Title, Thicker/Bigger Text
        # plt.title(...) # Removed
        
        # Axis Tick Styling - Even Bigger text, Normal weight
        plt.tick_params(axis='both', colors='#ABB2BF', labelsize=18, width=0, length=0)
        
        # Y-Axis Percent Format
        plt.gca().yaxis.set_major_formatter(mtick.PercentFormatter(decimals=1))
        
        # Grid and Spines
        plt.grid(True, color='#43454c', linewidth=1.5)
        for spine in plt.gca().spines.values():
            spine.set_visible(False) # Remove border
            
        # Format X-Axis Time
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.xticks(rotation=0)
        # plt.yticks()

        # Layout - tight_layout with padding modification to fill more space ("taller")
        plt.tight_layout(pad=1.5)
        
        # Save to memory buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', transparent=True)
        plt.close()
        
        # Encode to base64
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode('utf-8')
        stats["image_data"] = img_b64

        # Output stats as JSON
        print(json.dumps(stats))

    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    
    w = None
    h = None
    if len(sys.argv) > 3:
        try:
            w = int(sys.argv[2])
            h = int(sys.argv[3])
        except:
            pass
            
    fetch_and_plot(symbol, w, h)
