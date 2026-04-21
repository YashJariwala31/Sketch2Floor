import { Platform } from 'react-native';
import { Directory, File, Paths } from 'expo-file-system';
import * as FileSystemLegacy from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';

let cachedAndroidDirectoryUri = null;
const downloadDirectoryStore = new File(Paths.document, 'download-directory-uri.txt');

function getExtensionFromUrl(url) {
  const clean = (url || '').split('?')[0];
  const match = clean.match(/\.([a-zA-Z0-9]+)$/);
  return match ? match[1].toLowerCase() : 'png';
}

function getMimeType(extension) {
  if (extension === 'jpg' || extension === 'jpeg') {
    return 'image/jpeg';
  }
  return `image/${extension}`;
}

async function ensureAndroidDownloadDirectory() {
  if (cachedAndroidDirectoryUri) {
    return cachedAndroidDirectoryUri;
  }

  if (downloadDirectoryStore.exists) {
    const storedUri = (await downloadDirectoryStore.text()).trim();
    if (storedUri) {
      cachedAndroidDirectoryUri = storedUri;
      return cachedAndroidDirectoryUri;
    }
  }

  const initialUri = FileSystemLegacy.StorageAccessFramework.getUriForDirectoryInRoot('Download');
  const permission = await FileSystemLegacy.StorageAccessFramework.requestDirectoryPermissionsAsync(initialUri);

  if (!permission.granted || !permission.directoryUri) {
    throw new Error('Please choose your Downloads folder to save the image.');
  }

  cachedAndroidDirectoryUri = permission.directoryUri;
  downloadDirectoryStore.write(cachedAndroidDirectoryUri);
  return cachedAndroidDirectoryUri;
}

export async function saveImageToDevice(url, filePrefix = 'Sketch2FloorPlan') {
  if (!url) {
    throw new Error('There is no image available to download yet.');
  }

  const extension = getExtensionFromUrl(url);
  const mimeType = getMimeType(extension);
  const fileName = `${filePrefix}-${Date.now()}.${extension}`;
  const localDirectory = new Directory(Paths.document, 'Sketch2FloorPlan');

  if (!localDirectory.exists) {
    localDirectory.create({ idempotent: true, intermediates: true });
  }

  const localFile = new File(localDirectory, fileName);
  const downloaded = await File.downloadFileAsync(url, localFile, { idempotent: true });

  if (Platform.OS === 'android') {
    try {
      const directoryUri = await ensureAndroidDownloadDirectory();
      const targetUri = await FileSystemLegacy.StorageAccessFramework.createFileAsync(directoryUri, fileName, mimeType);
      const base64 = await downloaded.base64();

      await FileSystemLegacy.writeAsStringAsync(targetUri, base64, {
        encoding: FileSystemLegacy.EncodingType.Base64,
      });

      return {
        uri: targetUri,
        message: 'Saved to Downloads',
      };
    } catch (error) {
      cachedAndroidDirectoryUri = null;
      if (downloadDirectoryStore.exists) {
        downloadDirectoryStore.delete();
      }
      throw error;
    }
  }

  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(downloaded.uri, {
      dialogTitle: 'Save floorplan',
      mimeType,
    });

    return {
      uri: downloaded.uri,
      message: 'Opened save options',
    };
  }

  throw new Error('Saving is not available on this device.');
}
