import pandas as pd
import matplotlib.pyplot as plt

PLOT_TYPE = "separate"
REQUIRES_PRICE = False

def run(ax, df):
    # Calculate MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    
    # Plot
    # We ignore x-axis labels for the sub-chart usually, or share x-axis
    ax.plot(df.index, macd, label='MACD', color='#61afef', linewidth=1.5)
    ax.plot(df.index, signal, label='Signal', color='#e06c75', linewidth=1.5)
    
    # Histogram colors
    colors = ['#98c379' if v >= 0 else '#e06c75' for v in histogram]
    
    # Calculate dynamic width
    if len(df) > 1:
        # Calculate min diff to be safe against gaps
        # diffs = df.index.to_series().diff().dt.total_seconds().dropna()
        # width_days = diffs.min() / 86400.0 * 0.8
        # Simple approach:
        width = (df.index[1] - df.index[0]).total_seconds() / 86400.0 * 0.8
    else:
        width = 0.0005 # Fallback

    ax.bar(df.index, histogram, color=colors, alpha=0.5, width=width)
    
    ax.axhline(0, color='#ABB2BF', linestyle='--', linewidth=1.0, alpha=0.5)
    ax.legend(loc='upper left', fontsize='small', frameon=False, labelcolor='#ABB2BF')
    ax.grid(True, color='#43454c', linewidth=0.5, alpha=0.5)
    
    # Clean up styles to match main chart
    ax.tick_params(axis='both', colors='#ABB2BF', labelsize=12)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.patch.set_alpha(0.0)
