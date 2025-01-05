import subprocess
import os

# Run Flask app
flask_process = subprocess.Popen(["python", "website.py"])

# Run GUI app
gui_process = subprocess.Popen(["python", "app.py"])

try:
    print("Running Flask and GUI apps... Press Ctrl+C to stop.")
    flask_process.wait()
    gui_process.wait()
except KeyboardInterrupt:
    print("Stopping applications...")
    flask_process.terminate()
    gui_process.terminate()
