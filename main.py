from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from db import get_connection
import bcrypt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:60020",
        "https://green-forest-00c55ac03.4.azurestaticapps.net"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================
# MODELS
# ==============================

class LoginModel(BaseModel):
    username: str
    password: str


class VoteModel(BaseModel):
    idea_title: str
    voted_by: str
    category: str   # pillar name
    score: int      # 1-5


class InitiativeModel(BaseModel):
    title: str
    solution: str
    impact: str
    file: str | None = None


# ==============================
# ROOT
# ==============================
@app.get("/")
def root():
    return {"message": "Voting Backend Running"}



# ==============================
# GET INITIATIVES
# ==============================
@app.get("/get_initiatives")
def get_initiatives():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT AI_Initiative_Title,
               Summary_of_AI_Solution,
               Business_Impact_Explanation,
               FilePath
        FROM dbo.Initiative
    """)

    rows = cursor.fetchall()
    conn.close()

    initiatives = []
    for r in rows:
        initiatives.append({
            "title": r[0],
            "solution": r[1],
            "impact": r[2],
            "file": r[3]
        })

    return initiatives


# ==============================
# USER LOGIN
# ==============================
@app.post("/login")
def login_user(req: LoginModel):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT username, password
        FROM dbo.Users
        WHERE username = %s
    """, (req.username,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    stored_password = row[1]

    if stored_password.startswith("$2"):
        if not bcrypt.checkpw(req.password.encode(), stored_password.encode()):
            raise HTTPException(status_code=401, detail="Invalid credentials")
    else:
        if stored_password != req.password:
            raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"success": True, "username": row[0]}


# ==============================
# SUBMIT VOTE
# ==============================
@app.post("/submit_vote")
def submit_vote(vote: VoteModel):

    if vote.score < 1 or vote.score > 5:
        raise HTTPException(status_code=400, detail="Score must be 1-5")

    # Weights
    weights = {
        "Strategic Impact": 0.25,
        "Feasibility & Practicality": 0.20,
        "Innovation & Originality": 0.15,
        "Financial & Value": 0.20,
        "Proof of Concept Readiness": 0.20
    }

    weight = weights.get(vote.category, 0)

    percentage = vote.score * weight * 20   # convert to %

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO dbo.Voting
        (Idea_Title, Voting_By, Category, Score, Percentage)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        vote.idea_title,
        vote.voted_by,
        vote.category,
        vote.score,
        percentage
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "percentage": percentage
    }


# ==============================
# GET RESULTS
# ==============================
@app.get("/get_results/{idea_title}")
def get_results(idea_title: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT SUM(Percentage)
        FROM dbo.Voting
        WHERE Idea_Title = %s
    """, (idea_title,))

    row = cursor.fetchone()
    conn.close()

    total = row[0] if row[0] else 0

    return {"total_percentage": total}



