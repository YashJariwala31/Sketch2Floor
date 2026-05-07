import { Image } from 'react-native';
import { manipulateAsync, SaveFormat } from 'expo-image-manipulator';

export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

export function clampOffsets(offsets, limits) {
  return {
    x: clamp(offsets.x, -limits.x, limits.x),
    y: clamp(offsets.y, -limits.y, limits.y),
  };
}

export function fitCropBox(stageWidth, stageHeight, aspectRatio, frameScale = 0.92) {
  if (!stageWidth || !stageHeight || !aspectRatio) {
    return { width: 0, height: 0 };
  }

  const maxWidth = stageWidth * frameScale;
  const maxHeight = stageHeight * frameScale;

  let width = maxWidth;
  let height = width / aspectRatio;

  if (height > maxHeight) {
    height = maxHeight;
    width = height * aspectRatio;
  }

  return {
    width: Math.max(1, Math.round(width)),
    height: Math.max(1, Math.round(height)),
  };
}

export function getDisplayedImageSize(imageSize, cropBox, zoom = 1) {
  if (!imageSize?.width || !imageSize?.height || !cropBox?.width || !cropBox?.height) {
    return { width: 0, height: 0 };
  }

  const baseScale = Math.max(cropBox.width / imageSize.width, cropBox.height / imageSize.height);
  return {
    width: imageSize.width * baseScale * zoom,
    height: imageSize.height * baseScale * zoom,
  };
}

export function getPanLimits(displayedSize, cropBox) {
  return {
    x: Math.max(0, (displayedSize.width - cropBox.width) / 2),
    y: Math.max(0, (displayedSize.height - cropBox.height) / 2),
  };
}

export function calculateCropRect({ imageSize, cropBox, displayedSize, offsets }) {
  if (!imageSize?.width || !imageSize?.height || !cropBox?.width || !cropBox?.height || !displayedSize?.width || !displayedSize?.height) {
    return null;
  }

  const imageLeft = (cropBox.width - displayedSize.width) / 2 + offsets.x;
  const imageTop = (cropBox.height - displayedSize.height) / 2 + offsets.y;

  const originX = clamp(Math.round((-imageLeft / displayedSize.width) * imageSize.width), 0, imageSize.width - 1);
  const originY = clamp(Math.round((-imageTop / displayedSize.height) * imageSize.height), 0, imageSize.height - 1);

  const width = clamp(Math.round((cropBox.width / displayedSize.width) * imageSize.width), 1, imageSize.width - originX);
  const height = clamp(Math.round((cropBox.height / displayedSize.height) * imageSize.height), 1, imageSize.height - originY);

  return { originX, originY, width, height };
}

export function estimateOutputSize(cropRect, maxEdge) {
  if (!cropRect) {
    return null;
  }

  if (!maxEdge || Math.max(cropRect.width, cropRect.height) <= maxEdge) {
    return {
      width: Math.round(cropRect.width),
      height: Math.round(cropRect.height),
    };
  }

  if (cropRect.width >= cropRect.height) {
    return {
      width: Math.round(maxEdge),
      height: Math.max(1, Math.round((cropRect.height / cropRect.width) * maxEdge)),
    };
  }

  return {
    width: Math.max(1, Math.round((cropRect.width / cropRect.height) * maxEdge)),
    height: Math.round(maxEdge),
  };
}

function buildEditedFileName(fileName, format) {
  const extension = format === SaveFormat.PNG ? 'png' : 'jpg';
  const stem = (fileName || `floorplan-${Date.now()}`).replace(/\.[^.]+$/, '');
  return `${stem}-edited.${extension}`;
}

function getSaveFormat(mimeType) {
  if (mimeType?.includes('png')) {
    return SaveFormat.PNG;
  }
  return SaveFormat.JPEG;
}

export async function resolveImageSize(asset) {
  if (asset?.width && asset?.height) {
    return { width: asset.width, height: asset.height };
  }

  if (!asset?.uri) {
    throw new Error('Unable to read image details.');
  }

  return new Promise((resolve, reject) => {
    Image.getSize(
      asset.uri,
      (width, height) => resolve({ width, height }),
      () => reject(new Error('Unable to read image size.'))
    );
  });
}

export async function exportEditedAsset({ asset, cropRect, maxEdge }) {
  if (!asset?.uri || !cropRect) {
    throw new Error('Image crop data is incomplete.');
  }

  const format = getSaveFormat(asset.mimeType);
  const actions = [{ crop: cropRect }];

  if (maxEdge && Math.max(cropRect.width, cropRect.height) > maxEdge) {
    if (cropRect.width >= cropRect.height) {
      actions.push({ resize: { width: maxEdge } });
    } else {
      actions.push({ resize: { height: maxEdge } });
    }
  }

  const result = await manipulateAsync(asset.uri, actions, {
    compress: format === SaveFormat.PNG ? 1 : 0.95,
    format,
  });

  return {
    uri: result.uri,
    width: result.width,
    height: result.height,
    fileName: buildEditedFileName(asset.fileName, format),
    mimeType: format === SaveFormat.PNG ? 'image/png' : 'image/jpeg',
  };
}
