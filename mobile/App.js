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
  useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { StatusBar as ExpoStatusBar } from 'expo-status-bar';
import * as ImagePicker from 'expo-image-picker';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import AuthScreen from './src/screens/AuthScreen';
import HistoryScreen from './src/screens/HistoryScreen';
import LandingScreen from './src/screens/LandingScreen';
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

const AUTH_ROUTES = {
  LANDING: 'landing',
  LOGIN: 'login',
  SIGNUP: 'signup',
};

const TAB_META = {
  [TABS.HOME]: { label: 'Studio', icon: 'scan-outline', activeIcon: 'scan' },
  [TABS.HISTORY]: { label: 'Library', icon: 'layers-outline', activeIcon: 'layers' },
  [TABS.PROFILE]: { label: 'Profile', icon: 'person-outline', activeIcon: 'person' },
};

function TabButton({ active, tab, onPress, theme }) {
  const styles = createStyles(theme, false);
  const meta = TAB_META[tab];

  return (
    <Pressable style={[styles.tabButton, active ? styles.tabButtonActive : null]} onPress={onPress}>
      <Ionicons name={active ? meta.activeIcon : meta.icon} size={19} color={active ? theme.colors.text : theme.colors.softText} />
      <Text style={[styles.tabLabel, active ? styles.tabLabelActive : null]}>{meta.label}</Text>
    </Pressable>
  );
}

export default function App() {
  const theme = useMemo(() => getTheme('light'), []);
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
  const [session, setSession] = useState(null);
  const [authRoute, setAuthRoute] = useState(AUTH_ROUTES.LANDING);

  async function refreshConnection(showSuccess = false) {
    const result = await testBackendConnection();
    setConnection(result);
    if (!result.ok) {
      setError(result.error || 'Unable to reach backend');
    } else if (showSuccess) {
      setNotice('Connected');
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
    if (session) {
      loadJobs();
      return;
    }
    setJobs([]);
    setSelectedJob(null);
    setLoading(false);
    setError('');
    setNotice('');
  }, [session]);

  useEffect(() => {
    if (!session || !selectedJob || (selectedJob.status !== 'queued' && selectedJob.status !== 'processing')) {
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
      if (!session) {
        if (authRoute !== AUTH_ROUTES.LANDING) {
          setAuthRoute(AUTH_ROUTES.LANDING);
          return true;
        }
        return false;
      }
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
  }, [activeTab, selectedJob, session, authRoute]);

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
      setNotice(successNotice);
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
        Alert.alert('Permission needed', 'Please allow camera access.');
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
        description: 'Captured from camera',
        uploadingNotice: 'Uploading...',
        successNotice: 'Uploaded',
        successTitle: 'Upload complete',
        successMessage: 'Your sketch was added.',
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
      setNotice('Opening photos...');
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        Alert.alert('Permission needed', 'Please allow photo access.');
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
        name: 'Imported floorplan',
        description: 'Imported from phone',
        uploadingNotice: 'Uploading...',
        successNotice: 'Imported',
        successTitle: 'Upload complete',
        successMessage: 'Your sketch was added.',
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
      setNotice('Starting...');
      const started = await startJob(job.id);
      setSelectedJob(started);
      await loadJobs();
    } catch (err) {
      setError(err.message || 'Unable to start job');
      setNotice('');
      Alert.alert('Could not start', err.message || 'Unable to start job.');
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
      setNotice('Deleting...');
      await deleteJob(job.id);
      if (selectedJob?.id === job.id) {
        setSelectedJob(null);
      }
      setNotice('Deleted');
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
      setNotice('Preparing download...');
      const result = await saveImageToDevice(url, 'Sketch2FloorPlan');
      setNotice(result.message || 'Downloaded');
    } catch (err) {
      setError(err.message || 'Unable to prepare download');
      setNotice('');
      Alert.alert('Download failed', err.message || 'Unable to prepare download.');
    } finally {
      setBusy(false);
    }
  }

  function handleAuthSubmit(authValues) {
    setSession({
      email: authValues.email,
      name: authValues.fullName || authValues.email.split('@')[0],
    });
    setActiveTab(TABS.HOME);
    setSelectedJob(null);
    setNotice('Welcome back');
    setError('');
    setAuthRoute(AUTH_ROUTES.LANDING);
  }

  function handleSignOut() {
    setSession(null);
    setConnection(null);
    setActiveTab(TABS.HOME);
  }

  function renderCurrentScreen() {
    if (!session) {
      if (authRoute === AUTH_ROUTES.LANDING) {
        return <LandingScreen theme={theme} isLandscape={isLandscape} onLogin={() => setAuthRoute(AUTH_ROUTES.LOGIN)} onSignUp={() => setAuthRoute(AUTH_ROUTES.SIGNUP)} />;
      }

      return (
        <AuthScreen
          busy={busy}
          theme={theme}
          mode={authRoute === AUTH_ROUTES.SIGNUP ? 'signup' : 'login'}
          onBack={() => setAuthRoute(AUTH_ROUTES.LANDING)}
          onSwitchMode={() => setAuthRoute(authRoute === AUTH_ROUTES.SIGNUP ? AUTH_ROUTES.LOGIN : AUTH_ROUTES.SIGNUP)}
          onSubmit={handleAuthSubmit}
        />
      );
    }

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
      return (
        <ProfileScreen
          connection={connection}
          session={session}
          onRefreshConnection={() => refreshConnection(true)}
          onSignOut={handleSignOut}
          theme={theme}
          isLandscape={isLandscape}
        />
      );
    }

    return <HomeScreen busy={busy} onUploadImage={handleUploadImage} onPickFromGallery={handlePickFromGallery} theme={theme} isLandscape={isLandscape} />;
  }

  return (
    <SafeAreaProvider>
      <SafeAreaView edges={['top', 'left', 'right']} style={styles.safeArea}>
        <StatusBar barStyle={theme.isDark ? 'light-content' : 'dark-content'} backgroundColor={theme.colors.background} />
        <ExpoStatusBar style={theme.isDark ? 'light' : 'dark'} />

        <View style={styles.container}>
          {session && !selectedJob ? (
            <View style={styles.header}>
              <Text style={styles.brand}>Sketch2FloorPlan</Text>
              <Pressable style={styles.profileButton} onPress={() => setActiveTab(TABS.PROFILE)}>
                <Ionicons name="person-outline" size={19} color={theme.colors.text} />
              </Pressable>
            </View>
          ) : null}

          {notice && session && !selectedJob ? (
            <View style={styles.noticeBanner}>
              <Text style={styles.noticeText}>{notice}</Text>
            </View>
          ) : null}

          {error && session && !selectedJob ? (
            <View style={styles.errorBanner}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          <View style={styles.screenArea}>{renderCurrentScreen()}</View>

          {session && !selectedJob ? (
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
      paddingHorizontal: isLandscape ? 28 : 20,
      paddingBottom: 18,
    },
    header: {
      paddingTop: 8,
      paddingBottom: 16,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
    },
    brand: {
      color: theme.colors.text,
      fontSize: isLandscape ? 28 : 27,
      fontWeight: '900',
      letterSpacing: -0.9,
    },
    profileButton: {
      width: 42,
      height: 42,
      borderRadius: 21,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: theme.colors.surfaceElevated,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      ...theme.shadow.soft,
    },
    noticeBanner: {
      backgroundColor: theme.colors.noticeBg,
      borderRadius: 16,
      paddingHorizontal: 14,
      paddingVertical: 12,
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
      borderRadius: 16,
      paddingHorizontal: 14,
      paddingVertical: 12,
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
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: theme.colors.surfaceElevated,
      borderRadius: 22,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      paddingHorizontal: 7,
      paddingVertical: 7,
      ...theme.shadow.card,
    },
    tabButton: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      gap: 6,
      paddingVertical: 11,
      borderRadius: 18,
    },
    tabButtonActive: {
      backgroundColor: theme.colors.surface,
    },
    tabLabel: {
      color: theme.colors.softText,
      fontWeight: '800',
      fontSize: 12,
    },
    tabLabelActive: {
      color: theme.colors.text,
    },
  });
}
