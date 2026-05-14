import React from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { AuthBackdrop, HeroArtwork } from '../components/auth/AuthVisuals';
import { useEntranceAnimation } from '../hooks/useEntranceAnimation';

export default function HomeScreen({ busy, onOpenUploadScreen, onCaptureImage, theme, isLandscape }) {
  const animatedStyle = useEntranceAnimation();
  const styles = createStyles(theme, isLandscape);

  return (
    <AuthBackdrop theme={theme}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Animated.View style={animatedStyle}>
          <View style={styles.headerBlock}>
            <Text style={styles.title}>Sketch2FloorPlan</Text>
            <Text style={styles.subtitle}>AI floor plan digitizer</Text>
          </View>

          <View style={styles.heroCard}>
            <View style={styles.heroVisual}>
              <HeroArtwork theme={theme} />
            </View>
            <Text style={styles.heroTitle}>Upload or capture a hand-drawn sketch</Text>
          </View>

          <Pressable style={[styles.primaryButton, busy ? styles.buttonDisabled : null]} onPress={onOpenUploadScreen} disabled={busy}>
            <Text style={styles.primaryButtonText}>Upload Sketch</Text>
          </Pressable>

          <Pressable style={[styles.secondaryButton, busy ? styles.buttonDisabled : null]} onPress={onCaptureImage} disabled={busy}>
            <Text style={styles.secondaryButtonText}>{busy ? 'Opening Camera' : 'Capture Image'}</Text>
          </Pressable>
        </Animated.View>
      </ScrollView>
    </AuthBackdrop>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    content: {
      flexGrow: 1,
      paddingBottom: 8,
    },
    headerBlock: {
      marginBottom: 6,
    },
    title: {
      color: theme.colors.text,
      fontSize: isLandscape ? 30 : 27,
      fontWeight: '900',
      letterSpacing: -0.9,
    },
    subtitle: {
      marginTop: 4,
      marginBottom: 4,
      color: theme.colors.muted,
      fontWeight: '600',
    },
    heroCard: {
      backgroundColor: theme.colors.surface,
      borderRadius: 30,
      borderWidth: 1,
      borderColor: 'rgba(255,255,255,0.72)',
      padding: 10,
      marginBottom: 8,
      ...theme.shadow.card,
    },
    heroVisual: {
      minHeight: isLandscape ? 116 : 86,
      borderRadius: 22,
      marginBottom: 6,
      overflow: 'hidden',
    },
    heroTitle: {
      color: theme.colors.text,
      fontSize: isLandscape ? 21 : 18,
      lineHeight: isLandscape ? 25 : 22,
      fontWeight: '900',
      letterSpacing: -0.8,
      maxWidth: isLandscape ? '82%' : '100%',
    },
    primaryButton: {
      height: 54,
      borderRadius: 18,
      backgroundColor: theme.colors.authDark,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 6,
      ...theme.shadow.soft,
    },
    primaryButtonText: {
      color: '#ffffff',
      fontSize: 17,
      fontWeight: '800',
    },
    secondaryButton: {
      height: 54,
      borderRadius: 18,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 4,
    },
    secondaryButtonText: {
      color: theme.colors.text,
      fontSize: 17,
      fontWeight: '800',
    },
    buttonDisabled: {
      opacity: 0.72,
    },
  });
}
