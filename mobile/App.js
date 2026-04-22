import React, { useEffect, useMemo, useState } from 'react';
import { Alert, BackHandler, Platform, StatusBar, StyleSheet, View, useWindowDimensions } from 'react-native';
import { StatusBar as ExpoStatusBar } from 'expo-status-bar';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

import BottomTabBar from './src/components/navigation/BottomTabBar';
import { AUTH_ROUTES, HOME_VIEWS, TABS } from './src/constants/navigation';
import { useFloorplanJobs } from './src/hooks/useFloorplanJobs';
import AuthScreen from './src/screens/AuthScreen';
import HistoryScreen from './src/screens/HistoryScreen';
import HomeScreen from './src/screens/HomeScreen';
import LandingScreen from './src/screens/LandingScreen';
import ProfileScreen from './src/screens/ProfileScreen';
import ResultsScreen from './src/screens/ResultsScreen';
import UploadCaptureScreen from './src/screens/UploadCaptureScreen';
import { getTheme } from './src/theme';
import { captureImageFromCamera, pickImageFromGallery } from './src/utils/imageSelection';

const MAIN_TABS = [TABS.HOME, TABS.HISTORY, TABS.PROFILE];

function createSession(authValues) {
  return {
    email: authValues.email,
    name: authValues.fullName || authValues.email.split('@')[0],
  };
}

export default function App() {
  const theme = useMemo(() => getTheme(), []);
  const { width, height } = useWindowDimensions();
  const isLandscape = width > height;
  const styles = useMemo(() => createStyles(theme, isLandscape), [theme, isLandscape]);

  const [activeTab, setActiveTab] = useState(TABS.HOME);
  const [homeView, setHomeView] = useState(HOME_VIEWS.MAIN);
  const [session, setSession] = useState(null);
  const [authRoute, setAuthRoute] = useState(AUTH_ROUTES.LANDING);

  const {
    jobs,
    selectedJob,
    setSelectedJob,
    clearSelectedJob,
    loading,
    busy,
    error,
    connection,
    refreshConnection,
    loadJobs,
    uploadAsset,
    startExistingJob,
    deleteExistingJob,
    saveResult,
  } = useFloorplanJobs({
    enabled: Boolean(session),
  });

  useEffect(() => {
    if (session) {
      return;
    }

    setActiveTab(TABS.HOME);
    setHomeView(HOME_VIEWS.MAIN);
    setAuthRoute(AUTH_ROUTES.LANDING);
  }, [session]);

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
        clearSelectedJob();
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
  }, [activeTab, authRoute, clearSelectedJob, homeView, selectedJob, session]);

  async function handleConnectionRefresh(showSuccess = false) {
    const result = await refreshConnection();
    if (showSuccess && result.ok) {
      Alert.alert('Connection looks good', 'The backend is reachable.');
    }
    return result;
  }

  async function handleCaptureImage() {
    try {
      const asset = await captureImageFromCamera();
      if (!asset) {
        return;
      }

      await uploadAsset({
        asset,
        name: 'New floorplan scan',
        description: 'Captured from camera',
        fallbackName: `floorplan-${Date.now()}.jpg`,
        failureMessage: 'Unable to upload image',
      });

      setActiveTab(TABS.HISTORY);
      setHomeView(HOME_VIEWS.MAIN);
    } catch (err) {
      Alert.alert('Camera failed', err.message || 'Unable to open camera.');
    }
  }

  async function handlePickFromGallery() {
    try {
      const asset = await pickImageFromGallery();
      if (!asset) {
        return;
      }

      await uploadAsset({
        asset,
        name: 'Imported floorplan',
        description: 'Imported from phone',
        fallbackName: 'floorplan.jpg',
        failureMessage: 'Unable to import image',
      });

      setActiveTab(TABS.HISTORY);
      setHomeView(HOME_VIEWS.MAIN);
    } catch (err) {
      Alert.alert('Upload failed', err.message || 'Unable to import image.');
    }
  }

  async function handleStartJob(job) {
    try {
      await startExistingJob(job);
    } catch (err) {
      Alert.alert('Could not start', err.message || 'Unable to start job.');
    }
  }

  async function handleDeleteJob(job) {
    try {
      await deleteExistingJob(job);
    } catch (err) {
      Alert.alert('Delete failed', err.message || 'Unable to delete job.');
    }
  }

  async function handleSaveResult(url) {
    try {
      await saveResult(url);
      Alert.alert('Saved', 'The floor plan was sent to your device storage.');
    } catch (err) {
      Alert.alert('Download failed', err.message || 'Unable to prepare download.');
    }
  }

  function handleAuthSubmit(authValues) {
    setSession(createSession(authValues));
    setActiveTab(TABS.HOME);
    setHomeView(HOME_VIEWS.MAIN);
    clearSelectedJob();
    setAuthRoute(AUTH_ROUTES.LANDING);
  }

  function handleSignOut() {
    setSession(null);
  }

  function handleTabChange(tab) {
    setActiveTab(tab);
    if (tab === TABS.HOME) {
      setHomeView(HOME_VIEWS.MAIN);
    }
  }

  async function handleRefreshJobs() {
    try {
      await loadJobs();
    } catch (err) {
      Alert.alert('Refresh failed', err.message || 'Unable to refresh jobs.');
    }
  }

  function renderAuthenticatedScreen() {
    if (selectedJob) {
      return (
        <ResultsScreen
          job={selectedJob}
          busy={busy}
          error={error}
          onBack={clearSelectedJob}
          onRefresh={handleRefreshJobs}
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
          onRefreshConnection={() => handleConnectionRefresh(true)}
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
          onOpenCamera={handleCaptureImage}
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
        onCaptureImage={handleCaptureImage}
        theme={theme}
        isLandscape={isLandscape}
      />
    );
  }

  function renderCurrentScreen() {
    if (!session) {
      if (authRoute === AUTH_ROUTES.LANDING) {
        return (
          <LandingScreen
            theme={theme}
            isLandscape={isLandscape}
            onLogin={() => setAuthRoute(AUTH_ROUTES.LOGIN)}
            onSignUp={() => setAuthRoute(AUTH_ROUTES.SIGNUP)}
          />
        );
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

    return renderAuthenticatedScreen();
  }

  return (
    <SafeAreaProvider>
      <SafeAreaView edges={['top', 'left', 'right']} style={styles.safeArea}>
        <StatusBar barStyle="dark-content" backgroundColor={theme.colors.background} />
        <ExpoStatusBar style="dark" />

        <View style={styles.container}>
          <View style={styles.screenArea}>{renderCurrentScreen()}</View>

          {session && !selectedJob ? <BottomTabBar activeTab={activeTab} onSelectTab={handleTabChange} tabs={MAIN_TABS} theme={theme} /> : null}
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
  });
}
