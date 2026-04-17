import Constants from 'expo-constants';
import { NativeModules, Platform } from 'react-native';

function detectApiHost() {
  const expoHostCandidates = [
    Constants?.expoConfig?.hostUri,
    Constants?.manifest2?.extra?.expoClient?.hostUri,
    Constants?.manifest?.debuggerHost,
    Constants?.manifest?.hostUri,
  ];

  for (const candidate of expoHostCandidates) {
    if (typeof candidate === 'string' && candidate.length > 0) {
      const host = candidate.split(':')[0];
      if (host) {
        return host;
      }
    }
  }

  const scriptURL = NativeModules?.SourceCode?.scriptURL;
  if (scriptURL) {
    const match = scriptURL.match(/^[a-z]+:\/\/([^/:?#]+)(?::\d+)?/i);
    if (match?.[1]) {
      return match[1];
    }
  }

  if (Platform.OS === 'android') {
    return '10.0.2.2';
  }

  return '127.0.0.1';
}

const API_HOST = detectApiHost();
const API_BASE_URL = `http://${API_HOST}:8000/api`;

export function getApiBaseUrl() {
  return API_BASE_URL;
}

export function getApiHost() {
  return API_HOST;
}

async function readJson(response) {
  const text = await response.text();
  if (!text) {
    return null;
  }
  return JSON.parse(text);
}

function buildNetworkError(err) {
  if (err?.message?.includes('Network request failed')) {
    return new Error(
      `Unable to reach the backend at ${API_BASE_URL}. Make sure your phone and laptop are on the same Wi-Fi and Django is running on 0.0.0.0:8000.`
    );
  }

  return err;
}

export async function testBackendConnection() {
  try {
    const response = await fetch(`${API_BASE_URL}/health/`);
    const data = await readJson(response);

    if (!response.ok) {
      throw new Error(`Backend request failed with ${response.status}`);
    }

    return {
      ok: true,
      apiBaseUrl: API_BASE_URL,
      apiHost: API_HOST,
      data,
    };
  } catch (err) {
    const parsed = buildNetworkError(err);
    return {
      ok: false,
      apiBaseUrl: API_BASE_URL,
      apiHost: API_HOST,
      error: parsed.message || 'Unable to reach backend',
    };
  }
}

export async function fetchJobs() {
  try {
    const response = await fetch(`${API_BASE_URL}/jobs/`);
    if (!response.ok) {
      throw new Error(`Backend request failed with ${response.status}`);
    }
    const data = await readJson(response);
    return Array.isArray(data) ? data : [];
  } catch (err) {
    throw buildNetworkError(err);
  }
}

export async function createJobWithImage({ name, description, imageUri, imageName, mimeType }) {
  try {
    const form = new FormData();
    if (name) {
      form.append('name', name);
    }
    if (description) {
      form.append('description', description);
    }
    form.append('original_image', {
      uri: imageUri,
      name: imageName || 'floorplan.jpg',
      type: mimeType || 'image/jpeg',
    });

    const response = await fetch(`${API_BASE_URL}/jobs/`, {
      method: 'POST',
      body: form,
    });

    const data = await readJson(response);
    if (!response.ok) {
      throw new Error(data?.detail || `Job creation failed with ${response.status}`);
    }

    return data;
  } catch (err) {
    throw buildNetworkError(err);
  }
}

export async function startJob(jobId) {
  try {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/start/`, {
      method: 'POST',
    });

    const data = await readJson(response);
    if (!response.ok) {
      throw new Error(data?.detail || `Job start failed with ${response.status}`);
    }

    return data;
  } catch (err) {
    throw buildNetworkError(err);
  }
}

export async function deleteJob(jobId) {
  try {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(`Job delete failed with ${response.status}`);
    }

    return true;
  } catch (err) {
    throw buildNetworkError(err);
  }
}
