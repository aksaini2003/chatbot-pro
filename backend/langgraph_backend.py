from __future__ import annotations
from deep_translator import GoogleTranslator
import asyncio
import os
import sqlite3
import tempfile
import traceback
from typing import Annotated, Any, Dict, Optional, TypedDict

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import FakeEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
import requests

load_dotenv()

try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# -------------------
# 1. LLM + embeddings
# -------------------
# Initialize primary model (Groq)
try:
    groq_llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        max_tokens=1024
    )
except Exception:
    groq_llm = None

# Initialize fallback model (NVIDIA)
try:
    nvidia_llm = ChatNVIDIA(
        model="meta/llama-3.3-70b-instruct",
        temperature=0.1,
        max_tokens=1024
    )
except Exception:
    nvidia_llm = None

# Final Fallback Error Handler
class TechnicalDifficultyLLM:
    def invoke(self, messages, config=None):
        return AIMessage(content="I'm currently experiencing technical difficulties with the LLM APIs after multiple attempts. Please try again after few hours.")
    def bind_tools(self, tools):
        return self

# Create the final llm runnable with automatic fallback
base_llm = None
if groq_llm and nvidia_llm:
    base_llm = groq_llm.with_fallbacks([nvidia_llm])
    print("LLM initialized with Groq primary and NVIDIA fallback.")
elif groq_llm:
    base_llm = groq_llm
    print("LLM initialized with Groq (NVIDIA fallback failed).")
elif nvidia_llm:
    base_llm = nvidia_llm
    print("LLM initialized with NVIDIA (Groq failed).")
else:
    base_llm = TechnicalDifficultyLLM()
    print("CRITICAL: All LLM models failed initialization. Using technical difficulty handler.")

llm = base_llm

def _get_embeddings():
    google_api_key = os.environ.get('GOOGLE_API_KEY')
    if google_api_key:
        return GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", api_key=google_api_key)

    allow_fake = os.environ.get("ALLOW_FAKE_EMBEDDINGS", "false").lower() in ("1", "true", "yes")
    if allow_fake:
        return FakeEmbeddings(size=768)

    raise RuntimeError("GOOGLE_API_KEY is not set; cannot build embeddings for PDF ingestion")

# -------------------
# 2. PDF retriever store (per thread)
# -------------------
_THREAD_RETRIEVERS: Dict[str, Any] = {}
_THREAD_METADATA: Dict[str, dict] = {}

def _get_retriever(thread_id: Optional[str]):
    """Fetch the retriever for a thread if available."""
    if thread_id:
        thread_id_str = str(thread_id)
        if thread_id_str in _THREAD_RETRIEVERS:
            return _THREAD_RETRIEVERS[thread_id_str]
    return None

def ingest_pdf(file_bytes: bytes, thread_id: str, filename: Optional[str] = None) -> dict:
    """
    Build a FAISS retriever for the uploaded PDF and store it for the thread.
    Returns a summary dict that can be surfaced in the UI.
    """
    if not file_bytes:
        raise ValueError("No bytes received for ingestion.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(file_bytes)
        temp_path = temp_file.name

    try:
        loader = PyPDFLoader(temp_path)
        docs = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", " ", ""]
        )
        chunks = splitter.split_documents(docs)

        embeddings = _get_embeddings()
        try:
            vector_store = FAISS.from_documents(chunks, embeddings)
        except Exception as e:
            print(f"[DEBUG] Google embedding failed: {e}")
            allow_fake = os.environ.get("ALLOW_FAKE_EMBEDDINGS", "false").lower() in ("1", "true", "yes")
            if allow_fake:
                print("[DEBUG] Falling back to FakeEmbeddings for PDF ingestion")
                vector_store = FAISS.from_documents(chunks, FakeEmbeddings(size=768))
            else:
                raise RuntimeError(
                    "Failed to embed PDF chunks using Google model 'models/text-embedding-004'. "
                    "Check GOOGLE_API_KEY and that this model is enabled for embeddings in your project."
                ) from e
        retriever = vector_store.as_retriever(
            search_type="similarity", search_kwargs={"k": 4}
        )

        _THREAD_RETRIEVERS[str(thread_id)] = retriever
        _THREAD_METADATA[str(thread_id)] = {
            "filename": filename or os.path.basename(temp_path),
            "documents": len(docs),
            "chunks": len(chunks),
        }

        return {
            "filename": filename or os.path.basename(temp_path),
            "documents": len(docs),
            "chunks": len(chunks),
        }
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

# -------------------
# 3. Tools
# -------------------
@tool
def search_tool(input: str) -> str:
    """This is a search tool take a text as input and return the list of text from the real time websearch's data."""
    try:
        from tavily import TavilyClient
        import os
        
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            return "The web search service (Tavily) is currently unavailable because the TAVILY_API_KEY environment variable is missing. Please ask the user to configure it."
            
        client = TavilyClient(api_key=api_key)
        # Using advanced search depth provides comprehensive multi-page context
        response = client.search(query=input, search_depth="advanced", max_results=4)
        
        results = response.get("results", [])
        if not results:
            return "No web search results were found for this specific query."
            
        formatted_results = []
        for result in results:
            formatted_results.append(f"Title: {result.get('title', 'No title')}\nContent: {result.get('content', 'No content')}\nURL: {result.get('url', 'No link')}")
        return "\n--- Result Context ---\n".join(formatted_results)
    except Exception as e:
        return f"The web search service is currently experiencing high traffic or encountered an error. Technical details: {str(e)}"


#now lets add the language translation tool in it 
@tool 
def language_translation(text: str, target_language: str) -> str:
    """Translate text to the target language.
    the target language should be from the following list and use corresponding value symbol for the language translation
    languages={'Afrikaans': 'af', 'Albanian': 'sq', 'Amharic': 'am', 'Arabic': 'ar', 'Armenian': 'hy', 'Azerbaijani': 'az', 'Basque': 'eu', 'Belarusian': 'be', 'Bengali': 'bn', 'Bosnian': 'bs', 'Bulgarian': 'bg', 'Catalan': 'ca', 'Cebuano': 'ceb', 'Chichewa': 'ny', 'Chinese (simplified)': 'zh-CN', 'Chinese (traditional)': 'zh-TW', 'Corsican': 'co', 'Croatian': 'hr', 'Czech': 'cs', 'Danish': 'da', 'Dutch': 'nl', 'English': 'en', 'Esperanto': 'eo', 'Estonian': 'et', 'Filipino': 'tl', 'Finnish': 'fi', 'French': 'fr', 'Frisian': 'fy', 'Galician': 'gl', 'Georgian': 'ka', 'German': 'de', 'Greek': 'el', 'Gujarati': 'gu', 'Haitian creole': 'ht', 'Hausa': 'ha', 'Hawaiian': 'haw', 'Hebrew': 'he', 'Hindi': 'hi', 'Hmong': 'hmn', 'Hungarian': 'hu', 'Icelandic': 'is', 'Igbo': 'ig', 'Indonesian': 'id', 'Irish': 'ga', 'Italian': 'it', 'Japanese': 'ja', 'Javanese': 'jw', 'Kannada': 'kn', 'Kazakh': 'kk', 'Khmer': 'km', 'Korean': 'ko', 'Kurdish (kurmanji)': 'ku', 'Kyrgyz': 'ky', 'Lao': 'lo', 'Latin': 'la', 'Latvian': 'lv', 'Lithuanian': 'lt', 'Luxembourgish': 'lb', 'Macedonian': 'mk', 'Malagasy': 'mg', 'Malay': 'ms', 'Malayalam': 'ml', 'Maltese': 'mt', 'Maori': 'mi', 'Marathi': 'mr', 'Mongolian': 'mn', 'Myanmar (burmese)': 'my', 'Nepali': 'ne', 'Norwegian': 'no', 'Odia': 'or', 'Pashto': 'ps', 'Persian': 'fa', 'Polish': 'pl', 'Portuguese': 'pt', 'Punjabi': 'pa', 'Romanian': 'ro', 'Russian': 'ru', 'Samoan': 'sm', 'Scots gaelic': 'gd', 'Serbian': 'sr', 'Sesotho': 'st', 'Shona': 'sn', 'Sindhi': 'sd', 'Sinhala': 'si', 'Slovak': 'sk', 'Slovenian': 'sl', 'Somali': 'so', 'Spanish': 'es', 'Sundanese': 'su', 'Swahili': 'sw', 'Swedish': 'sv', 'Tajik': 'tg', 'Tamil': 'ta', 'Telugu': 'te', 'Thai': 'th', 'Turkish': 'tr', 'Ukrainian': 'uk', 'Urdu': 'ur', 'Uyghur': 'ug', 'Uzbek': 'uz', 'Vietnamese': 'vi', 'Welsh': 'cy', 'Xhosa': 'xh', 'Yiddish': 'yi', 'Yoruba': 'yo', 'Zulu': 'zu'}
"""
    
    return GoogleTranslator(source='auto', target=target_language).translate(text)

@tool 
def get_current_date_and_time() -> str: 
    """Get the current date and time."""
    from datetime import datetime
    
    now = datetime.now()
    return f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}"
@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform basic math operations. Use this tool to calculate:
    - add: addition
    - sub: subtraction
    - mul: multiplication
    - div: division
    Returns the result of the operation.
    """
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero is not allowed"}
            result = first_num / second_num
        else:
            return {"error": f"Unsupported operation '{operation}'"}

        return {
            "first_num": first_num,
            "second_num": second_num,
            "operation": operation,
            "result": result,
        }
    except Exception as e:
        return {"error": str(e)}

@tool
def get_stock_price(symbol: str) -> dict:
    """
    Get the latest stock price for a company symbol.
    Provide the stock symbol (e.g., AAPL, TSLA, GOOGL).
    Returns current price and trading information.
    """
    url = (
        "https://www.alphavantage.co/query"
        f"?function=GLOBAL_QUOTE&symbol={symbol}&apikey=C9PE94QUEW9VWGFM"
    )
    r = requests.get(url)
    return r.json()

@tool 
def get_weather(location: str) -> dict:
    """Fetch the current weather for a given city using the openweather api"""
    api_key = os.environ['WEATHER_API_KEY']
    url = f"https://api.weatherapi.com/v1/current.json"
    params = {
        "key": api_key,
        "q": location,
        "aqi": "no"
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data

@tool
def currency_conversion(amount: float, from_currency_code: str, to_currency_code: str) -> dict:
    """
    Fetch realtime rates and convert amount between currency codes (e.g., 'USD', 'INR').
    """
    try:
        from_cc = (from_currency_code or "").upper()
        to_cc = (to_currency_code or "").upper()
        if not from_cc or not to_cc:
            return {"error": "Missing currency code"}
        if from_cc == to_cc:
            return {
                "from_currency_code": from_cc,
                "to_currency_code": to_cc,
                "amount": amount,
                "output_value": round(amount, 2),
                "rate": 1.0,
            }

        url = f"https://api.frankfurter.dev/v1/latest?base={from_cc}&symbols={to_cc}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return {"error": f"API request failed with status {resp.status_code}"}

        data = resp.json()
        rate = data.get("rates", {}).get(to_cc)
        if rate is None:
            return {"error": "Invalid currency code or API returned no rate", "api_response": data}

        return {
            "from_currency_code": from_cc,
            "to_currency_code": to_cc,
            "amount": amount,
            "rate": rate,
            "output_value": round(amount * rate, 2),
        }
    except requests.RequestException as e:
        return {"error": "Request failed", "details": str(e)}
    except Exception as e:
        return {"error": "Unexpected error", "details": str(e)}

tools = [currency_conversion, search_tool, language_translation,get_stock_price, calculator, get_weather, get_current_date_and_time]

# -------------------
# 4. State
# -------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# -------------------
# 5. Nodes
# -------------------
def chat_node(state: ChatState, config=None):
    """LLM node that may answer or request a tool call."""
    thread_id = None
    if config and isinstance(config, dict):
        thread_id = config.get("configurable", {}).get("thread_id")

    # Create a custom rag_tool with thread_id bound
    @tool
    def rag_tool_with_thread(query: str) -> dict:
        """
        Search and retrieve relevant information from the uploaded PDF document.
        Use this tool ONLY if the user is asking about a specific document they have uploaded.
        If no document is uploaded, do NOT use this tool.
        """
        retriever = _get_retriever(thread_id if thread_id else None)
        if retriever is None:
            return {
                "error": "No document has been uploaded for this conversation yet. Please tell the user to upload a PDF if they want to ask questions about a document. Otherwise, answer the user's question directly without using this tool.",
                "status": "no_document_uploaded"
            }

        result = retriever.invoke(query)
        context = [doc.page_content for doc in result]
        metadata = [doc.metadata for doc in result]

        return {
            "query": query,
            "context": context,
            "metadata": metadata,
            "source_file": _THREAD_METADATA.get(str(thread_id) if thread_id else "", {}).get("filename"),
        }

    # Check if document is available for this thread
    has_document = _get_retriever(thread_id if thread_id else None) is not None
    
    # Build System Prompt
    system_base = (
        "You are a helpful AI assistant built by Aashish Kumar Saini, a Data Scientist from Alwar, Rajasthan. "
        "IDENTITY: If asked about your creator, always say: 'I was built by Aashish Kumar Saini, a Data Scientist from Alwar.' "
        "CRITICAL: Be concise. Only use tools when explicitly needed. For greetings, answer naturally without tools."
    )
    
    if has_document:
        tools_with_thread = [currency_conversion, search_tool,language_translation, get_stock_price, calculator, get_current_date_and_time, rag_tool_with_thread, get_weather]
        system_content = f"{system_base} You can answer questions about uploaded documents using 'rag_tool_with_thread'."
    else:
        tools_with_thread = [currency_conversion, search_tool,language_translation, get_stock_price, calculator, get_current_date_and_time, get_weather]
        system_content = system_base
    
    llm_with_thread_tools = llm.bind_tools(tools_with_thread)
    system_message = SystemMessage(content=system_content)
    
    # Limit message history to last 10 messages to avoid token limit issues
    history = state["messages"][-10:] if len(state["messages"]) > 10 else state["messages"]
    
    messages = [system_message, *history]
    try:
        response = llm_with_thread_tools.invoke(messages, config=config)
    except Exception as e:
        print(f"[ERROR] LLM invocation failed: {traceback.format_exc()}")
        return {"messages": [AIMessage(content="I encountered an error while processing your request. Please try again.")]}
    
    return {"messages": [response]}

def tool_node(state: ChatState, config=None):
    """Execute tools with thread_id context."""
    thread_id = None
    if config and isinstance(config, dict):
        thread_id = config.get("configurable", {}).get("thread_id")
    
    # Check if document is available for this thread
    has_document = _get_retriever(thread_id if thread_id else None) is not None
    
    # Create rag_tool with thread context
    @tool
    def rag_tool_with_thread(query: str) -> dict:
        """
        Search and retrieve relevant information from the uploaded PDF document.
        Use this tool ONLY if the user is asking about a specific document they have uploaded.
        If no document is uploaded, do NOT use this tool.
        """
        retriever = _get_retriever(thread_id if thread_id else None)
        if retriever is None:
            return {
                "error": "No document has been uploaded for this conversation yet. Please tell the user to upload a PDF if they want to ask questions about a document. Otherwise, answer the user's question directly without using this tool.",
                "status": "no_document_uploaded"
            }

        result = retriever.invoke(query)
        context = [doc.page_content for doc in result]
        metadata = [doc.metadata for doc in result]

        return {
            "query": query,
            "context": context,
            "metadata": metadata,
            "source_file": _THREAD_METADATA.get(str(thread_id) if thread_id else "", {}).get("filename"),
        }
    
    # Create tool node with thread-aware rag tool - only include if document exists
    if has_document:
        tools_with_thread = [currency_conversion, search_tool,language_translation, get_current_date_and_time, get_stock_price, calculator, rag_tool_with_thread, get_weather]
    else:
        tools_with_thread = [currency_conversion, search_tool,language_translation, get_current_date_and_time, get_stock_price, calculator, get_weather]
    
    tool_node_executor = ToolNode(tools_with_thread)
    
    return tool_node_executor.invoke(state, config=config)

# -------------------
# 6. Checkpointer
# -------------------
conn = sqlite3.connect(database="chatbot_production.db", check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)

# -------------------
# 7. Graph
# -------------------
graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition)
graph.add_edge("tools", "chat_node")

chatbot = graph.compile(checkpointer=checkpointer)

# -------------------
# 8. Helpers
# -------------------   
def retrieve_all_threads():
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])
    return list(all_threads)

def thread_has_document(thread_id: str) -> bool:
    return str(thread_id) in _THREAD_RETRIEVERS

def thread_document_metadata(thread_id: str) -> dict:
    return _THREAD_METADATA.get(str(thread_id), {})

def get_indexed_documents(thread_id: str) -> dict:
    """Get info about indexed documents for a thread."""
    thread_id_str = str(thread_id)
    return {
        "thread_id": thread_id_str,
        "has_document": thread_id_str in _THREAD_RETRIEVERS,
        "metadata": _THREAD_METADATA.get(thread_id_str, {}),
        "all_indexed_threads": list(_THREAD_RETRIEVERS.keys())
    }
