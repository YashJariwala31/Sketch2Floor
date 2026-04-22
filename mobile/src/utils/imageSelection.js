import * as ImagePicker from 'expo-image-picker';

async function ensurePermission(requestPermission, message) {
  const permission = await requestPermission();
  if (!permission.granted) {
    throw new Error(message);
  }
}

export async function captureImageFromCamera() {
  await ensurePermission(ImagePicker.requestCameraPermissionsAsync, 'Please allow camera access.');

  const result = await ImagePicker.launchCameraAsync({
    mediaTypes: ['images'],
    quality: 1,
    cameraType: ImagePicker.CameraType.back,
  });

  if (result.canceled || !result.assets?.length) {
    return null;
  }

  return result.assets[0];
}

export async function pickImageFromGallery() {
  await ensurePermission(ImagePicker.requestMediaLibraryPermissionsAsync, 'Please allow photo access.');

  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    quality: 1,
  });

  if (result.canceled || !result.assets?.length) {
    return null;
  }

  return result.assets[0];
}
