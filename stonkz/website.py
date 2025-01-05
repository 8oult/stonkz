from flask import Flask, jsonify, render_template
import yfinance as yf
import sqlite3
import pandas_ta as ta
import numpy as np

# Initialize the Flask app
app = Flask(__name__)

# Database connection function
def get_tickers_from_db():
    """Fetch tickers from the SQLite database."""
    conn = sqlite3.connect('tickers.db')
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM tickers")
    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tickers

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

@app.route('/')
def home():
    """Render the homepage."""
    return render_template('index.html')

@app.route('/stocks')
def get_stocks():
    """Fetch stock data and identify parabolic alerts."""
    tickers = get_tickers_from_db()  # Dynamically fetch tickers from the database
    data = []
    parabolic_alerts = []

    for ticker in tickers:
        try:
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
                parabolic_alerts.append({
                    "ticker": ticker,
                    "price": current_price,
                    "volume": current_volume,
                    "change": round(sar_percentage, 2)
                })

            # Append stock data
            data.append({
                "ticker": ticker,
                "price": current_price,
                "volume": current_volume,
                "change": round(sar_percentage, 2)
            })
        except Exception as e:
            data.append({
                "ticker": ticker,
                "price": "Error",
                "volume": "Error",
                "change": "Error"
            })
            print(f"Error fetching data for {ticker}: {e}")

    return jsonify({"stocks": data, "parabolic_alerts": parabolic_alerts})

if __name__ == '__main__':
    app.run(debug=True)
