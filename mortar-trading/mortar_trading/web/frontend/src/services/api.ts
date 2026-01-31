import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const storage = localStorage.getItem('mortar-auth');
  if (storage) {
    const { state } = JSON.parse(storage);
    if (state?.token) {
      config.headers.Authorization = `Bearer ${state.token}`;
    }
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Clear auth state on 401
      localStorage.removeItem('mortar-auth');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;

// API functions
export const tradingApi = {
  // Status
  getStatus: () => api.get('/status'),
  getHealth: () => api.get('/health'),

  // Account
  getAccount: () => api.get('/account'),

  // Positions
  getPositions: () => api.get('/positions'),
  getPosition: (symbol: string) => api.get(`/positions/${symbol}`),
  closePosition: (symbol: string) => api.delete(`/positions/${symbol}`),

  // Orders
  getOrders: (status?: string) => api.get('/orders', { params: { status } }),
  createOrder: (order: any) => api.post('/orders', order),
  cancelOrder: (orderId: string) => api.delete(`/orders/${orderId}`),

  // Master Input
  getMasterInput: () => api.get('/master-input'),
  updateMasterInput: (direction: string, confidence: string) =>
    api.put('/master-input', { direction, confidence }),
  updateKeyLevels: (support?: number, resistance?: number) =>
    api.put('/master-input/levels', { support, resistance }),

  // Risk
  getRiskStatus: () => api.get('/risk'),

  // Performance
  getPerformance: () => api.get('/performance'),

  // Market Data
  getSentiment: (symbol: string) => api.get(`/sentiment/${symbol}`),
  getVolatility: (symbol: string) => api.get(`/volatility/${symbol}`),
  getRegime: (symbol: string) => api.get(`/regime/${symbol}`),

  // Settings
  getSettings: () => api.get('/settings'),
};

// WebSocket connection
export class TradingWebSocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private listeners: Map<string, Set<(data: any) => void>> = new Map();

  connect(token: string) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/stream?token=${token}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.emit('connected', {});
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.emit(data.type, data);
        if (data.event_type) {
          this.emit(data.event_type, data);
        }
      } catch (e) {
        console.error('WebSocket message parse error:', e);
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.emit('disconnected', {});
      this.tryReconnect(token);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  private tryReconnect(token: string) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        console.log(`Reconnecting... (attempt ${this.reconnectAttempts})`);
        this.connect(token);
      }, 2000 * this.reconnectAttempts);
    }
  }

  subscribe(channels: string[]) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'subscribe', channels }));
    }
  }

  unsubscribe(channels: string[]) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'unsubscribe', channels }));
    }
  }

  on(event: string, callback: (data: any) => void) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  off(event: string, callback: (data: any) => void) {
    this.listeners.get(event)?.delete(callback);
  }

  private emit(event: string, data: any) {
    this.listeners.get(event)?.forEach((callback) => callback(data));
  }

  disconnect() {
    this.ws?.close();
  }
}

export const tradingWs = new TradingWebSocket();
