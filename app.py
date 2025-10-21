from flask import Flask
app = Flask(__name__)

@app.get("/")
def index():
    return "Test-question-extractor: OK"

if __name__ == "__main__":
    app.run(debug=True)
