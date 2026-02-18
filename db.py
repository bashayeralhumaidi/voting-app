import pyodbc

def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=confirmaapplication.database.windows.net,1433;"
        "DATABASE=voting;"
        "UID=Julphar_Admin;"
        "PWD=Bashayer01;"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )
