from flask import Flask, jsonify, render_template
import yfinance as yf

# Initialize the Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/stocks')
def get_stocks():
    tickers = ["CTM", "CYN", "MDAI", "RVSN", "IDAI", "KULR"]
    data = []
    parabolic_alerts = []

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            previous_close = info.get("regularMarketPreviousClose", 0)
            current_price = info.get("currentPrice", 0)
            current_volume = info.get("regularMarketVolume", 0)
            avg_volume = info.get("averageVolume", 1)  # Prevent division by zero

            # Calculate percentage price change
            percent_change = 0
            if previous_close > 0:
                percent_change = ((current_price - previous_close) / previous_close) * 100

            # Detect parabolic movements (positive change only)
            if percent_change > 3 and current_volume > (1.5 * avg_volume):
                parabolic_alerts.append({
                    "ticker": ticker,
                    "price": current_price,
                    "volume": current_volume,
                    "change": round(percent_change, 2)
                })

            data.append({
                "ticker": ticker,
                "price": current_price,
                "volume": current_volume,
                "change": round(percent_change, 2)
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
