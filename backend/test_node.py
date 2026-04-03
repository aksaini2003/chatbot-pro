import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph_backend import chat_node, ChatState, llm

load_dotenv()

# Simulate state
state = {"messages": [HumanMessage(content="who are you?")]}
config = {"configurable": {"thread_id": "test_thread"}}

try:
    print("Testing chat_node...")
    res = chat_node(state, config)
    print("Result:", res["messages"][0].content)
except Exception as e:
    print("chat_node failed with error:", e)
    import traceback
    traceback.print_exc()
