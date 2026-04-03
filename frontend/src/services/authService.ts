import { api } from './api';
import { User, AuthResponse } from '../types';

export const authService = {
  async login(identifier: string, password: string): Promise<AuthResponse> {
    const formData = new FormData();
    // Backend uses OAuth2PasswordRequestForm -> field name must be 'username'
    formData.append('username', identifier);
    formData.append('password', password);
    
    const response = await api.post('/auth/token', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },

  async forgotPassword(email: string): Promise<{ message: string }> {
    const formData = new FormData();
    formData.append('email', email);
    const response = await api.post('/auth/forgot-password', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },

  async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    const formData = new FormData();
    formData.append('token', token);
    formData.append('new_password', newPassword);
    const response = await api.post('/auth/reset-password', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },

  async register(username: string, email: string, password: string): Promise<AuthResponse> {
    const response = await api.post('/auth/register', {
      username,
      email,
      password,
    });
    return response.data;
  },

  async getCurrentUser(): Promise<User> {
    const response = await api.get('/auth/me');
    return response.data;
  },
};
