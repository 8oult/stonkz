import sqlite3

# Connect to SQLite database (this will create the file if it doesn't exist)
conn = sqlite3.connect('tickers.db')
cursor = conn.cursor()

# Read and execute schema.sql
with open('schema.sql', 'r') as file:
    cursor.executescript(file.read())

# Commit changes and close the connection
conn.commit()
conn.close()

print("Database initialized successfully.")
