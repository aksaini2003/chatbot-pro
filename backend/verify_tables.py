import os
from database import engine, Base, create_tables
from dotenv import load_dotenv

load_dotenv()

print(f"Connecting to: {os.getenv('DATABASE_URL')[:20]}...")

try:
    print("Creating tables if they don't exist...")
    create_tables()
    print("Tables created successfully (or already existed)!")
    
    # Check if tables exist
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Existing tables: {tables}")
    
    if len(tables) > 0:
        print("Verification SUCCESS: Tables are present in the Neon DB.")
    else:
        print("Verification FAILURE: No tables found.")

except Exception as e:
    print(f"Error during table creation/verification: {e}")
