import { api } from './api';
import { Conversation, ConversationDetail, Message, Document, ChatStreamEvent } from '../types';

export const chatService = {
  async getConversations(): Promise<Conversation[]> {
    const response = await api.get('/conversations');
    return response.data;
  },

  async createConversation(title: string): Promise<Conversation> {
    const formData = new FormData();
    formData.append('title', title);
    
    const response = await api.post('/conversations', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },

  async getConversation(conversationId: number): Promise<ConversationDetail> {
    const response = await api.get(`/conversations/${conversationId}`);
    return response.data;
  },

  async deleteConversation(conversationId: number): Promise<void> {
    await api.delete(`/conversations/${conversationId}`);
  },

  async uploadDocument(conversationId: number, file: File): Promise<Document> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post(`/conversations/${conversationId}/upload`, formData, {
      headers: {
        'Accept': 'application/json',
      },
    });
    return response.data;
  },

  async sendMessage(conversationId: number, message: string): Promise<ReadableStream<ChatStreamEvent>> {
    const API_BASE_URL = (api.defaults.baseURL || 'http://localhost:8000').toString();
    const token = localStorage.getItem('token');

    const body = new URLSearchParams();
    body.set('message', message);

    const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body,
    });

    if (response.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    if (!response.ok) {
      throw new Error(`Failed to send message (${response.status})`);
    }

    if (!response.body) {
      throw new Error('No response body');
    }

    return this.createStream(response.body);
  },

  createStream(responseBody: ReadableStream<Uint8Array>): ReadableStream<ChatStreamEvent> {
    const reader = responseBody.getReader();
    const decoder = new TextDecoder();

    return new ReadableStream({
      async start(controller) {
        try {
          let buffer = '';
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  controller.enqueue(data);
                  
                  // Don't close on 'end' event, let the frontend handle it
                  // The frontend will handle the 'end' event and we'll close naturally
                } catch (e) {
                  // Ignore parsing errors for malformed chunks
                }
              }
            }
          }

          if (buffer.trim()) {
            const leftoverLines = buffer.split('\n');
            for (const line of leftoverLines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  controller.enqueue(data);
                } catch (e) {
                  // Ignore parsing errors
                }
              }
            }
          }

          controller.close();
        } catch (error) {
          controller.error(error);
        }
      },
    });
  },
};
