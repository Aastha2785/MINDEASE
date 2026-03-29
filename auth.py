from fastapi import APIRouter, Form
from database import get_db
from passlib.hash import bcrypt

router = APIRouter()


@router.post("/signup")
def signup(username: str = Form(...),
           email: str = Form(...),
           password: str = Form(...)):

    db = get_db()
    cursor = db.cursor()

    password_hash = bcrypt.hash(password)

    query = """
    INSERT INTO users(username,email,password_hash)
    VALUES(%s,%s,%s)
    """

    cursor.execute(query,(username,email,password_hash))
    db.commit()

    return {"message":"Signup successful"}
@router.post("/login")
def login(email: str = Form(...),
          password: str = Form(...)):

    db = get_db()
    cursor = db.cursor(dictionary=True)

    query = "SELECT * FROM users WHERE email=%s"
    cursor.execute(query,(email,))
    user = cursor.fetchone()

    if not user:
        return {"message":"User not found"}

    if bcrypt.verify(password,user["password_hash"]):
        return {"message":"Login success","user_id":user["id"]}

    return {"message":"Invalid password"}