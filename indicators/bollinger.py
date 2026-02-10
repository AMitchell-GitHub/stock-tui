import pandas as pd

PLOT_TYPE = "overlay"
REQUIRES_PRICE = True

def run(ax, df):
    # Calculate Bollinger Bands
    window = 20
    no_of_std = 2
    
    rolling_mean = df['Close'].rolling(window).mean()
    rolling_std = df['Close'].rolling(window).std()
    
    upper_band = rolling_mean + (rolling_std * no_of_std)
    lower_band = rolling_mean - (rolling_std * no_of_std)
    
    # Plot
    ax.plot(df.index, upper_band, label='Upper BB', color='#d19a66', linestyle='--', linewidth=1, alpha=0.7)
    ax.plot(df.index, lower_band, label='Lower BB', color='#d19a66', linestyle='--', linewidth=1, alpha=0.7)
    ax.fill_between(df.index, upper_band, lower_band, color='#d19a66', alpha=0.1)
