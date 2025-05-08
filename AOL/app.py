import os
from flask import Flask
import requests

app = Flask(__name__) 

@app.route('/', methods=['GET'])
def home():
    print('service is running')
    return "Service is running"

if __name__ == "__main__":
    app.run(debug=True, port=5001, host="0.0.0.0")
