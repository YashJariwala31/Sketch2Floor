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

function jobAnnotatedPreviewPointerFile(jobId) {
  const safe = String(jobId ?? 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
  return new File(Paths.document, `s2fp_annotations_preview_${safe}.txt`);
}

function versionedAnnotatedPreviewFile(jobId) {
  const safe = String(jobId ?? 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
  return new File(Paths.document, `s2fp_annotations_preview_${safe}_${Date.now()}.png`);
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
    const pointerFile = jobAnnotatedPreviewPointerFile(jobId);
    if (pointerFile.exists) {
      const latestUri = (await pointerFile.text()).trim();
      if (latestUri) {
        const latestFile = new File(latestUri);
        if (latestFile.exists) {
          return latestFile.uri;
        }
      }
    }

    const legacyFile = jobAnnotatedPreviewFile(jobId);
    return legacyFile.exists ? legacyFile.uri : null;
  } catch (_err) {
    return null;
  }
}

export async function saveAnnotatedPreview(jobId, sourceUri) {
  if (!sourceUri) {
    return null;
  }

  const pointerFile = jobAnnotatedPreviewPointerFile(jobId);
  let previousUri = null;

  if (pointerFile.exists) {
    previousUri = (await pointerFile.text()).trim() || null;
  }

  const file = versionedAnnotatedPreviewFile(jobId);
  await FileSystemLegacy.copyAsync({
    from: sourceUri,
    to: file.uri,
  });

  if (!pointerFile.exists) {
    await pointerFile.create({ intermediates: true });
  }
  await pointerFile.write(file.uri);

  if (previousUri && previousUri !== file.uri) {
    await FileSystemLegacy.deleteAsync(previousUri, { idempotent: true });
  }

  const legacyFile = jobAnnotatedPreviewFile(jobId);
  if (legacyFile.uri !== file.uri) {
    await FileSystemLegacy.deleteAsync(legacyFile.uri, { idempotent: true });
  }

  return file.uri;
}

