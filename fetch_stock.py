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

def get_extended_period(period, interval):
    periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]
    
    if period == "ytd":
        return "2y" 
    if period == "max":
        return "max"
        
    try:
        idx = periods.index(period)
    except ValueError:
        return period
        
    limit_days = 99999
    if interval == "1m":
        limit_days = 7
    elif interval.endswith("m"): 
        limit_days = 60
    elif interval == "1h":
        limit_days = 730
        
    p_days = {
        "1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, 
        "1y": 365, "2y": 730, "5y": 1825, "10y": 3650, "max": 99999
    }
    
    target_idx = idx + 2 
    if target_idx >= len(periods):
        target_idx = len(periods) - 1
        
    while target_idx > idx:
        cand = periods[target_idx]
        d = p_days.get(cand, 99999)
        if d <= limit_days:
            return cand
        target_idx -= 1
        
    return period

def get_period_timedelta(period):
    if period == "1d": return timedelta(days=1)
    if period == "5d": return timedelta(days=5)
    if period == "1wk": return timedelta(weeks=1)
    if period == "1mo": return timedelta(days=30)
    if period == "3mo": return timedelta(days=90)
    if period == "6mo": return timedelta(days=180)
    if period == "1y": return timedelta(days=365)
    if period == "2y": return timedelta(days=365*2)
    if period == "5y": return timedelta(days=365*5)
    if period == "10y": return timedelta(days=365*10)
    return None

def fetch_and_plot(ticker_symbol, width=None, height=None, active_indicators=None, time_format="24h", chart_mode="default", period="1d", interval="1m", graph_type="line"):
    if active_indicators is None:
        active_indicators = []

    try:
        # Fetch data with extended period
        fetch_period = get_extended_period(period, interval)
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period=fetch_period, interval=interval)
        
        if hist.empty:
            print(json.dumps({"error": "No data found"}))
            return

        if hist.index.tz is not None:
            # Convert to NY if possible
            hist.index = hist.index.tz_convert('America/New_York')
        else:
            # If interval indicates intraday, assume UTC and convert, otherwise leave naive or assume local
            if interval.endswith('m') or interval.endswith('h'):
                hist.index = hist.index.tz_localize('UTC').tz_convert('America/New_York')
            else:
                pass

        prev_close = ticker.info.get('previousClose')
        if prev_close is None:
            if len(hist) > 1:
                if interval.endswith('m') or interval.endswith('h'):
                    last_date = hist.index[-1].date()
                    prior_days = hist[hist.index.date < last_date]
                    if not prior_days.empty:
                        prev_close = prior_days.iloc[-1]['Close']
                    else:
                        prev_close = hist.iloc[0]['Open']
                else:
                    if len(hist) >= 2:
                        prev_close = hist.iloc[-2]['Close']
                    else:
                        prev_close = hist.iloc[0]['Open']
            else:
                prev_close = hist.iloc[0]['Open']

        latest = hist.iloc[-1]
        current_price = latest['Close']
        change = current_price - prev_close
        pct_change = (change / prev_close) * 100
        
        last_date = hist.index[-1].date()
        if interval.endswith('m') or interval.endswith('h'):
            today_data_stats = hist[hist.index.date == last_date]
        else:
            today_data_stats = hist.iloc[[-1]] 

        stats = {
            "symbol": ticker_symbol.upper(),
            "price": round(current_price, 2),
            "open": round(today_data_stats.iloc[0]['Open'], 2) if not today_data_stats.empty else 0,
            "high": round(today_data_stats['High'].max(), 2) if not today_data_stats.empty else 0,
            "low": round(today_data_stats['Low'].min(), 2) if not today_data_stats.empty else 0,
            "volume": int(today_data_stats['Volume'].sum()) if not today_data_stats.empty else 0,
            "change": round(change, 2),
            "pct_change": round(pct_change, 2)
        }

        # Prepare Plot Data
        hist.index = hist.index.tz_localize(None)
        plot_data = hist
        
        # Calculate View Limits (Naive times)
        view_end = hist.index[-1]
        view_start = hist.index[0] # Default to full history
        
        if period == "1d":
            # 1d handled specifically later for xlims
            view_start = view_end # placeholder
        elif period == "ytd":
             year_start = datetime(view_end.year, 1, 1)
             view_start = year_start
        elif period == "max":
             view_start = hist.index[0]
        else:
             delta = get_period_timedelta(period)
             if delta:
                 view_start = view_end - delta
                 
        # Ensure view_start is within data bounds (if we have data)
        if view_start < hist.index[0]:
            view_start = hist.index[0]

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
        ratios = [3] + [1] * separate_plots
        
        fig, axes = plt.subplots(total_rows, 1, figsize=(w_in, h_in), dpi=80, 
                                 gridspec_kw={'height_ratios': ratios}, sharex=True)
        
        if total_rows == 1:
            axes = [axes]
        
        main_ax = axes[0]

        plot_price = False
        if chart_mode == "price" or graph_type == "candle":
            plot_price = True
        elif chart_mode == "percent":
            plot_price = False
        else:
            plot_price = len(active_indicators) > 0
        
        fig.patch.set_alpha(0.0)
        for ax in axes:
            ax.patch.set_alpha(0.0)
        
        # Calculate chart baseline based on view_start
        if period == "1d":
            chart_baseline = prev_close
        else:
            # Find closest price to view_start
            # Filter plot_data for >= view_start
            view_data = plot_data[plot_data.index >= view_start]
            if not view_data.empty:
                chart_baseline = view_data.iloc[0]['Close']
            else:
                chart_baseline = prev_close

        # Calculate dynamic width for candles and volume
        if len(plot_data) > 1:
            width = (plot_data.index[1] - plot_data.index[0]).total_seconds() / 86400.0 * 0.8
        else:
            width = 0.0005

        if graph_type == "candle":
            up = plot_data[plot_data.Close >= plot_data.Open]
            down = plot_data[plot_data.Close < plot_data.Open]

            # Up candles (Green)
            main_ax.bar(up.index, up.Close - up.Open, bottom=up.Open, color='#98c379', width=width, zorder=2)
            main_ax.vlines(up.index, up.Low, up.High, color='#98c379', linewidth=1, zorder=2)

            # Down candles (Red)
            # height is negative if Close < Open, which is fine, or we can normalize
            main_ax.bar(down.index, down.Close - down.Open, bottom=down.Open, color='#e06c75', width=width, zorder=2)
            main_ax.vlines(down.index, down.Low, down.High, color='#e06c75', linewidth=1, zorder=2)
            
            if period == "1d":
                main_ax.axhline(prev_close, color='#ABB2BF', linestyle='--', linewidth=1.0, alpha=0.5, label='Prev Close', zorder=2)

        elif plot_price:
            main_ax.plot(plot_data.index, plot_data['Close'], color='#4674d7', linewidth=2.0, label='Price', zorder=2)
            if period == "1d":
                main_ax.axhline(prev_close, color='#ABB2BF', linestyle='--', linewidth=1.0, alpha=0.5, label='Prev Close', zorder=2)
        else:
            pct_series = ((plot_data['Close'] - chart_baseline) / chart_baseline) * 100
            main_ax.plot(plot_data.index, pct_series, color='#4674d7', linewidth=2.5, zorder=2)
            main_ax.axhline(0, color='#ABB2BF', linestyle='--', linewidth=2.0, zorder=2)
            main_ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=1))

        # Date Formatting and Limits
        if period == "1d":
            start_time = datetime.combine(last_date, time(9, 30))
            end_time = datetime.combine(last_date, time(16, 0))
            main_ax.set_xlim(start_time, end_time)
            
            time_fmt_str = '%H:%M' if time_format == '24h' else '%I:%M %p'
            axes[-1].xaxis.set_major_formatter(mdates.DateFormatter(time_fmt_str))
        else:
            # Explicitly set xlim for other periods to hide the fetched history extension
            main_ax.set_xlim(view_start, view_end)
            
            if period == "5d":
                time_fmt_str = '%a %H:%M' if time_format == '24h' else '%a %I:%M %p'
                axes[-1].xaxis.set_major_formatter(mdates.DateFormatter(time_fmt_str))
            elif period == "1wk" or period == "1mo":
                 if interval.endswith('m') or interval.endswith('h'):
                     axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b %d %H:%M'))
                 else:
                     axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
            elif period == "6mo" or period == "1y" or period == "ytd":
                 axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
            elif period == "5y" or period == "max":
                 axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
            else:
                 axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

        # Style Main Axis
        main_ax.tick_params(axis='both', colors='#ABB2BF', labelsize=16, width=0, length=0)
        main_ax.grid(True, color='#43454c', linewidth=0.5)
        for spine in main_ax.spines.values():
            spine.set_visible(False)
        
        # Execute Indicators
        separate_idx = 1
        for module, plot_type in loaded_indicators:
            try:
                if plot_type == "overlay":
                    module.run(main_ax, hist)
                elif plot_type == "separate":
                    target_ax = axes[separate_idx]
                    module.run(target_ax, hist)
                    separate_idx += 1
            except Exception as e:
                sys.stderr.write(f"Error running indicator: {e}\n")

        # Handle Y-Scaling
        # Use the manual visible calculation for all periods to ensure scaling matches view
        # main_ax.get_xlim() returns floats (dates converted to numbers), no need for date2num
        x_min_num = main_ax.get_xlim()[0]
        x_max_num = main_ax.get_xlim()[1]

        for ax in axes:
            visible_y_values = []
            
            # 1. Lines (plot)
            for line in ax.get_lines():
                x_data = line.get_xdata()
                y_data = line.get_ydata()
                
                x_data = np.array(x_data)
                y_data = np.array(y_data)
                
                if np.issubdtype(x_data.dtype, np.datetime64) or np.issubdtype(x_data.dtype, np.object_):
                    try:
                        x_data = mdates.date2num(x_data)
                    except:
                        pass

                mask = (x_data >= x_min_num) & (x_data <= x_max_num)
                # Handle possible NaNs in y_data
                valid_y = y_data[mask]
                visible_y_values.extend(valid_y[np.isfinite(valid_y)])
            
            # 2. Collections (scatter, fill_between)
            for collection in ax.collections:
                # fill_between uses paths, get_offsets might be empty or partial
                # But for standard scatter it works. For fill_between it's harder to inspect directly 
                # without iterating paths. However, usually lines (upper/lower band) cover the extent.
                offsets = collection.get_offsets()
                if len(offsets) > 0:
                        x_data = offsets[:, 0]
                        y_data = offsets[:, 1]
                        if np.issubdtype(x_data.dtype, np.datetime64) or np.issubdtype(x_data.dtype, np.object_):
                            try:
                                x_data = mdates.date2num(x_data)
                            except:
                                pass
                        mask = (x_data >= x_min_num) & (x_data <= x_max_num)
                        valid_y = y_data[mask]
                        visible_y_values.extend(valid_y[np.isfinite(valid_y)])
            
            # 3. Patches (bars for MACD)
            for p in ax.patches:
                # Patches x might be center or left edge.
                # Assuming simple Rectangles
                px = p.get_x()
                pw = p.get_width()
                # Check if any part of the bar is in view
                if (px + pw >= x_min_num) and (px <= x_max_num):
                    py = p.get_y()
                    ph = p.get_height()
                    visible_y_values.append(py)
                    visible_y_values.append(py + ph)

            if visible_y_values:
                y_min = np.nanmin(visible_y_values)
                y_max = np.nanmax(visible_y_values)
                y_range = y_max - y_min
                if y_range == 0:
                    y_range = abs(y_max) * 0.02 if y_max != 0 else 1.0
                pad = y_range * 0.05
                ax.set_ylim(y_min - pad, y_max + pad) 

        for ax in axes[:-1]:
            plt.setp(ax.get_xticklabels(), visible=False)
        
        plt.setp(axes[-1].get_xticklabels(), rotation=0, ha='center') 
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
    
    period = sys.argv[7] if len(sys.argv) > 7 else "1d"
    interval = sys.argv[8] if len(sys.argv) > 8 else "1m"
    graph_type = sys.argv[9] if len(sys.argv) > 9 else "line"

    fetch_and_plot(symbol, w, h, indicators, time_format, chart_mode, period, interval, graph_type)
