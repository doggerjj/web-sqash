import json, re, os
import uvicorn, glob, uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from datetime import datetime, timedelta
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse


load_dotenv()
app = FastAPI()
active_sessions = {}
USERS = {os.getenv("USERNAME"): os.getenv("PASSWORD")}

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def read_trading_logs():
    data = {}
    pattern = r'([A-Z]+USDT)_(\w+)_log_file\.json'
    for filename in glob.glob("*_log_file.json"):
        match = re.match(pattern, filename)
        if match:
            pair = match.group(1)
            interval = match.group(2)
            try:
                with open(filename, 'r') as f:
                    content = json.load(f)
                    if content:
                        key = f"{pair}_{interval}"
                        data[key] = content
            except json.JSONDecodeError as e:
                print(f"Error reading {filename}: {e}")
                continue
    return data


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path == "/login" or request.url.path.startswith("/static"):
        return await call_next(request)

    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in active_sessions:
        return RedirectResponse(url="/login", status_code=303)
    
    # Check if session is expired (30 minutes)
    if datetime.now() > active_sessions[session_id]["expires"]:
        del active_sessions[session_id]
        return RedirectResponse(url="/login", status_code=303)
    
    return await call_next(request)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )

@app.post("/login")
async def login(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")

    if username in USERS and USERS[username] == password:
        session_id = f"session_{username}_{datetime.now().timestamp()}"
        active_sessions[session_id] = {
            "username": username,
            "expires": datetime.now() + timedelta(minutes=30)
        }
        
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_id", value=session_id)
        return response
    
    return RedirectResponse(url="/login?error=1", status_code=303)

@app.post("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id in active_sessions:
        del active_sessions[session_id]
    
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_id")
    return response

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
        port=8080,
        reload=True
    )