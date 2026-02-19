from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from db import get_connection
import bcrypt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:52795",
        "https://green-forest-00c55ac03.4.azurestaticapps.net"
    ],
    allow_origin_regex=r"http://localhost:\d+",
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
    username: str
    category: str   # pillar name
    score: int      # 1-5


class InitiativeModel(BaseModel):
    title: str
    solution: str
    impact: str
    file: str | None = None

class FinalVoteModel(BaseModel):
    username: str
    idea_title: str
    percentage: float
    submit: bool

class ChangePasswordModel(BaseModel):
    username: str
    old_password: str
    new_password: str

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

    # Convert bytes to string if needed
    if isinstance(stored_password, bytes):
        stored_password = stored_password.decode()

    # CASE 1: Already encrypted (bcrypt)
    if stored_password.startswith("$2"):
        if not bcrypt.checkpw(req.password.encode(), stored_password.encode()):
            raise HTTPException(status_code=401, detail="Invalid credentials")

    # CASE 2: Plain text (first login)
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

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO dbo.Voting
        (Idea_Title, username, Category, Score)
        VALUES (%s, %s, %s, %s)
    """, (
        vote.idea_title,
        vote.username,
        vote.category,
        vote.score
    ))

    conn.commit()
    conn.close()

    return {"success": True}


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

# ==============================
#  Final Vote
# ==============================

@app.post("/submit_final_vote")
def submit_final_vote(data: FinalVoteModel):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO dbo.FinalVoting
        (Username, Idea_Title, Percentage, Submit)
        VALUES (%s, %s, %s, %s)
    """, (
        data.username,
        data.idea_title,
        data.percentage,
        1 if data.submit else 0
    ))

    conn.commit()
    conn.close()

    return {"success": True}

# ==============================
#  Disable the button
# ==============================

@app.get("/check_final_vote/{username}/{idea_title}")
def check_final_vote(username: str, idea_title: str):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT Submit
        FROM dbo.FinalVoting
        WHERE Username = %s AND Idea_Title = %s
    """, (username, idea_title))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {"submitted": bool(row[0])}

    return {"submitted": False}


@app.get("/admin/summary")
def admin_summary():
    conn = get_connection()
    cursor = conn.cursor()

    # Total initiatives from Initiative table
    cursor.execute("SELECT COUNT(*) FROM dbo.Initiative")
    total_initiatives = cursor.fetchone()[0]

    # Total votes from FinalVoting table
    cursor.execute("SELECT COUNT(*) FROM dbo.FinalVoting")
    total_votes = cursor.fetchone()[0]

    # Submitted votes
    cursor.execute("SELECT COUNT(*) FROM dbo.FinalVoting WHERE Submit = 1")
    submitted = cursor.fetchone()[0]

    # Average percentage
    cursor.execute("SELECT ISNULL(AVG(Percentage),0) FROM dbo.FinalVoting")
    avg_percentage = round(cursor.fetchone()[0], 2)

    conn.close()

    return {
        "total_initiatives": total_initiatives,
        "total_votes": total_votes,
        "submitted": submitted,
        "avg_percentage": avg_percentage
    }

@app.get("/admin/results")
def admin_results():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            ROW_NUMBER() OVER (ORDER BY AVG(Percentage) DESC) AS rank,
            Idea_Title,
            COUNT(*) AS votes,
            CAST(AVG(Percentage) AS INT) AS average_percentage
        FROM dbo.FinalVoting
        WHERE Submit = 1
        GROUP BY Idea_Title
        ORDER BY average_percentage DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "rank": row[0],
            "title": row[1],
            "votes": row[2],
            "average_percentage": row[3]
        })

    return results

@app.post("/final_submit")
def final_submit(data: dict):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO dbo.FinalVoting (Username, Idea_Title, Percentage, Submit)
        VALUES (?, ?, ?, 1)
    """, (
        data["username"],
        data["idea_title"],
        data["percentage"]
    ))

    conn.commit()
    conn.close()

    return {"success": True}



# ==============================
# CHANGE PASSWORD ENDPOINT
# ==============================
# ==============================
# CHANGE PASSWORD ENDPOINT
# ==============================
@app.post("/change_password")
def change_password(data: ChangePasswordModel):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT password
        FROM dbo.Users
        WHERE username = %s
    """, (data.username,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    stored_password = row[0]

    if isinstance(stored_password, bytes):
        stored_password = stored_password.decode()

    # Verify old password
    if stored_password.startswith("$2"):
        if not bcrypt.checkpw(data.old_password.encode(), stored_password.encode()):
            conn.close()
            raise HTTPException(status_code=401, detail="Old password incorrect")
    else:
        if stored_password != data.old_password:
            conn.close()
            raise HTTPException(status_code=401, detail="Old password incorrect")

    # Encrypt new password
    new_hash = bcrypt.hashpw(
        data.new_password.encode(),
        bcrypt.gensalt()
    ).decode()

    cursor.execute("""
        UPDATE dbo.Users
        SET password = %s
        WHERE username = %s
    """, (new_hash, data.username))

    conn.commit()
    conn.close()

    return {"success": True}
