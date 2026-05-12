import * as FileSystem from 'expo-file-system';

function jobAnnotationsPath(jobId) {
  const safe = String(jobId ?? 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
  return `${FileSystem.documentDirectory}s2fp_annotations_job_${safe}.json`;
}

export async function loadLocalAnnotations(jobId) {
  try {
    const path = jobAnnotationsPath(jobId);
    const info = await FileSystem.getInfoAsync(path);
    if (!info.exists) {
      return null;
    }
    const raw = await FileSystem.readAsStringAsync(path);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : null;
  } catch (_err) {
    return null;
  }
}

export async function saveLocalAnnotations(jobId, annotations) {
  const path = jobAnnotationsPath(jobId);
  const payload = JSON.stringify(Array.isArray(annotations) ? annotations : [], null, 2);
  await FileSystem.writeAsStringAsync(path, payload, { encoding: FileSystem.EncodingType.UTF8 });
  return path;
}

