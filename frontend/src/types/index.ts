export interface User {
  id: number;
  username: string;
  email: string;
  created_at: string;
}

export interface Conversation {
  id: number;
  thread_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface Message {
  id: number;
  content: string;
  role: 'user' | 'assistant';
  created_at: string;
}

export interface Document {
  id: number;
  filename: string;
  chunks_count: number;
  pages_count: number;
  indexed_at: string;
}

export interface ConversationDetail {
  id: number;
  thread_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
  documents: Document[];
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface ChatStreamEvent {
  type: 'content' | 'tool_start' | 'tool_end' | 'end';
  content?: string;
  tool?: string;
  result?: string;
}
