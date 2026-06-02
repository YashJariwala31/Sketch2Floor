import { File, Paths } from 'expo-file-system';
import * as FileSystemLegacy from 'expo-file-system/legacy';

function accountToken(accountKey) {
  const normalized = String(accountKey || 'shared').trim().toLowerCase();
  return normalized.replace(/[^a-zA-Z0-9_-]/g, '_') || 'shared';
}

function jobAnnotationsFile(jobId, accountKey) {
  const safe = String(jobId ?? 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
  return new File(Paths.document, `s2fp_annotations_${accountToken(accountKey)}_job_${safe}.json`);
}

function jobAnnotatedPreviewFile(jobId, accountKey) {
  const safe = String(jobId ?? 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
  return new File(Paths.document, `s2fp_annotations_preview_${accountToken(accountKey)}_${safe}.png`);
}

function jobAnnotatedPreviewPointerFile(jobId, accountKey) {
  const safe = String(jobId ?? 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
  return new File(Paths.document, `s2fp_annotations_preview_${accountToken(accountKey)}_${safe}.txt`);
}

function versionedAnnotatedPreviewFile(jobId, accountKey) {
  const safe = String(jobId ?? 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
  return new File(Paths.document, `s2fp_annotations_preview_${accountToken(accountKey)}_${safe}_${Date.now()}.png`);
}

function jobAnnotatedPreviewPrefix(jobId, accountKey) {
  const safe = String(jobId ?? 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
  return `s2fp_annotations_preview_${accountToken(accountKey)}_${safe}_`;
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

async function deleteVersionedPreviewFiles(jobId, accountKey, keepUri = null) {
  try {
    const entries = await FileSystemLegacy.readDirectoryAsync(Paths.document.uri);
    const prefix = jobAnnotatedPreviewPrefix(jobId, accountKey);
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

export async function loadLocalAnnotationState(jobId, accountKey) {
  try {
    const file = jobAnnotationsFile(jobId, accountKey);
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

export async function loadLocalAnnotations(jobId, accountKey) {
  const state = await loadLocalAnnotationState(jobId, accountKey);
  return state?.annotations ?? null;
}

export async function saveLocalAnnotations(jobId, annotations, options = {}) {
  const file = jobAnnotationsFile(jobId, options.accountKey);
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

export async function loadAnnotatedPreview(jobId, accountKey) {
  try {
    const pointerFile = jobAnnotatedPreviewPointerFile(jobId, accountKey);
    if (pointerFile.exists) {
      const latestUri = (await pointerFile.text()).trim();
      if (latestUri) {
        const latestFile = new File(latestUri);
        if (latestFile.exists) {
          return latestFile.uri;
        }
      }
    }

    const legacyFile = jobAnnotatedPreviewFile(jobId, accountKey);
    return legacyFile.exists ? legacyFile.uri : null;
  } catch (_err) {
    return null;
  }
}

export async function saveAnnotatedPreview(jobId, sourceUri, accountKey) {
  if (!sourceUri) {
    return null;
  }

  const pointerFile = jobAnnotatedPreviewPointerFile(jobId, accountKey);
  let previousUri = null;

  if (pointerFile.exists) {
    previousUri = (await pointerFile.text()).trim() || null;
  }

  const file = versionedAnnotatedPreviewFile(jobId, accountKey);
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

  await deleteVersionedPreviewFiles(jobId, accountKey, file.uri);

  const legacyFile = jobAnnotatedPreviewFile(jobId, accountKey);
  if (legacyFile.uri !== file.uri) {
    await FileSystemLegacy.deleteAsync(legacyFile.uri, { idempotent: true });
  }

  return file.uri;
}

export async function deleteLocalJobArtifacts(jobId, accountKey) {
  try {
    const pointerFile = jobAnnotatedPreviewPointerFile(jobId, accountKey);
    let currentPreviewUri = null;

    if (pointerFile.exists) {
      currentPreviewUri = (await pointerFile.text()).trim() || null;
    }

    await deleteFileIfExists(jobAnnotationsFile(jobId, accountKey));
    await deleteFileIfExists(pointerFile);
    await deleteFileIfExists(currentPreviewUri);
    await deleteFileIfExists(jobAnnotatedPreviewFile(jobId, accountKey));
    await deleteVersionedPreviewFiles(jobId, accountKey);
  } catch (_err) {
    return false;
  }

  return true;
}
