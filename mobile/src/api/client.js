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
    if (typeof candidate !== 'string' || candidate.length === 0) {
      continue;
    }

    const host = candidate.split(':')[0];
    if (host) {
      return host;
    }
  }

  const scriptURL = NativeModules?.SourceCode?.scriptURL;
  if (scriptURL) {
    const match = scriptURL.match(/^[a-z]+:\/\/([^/:?#]+)(?::\d+)?/i);
    if (match?.[1]) {
      return match[1];
    }
  }

  return Platform.OS === 'android' ? '10.0.2.2' : '127.0.0.1';
}

const API_HOST = detectApiHost();
const API_BASE_URL = `http://${API_HOST}:8000/api`;

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

async function request(path, options) {
  try {
    return await fetch(`${API_BASE_URL}${path}`, options);
  } catch (err) {
    throw buildNetworkError(err);
  }
}

async function requestJson(path, options, fallbackMessage) {
  const response = await request(path, options);
  const data = await readJson(response);

  if (!response.ok) {
    throw new Error(data?.detail || `${fallbackMessage} with ${response.status}`);
  }

  return data;
}

export async function patchJob(jobId, payload) {
  return requestJson(
    `/jobs/${jobId}/`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload || {}),
    },
    'Job update failed'
  );
}

export async function saveJobAnnotations(jobId, annotations) {
  return patchJob(jobId, { annotations: Array.isArray(annotations) ? annotations : [] });
}

export async function testBackendConnection() {
  try {
    const data = await requestJson('/health/', undefined, 'Backend request failed');
    return {
      ok: true,
      apiBaseUrl: API_BASE_URL,
      apiHost: API_HOST,
      data,
    };
  } catch (err) {
    return {
      ok: false,
      apiBaseUrl: API_BASE_URL,
      apiHost: API_HOST,
      error: err.message || 'Unable to reach backend',
    };
  }
}

export async function fetchJobs() {
  const data = await requestJson('/jobs/', undefined, 'Backend request failed');
  return Array.isArray(data) ? data : [];
}

export async function createJobWithImage({ name, description, imageUri, imageName, mimeType }) {
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

  return requestJson(
    '/jobs/',
    {
      method: 'POST',
      body: form,
    },
    'Job creation failed'
  );
}

export async function startJob(jobId) {
  return requestJson(
    `/jobs/${jobId}/start/`,
    {
      method: 'POST',
    },
    'Job start failed'
  );
}

export async function deleteJob(jobId) {
  const response = await request(`/jobs/${jobId}/`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`Job delete failed with ${response.status}`);
  }

  return true;
}
