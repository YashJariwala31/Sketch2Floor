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
import HomeScreen from './src/screens/HomeScreen';
import LandingScreen from './src/screens/LandingScreen';
import ProfileScreen from './src/screens/ProfileScreen';
import ResultsScreen from './src/screens/ResultsScreen';
import UploadCaptureScreen from './src/screens/UploadCaptureScreen';
import { createJobWithImage, deleteJob, fetchJobs, startJob, testBackendConnection } from './src/api/client';
import { getTheme } from './src/theme';
import { saveImageToDevice } from './src/utils/saveImageToDevice';

const TABS = {
  HOME: 'home',
  HISTORY: 'history',
  PROFILE: 'profile',
};

const HOME_VIEWS = {
  MAIN: 'main',
  UPLOAD: 'upload',
};

const AUTH_ROUTES = {
  LANDING: 'landing',
  LOGIN: 'login',
  SIGNUP: 'signup',
};

const TAB_META = {
  [TABS.HOME]: { label: 'Home', icon: 'home-outline', activeIcon: 'home' },
  [TABS.HISTORY]: { label: 'History', icon: 'time-outline', activeIcon: 'time' },
  [TABS.PROFILE]: { label: 'Profile', icon: 'person-outline', activeIcon: 'person' },
};

function TabButton({ active, tab, onPress, theme }) {
  const styles = createStyles(theme, false);
  const meta = TAB_META[tab];

  return (
    <Pressable style={[styles.tabButton, active ? styles.tabButtonActive : null]} onPress={onPress}>
      <Ionicons name={active ? meta.activeIcon : meta.icon} size={19} color={active ? theme.colors.accent : theme.colors.softText} />
      <Text style={[styles.tabLabel, active ? styles.tabLabelActive : null]}>{meta.label}</Text>
    </Pressable>
  );
}

export default function App() {
  const theme = useMemo(() => getTheme(), []);
  const { width, height } = useWindowDimensions();
  const isLandscape = width > height;
  const styles = useMemo(() => createStyles(theme, isLandscape), [theme, isLandscape]);

  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState(TABS.HOME);
  const [homeView, setHomeView] = useState(HOME_VIEWS.MAIN);
  const [connection, setConnection] = useState(null);
  const [session, setSession] = useState(null);
  const [authRoute, setAuthRoute] = useState(AUTH_ROUTES.LANDING);

  async function refreshConnection(showSuccess = false) {
    const result = await testBackendConnection();
    setConnection(result);

    if (!result.ok) {
      setError(result.error || 'Unable to reach backend');
    } else if (showSuccess) {
      Alert.alert('Connection looks good', 'The backend is reachable.');
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
    setActiveTab(TABS.HOME);
    setHomeView(HOME_VIEWS.MAIN);
  }, [session]);

  useEffect(() => {
    if (!session || !selectedJob || (selectedJob.status !== 'queued' && selectedJob.status !== 'processing')) {
      return undefined;
    }

    const intervalId = setInterval(() => {
      loadJobs();
    }, 4000);

    return () => clearInterval(intervalId);
  }, [session, selectedJob]);

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

      if (activeTab === TABS.HOME && homeView === HOME_VIEWS.UPLOAD) {
        setHomeView(HOME_VIEWS.MAIN);
        return true;
      }

      if (activeTab !== TABS.HOME) {
        setActiveTab(TABS.HOME);
        return true;
      }

      return false;
    });

    return () => subscription.remove();
  }, [activeTab, authRoute, homeView, selectedJob, session]);

  async function uploadCapturedSketch({
    imageUri,
    imageName,
    mimeType,
    name,
    description,
    failureMessage,
  }) {
    try {
      setBusy(true);
      setError('');

      const created = await createJobWithImage({
        name,
        description,
        imageUri,
        imageName,
        mimeType,
      });

      let nextJob = created;
      try {
        nextJob = await startJob(created.id);
      } catch (startError) {
        setError(startError.message || 'Uploaded, but could not start processing');
      }

      setSelectedJob(nextJob);
      setActiveTab(TABS.HISTORY);
      setHomeView(HOME_VIEWS.MAIN);
      await loadJobs();
    } catch (err) {
      setError(err.message || failureMessage);
      Alert.alert('Upload failed', err.message || failureMessage);
    } finally {
      setBusy(false);
    }
  }

  async function handleUploadImage() {
    try {
      setBusy(true);
      setError('');

      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        Alert.alert('Permission needed', 'Please allow camera access.');
        return;
      }

      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ['images'],
        quality: 1,
        cameraType: ImagePicker.CameraType.back,
      });

      if (result.canceled || !result.assets?.length) {
        return;
      }

      const asset = result.assets[0];
      await uploadCapturedSketch({
        imageUri: asset.uri,
        imageName: asset.fileName || `floorplan-${Date.now()}.jpg`,
        mimeType: asset.mimeType || 'image/jpeg',
        name: 'New floorplan scan',
        description: 'Captured from camera',
        failureMessage: 'Unable to upload image',
      });
    } catch (err) {
      setError(err.message || 'Unable to open camera');
      Alert.alert('Camera failed', err.message || 'Unable to open camera.');
    } finally {
      setBusy(false);
    }
  }

  async function handlePickFromGallery() {
    try {
      setBusy(true);
      setError('');

      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        Alert.alert('Permission needed', 'Please allow photo access.');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        quality: 1,
      });

      if (result.canceled || !result.assets?.length) {
        return;
      }

      const asset = result.assets[0];
      await uploadCapturedSketch({
        imageUri: asset.uri,
        imageName: asset.fileName || 'floorplan.jpg',
        mimeType: asset.mimeType || 'image/jpeg',
        name: 'Imported floorplan',
        description: 'Imported from phone',
        failureMessage: 'Unable to import image',
      });
    } catch (err) {
      setError(err.message || 'Unable to import image');
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
      const started = await startJob(job.id);
      setSelectedJob(started);
      await loadJobs();
    } catch (err) {
      setError(err.message || 'Unable to start job');
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
      await deleteJob(job.id);

      if (selectedJob?.id === job.id) {
        setSelectedJob(null);
      }

      await loadJobs();
    } catch (err) {
      setError(err.message || 'Unable to delete job');
      Alert.alert('Delete failed', err.message || 'Unable to delete job.');
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveResult(url) {
    try {
      setBusy(true);
      setError('');
      await saveImageToDevice(url, 'Sketch2FloorPlan');
      Alert.alert('Saved', 'The floor plan was sent to your device storage.');
    } catch (err) {
      setError(err.message || 'Unable to prepare download');
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
    setHomeView(HOME_VIEWS.MAIN);
    setSelectedJob(null);
    setError('');
    setAuthRoute(AUTH_ROUTES.LANDING);
  }

  function handleSignOut() {
    setSession(null);
    setConnection(null);
    setActiveTab(TABS.HOME);
    setHomeView(HOME_VIEWS.MAIN);
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

    if (homeView === HOME_VIEWS.UPLOAD) {
      return (
        <UploadCaptureScreen
          busy={busy}
          onPickFromGallery={handlePickFromGallery}
          onOpenCamera={handleUploadImage}
          onBack={() => setHomeView(HOME_VIEWS.MAIN)}
          theme={theme}
          isLandscape={isLandscape}
        />
      );
    }

    return (
      <HomeScreen
        busy={busy}
        onOpenUploadScreen={() => setHomeView(HOME_VIEWS.UPLOAD)}
        onCaptureImage={handleUploadImage}
        theme={theme}
        isLandscape={isLandscape}
      />
    );
  }

  return (
    <SafeAreaProvider>
      <SafeAreaView edges={['top', 'left', 'right']} style={styles.safeArea}>
        <StatusBar barStyle="dark-content" backgroundColor={theme.colors.background} />
        <ExpoStatusBar style="dark" />

        <View style={styles.container}>
          <View style={styles.screenArea}>{renderCurrentScreen()}</View>

          {session && !selectedJob ? (
            <View style={styles.bottomNav}>
              <TabButton
                active={activeTab === TABS.HOME}
                tab={TABS.HOME}
                onPress={() => {
                  setActiveTab(TABS.HOME);
                  setHomeView(HOME_VIEWS.MAIN);
                }}
                theme={theme}
              />
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
      paddingTop: 10,
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
      backgroundColor: theme.colors.heroTint,
    },
    tabLabel: {
      color: theme.colors.softText,
      fontWeight: '800',
      fontSize: 12,
    },
    tabLabelActive: {
      color: theme.colors.accent,
    },
  });
}
