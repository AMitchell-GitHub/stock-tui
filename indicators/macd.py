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
    ax.bar(df.index, histogram, color=colors, alpha=0.5, width=0.0005) # width depends on time scale
    
    ax.axhline(0, color='#ABB2BF', linestyle='--', linewidth=1.0, alpha=0.5)
    ax.legend(loc='upper left', fontsize='small', frameon=False, labelcolor='#ABB2BF')
    ax.grid(True, color='#43454c', linewidth=0.5, alpha=0.5)
    
    # Clean up styles to match main chart
    ax.tick_params(axis='both', colors='#ABB2BF', labelsize=12)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.patch.set_alpha(0.0)
