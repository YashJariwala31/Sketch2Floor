import { File, Paths } from 'expo-file-system';
import * as MediaLibrary from 'expo-media-library';

function getExtensionFromUrl(url) {
  const clean = (url || '').split('?')[0];
  const match = clean.match(/\.([a-zA-Z0-9]+)$/);
  return match ? match[1].toLowerCase() : 'png';
}

export async function saveImageToDevice(url, filePrefix = 'Sketch2FloorPlan') {
  if (!url) {
    throw new Error('There is no image available to save yet.');
  }

  const permission = await MediaLibrary.requestPermissionsAsync();
  if (!permission.granted) {
    throw new Error('Please allow photo library access so the app can save your floorplan.');
  }

  const extension = getExtensionFromUrl(url);
  const file = new File(Paths.cache, `${filePrefix}-${Date.now()}.${extension}`);
  const downloaded = await File.downloadFileAsync(url, file, { idempotent: true });

  await MediaLibrary.saveToLibraryAsync(downloaded.uri);
  return downloaded.uri;
}
