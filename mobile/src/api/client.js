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

function normalizeOwnerEmail(ownerEmail) {
  return String(ownerEmail || '').trim().toLowerCase();
}

function withOwnerHeaders(ownerEmail, headers = {}) {
  const normalized = normalizeOwnerEmail(ownerEmail);
  if (!normalized) {
    return headers;
  }

  return {
    ...headers,
    'X-User-Email': normalized,
  };
}

async function readJson(response) {
  const text = await response.text();
  if (!text) {
    return { data: null, rawText: '' };
  }

  try {
    return {
      data: JSON.parse(text),
      rawText: text,
    };
  } catch (_err) {
    return {
      data: null,
      rawText: text,
    };
  }
}

function flattenDetailValue(value) {
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  if (Array.isArray(value)) {
    const nested = value.map(flattenDetailValue).filter(Boolean);
    return nested.length ? nested.join(', ') : '';
  }
  if (value && typeof value === 'object') {
    const nested = Object.entries(value)
      .map(([key, nestedValue]) => {
        const resolved = flattenDetailValue(nestedValue);
        return resolved ? `${key}: ${resolved}` : '';
      })
      .filter(Boolean);
    return nested.length ? nested.join(' | ') : '';
  }
  return '';
}

function extractErrorMessage(data, rawText, fallbackMessage, status) {
  const directMessage = flattenDetailValue(data?.detail);
  if (directMessage) {
    return directMessage;
  }

  const wrappedMessage = flattenDetailValue(data?.error?.message);
  if (wrappedMessage && wrappedMessage !== 'Request failed.') {
    return wrappedMessage;
  }

  const wrappedDetails = flattenDetailValue(data?.error?.details);
  if (wrappedDetails) {
    return wrappedDetails;
  }

  if (typeof rawText === 'string' && rawText.trim()) {
    const compact = rawText.replace(/\s+/g, ' ').trim();
    return compact.length > 220 ? `${compact.slice(0, 217)}...` : compact;
  }

  return `${fallbackMessage} with ${status}`;
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
  const { data, rawText } = await readJson(response);

  if (!response.ok) {
    throw new Error(extractErrorMessage(data, rawText, fallbackMessage, response.status));
  }

  if (!data && rawText) {
    throw new Error(`Unexpected backend response from ${path}. Expected JSON but received something else.`);
  }

  return data;
}

export async function patchJob(jobId, payload, ownerEmail) {
  return requestJson(
    `/jobs/${jobId}/`,
    {
      method: 'PATCH',
      headers: withOwnerHeaders(ownerEmail, {
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify(payload || {}),
    },
    'Job update failed'
  );
}

export async function saveJobAnnotations(jobId, annotations, ownerEmail) {
  return patchJob(jobId, { annotations: Array.isArray(annotations) ? annotations : [] }, ownerEmail);
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

export async function fetchJobs(ownerEmail) {
  const data = await requestJson(
    '/jobs/',
    {
      headers: withOwnerHeaders(ownerEmail),
    },
    'Backend request failed'
  );
  return Array.isArray(data) ? data : [];
}

export async function createJobWithImage({ name, description, imageUri, imageName, mimeType, ownerEmail }) {
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
      headers: withOwnerHeaders(ownerEmail),
      body: form,
    },
    'Job creation failed'
  );
}

export async function startJob(jobId, ownerEmail) {
  return requestJson(
    `/jobs/${jobId}/start/`,
    {
      method: 'POST',
      headers: withOwnerHeaders(ownerEmail),
    },
    'Job start failed'
  );
}

export async function deleteJob(jobId, ownerEmail) {
  const response = await request(`/jobs/${jobId}/`, {
    method: 'DELETE',
    headers: withOwnerHeaders(ownerEmail),
  });

  if (!response.ok) {
    throw new Error(`Job delete failed with ${response.status}`);
  }

  return true;
}
