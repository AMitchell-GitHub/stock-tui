import pandas as pd
import numpy as np

PLOT_TYPE = "separate"
REQUIRES_PRICE = False

def run(ax, df):
    # ADX Calculation parameters
    period = 14
    
    # Calculate True Range (TR)
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    
    # Calculate Directional Movement (+DM, -DM)
    df['+DM'] = np.where((df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']), 
                         np.maximum(df['High'] - df['High'].shift(1), 0), 0)
    df['-DM'] = np.where((df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)), 
                         np.maximum(df['Low'].shift(1) - df['Low'], 0), 0)
    
    # Smooth TR, +DM, -DM (Wilder's Smoothing)
    # First value is simple sum
    # Subsequent values: prev_smoothed - (prev_smoothed/period) + current
    # Pandas ewm with adjust=False and alpha=1/period is widely used as approximation or equivalent for EMA
    # But Wilder's smoothing is slightly different: alpha = 1/period.
    
    alpha = 1/period
    
    # Helper for Wilder's Smoothing
    def wilder_smooth(series, n):
        # Initialize with SMA
        # But standard pandas ewm(alpha=1/n, adjust=False) matches roughly. 
        # Wilder's is specifically: (Prev * (n-1) + Curr) / n  -> Prev * (1 - 1/n) + Curr * (1/n) ? 
        # Wait, Wilder's is: Prev - (Prev/n) + Curr
        return series.ewm(alpha=1/n, adjust=False).mean() * n # ewm mean is weighted average, multiplied by n gives sum-like scale?
        # Actually standard practice often uses straightforward ewm(span=2*n-1) or alpha=1/n.
        # Let's use simple ewm(alpha=1/period, adjust=False)
    
    # Using simple EWM for simplicity and speed, consistent with many implementations
    tr_smooth = df['TR'].ewm(alpha=alpha, adjust=False).mean()
    plus_dm_smooth = df['+DM'].ewm(alpha=alpha, adjust=False).mean()
    minus_dm_smooth = df['-DM'].ewm(alpha=alpha, adjust=False).mean()
    
    # Calculate +DI, -DI
    df['+DI'] = 100 * (plus_dm_smooth / tr_smooth)
    df['-DI'] = 100 * (minus_dm_smooth / tr_smooth)
    
    # Calculate DX
    df['DX'] = 100 * abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI'])
    
    # Calculate ADX (Smooth DX)
    df['ADX'] = df['DX'].ewm(alpha=alpha, adjust=False).mean()
    
    # Plot
    ax.plot(df.index, df['ADX'], label='ADX', color='#e5c07b', linewidth=1.5)
    ax.plot(df.index, df['+DI'], label='+DI', color='#98c379', linewidth=1.0, alpha=0.8)
    ax.plot(df.index, df['-DI'], label='-DI', color='#e06c75', linewidth=1.0, alpha=0.8)
    
    ax.axhline(25, color='#ABB2BF', linestyle='--', linewidth=0.5, alpha=0.5)
    
    ax.legend(loc='upper left', fontsize='small', frameon=False, labelcolor='#ABB2BF')
    ax.grid(True, color='#43454c', linewidth=0.5, alpha=0.5)
    
    # Styling
    ax.tick_params(axis='both', colors='#ABB2BF', labelsize=12)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.patch.set_alpha(0.0)
