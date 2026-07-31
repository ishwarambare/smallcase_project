import os
import django
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta

# Ensure Django is setup if run as a standalone script
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smallcase_project.settings')
django.setup()

from demand_supply.models import DemandSupplyZone

def visualize_zones(symbol, df, title=None):
    """
    Visualizes historical OHLC data with Demand and Supply zones using Plotly.

    GTF Position Rules:
        - Demand zones only shown BELOW current price (proximal_line <= last close)
        - Supply zones only shown ABOVE current price (proximal_line >= last close)

    Args:
        symbol (str): The stock symbol (e.g., 'RELIANCE')
        df (pd.DataFrame): Historical data dataframe containing 'Open', 'High', 'Low', 'Close'.
        title (str): Optional title for the chart.
    """
    if 'Date' in df.columns:
        dates = pd.to_datetime(df['Date'])
    else:
        dates = df.index

    # Current price = last close
    current_price = float(df['Close'].iloc[-1]) if not df.empty else None

    # Create the candlestick chart
    fig = go.Figure(data=[go.Candlestick(
        x=dates,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Candlestick'
    )])

    # Fetch Demand & Supply Zones for this symbol
    zones = DemandSupplyZone.objects.filter(symbol=symbol)

    # Apply GTF position rule
    if current_price is not None:
        # Demand: proximal_line <= current_price (zone is below price)
        demand_zones = zones.filter(zone_type='demand', proximal_line__lte=current_price)
        # Supply: proximal_line >= current_price (zone is above price)
        supply_zones = zones.filter(zone_type='supply', proximal_line__gte=current_price)
    else:
        demand_zones = zones.filter(zone_type='demand')
        supply_zones = zones.filter(zone_type='supply')

    # X-axis range for drawing zones
    start_date = dates.min()
    end_date = dates.max() + timedelta(days=10)  # Extend slightly into the future

    # Add Demand Zones (Green Rectangles)
    for zone in demand_zones:
        fig.add_shape(
            type="rect",
            x0=zone.formed_date if hasattr(zone, 'formed_date') and zone.formed_date else start_date,
            y0=float(zone.distal_line),
            x1=end_date,
            y1=float(zone.proximal_line),
            fillcolor="rgba(16, 185, 129, 0.2)",  # Green with opacity
            line=dict(color="rgba(16, 185, 129, 0.8)", width=1, dash='dash'),
            layer="below"
        )
        # Add annotation for the demand zone
        fig.add_annotation(
            x=end_date,
            y=float(zone.proximal_line),
            text=f"Demand {zone.timeframe}",
            showarrow=False,
            xanchor="left",
            font=dict(color="#10b981", size=10)
        )

    # Add Supply Zones (Red Rectangles)
    for zone in supply_zones:
        fig.add_shape(
            type="rect",
            x0=zone.formed_date if hasattr(zone, 'formed_date') and zone.formed_date else start_date,
            y0=float(zone.proximal_line),
            x1=end_date,
            y1=float(zone.distal_line),
            fillcolor="rgba(239, 68, 68, 0.2)",  # Red with opacity
            line=dict(color="rgba(239, 68, 68, 0.8)", width=1, dash='dash'),
            layer="below"
        )
        # Add annotation for the supply zone
        fig.add_annotation(
            x=end_date,
            y=float(zone.proximal_line),
            text=f"Supply {zone.timeframe}",
            showarrow=False,
            xanchor="left",
            font=dict(color="#ef4444", size=10)
        )

    # Layout settings
    fig.update_layout(
        title=title or f"{symbol} - Demand & Supply Zones",
        yaxis_title="Price",
        xaxis_title="Date",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",  # Use dark theme to match the frontend
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig

def plot_and_show(symbol, df):
    """
    Generates the chart and opens it in the browser.
    """
    fig = visualize_zones(symbol, df)
    fig.show()

def get_html_div(symbol, df):
    """
    Generates the chart and returns the HTML div string to embed in a Django template.
    """
    fig = visualize_zones(symbol, df)
    return fig.to_html(full_html=False, include_plotlyjs='cdn')

if __name__ == '__main__':
    print("This module provides visualization functions for Demand & Supply zones.")
    print("Usage: import visualize; fig = visualize.visualize_zones('RELIANCE', df)")
    print("Requires: pip install plotly pandas")
