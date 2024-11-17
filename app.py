from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import json
import glob
import re
import uvicorn

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def read_trading_logs():
    data = {}
    pattern = r'([A-Z]+USDT)_1h_log_file\.json'
    
    for filename in glob.glob("*_1h_log_file.json"):
        match = re.match(pattern, filename)
        if match:
            pair = match.group(1)
            try:
                with open(filename, 'r') as f:
                    content = json.load(f)
                    if content:  # Only add if file has content
                        data[pair] = content
            except json.JSONDecodeError as e:
                print(f"Error reading {filename}: {e}")
                continue
    return data

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

@app.get("/api/trades")
async def get_trades():
    data = read_trading_logs()
    return JSONResponse(content=data)

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )