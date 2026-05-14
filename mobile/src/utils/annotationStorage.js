import { File, Paths } from 'expo-file-system';
import * as FileSystemLegacy from 'expo-file-system/legacy';

function jobAnnotationsFile(jobId) {
  const safe = String(jobId ?? 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
  return new File(Paths.document, `s2fp_annotations_job_${safe}.json`);
}

function jobAnnotatedPreviewFile(jobId) {
  const safe = String(jobId ?? 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
  return new File(Paths.document, `s2fp_annotations_preview_${safe}.png`);
}

export async function loadLocalAnnotations(jobId) {
  try {
    const file = jobAnnotationsFile(jobId);
    if (!file.exists) {
      return null;
    }

    const raw = await file.text();
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
  const file = jobAnnotationsFile(jobId);
  const payload = JSON.stringify(Array.isArray(annotations) ? annotations : [], null, 2);

  if (!file.exists) {
    await file.create({ intermediates: true });
  }

  await file.write(payload);
  return file.uri;
}

export async function loadAnnotatedPreview(jobId) {
  try {
    const file = jobAnnotatedPreviewFile(jobId);
    return file.exists ? file.uri : null;
  } catch (_err) {
    return null;
  }
}

export async function saveAnnotatedPreview(jobId, sourceUri) {
  if (!sourceUri) {
    return null;
  }

  const file = jobAnnotatedPreviewFile(jobId);
  await FileSystemLegacy.deleteAsync(file.uri, { idempotent: true });
  await FileSystemLegacy.copyAsync({
    from: sourceUri,
    to: file.uri,
  });
  return file.uri;
}

