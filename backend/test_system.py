import os
import time
import json
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph_backend import chatbot

# Load environment variables
load_dotenv()

def test_tool(query, description):
    print(f"\n--- Testing: {description} ---")
    print(f"Query: {query}")
    
    config = {"configurable": {"thread_id": "test_verification_thread_unique_id"}}
    
    try:
        # We'll use stream to see the chunks and identify tool calls
        found_tool = False
        final_answer = ""
        
        for event in chatbot.stream({"messages": [HumanMessage(content=query)]}, config=config, stream_mode="values"):
            if "messages" in event:
                last_msg = event["messages"][-1]
                if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                    print(f"[TOOL CALL] {last_msg.tool_calls[0]['name']} with {last_msg.tool_calls[0]['args']}")
                    found_tool = True
                elif last_msg.type == "ai" and not last_msg.tool_calls:
                    final_answer = last_msg.content

        if found_tool:
            print(f"[SUCCESS] Tool was called.")
        else:
            print(f"[NOTICE] No tool called. Response summary: {final_answer[:100]}...")
            
        return found_tool
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        return False

# List of tests
tests = [
    ("What is 1532 * 45?", "Calculator"),
    ("What is the current weather in Alwar, Rajasthan?", "Weather Tool"),
    ("What is the current price of AAPL?", "Stock Price Tool"),
    ("Convert 100 USD to INR", "Currency Conversion"),
    ("What is the current time right now?", "Date/Time Tool"),
    ("Who won the last Super Bowl?", "Web Search Tool"),
    ("Who is Aashish Kumar Saini?", "Identity Check"),
]

print("Starting System Integration Test with delays (to avoid TPM limits)...")
results = []

for i, (query, desc) in enumerate(tests):
    if i > 0:
        print(f"...Waiting 10 seconds before next test to prevent rate limits...")
        time.sleep(10)
    
    success = test_tool(query, desc)
    results.append((desc, success))

print("\n--- Final Test Summary ---")
for desc, success in results:
    status = "PASS" if success else "NOTICE (Check output)"
    print(f"{desc}: {status}")
