import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../services/api';

interface User {
  id: string;
  username: string;
  email: string | null;
  full_name: string | null;
  role: string;
}

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      user: null,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.post('/auth/login', { username, password });
          const { access_token, refresh_token } = response.data;

          set({
            token: access_token,
            refreshToken: refresh_token,
            isLoading: false
          });

          // Fetch user data
          await get().fetchUser();
        } catch (error: any) {
          set({
            isLoading: false,
            error: error.response?.data?.detail || 'Login failed'
          });
          throw error;
        }
      },

      logout: () => {
        set({ token: null, refreshToken: null, user: null });
      },

      fetchUser: async () => {
        try {
          const response = await api.get('/auth/me');
          set({ user: response.data });
        } catch (error) {
          // Token might be invalid, logout
          set({ token: null, refreshToken: null, user: null });
        }
      },
    }),
    {
      name: 'mortar-auth',
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken
      }),
    }
  )
);
