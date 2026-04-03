import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { chatService } from '../services/chatService';
import { Conversation, Message, Document, ChatStreamEvent } from '../types';
import { 
  MessageSquare, 
  Plus, 
  Upload, 
  Moon, 
  Sun, 
  LogOut, 
  Trash2, 
  FileText,
  Loader2,
  Send,
  Wrench
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const ChatPage: React.FC = () => {
  const { user, logout } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false); // eslint-disable-line @typescript-eslint/no-unused-vars
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentTool, setCurrentTool] = useState<string | null>(null);
  const [streamingMessage, setStreamingMessage] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const selectedConversationIdRef = useRef<number | null>(null);
  const messageInputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    if (selectedConversation) {
      if (selectedConversationIdRef.current !== selectedConversation.id) {
        setMessages([]);
        setDocuments([]);
      }
      selectedConversationIdRef.current = selectedConversation.id;
      loadConversation(selectedConversation.id);
    } else {
      selectedConversationIdRef.current = null;
    }
  }, [selectedConversation]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  useEffect(() => {
    if (selectedConversation) {
      messageInputRef.current?.focus();
    }
  }, [selectedConversation]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadConversations = async () => {
    try {
      const convs = await chatService.getConversations();
      setConversations(convs);
      
      if (convs.length > 0 && !selectedConversation) {
        setSelectedConversation(convs[0]);
      }

      const selectedId = selectedConversationIdRef.current;
      if (selectedId != null) {
        const updatedSelected = convs.find(c => c.id === selectedId);
        if (updatedSelected) {
          setSelectedConversation(updatedSelected);
        }
      }
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConversation = async (conversationId: number) => {
    if (selectedConversationIdRef.current !== conversationId) return;
    
    try {
      const conversationDetail = await chatService.getConversation(conversationId);
      // Ensure we haven't switched conversations while waiting for the request
      if (selectedConversationIdRef.current === conversationId) {
        setMessages(prev => {
          // If backend has no messages, keep our local greeting
          if (conversationDetail.messages.length === 0) return prev;
          // Otherwise, sync with backend (this clears local temporary IDs to prevent duplicates)
          return conversationDetail.messages;
        });
        setDocuments(prev => {
          const merged = [...prev];
          conversationDetail.documents.forEach(doc => {
            if (!merged.find(m => m.id === doc.id)) {
              merged.push(doc);
            }
          });
          return merged;
        });
      }
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const createNewConversation = async () => {
    try {
      const newConv = await chatService.createConversation('New Chat');
      setConversations(prev => [newConv, ...prev]);
      selectedConversationIdRef.current = newConv.id;
      setSelectedConversation(newConv);
      setMessages([]);
      setDocuments([]);
      return newConv;
    } catch (error) {
      console.error('Failed to create conversation:', error);
      throw error;
    }
  };

  const deleteConversation = async (conversationId: number) => {
    try {
      await chatService.deleteConversation(conversationId);
      
      setConversations(prev => {
        const updatedConvs = prev.filter(c => c.id !== conversationId);
        
        // If we deleted the currently selected conversation
        if (selectedConversationIdRef.current === conversationId) {
          const nextSelected = updatedConvs.length > 0 ? updatedConvs[0] : null;
          selectedConversationIdRef.current = nextSelected?.id || null;
          setSelectedConversation(nextSelected);
          
          setMessages([]);
          setDocuments([]);
        }
        
        return updatedConvs;
      });
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.pdf')) {
      alert('Please upload a PDF file');
      return;
    }

    try {
      setIsUploading(true);
      let contextConv = selectedConversation;
      let isNew = false;
      
      // If no conversation is selected (welcome screen), create one
      if (!contextConv) {
        contextConv = await createNewConversation();
        selectedConversationIdRef.current = contextConv.id;
        isNew = true;
      }

      const document = await chatService.uploadDocument(contextConv.id, file);
      
      // Update sidebar message count for contextConv
      setConversations(prev => prev.map(c => 
        c.id === contextConv!.id ? { ...c, message_count: c.message_count } : c
      ));

      if (isNew) {
        setDocuments([document]);
      } else {
        setDocuments(prev => [...prev, document]);
      }

      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      console.error('Failed to upload document:', error);
      let message = 'Failed to upload document';
      if (axios.isAxiosError(error)) {
        const detail = (error.response?.data as any)?.detail;
        if (typeof detail === 'string' && detail.trim()) {
          message = detail;
        }
      } else if (error instanceof Error && error.message) {
        message = error.message;
      }
      alert(message);
    } finally {
      setIsUploading(false);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isStreaming) return;

    let conversation = selectedConversation;
    
    if (!conversation) {
      conversation = await createNewConversation();
    }

    const messageToSend = inputMessage;

    const userMessage: Message = {
      id: Date.now(),
      content: messageToSend,
      role: 'user',
      created_at: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsStreaming(true);
    setStreamingMessage('');

    try {
      const stream = await chatService.sendMessage(conversation.id, messageToSend);
      const reader = stream.getReader();

      let assistantText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const event: ChatStreamEvent = value;

        if (event.type === 'tool_start') {
          setCurrentTool(event.tool || null);
        } else if (event.type === 'tool_end') {
          setCurrentTool(null);
        } else if (event.type === 'content' && event.content) {
          assistantText += event.content;
          setStreamingMessage(assistantText);
        } else if (event.type === 'end') {
          const assistantMessage: Message = {
            id: Date.now(),
            content: assistantText,
            role: 'assistant',
            created_at: new Date().toISOString(),
          };
          setMessages(prev => [...prev, assistantMessage]);
          setStreamingMessage('');
          setCurrentTool(null);
          setIsStreaming(false);
          loadConversations(); // Refresh conversation list
          break; // This will exit the loop and naturally close the stream
        }
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      setIsStreaming(false);
      setCurrentTool(null);
      setStreamingMessage('');
    }
  };

  const renderMessageContent = (content: string, role: string) => {
    return (
      <div className={`markdown-content ${role === 'user' ? 'text-white' : 'text-gray-900 dark:text-gray-100'}`}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({...props}) => <h1 className="text-2xl font-bold mb-4" {...props} />,
            h2: ({...props}) => <h2 className="text-xl font-bold mb-3" {...props} />,
            h3: ({...props}) => <h3 className="text-lg font-bold mb-2" {...props} />,
            ul: ({...props}) => <ul className="list-disc pl-5 mb-4 space-y-1" {...props} />,
            ol: ({...props}) => <ol className="list-decimal pl-5 mb-4 space-y-1" {...props} />,
            li: ({...props}) => <li className="mb-1" {...props} />,
            p: ({...props}) => <p className="mb-4 last:mb-0" {...props} />,
            code: ({...props}) => (
              <code className="bg-gray-200 dark:bg-gray-800 rounded px-1 py-0.5 text-sm font-mono" {...props} />
            ),
            pre: ({...props}) => (
              <pre className="bg-gray-200 dark:bg-gray-800 rounded p-3 mb-4 overflow-x-auto" {...props} />
            ),
            blockquote: ({...props}) => (
              <blockquote className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 italic mb-4" {...props} />
            ),
            a: ({...props}) => (
              <a className="text-blue-600 dark:text-blue-400 hover:underline" target="_blank" rel="noopener noreferrer" {...props} />
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    );
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex h-screen bg-white dark:bg-chat-bg">
      {/* Sidebar */}
      <div className="w-80 bg-gray-50 dark:bg-sidebar-bg border-r border-gray-200 dark:border-border-color flex flex-col">
        {/* Sidebar Header */}
        <div className="p-4 border-b border-gray-200 dark:border-border-color">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <MessageSquare className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              <h1 className="text-lg font-semibold text-gray-900 dark:text-white">ChatBot</h1>
            </div>
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-hover-bg transition-colors"
            >
              {isDark ? <Sun className="h-4 w-4 text-gray-600 dark:text-gray-400" /> : <Moon className="h-4 w-4 text-gray-600" />}
            </button>
          </div>
          
          <button
            onClick={createNewConversation}
            className="w-full flex items-center justify-center space-x-2 p-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <Plus className="h-4 w-4" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto p-4">
          <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">Conversations</h2>
          <div className="space-y-2">
            {conversations.map((conversation) => (
              <div
                key={conversation.id}
                className={`p-3 rounded-lg cursor-pointer transition-colors group ${
                  selectedConversation?.id === conversation.id
                    ? 'bg-blue-100 dark:bg-blue-900'
                    : 'hover:bg-gray-100 dark:hover:bg-hover-bg'
                }`}
                onClick={() => setSelectedConversation(conversation)}
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium text-gray-900 dark:text-white truncate">
                    {conversation.title}
                  </h3>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteConversation(conversation.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 dark:hover:bg-red-900 rounded transition-all"
                  >
                    <Trash2 className="h-3 w-3 text-red-600 dark:text-red-400" />
                  </button>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {conversation.message_count} messages
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* User Menu */}
        <div className="p-4 border-t border-gray-200 dark:border-border-color">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="h-8 w-8 bg-blue-600 rounded-full flex items-center justify-center">
                <span className="text-white text-sm font-medium">
                  {user?.username.charAt(0).toUpperCase()}
                </span>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">{user?.username}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">{user?.email}</p>
              </div>
            </div>
            <button
              onClick={logout}
              className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-hover-bg transition-colors"
            >
              <LogOut className="h-4 w-4 text-gray-600 dark:text-gray-400" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Chat Header */}
        <div className="p-4 border-b border-gray-200 dark:border-border-color bg-white dark:bg-chat-bg">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              {selectedConversation ? selectedConversation.title : 'New Chat'}
            </h2>
            {documents.length > 0 && (
              <div className="flex items-center space-x-2 mt-1">
                <FileText className="h-4 w-4 text-green-600 dark:text-green-400" />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {documents.length} document(s) uploaded
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && documents.length === 0 && !isStreaming && (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center p-8 welcome-animation">
              <div className="relative mb-8">
                <div className="absolute inset-0 bg-blue-500/10 blur-3xl rounded-full"></div>
                <div className="relative h-20 w-20 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/20 transform hover:scale-110 transition-transform duration-300">
                  <MessageSquare className="h-10 w-10 text-white" />
                </div>
              </div>
              
              <h2 className="text-4xl font-bold text-gray-900 dark:text-white mb-3">
                Hi {user?.username} 🖐
              </h2>
              <p className="text-gray-500 dark:text-gray-400 text-xl max-w-md mx-auto mb-10">
                I'm your AI assistant. How can I help you today?
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl w-full">
                <button 
                  onClick={() => setInputMessage("What can you do?")}
                  className="p-5 bg-white dark:bg-input-bg border border-gray-200 dark:border-border-color rounded-2xl text-left hover:border-blue-500 hover:shadow-xl hover:shadow-blue-500/5 transition-all duration-300 group"
                >
                  <p className="font-semibold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 mb-1">Capabilities</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Explore my tool integration and features.</p>
                </button>
                <button 
                  onClick={async () => {
                    const botMsg: Message = {
                      id: Date.now(),
                      content: "Please upload a PDF file first so I can analyze it for you! 📄",
                      role: 'assistant',
                      created_at: new Date().toISOString(),
                    };
                    
                    if (!selectedConversation) {
                      await createNewConversation();
                    }
                    setMessages([botMsg]);
                    fileInputRef.current?.click();
                  }}
                  className="p-5 bg-white dark:bg-input-bg border border-gray-200 dark:border-border-color rounded-2xl text-left hover:border-green-500 hover:shadow-xl hover:shadow-green-500/5 transition-all duration-300 group"
                >
                  <p className="font-semibold text-gray-900 dark:text-white group-hover:text-green-600 dark:group-hover:text-green-400 mb-1">Analyze PDF</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Upload documents for context-aware chat.</p>
                </button>
              </div>
            </div>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-3xl p-4 rounded-lg ${
                  message.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 dark:bg-input-bg text-gray-900 dark:text-white'
                }`}
              >
                {renderMessageContent(message.content, message.role)}
              </div>
            </div>
          ))}

          {isStreaming && (
            <div className="flex justify-start">
              <div className="max-w-3xl p-4 rounded-lg bg-gray-100 dark:bg-input-bg text-gray-900 dark:text-white">
                {currentTool && (
                  <div className="flex items-center space-x-2 mb-2 text-sm text-blue-600 dark:text-blue-400">
                    <Wrench className="h-4 w-4 animate-spin" />
                    <span>{currentTool}</span>
                  </div>
                )}
                {renderMessageContent(streamingMessage, 'assistant')}
                <Loader2 className="h-4 w-4 animate-spin mt-2 text-gray-500 dark:text-gray-400" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-gray-200 dark:border-border-color bg-white dark:bg-chat-bg">
          <div className="flex items-end space-x-4">
            {selectedConversation && (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  onChange={handleFileUpload}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  className="p-3 bg-gray-100 dark:bg-input-bg hover:bg-gray-200 dark:hover:bg-hover-bg rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Upload PDF"
                >
                  {isUploading ? (
                    <Loader2 className="h-5 w-5 text-gray-600 dark:text-gray-400 animate-spin" />
                  ) : (
                    <Upload className="h-5 w-5 text-gray-600 dark:text-gray-400" />
                  )}
                </button>
              </>
            )}
            <textarea
              ref={messageInputRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message..."
              className="flex-1 p-3 border border-gray-300 dark:border-border-color rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-input-bg text-gray-900 dark:text-white"
              rows={1}
              disabled={isStreaming}
            />
            <button
              onClick={sendMessage}
              disabled={!inputMessage.trim() || isStreaming}
              className="p-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-lg transition-colors disabled:cursor-not-allowed"
            >
              <Send className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
