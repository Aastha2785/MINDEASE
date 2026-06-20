from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import pymysql
import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
from groq import Groq
import json
import os
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
# --- INITIALIZATION ---
app = FastAPI(title="MindEase")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- CONFIGURATION ---
# SECRET_KEY = "aastha_mind_ease_2785"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Initialize Groq
client = Groq(api_key=api_key)

# --- DATABASE ---
def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password=os.getenv("DB_PASSWORD"),
        database="mindEase",
        cursorclass=pymysql.cursors.DictCursor
    )

# --- SECURITY UTILS ---
def hash_pass(password: str):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_pass(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise HTTPException(status_code=401)
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Session expired")

# --- MODELS ---
class UserSignup(BaseModel):
    username: str
    email: str
    password: str

class JournalCreate(BaseModel):
    entry_text: str

class TaskCreate(BaseModel):
    title: str
    deadline: str | None = None

# --- HTML PAGE ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page_explicit(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/todo", response_class=HTMLResponse)
async def todo_page(request: Request):
    return templates.TemplateResponse("todo.html", {"request": request})

@app.get("/journal", response_class=HTMLResponse)
async def journal_page(request: Request):
    return templates.TemplateResponse("journal.html", {"request": request})

# --- AUTH API ---
@app.post("/signup")
async def signup(user: UserSignup):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username=%s", (user.username,))
            if cursor.fetchone(): raise HTTPException(status_code=400, detail="User exists")
            sql = "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)"
            cursor.execute(sql, (user.username, user.email, hash_pass(user.password)))
            conn.commit()
            return {"message": "Success"}
    finally: conn.close()

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username=%s", (form_data.username,))
            user = cursor.fetchone()
            if not user or not verify_pass(form_data.password, user['password_hash']):
                raise HTTPException(status_code=401, detail="Invalid credentials")
            return {"access_token": create_token({"sub": user['username']}), "token_type": "bearer"}
    finally: conn.close()



# --- JOURNAL API (Integrated Groq) ---
# --- SIMPLIFIED JOURNAL API (Matching your logic) ---
@app.post("/api/journal")
async def add_journal(journal: JournalCreate, username: str = Depends(get_current_user)):
    try:
        # Using the exact prompt and model from your test script
        prompt = f"{journal.entry_text}. Predict the mood in 3 to 6 words only with one emoji"
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant", # Updated model
        )
        
        # Get the simple text response
        mood_prediction = chat_completion.choices[0].message.content.strip()
        print(f"DEBUG - Mood Result: {mood_prediction}")
        
    except Exception as e:
        print(f"AI Error: {e}")
        mood_prediction = "Feeling a bit overwhelmed today."

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Get User ID
            cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
            user = cursor.fetchone()
            user_id = user['id']
            
            # Save the text response to your database
            sql = "INSERT INTO journal_entries (user_id, entry_text, predicted_mood) VALUES (%s, %s, %s)"
            cursor.execute(sql, (user_id, journal.entry_text, mood_prediction))
            conn.commit()
            
            # Suggestion logic (we can make this dynamic later)
            suggestion = "Consider taking a short break or listening to some music."
            if "tired" in journal.entry_text.lower():
                suggestion = "Try to get some rest and stay hydrated."
                
            return {"mood": mood_prediction, "suggestion": suggestion}
    finally:
        conn.close()
# Ensure the variable name is {entry_id} and matches the function argument
@app.delete("/api/journal-history/{entry_id}")
async def delete_journal_entry(entry_id: int, username: str = Depends(get_current_user)):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Get the current user's ID
            cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
            user = cursor.fetchone()
            
            # 2. Execute the delete (Safety check: user_id ensures users can only delete their own data)
            sql = "DELETE FROM journal_entries WHERE id=%s AND user_id=%s"
            cursor.execute(sql, (entry_id, user['id']))
            conn.commit()
            
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Entry not found")
            return {"message": "Deleted"}
    finally:
        conn.close()
        
from collections import defaultdict

@app.get("/api/journal-history")
async def get_journal_history(username: str = Depends(get_current_user)):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
            user = cursor.fetchone()
            
            cursor.execute("""
                SELECT id, entry_text, predicted_mood, created_at 
                FROM journal_entries 
                WHERE user_id=%s 
                ORDER BY created_at DESC
            """, (user['id'],))
            rows = cursor.fetchall()
            
            # Grouping entries by date
            grouped_data = defaultdict(list)
            for row in rows:
                # Format date as '7 Mar 2026'
                date_str = row['created_at'].strftime("%d %b %Y")
                grouped_data[date_str].append({
                    "id": row["id"],
                    "entry_text": row["entry_text"],
                    "predicted_mood": row["predicted_mood"],
                    "time": row["created_at"].strftime("%I:%M %p")
                })
            
            return grouped_data
    finally:
        conn.close()
# --- TASK API ---

@app.get("/api/tasks")
async def get_tasks(username: str = Depends(get_current_user)):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
            user = cursor.fetchone()
            
            # Use 'AS deadline' so your JavaScript t.deadline logic works!
            cursor.execute("""
                SELECT id, title, is_completed, due_date AS deadline 
                FROM tasks 
                WHERE user_id=%s 
                ORDER BY is_completed ASC, due_date ASC, created_at DESC
            """, (user['id'],))
            return cursor.fetchall()
    finally:
        conn.close()

# --- TASK API UPDATES ---

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int, username: str = Depends(get_current_user)):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Secure delete: Ensure the task belongs to the logged-in user
            cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
            user_id = cursor.fetchone()['id']
            
            sql = "DELETE FROM tasks WHERE id=%s AND user_id=%s"
            cursor.execute(sql, (task_id, user_id))
            conn.commit()
            return {"message": "Task deleted"}
    finally:
        conn.close()

@app.post("/api/tasks")
async def add_task(task: TaskCreate, username: str = Depends(get_current_user)):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
            user_id = cursor.fetchone()['id']
            
            # Use the correct column name from your SQL schema: due_date
            sql = "INSERT INTO tasks (user_id, title, due_date) VALUES (%s, %s, %s)"
            cursor.execute(sql, (user_id, task.title, task.deadline))
            conn.commit()
            return {"message": "Task created"}
    finally:
        conn.close()

@app.get("/api/user-stats")
async def get_user_stats(username: str = Depends(get_current_user)):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Get the primary key for Aastha
            cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
            user = cursor.fetchone()
            user_id = user['id']
            
            # 2. PENDING: Count tasks where is_completed is 0
            cursor.execute("SELECT COUNT(*) as pending FROM tasks WHERE user_id=%s AND is_completed=0", (user_id,))
            pending_count = cursor.fetchone()['pending']
            
            # 3. DONE: Count tasks where is_completed is 1
            cursor.execute("SELECT COUNT(*) as done FROM tasks WHERE user_id=%s AND is_completed=1", (user_id,))
            done_count = cursor.fetchone()['done']
            
            # 4. Return keys that match your JavaScript IDs
            return {
                "username": username,
                "tasks_pending": pending_count,
                "tasks_done": done_count,
                "is_card_ready": True
            }
    finally:
        conn.close()

@app.put("/api/tasks/{task_id}")
async def toggle_task(task_id: int, username: str = Depends(get_current_user)):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
            user_id = cursor.fetchone()['id']
            # Toggle logic: if 0 -> 1 (set time), if 1 -> 0 (clear time)
            sql = """
                UPDATE tasks 
                SET is_completed = NOT is_completed,
                    completed_at = CASE WHEN is_completed = 0 THEN CURRENT_TIMESTAMP ELSE NULL END
                WHERE id=%s AND user_id=%s
            """
            cursor.execute(sql, (task_id, user_id))
            conn.commit()
            return {"status": "updated"}
    finally:
        conn.close()
import re

# Add this route to main.py
@app.get("/daily-card", response_class=HTMLResponse)
async def daily_card_page(request: Request):
    return templates.TemplateResponse("daily-card.html", {"request": request})
from datetime import datetime

from collections import Counter
import re
from datetime import datetime

from datetime import datetime
from collections import Counter
import re

from datetime import datetime
import re

@app.get("/api/daily-summary")
async def get_daily_summary(username: str = Depends(get_current_user)):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:

            # 🔹 1. Get user_id
            cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
            user = cursor.fetchone()
            user_id = user['id']

            # 🔹 2. GET TODAY'S JOURNAL TEXT
            cursor.execute("""
                SELECT entry_text 
                FROM journal_entries
                WHERE user_id=%s AND DATE(created_at) = CURDATE()
            """, (user_id,))
            
            entries = cursor.fetchall()
            combined_text = " ".join([row['entry_text'] for row in entries])

            print("DEBUG - Combined Text:", combined_text)

            # 🔹 3. EMOJI FROM GROQ (SAFE)
            if not combined_text.strip():
                emojis = ["🌿", "✨", "🌸"]
                quote = "Every day is a fresh start"
            else:
                try:
                    prompt = f"""
                    Based on this user's day:
                    {combined_text}

                    Write a short motivational line (max 10 words).
                    No emoji.
                    """

                    chat = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.1-8b-instant"
                    )

                    quote = chat.choices[0].message.content.strip()
                    prompt = f"""
                    You are a mental wellness assistant.

                    Based on the user's journal entries:
                    {combined_text}

                    Return exactly three emoji that represents their overall emotional state.
                    No explanation. Only emoji.
                    """

                    chat = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="llama-3.1-8b-instant"
                    )

                    raw_output = chat.choices[0].message.content.strip()
                    print("DEBUG - Raw Emoji:", raw_output)

                    # Extract only emoji
                    emojis = re.findall(
                        r'[\U0001F600-\U0001F64F'
                        r'\U0001F300-\U0001F5FF'
                        r'\U0001F680-\U0001F6FF'
                        r'\U0001F1E0-\U0001F1FF]+',
                        raw_output
                    )

                    emojis = emojis[:3] if len(emojis)<=3 else ["❤️","😊","🫰"]

                except Exception as e:
                    print("AI Error:", e)
                    emojis = ["😐", "🌿", "✨"]
                    quote = "Take it easy, tomorrow is a fresh start"

            # 🔹 4. TASK STATS (FIXED LOGIC ✅)
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) as done_total,
                    SUM(CASE WHEN is_completed = 0 THEN 1 ELSE 0 END) as pending_total
                FROM tasks
                WHERE user_id=%s
            """, (user_id,))
            
            stats = cursor.fetchone()

            done = stats['done_total'] or 0
            pending = stats['pending_total'] or 0
            total = done + pending

            productivity = (done / total * 100) if total > 0 else 0

            print("DEBUG - Done:", done, "Pending:", pending)

            # 🔹 5. PRODUCTIVITY LABEL
            if productivity >= 75:
                productivity_label = "Highly Productive 🔥"
            elif productivity >= 40:
                productivity_label = "Moderate 🙂"
            else:
                productivity_label = "Low 😞"

            # 🔹 6. SMART MESSAGE
            if productivity > 70:
                message = "You had a strong and productive day 🌸"
            elif productivity < 40:
                message = "Take it slow, tomorrow is a fresh start 💙"
            else:
                message = "You're doing well, keep going 🌿"
            

            # 🔹 7. FINAL RESPONSE
            return {
                "date": datetime.now().strftime("%B %d, %Y"),
                "emojis": emojis,
                "quote":quote,
                "tasks_completed": done,
                "tasks_remaining": pending,
                "productivity": round(productivity),
                "productivity_label": productivity_label,
                "message": message
            }

    finally:
        conn.close()
# Also add the HTML route to show the page
@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
