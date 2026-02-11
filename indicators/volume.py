import pandas as pd
import matplotlib.pyplot as plt

PLOT_TYPE = "overlay"
REQUIRES_PRICE = False

def run(ax, df):
    # Calculate dynamic width
    if len(df) > 1:
        width = (df.index[1] - df.index[0]).total_seconds() / 86400.0 * 0.8
    else:
        width = 0.0005

    # Create twin axis for volume
    vol_ax = ax.twinx()
    
    # Determine colors
    vol_colors = ['#98c379' if c >= o else '#e06c75' for c, o in zip(df['Close'], df['Open'])]
    
    # Plot volume bars
    vol_ax.bar(df.index, df['Volume'], color=vol_colors, alpha=0.3, width=width, zorder=1)
    
    # Scale volume to bottom 20%
    if not df['Volume'].empty:
        vol_max = df['Volume'].max()
        vol_ax.set_ylim(0, vol_max * 5)
    
    vol_ax.axis('off')
    vol_ax.grid(False)
