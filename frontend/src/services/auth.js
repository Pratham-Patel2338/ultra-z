const BASE_URL = 'http://127.0.0.1:8000';
const TOKEN_KEY = 'ultra_z_token';

export async function login(pin) {
  try {
    const res = await fetch(`${BASE_URL}/api/v1/auth/pin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin }),
    });

    if (!res.ok) {
      return false;
    }

    const data = await res.json();
    if (data?.access_token) {
      localStorage.setItem(TOKEN_KEY, data.access_token);
      return true;
    }
    return false;
  } catch (err) {
    console.warn('Auth login error', err);
    throw err;
  }
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function isAuthenticated() {
  return !!getToken();
}
