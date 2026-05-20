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

function jobAnnotatedPreviewPrefix(jobId) {
  const safe = String(jobId ?? 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
  return `s2fp_annotations_preview_${safe}_`;
}

async function deleteFileIfExists(fileOrUri) {
  if (!fileOrUri) {
    return;
  }

  const target = typeof fileOrUri === 'string' ? fileOrUri : fileOrUri.uri;
  if (!target) {
    return;
  }

  await FileSystemLegacy.deleteAsync(target, { idempotent: true });
}

async function deleteVersionedPreviewFiles(jobId, keepUri = null) {
  try {
    const entries = await FileSystemLegacy.readDirectoryAsync(Paths.document.uri);
    const prefix = jobAnnotatedPreviewPrefix(jobId);
    const keepTarget = typeof keepUri === 'string' && keepUri ? keepUri : null;

    await Promise.all(
      entries
        .filter((name) => name.startsWith(prefix) && name.endsWith('.png'))
        .map((name) => `${Paths.document.uri}${name}`)
        .filter((uri) => uri !== keepTarget)
        .map((uri) => FileSystemLegacy.deleteAsync(uri, { idempotent: true }))
    );
  } catch (_err) {
    return;
  }
}

function normalizeAnnotationState(parsed) {
  if (Array.isArray(parsed)) {
    return {
      annotations: parsed,
      backendSynced: false,
    };
  }

  if (parsed && typeof parsed === 'object') {
    return {
      annotations: Array.isArray(parsed.annotations) ? parsed.annotations : [],
      backendSynced: parsed.backendSynced === true,
    };
  }

  return null;
}

export async function loadLocalAnnotationState(jobId) {
  try {
    const file = jobAnnotationsFile(jobId);
    if (!file.exists) {
      return null;
    }

    const raw = await file.text();
    if (!raw) {
      return null;
    }

    return normalizeAnnotationState(JSON.parse(raw));
  } catch (_err) {
    return null;
  }
}

export async function loadLocalAnnotations(jobId) {
  const state = await loadLocalAnnotationState(jobId);
  return state?.annotations ?? null;
}

export async function saveLocalAnnotations(jobId, annotations, options = {}) {
  const file = jobAnnotationsFile(jobId);
  const payload = JSON.stringify(
    {
      annotations: Array.isArray(annotations) ? annotations : [],
      backendSynced: options.backendSynced === true,
      savedAt: new Date().toISOString(),
    },
    null,
    2
  );

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

  await deleteVersionedPreviewFiles(jobId, file.uri);

  const legacyFile = jobAnnotatedPreviewFile(jobId);
  if (legacyFile.uri !== file.uri) {
    await FileSystemLegacy.deleteAsync(legacyFile.uri, { idempotent: true });
  }

  return file.uri;
}

export async function deleteLocalJobArtifacts(jobId) {
  try {
    const pointerFile = jobAnnotatedPreviewPointerFile(jobId);
    let currentPreviewUri = null;

    if (pointerFile.exists) {
      currentPreviewUri = (await pointerFile.text()).trim() || null;
    }

    await deleteFileIfExists(jobAnnotationsFile(jobId));
    await deleteFileIfExists(pointerFile);
    await deleteFileIfExists(currentPreviewUri);
    await deleteFileIfExists(jobAnnotatedPreviewFile(jobId));
    await deleteVersionedPreviewFiles(jobId);
  } catch (_err) {
    return false;
  }

  return true;
}
