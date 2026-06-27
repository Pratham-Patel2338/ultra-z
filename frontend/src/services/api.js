import axios from 'axios';

const baseURL = 'http://127.0.0.1:8000';
const TOKEN_KEY = 'ultra_z_token';
const client = axios.create({ baseURL, timeout: 12000 });

// Attach auth token to every request
client.interceptors.request.use((config) => {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch (err) {
    // ignore
  }
  return config;
});

// Handle 401 globally
client.interceptors.response.use(
  (res) => res,
  (error) => {
    const status = error?.response?.status;
    if (status === 401) {
      try {
        localStorage.removeItem(TOKEN_KEY);
      } catch (e) {
        // ignore
      }
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export async function sendMessage(message) {
  try {
    const response = await client.post('/api/v1/chat', { message });
    return response.data?.response || 'I am ready to chat with you.';
  } catch (error) {
    console.warn('sendMessage failed', error);
    return 'I could not reach the assistant right now. Please try again.';
  }
}

export async function getMemories() {
  try {
    const response = await client.get('/api/v1/memories');
    return response.data || [];
  } catch (error) {
    console.warn('getMemories failed', error);
    return [];
  }
}

export async function getSettings() {
  try {
    const response = await client.get('/api/v1/settings');
    return response.data || {};
  } catch (error) {
    console.warn('getSettings failed', error);
    return {};
  }
}

export async function updateSettings(settings) {
  try {
    const response = await client.put('/api/v1/settings', settings);
    return response.data || settings;
  } catch (error) {
    console.warn('updateSettings failed', error);
    return settings;
  }
}

export async function getStatus() {
  try {
    const response = await client.get('/api/v1/status');
    return response.data || { online: false };
  } catch (error) {
    console.warn('getStatus failed', error);
    return { online: false };
  }
}

export { client };
