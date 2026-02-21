from fastapi import FastAPI, HTTPException
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
    category: str
    score: int

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
        SELECT 
            CAST(AI_Initiative_Title AS NVARCHAR(MAX)),
            CAST(Summary_of_AI_Solution AS NVARCHAR(MAX)),
            CAST(Business_Impact_Explanation AS NVARCHAR(MAX)),
            CAST(FilePath AS NVARCHAR(MAX))
        FROM dbo.Initiative
    """)

    rows = cursor.fetchall()
    conn.close()

    initiatives = []
    for r in rows:
        initiatives.append({
            "title": str(r[0] or ""),
            "solution": str(r[1] or ""),
            "impact": str(r[2] or ""),
            "file": str(r[3] or "")
        })

    return initiatives


# ==============================
# LOGIN
# ==============================

@app.post("/login")
def login_user(req: LoginModel):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT username, password
        FROM dbo.Users
        WHERE LTRIM(RTRIM(CAST(username AS NVARCHAR(MAX)))) = LTRIM(RTRIM(%s))
    """, (req.username.strip(),))

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    stored = row[1].strip()
    input_password = req.password.strip()

    if stored.startswith("$2"):
        if not bcrypt.checkpw(input_password.encode(), stored.encode()):
            raise HTTPException(status_code=401, detail="Invalid credentials")
    else:
        if stored != input_password:
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
        vote.idea_title.strip(),
        vote.username.strip(),
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
        WHERE LTRIM(RTRIM(CAST(Idea_Title AS NVARCHAR(MAX)))) = LTRIM(RTRIM(%s))
    """, (idea_title,))

    row = cursor.fetchone()
    conn.close()

    total = row[0] if row and row[0] else 0

    return {"total_percentage": float(total)}


# ==============================
# FINAL VOTE
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
        data.username.strip(),
        data.idea_title.strip(),
        data.percentage,
        1 if data.submit else 0
    ))

    conn.commit()
    conn.close()

    return {"success": True}


# ==============================
# CHECK FINAL VOTE
# ==============================

@app.get("/check_final_vote/{username}/{idea_title}")
def check_final_vote(username: str, idea_title: str):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT Submit
        FROM dbo.FinalVoting
        WHERE LTRIM(RTRIM(CAST(Username AS NVARCHAR(MAX)))) = LTRIM(RTRIM(%s))
          AND LTRIM(RTRIM(CAST(Idea_Title AS NVARCHAR(MAX)))) = LTRIM(RTRIM(%s))
    """, (username, idea_title))

    row = cursor.fetchone()
    conn.close()

    return {"submitted": bool(row[0]) if row else False}


# ==============================
# ADMIN FULL REPORT
# ==============================

@app.get("/admin/full_report")
def admin_full_report():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM dbo.Initiative")
    total_projects = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(DISTINCT CAST(Idea_Title AS NVARCHAR(MAX)))
        FROM dbo.FinalVoting
        WHERE Submit = 1
    """)
    completed_projects = cursor.fetchone()[0] or 0

    # USERS
    cursor.execute("""
        SELECT username, Names
        FROM dbo.Users
        WHERE username IS NOT NULL
          AND LTRIM(RTRIM(username)) <> ''
          AND username <> 'Admin'
    """)

    user_rows = cursor.fetchall()
    users_summary = []
    valid_usernames = []

    for username, display_name in user_rows:

        valid_usernames.append(username)

        cursor.execute("""
            SELECT COUNT(DISTINCT CAST(Idea_Title AS NVARCHAR(MAX)))
            FROM dbo.FinalVoting
            WHERE Username = %s AND Submit = 1
        """, (username,))

        finished = cursor.fetchone()[0] or 0

        users_summary.append({
            "name": str(display_name or username),
            "username": str(username),
            "finished": int(finished),
            "remaining": int(total_projects - finished)
        })

    # PROJECTS
    cursor.execute("""
        SELECT 
            CAST(AI_Initiative_Title AS NVARCHAR(MAX)),
            CAST(Summary_of_AI_Solution AS NVARCHAR(MAX)),
            CAST(Business_Impact_Explanation AS NVARCHAR(MAX)),
            CAST(FilePath AS NVARCHAR(MAX))
        FROM dbo.Initiative
    """)

    initiatives = cursor.fetchall()
    projects = []

    for title, solution, impact, file_path in initiatives:

        cursor.execute("""
            SELECT 
                CAST(Username AS NVARCHAR(MAX)),
                Percentage
            FROM dbo.FinalVoting
            WHERE LTRIM(RTRIM(CAST(Idea_Title AS NVARCHAR(MAX)))) = LTRIM(RTRIM(%s))
              AND Submit = 1
        """, (title,))

        voted_data = cursor.fetchall()

        user_percentages = {}
        for username, percentage in voted_data:
            if username and username.strip() != '' and username != 'Admin':
                user_percentages[username] = float(percentage or 0)

        avg = 0
        if user_percentages:
            avg = sum(user_percentages.values()) / len(user_percentages)

        projects.append({
            "project": str(title or ""),
            "solution": str(solution or ""),
            "impact": str(impact or ""),
            "file": str(file_path or ""),
            "total_voters": len(user_percentages),
            "average_percentage": round(avg, 2),
            "voted_users": list(user_percentages.keys()),
            "user_percentages": user_percentages
        })

    projects.sort(key=lambda x: x["average_percentage"], reverse=True)

    for i, p in enumerate(projects):
        p["rank"] = i + 1

    conn.close()

    return {
        "total_projects": int(total_projects),
        "completed_projects": int(completed_projects),
        "projects": projects,
        "users_summary": users_summary
    }
