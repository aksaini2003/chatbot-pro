import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

try:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        max_tokens=1024
    )
    res = llm.invoke("test")
    print("Groq works:", res.content)
except Exception as e:
    print("Groq failed:", e)
