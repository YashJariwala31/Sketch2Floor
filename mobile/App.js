import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  BackHandler,
  Platform,
  Pressable,
  StatusBar,
  StyleSheet,
  Text,
  View,
  useColorScheme,
  useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { StatusBar as ExpoStatusBar } from 'expo-status-bar';
import * as ImagePicker from 'expo-image-picker';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import HistoryScreen from './src/screens/HistoryScreen';
import HomeScreen from './src/screens/HomeScreen';
import ProfileScreen from './src/screens/ProfileScreen';
import ResultsScreen from './src/screens/ResultsScreen';
import { createJobWithImage, deleteJob, fetchJobs, startJob, testBackendConnection } from './src/api/client';
import { getTheme } from './src/theme';
import { saveImageToDevice } from './src/utils/saveImageToDevice';

const TABS = {
  HOME: 'home',
  HISTORY: 'history',
  PROFILE: 'profile',
};

const TAB_META = {
  [TABS.HOME]: { label: 'Home', icon: 'sparkles-outline', activeIcon: 'sparkles' },
  [TABS.HISTORY]: { label: 'History', icon: 'albums-outline', activeIcon: 'albums' },
  [TABS.PROFILE]: { label: 'Profile', icon: 'person-outline', activeIcon: 'person' },
};

function TabButton({ active, tab, onPress, theme }) {
  const styles = createStyles(theme, false);
  const meta = TAB_META[tab];

  return (
    <Pressable style={[styles.tabButton, active ? styles.tabButtonActive : null]} onPress={onPress}>
      <Ionicons
        name={active ? meta.activeIcon : meta.icon}
        size={18}
        color={active ? theme.colors.accent : theme.colors.softText}
      />
      <Text style={[styles.tabLabel, active ? styles.tabLabelActive : null]}>{meta.label}</Text>
    </Pressable>
  );
}

export default function App() {
  const systemScheme = useColorScheme();
  const scheme = systemScheme === 'dark' ? 'dark' : 'light';
  const theme = useMemo(() => getTheme(scheme), [scheme]);
  const { width, height } = useWindowDimensions();
  const isLandscape = width > height;
  const styles = useMemo(() => createStyles(theme, isLandscape), [theme, isLandscape]);

  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [activeTab, setActiveTab] = useState(TABS.HOME);
  const [connection, setConnection] = useState(null);

  const headerMeta = selectedJob
    ? 'Project result'
    : activeTab === TABS.HISTORY
      ? 'Your converted floorplans'
      : activeTab === TABS.PROFILE
        ? 'Connection and device settings'
        : 'Capture a sketch and keep the final result in the app';

  async function refreshConnection(showSuccess = false) {
    const result = await testBackendConnection();
    setConnection(result);
    if (!result.ok) {
      setError(result.error || 'Unable to reach backend');
    } else if (showSuccess) {
      setNotice('Backend connection looks good.');
    }
    return result;
  }

  async function loadJobs() {
    try {
      setLoading(true);
      const [data, connectionResult] = await Promise.all([fetchJobs(), refreshConnection(false)]);
      setJobs(data);

      if (selectedJob) {
        const refreshed = data.find((item) => item.id === selectedJob.id);
        if (refreshed) {
          setSelectedJob(refreshed);
        }
      }

      if (connectionResult.ok) {
        setError('');
      }
    } catch (err) {
      setError(err.message || 'Unable to reach backend');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadJobs();
  }, []);

  useEffect(() => {
    if (!selectedJob || (selectedJob.status !== 'queued' && selectedJob.status !== 'processing')) {
      return undefined;
    }

    const intervalId = setInterval(() => {
      loadJobs();
    }, 4000);

    return () => clearInterval(intervalId);
  }, [selectedJob]);

  useEffect(() => {
    if (Platform.OS !== 'android') {
      return undefined;
    }

    const subscription = BackHandler.addEventListener('hardwareBackPress', () => {
      if (selectedJob) {
        setSelectedJob(null);
        return true;
      }
      if (activeTab !== TABS.HOME) {
        setActiveTab(TABS.HOME);
        return true;
      }
      return false;
    });

    return () => subscription.remove();
  }, [activeTab, selectedJob]);

  async function uploadCapturedSketch({
    imageUri,
    imageName,
    mimeType,
    name,
    description,
    uploadingNotice,
    successNotice,
    successTitle,
    successMessage,
    failureMessage,
  }) {
    try {
      setBusy(true);
      setError('');
      setNotice(uploadingNotice);
      const created = await createJobWithImage({
        name,
        description,
        imageUri,
        imageName,
        mimeType,
      });

      setSelectedJob(created);
      setActiveTab(TABS.HISTORY);
      setNotice(`${successNotice} Processing has started automatically.`);
      Alert.alert(successTitle, successMessage);
      await loadJobs();
    } catch (err) {
      setError(err.message || failureMessage);
      setNotice('');
      Alert.alert('Upload failed', err.message || failureMessage);
    } finally {
      setBusy(false);
    }
  }

  async function handleUploadImage() {
    try {
      setBusy(true);
      setError('');
      setNotice('Opening camera...');
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        Alert.alert('Permission needed', 'Please allow camera access to capture sketches.');
        setNotice('');
        return;
      }

      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ['images'],
        quality: 1,
        cameraType: ImagePicker.CameraType.back,
      });

      if (result.canceled || !result.assets?.length) {
        setNotice('');
        return;
      }

      const asset = result.assets[0];
      await uploadCapturedSketch({
        imageUri: asset.uri,
        imageName: asset.fileName || `floorplan-${Date.now()}.jpg`,
        mimeType: asset.mimeType || 'image/jpeg',
        name: 'New floorplan scan',
        description: 'Captured from the device camera.',
        uploadingNotice: 'Uploading your sketch...',
        successNotice: 'Sketch uploaded successfully.',
        successTitle: 'Upload complete',
        successMessage: 'Your sketch was captured and added to your conversions.',
        failureMessage: 'Unable to upload image',
      });
    } catch (err) {
      setError(err.message || 'Unable to open camera');
      setNotice('');
      Alert.alert('Camera failed', err.message || 'Unable to open camera.');
    } finally {
      setBusy(false);
    }
  }

  async function handlePickFromGallery() {
    try {
      setBusy(true);
      setError('');
      setNotice('Opening your photos...');
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        Alert.alert('Permission needed', 'Please allow photo access to choose an existing sketch.');
        setNotice('');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        quality: 1,
      });

      if (result.canceled || !result.assets?.length) {
        setNotice('');
        return;
      }

      const asset = result.assets[0];
      await uploadCapturedSketch({
        imageUri: asset.uri,
        imageName: asset.fileName || 'floorplan.jpg',
        mimeType: asset.mimeType || 'image/jpeg',
        name: 'Imported floorplan project',
        description: 'Selected from the device gallery.',
        uploadingNotice: 'Uploading your selected sketch...',
        successNotice: 'Sketch imported successfully.',
        successTitle: 'Upload complete',
        successMessage: 'Your sketch was imported and added to your conversions.',
        failureMessage: 'Unable to import image',
      });
    } catch (err) {
      setError(err.message || 'Unable to import image');
      setNotice('');
      Alert.alert('Upload failed', err.message || 'Unable to import image.');
    } finally {
      setBusy(false);
    }
  }

  async function handleStartJob(job) {
    if (!job) {
      return;
    }
    try {
      setBusy(true);
      setError('');
      setNotice('Starting floorplan processing...');
      const started = await startJob(job.id);
      setSelectedJob(started);
      Alert.alert('Processing started', 'Your project is now being processed.');
      await loadJobs();
    } catch (err) {
      setError(err.message || 'Unable to start job');
      setNotice('');
      Alert.alert('Could not start processing', err.message || 'Unable to start job.');
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteJob(job) {
    if (!job) {
      return;
    }

    try {
      setBusy(true);
      setError('');
      setNotice('Deleting project...');
      await deleteJob(job.id);
      if (selectedJob?.id === job.id) {
        setSelectedJob(null);
      }
      setNotice('Project deleted.');
      await loadJobs();
    } catch (err) {
      setError(err.message || 'Unable to delete job');
      setNotice('');
      Alert.alert('Delete failed', err.message || 'Unable to delete job.');
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveResult(url) {
    try {
      setBusy(true);
      setError('');
      setNotice('Saving floorplan to your phone...');
      await saveImageToDevice(url, 'Sketch2FloorPlan');
      setNotice('Floorplan saved to your photo library.');
      Alert.alert('Saved', 'Your floorplan image was saved to the phone gallery.');
    } catch (err) {
      setError(err.message || 'Unable to save image');
      setNotice('');
      Alert.alert('Save failed', err.message || 'Unable to save image.');
    } finally {
      setBusy(false);
    }
  }

  function renderCurrentScreen() {
    if (selectedJob) {
      return (
        <ResultsScreen
          job={selectedJob}
          busy={busy}
          error={error}
          onBack={() => setSelectedJob(null)}
          onRefresh={loadJobs}
          onStartJob={() => handleStartJob(selectedJob)}
          onDeleteJob={handleDeleteJob}
          onSaveResult={handleSaveResult}
          theme={theme}
          isLandscape={isLandscape}
        />
      );
    }

    if (activeTab === TABS.HISTORY) {
      return (
        <HistoryScreen
          jobs={jobs}
          loading={loading}
          error={error}
          onSelectJob={setSelectedJob}
          onDeleteJob={handleDeleteJob}
          theme={theme}
          isLandscape={isLandscape}
        />
      );
    }

    if (activeTab === TABS.PROFILE) {
      return <ProfileScreen connection={connection} onRefreshConnection={() => refreshConnection(true)} theme={theme} isLandscape={isLandscape} />;
    }

    return <HomeScreen busy={busy} onUploadImage={handleUploadImage} onPickFromGallery={handlePickFromGallery} theme={theme} isLandscape={isLandscape} />;
  }

  return (
    <SafeAreaProvider>
      <SafeAreaView edges={['top', 'left', 'right']} style={styles.safeArea}>
        <StatusBar barStyle={theme.isDark ? 'light-content' : 'dark-content'} backgroundColor={theme.colors.background} />
        <ExpoStatusBar style={theme.isDark ? 'light' : 'dark'} />
        <View style={styles.container}>
          <View style={styles.header}>
            <View style={styles.headerCopy}>
              <Text style={styles.brand}>Sketch2FloorPlan</Text>
              <Text style={styles.headerMeta}>{headerMeta}</Text>
            </View>
            {!selectedJob ? (
              <Pressable style={styles.profileButton} onPress={() => setActiveTab(TABS.PROFILE)}>
                <Ionicons name="person-outline" size={20} color={theme.colors.text} />
              </Pressable>
            ) : null}
          </View>

          {notice && !selectedJob ? (
            <View style={styles.noticeBanner}>
              <Text style={styles.noticeText}>{notice}</Text>
            </View>
          ) : null}

          {error && !selectedJob ? (
            <View style={styles.errorBanner}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          <View style={styles.screenArea}>{renderCurrentScreen()}</View>

          {!selectedJob ? (
            <View style={styles.bottomNav}>
              <TabButton active={activeTab === TABS.HOME} tab={TABS.HOME} onPress={() => setActiveTab(TABS.HOME)} theme={theme} />
              <TabButton active={activeTab === TABS.HISTORY} tab={TABS.HISTORY} onPress={() => setActiveTab(TABS.HISTORY)} theme={theme} />
              <TabButton active={activeTab === TABS.PROFILE} tab={TABS.PROFILE} onPress={() => setActiveTab(TABS.PROFILE)} theme={theme} />
            </View>
          ) : null}
        </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    safeArea: {
      flex: 1,
      backgroundColor: theme.colors.background,
    },
    container: {
      flex: 1,
      backgroundColor: theme.colors.background,
      paddingHorizontal: isLandscape ? 28 : 18,
      paddingBottom: 18,
    },
    header: {
      paddingTop: 10,
      paddingBottom: 18,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
    },
    headerCopy: {
      flex: 1,
      paddingRight: 12,
    },
    brand: {
      color: theme.colors.text,
      fontSize: isLandscape ? 30 : 29,
      fontWeight: '900',
      letterSpacing: -0.9,
    },
    headerMeta: {
      marginTop: 5,
      color: theme.colors.softText,
      fontWeight: '700',
      lineHeight: 20,
    },
    profileButton: {
      width: 44,
      height: 44,
      backgroundColor: theme.colors.surface,
      borderRadius: 22,
      alignItems: 'center',
      justifyContent: 'center',
      borderWidth: 1,
      borderColor: theme.colors.border,
      ...theme.shadow.soft,
    },
    noticeBanner: {
      backgroundColor: theme.colors.noticeBg,
      borderRadius: 18,
      paddingHorizontal: 16,
      paddingVertical: 13,
      marginBottom: 14,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
    },
    noticeText: {
      color: theme.colors.accentStrong,
      fontWeight: '800',
    },
    errorBanner: {
      backgroundColor: theme.colors.errorBg,
      borderRadius: 18,
      paddingHorizontal: 16,
      paddingVertical: 13,
      marginBottom: 14,
      borderWidth: 1,
      borderColor: theme.colors.errorBorder,
    },
    errorText: {
      color: theme.colors.danger,
      fontWeight: '800',
    },
    screenArea: {
      flex: 1,
    },
    bottomNav: {
      marginTop: 12,
      backgroundColor: theme.colors.surface,
      borderRadius: 28,
      borderWidth: 1,
      borderColor: theme.colors.border,
      paddingHorizontal: 8,
      paddingVertical: 8,
      flexDirection: 'row',
      justifyContent: 'space-between',
      ...theme.shadow.card,
    },
    tabButton: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
      paddingVertical: 12,
      borderRadius: theme.radius.pill,
    },
    tabButtonActive: {
      backgroundColor: theme.colors.accentSoft,
    },
    tabLabel: {
      color: theme.colors.softText,
      fontWeight: '800',
    },
    tabLabelActive: {
      color: theme.colors.accent,
    },
  });
}
