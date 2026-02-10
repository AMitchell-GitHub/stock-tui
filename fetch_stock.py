import sys
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mtick
import json
import io
import base64
import importlib
from datetime import datetime, time, timedelta
import pandas as pd
import numpy as np

def fetch_and_plot(ticker_symbol, width=None, height=None, active_indicators=None, time_format="24h", chart_mode="default"):
    if active_indicators is None:
        active_indicators = []

    try:
        # Fetch data
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="5d", interval="1m")
        
        if hist.empty:
            print(json.dumps({"error": "No data found"}))
            return

        if hist.index.tz is not None:
            hist.index = hist.index.tz_convert('America/New_York')
        else:
            hist.index = hist.index.tz_localize('UTC').tz_convert('America/New_York')

        prev_close = ticker.info.get('previousClose')
        if prev_close is None:
            last_date = hist.index[-1].date()
            prior_days = hist[hist.index.date < last_date]
            if not prior_days.empty:
                prev_close = prior_days.iloc[-1]['Close']
            else:
                prev_close = hist.iloc[0]['Open']

        latest = hist.iloc[-1]
        current_price = latest['Close']
        change = current_price - prev_close
        pct_change = (change / prev_close) * 100
        
        last_date = hist.index[-1].date()
        today_data = hist[hist.index.date == last_date]

        stats = {
            "symbol": ticker_symbol.upper(),
            "price": round(current_price, 2),
            "open": round(today_data.iloc[0]['Open'], 2),
            "high": round(today_data['High'].max(), 2),
            "low": round(today_data['Low'].min(), 2),
            "volume": int(today_data['Volume'].sum()),
            "change": round(change, 2),
            "pct_change": round(pct_change, 2)
        }

        hist.index = hist.index.tz_localize(None)
        today_data = hist[hist.index.date == last_date]

        loaded_indicators = []
        separate_plots = 0
        for name in active_indicators:
            try:
                module = importlib.import_module(f"indicators.{name}")
                plot_type = getattr(module, "PLOT_TYPE", "overlay")
                if plot_type == "separate":
                    separate_plots += 1
                loaded_indicators.append((module, plot_type))
            except Exception as e:
                sys.stderr.write(f"Failed to load indicator {name}: {e}\n")

        w_in = 10
        h_in = 5
        if width and height:
            w_in = int(width) / 7.5   
            h_in = int(height) / 3.4

        total_rows = 1 + separate_plots
        # Make main chart larger than separate indicators (3:1 ratio)
        ratios = [3] + [1] * separate_plots
        
        fig, axes = plt.subplots(total_rows, 1, figsize=(w_in, h_in), dpi=80, 
                                 gridspec_kw={'height_ratios': ratios}, sharex=True)
        
        if total_rows == 1:
            axes = [axes]
        
        main_ax = axes[0]

        plot_price = False
        if chart_mode == "price":
            plot_price = True
        elif chart_mode == "percent":
            plot_price = False
        else:
            plot_price = len(active_indicators) > 0
        
        fig.patch.set_alpha(0.0)
        for ax in axes:
            ax.patch.set_alpha(0.0)
        
        if plot_price:
            main_ax.plot(today_data.index, today_data['Close'], color='#4674d7', linewidth=2.0, label='Price')
            main_ax.axhline(prev_close, color='#ABB2BF', linestyle='--', linewidth=1.0, alpha=0.5, label='Prev Close')
        else:
            pct_series = ((today_data['Close'] - prev_close) / prev_close) * 100
            main_ax.plot(today_data.index, pct_series, color='#4674d7', linewidth=2.5)
            main_ax.axhline(0, color='#ABB2BF', linestyle='--', linewidth=2.0)
            main_ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=1))

        start_time = datetime.combine(last_date, time(9, 30))
        end_time = datetime.combine(last_date, time(16, 0))
        main_ax.set_xlim(start_time, end_time)

        # Style Main Axis
        main_ax.tick_params(axis='both', colors='#ABB2BF', labelsize=14, width=0, length=0)
        main_ax.grid(True, color='#43454c', linewidth=0.5)
        for spine in main_ax.spines.values():
            spine.set_visible(False)

        # Execute Indicators and track overlay values for Y-axis scaling
        overlay_vals = []
        if plot_price:
            overlay_vals.extend(today_data['Close'].values)
        else:
            overlay_vals.extend(((today_data['Close'] - prev_close) / prev_close * 100).values)

        separate_idx = 1
        for module, plot_type in loaded_indicators:
            try:
                if plot_type == "overlay":
                    # For scaling, we need to know what the indicator is plotting.
                    # We'll capture the data before calling run if possible, 
                    # but simple run() is what the API is.
                    # To fix scaling, we'll manually calculate bounds or let matplotlib handle it,
                    # but we need to ensure it only scales based on the VISIBLE data.
                    module.run(main_ax, hist)
                elif plot_type == "separate":
                    target_ax = axes[separate_idx]
                    module.run(target_ax, hist)
                    separate_idx += 1
            except Exception as e:
                sys.stderr.write(f"Error running indicator: {e}\n")

        # FIX SCALING: Iterate through all axes and lines to find the min/max Y for the VISIBLE X-range
        # This handles indicators that plotted 5 days of data.
        
        # Convert limits to matplotlib date nums
        x_min_num = mdates.date2num(start_time)
        x_max_num = mdates.date2num(end_time)

        for ax in axes:
            visible_y_values = []
            for line in ax.get_lines():
                x_data = line.get_xdata()
                y_data = line.get_ydata()
                
                # Convert x_data to numpy array
                x_data = np.array(x_data)
                y_data = np.array(y_data)
                
                # If x_data is datetime-like (common with pandas plots), convert to mdates float
                if np.issubdtype(x_data.dtype, np.datetime64) or np.issubdtype(x_data.dtype, np.object_):
                    try:
                        x_data = mdates.date2num(x_data)
                    except:
                        pass

                mask = (x_data >= x_min_num) & (x_data <= x_max_num)
                if np.any(mask):
                    visible_y_values.extend(y_data[mask])
            
            # Check for bars/collections (like MACD histogram)
            for collection in ax.collections:
                # get_offsets returns (x, y) pairs
                offsets = collection.get_offsets()
                if len(offsets) > 0:
                    x_data = offsets[:, 0]
                    y_data = offsets[:, 1]
                    
                    # Convert if necessary (though usually offsets are already float)
                    if np.issubdtype(x_data.dtype, np.datetime64) or np.issubdtype(x_data.dtype, np.object_):
                         try:
                            x_data = mdates.date2num(x_data)
                         except:
                            pass
                    
                    mask = (x_data >= x_min_num) & (x_data <= x_max_num)
                    if np.any(mask):
                        visible_y_values.extend(y_data[mask])
            
            # Also check for patches (bar plots often use patches or collections)
            # Standard ax.bar creates Patches, but modern mpl might use collections.
            # If standard patches, we might need ax.patches. 
            # However, MACD implementation uses ax.bar which usually creates rectangles.
            # Iterate patches is complex because x is start, not center often.
            # Let's assume most indicators use lines or collections. 
            # For MACD histogram: ax.bar returns a BarContainer of Rectangle patches.
            for patch in ax.patches:
                # Rectangle(xy=(x, y), width, height)
                # We need to see if the patch is in range.
                if hasattr(patch, 'get_x') and hasattr(patch, 'get_height'):
                    x = patch.get_x() + patch.get_width() / 2 # Center
                    # If x is datetime, convert.
                    # Usually patches store float coordinates in mpl.
                    
                    if x >= x_min_num and x <= x_max_num:
                        # For bar, we care about top and bottom (if non-zero start)
                        # usually bottom=0 for MACD
                        y_top = patch.get_y() + patch.get_height()
                        y_bottom = patch.get_y()
                        visible_y_values.append(y_top)
                        visible_y_values.append(y_bottom)

            # If we found any visible data, set the limits
            if visible_y_values:
                y_min = np.nanmin(visible_y_values)
                y_max = np.nanmax(visible_y_values)
                
                # Add a small padding (e.g. 5%)
                y_range = y_max - y_min
                if y_range == 0:
                    y_range = abs(y_max) * 0.02 if y_max != 0 else 1.0 # fallback padding
                
                pad = y_range * 0.05
                ax.set_ylim(y_min - pad, y_max + pad)
            else:
                # Fallback
                ax.relim()
                ax.autoscale_view(scalex=False, scaley=True)

        # Format X-Axis Time
        time_fmt_str = '%H:%M' if time_format == '24h' else '%I:%M %p'
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter(time_fmt_str))
        plt.xticks(rotation=0)

        for ax in axes[:-1]:
            plt.setp(ax.get_xticklabels(), visible=False)

        plt.tight_layout(pad=1.0)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', transparent=True)
        plt.close(fig)
        
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode('utf-8')
        stats["image_data"] = img_b64

        print(json.dumps(stats))

    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    w = int(sys.argv[2]) if len(sys.argv) > 2 else None
    h = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    indicators = []
    if len(sys.argv) > 4:
        raw_inds = sys.argv[4]
        if raw_inds and raw_inds != "None":
            indicators = [i.strip() for i in raw_inds.split(',')]
            
    time_format = sys.argv[5] if len(sys.argv) > 5 else "24h"
    chart_mode = sys.argv[6] if len(sys.argv) > 6 else "default"

    fetch_and_plot(symbol, w, h, indicators, time_format, chart_mode)
