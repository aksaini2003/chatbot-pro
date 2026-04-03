import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

print(f"Testing connection to: {DATABASE_URL[:20]}...")

try:
    # Neon DB usually requires SSL, and it's already in the URL: sslmode=require
    # Also, we should remove the SQLite-specific connect_args if we were using them in the main code
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print("Successfully connected to Neon DB!")
        print(f"Query Result: {result.fetchone()[0]}")
        
except Exception as e:
    print(f"Error connecting to Neon DB: {e}")
