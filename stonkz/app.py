import os
import tkinter as tk
from tkinter import simpledialog, messagebox
from ttkbootstrap import Style
from tkinter import ttk
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import sqlite3
import threading
import time
import discord
from discord.ext import commands
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import numpy as np
import datetime
import subprocess
from dotenv import load_dotenv
import io

# Load environment variables from .env file in the parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Function to send Discord message with image from buffer
def send_discord_alert_with_image(alert_message, image_buffer):
    async def send_message():
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            image_buffer.seek(0)
            await channel.send(alert_message, file=discord.File(fp=image_buffer, filename="chart.png"))
    bot.loop.create_task(send_message())

# Function to generate a 1-month custom chart with real-time data
def generate_1month_chart_with_realtime(ticker):
    try:
        # Fetch 1 month of historical daily data
        stock = yf.Ticker(ticker)
        data = stock.history(period="1mo", interval="1d")
        
        if (data.empty):
            raise ValueError("No data available for the given ticker.")

        # Fetch real-time data for the current day (minute-by-minute)
        real_time_data = stock.history(period="1d", interval="1m")
        
        if not real_time_data.empty:
            # Get the latest price
            current_time = real_time_data.index[-1]
            current_price = real_time_data["Close"].iloc[-1]

            # Append the real-time data (last price of the day) to the historical data
            data.loc[current_time] = {"Close": current_price, "Open": None, "High": None, "Low": None, "Volume": None}

        # Set dark mode style
        plt.style.use("dark_background")

        # Create figure and axis (smaller size)
        fig, ax = plt.subplots(figsize=(5, 2.5))

        # Plot only the price line
        ax.plot(data.index, data['Close'], color="#00FFCC", linewidth=1.5)

        # Remove all unnecessary elements
        ax.axis('off')

        # Save the chart to an in-memory buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format="png", bbox_inches="tight", dpi=100, pad_inches=0)
        plt.close(fig)
        print(f"Chart for {ticker} generated successfully.")
        return buffer

    except Exception as e:
        print(f"Error generating chart for {ticker}: {e}")
        return None

# Database setup
def init_db():
    conn = sqlite3.connect('tickers.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT UNIQUE NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def get_tickers_from_db():
    conn = sqlite3.connect('tickers.db')
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM tickers")
    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tickers

def push_to_github():
    """Push changes to the GitHub repository."""
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Update ticker list"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("Changes pushed to GitHub successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error pushing changes to GitHub: {e}")

def add_ticker_to_db(ticker):
    if ticker:
        conn = sqlite3.connect('tickers.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO tickers (ticker) VALUES (?)", (ticker,))
        conn.commit()
        conn.close()
        tickers.append(ticker)
        update_list()
        push_to_github()  # Push changes to GitHub

def remove_ticker_from_db(ticker):
    if ticker:
        conn = sqlite3.connect('tickers.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tickers WHERE ticker = ?", (ticker,))
        conn.commit()
        conn.close()
        tickers.remove(ticker)
        update_list()
        push_to_github()  # Push changes to GitHub

def calculate_custom_momentum(data, period=10, wma_period=10, threshold=1.18):
    close = data['Close']
    
    # Calculate 10-period average and standard deviation
    avg_close = close.rolling(window=period).mean()
    stdev_close = close.rolling(window=period).std()
    
    # Z-score calculation
    z_score = (close - avg_close) / stdev_close
    
    # Weighted Moving Average (WMA) of Z-score
    weights = np.arange(1, wma_period + 1)
    wma = z_score.rolling(window=wma_period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
    
    return wma.iloc[-1] > threshold

# Dictionary to store sent alerts for the current day
sent_alerts = {}

# Function to check if today is a market day (Monday to Friday)
def is_market_day(date):
    return date.weekday() < 5  # Monday is 0 and Friday is 4

# Function to reset sent alerts at the start of a new market day
def reset_sent_alerts():
    global sent_alerts
    sent_alerts = {}
    print("Sent alerts reset for the new market day.")

# Schedule reset at the start of a new market day (e.g., 9:30 AM)
def schedule_reset():
    now = datetime.datetime.now()
    reset_time = datetime.datetime(now.year, now.month, now.day, 9, 30)
    if now > reset_time:
        reset_time += datetime.timedelta(days=1)
    
    # Ensure the reset time is on a market day
    while not is_market_day(reset_time):
        reset_time += datetime.timedelta(days=1)
    
    delay = (reset_time - now).total_seconds()
    threading.Timer(delay, reset_and_reschedule).start()

def reset_and_reschedule():
    reset_sent_alerts()
    schedule_reset()

# Call schedule_reset when the script starts
schedule_reset()

# Interval for fetching data (in seconds)
FETCH_INTERVAL = 60  # 1 minute

# Flag to control the periodic scanning
scanning = False

# Function to clear all flagged/blacklisted tickers
def clear_flagged_tickers():
    global sent_alerts
    sent_alerts = {}
    print("All flagged/blacklisted tickers have been cleared.")

def fetch_data():
    if not tickers:
        messagebox.showwarning("Warning", "No tickers to fetch data for!")
        return

    def fetch():
        alerts = []
        for ticker in tickers:
            if ticker in sent_alerts:
                print(f"Skipping {ticker} as it has already been flagged for today.")
                continue

            try:
                print(f"Fetching data for {ticker}...")
                stock = yf.Ticker(ticker)
                data = stock.history(period="1mo", interval="30m")  # 1 month, 30-minute intervals
                if data.empty:
                    print(f"No data available for {ticker}")
                    continue

                # Fetch additional info
                info = stock.info
                current_price = info.get("currentPrice", 0)
                current_volume = info.get("regularMarketVolume", 0)
                avg_volume = info.get("averageVolume", 1)  # Avoid division by zero

                # Calculate Parabolic SAR
                data["SAR"] = ta.psar(data["High"], data["Low"], data["Close"])["PSARl_0.02_0.2"]
                latest_sar = data["SAR"].iloc[-1]

                # Calculate custom momentum (no text in alert)
                momentum_signal = calculate_custom_momentum(data, period=10, wma_period=10, threshold=1.18)

                # Calculate percentage differences
                sar_percentage = ((current_price - latest_sar) / latest_sar) * 100
                volume_percentage = ((current_volume / avg_volume) - 1) * 100

                # Check conditions for BUY alert
                if current_price > latest_sar and current_volume >= 1.5 * avg_volume and momentum_signal:
                    alert_message = (
                        f"🚨 @everyone BUY Alert for **{ticker}**:\n"
                        f"Price: ${current_price:.2f}\n"
                        f"SAR: {sar_percentage:.2f}% higher\n"
                        f"Volume: {volume_percentage:.2f}% higher"
                    )
                    alerts.append((ticker, alert_message))
                    sent_alerts[ticker] = True

            except Exception as e:
                print(f"Error fetching data for {ticker}: {e}")

        # Generate and send alerts
        for ticker, alert_message in alerts:
            print(f"Generating chart for {ticker}...")
            chart_buffer = generate_1month_chart_with_realtime(ticker)
            if chart_buffer:
                print(f"Sending alert for {ticker}...")
                send_discord_alert_with_image(alert_message, chart_buffer)
            else:
                print(f"Failed to generate chart for {ticker}.")

        # Schedule the next fetch if scanning is enabled
        if scanning:
            threading.Timer(FETCH_INTERVAL, fetch).start()

    threading.Thread(target=fetch).start()

def toggle_scanning():
    global scanning
    scanning = not scanning
    if scanning:
        fetch_data()
        toggle_button.config(text="Stop Scanning")
    else:
        toggle_button.config(text="Start Scanning")

# GUI setup
def update_list():
    listbox.delete(0, tk.END)
    for ticker in tickers:
        listbox.insert(tk.END, ticker)

# Initialize the database and load tickers
init_db()
tickers = get_tickers_from_db()

# Initialize ttkbootstrap style
style = Style(theme="darkly")

root = style.master
root.title("Ticker Manager with Parabolic Alerts")

frame = ttk.Frame(root)
frame.pack(pady=10)

listbox = tk.Listbox(frame, selectmode=tk.SINGLE, width=30, height=10, bg="#2c2c2e", fg="#ffffff", selectbackground="#ffcc00")
listbox.pack(side=tk.LEFT, padx=5)

scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, style="TScrollbar")
scrollbar.config(command=listbox.yview)
listbox.config(yscrollcommand=scrollbar.set)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

ttk.Button(root, text="Add Ticker", command=lambda: add_ticker_to_db(simpledialog.askstring("Input", "Enter a ticker to add:").upper()), width=20).pack(pady=5)
ttk.Button(root, text="Remove Ticker", command=lambda: remove_ticker_from_db(tickers[listbox.curselection()[0]]), width=20).pack(pady=5)
toggle_button = ttk.Button(root, text="Start Scanning", command=toggle_scanning, width=20)
toggle_button.pack(pady=5)
ttk.Button(root, text="Clear Flagged Tickers", command=clear_flagged_tickers, width=20).pack(pady=5)

update_list()

def run_bot():
    bot.run(DISCORD_TOKEN)

discord_thread = threading.Thread(target=run_bot, daemon=True)
discord_thread.start()

root.mainloop()
