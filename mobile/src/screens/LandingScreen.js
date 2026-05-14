import React from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { AuthBackdrop, HeroArtwork } from '../components/auth/AuthVisuals';
import { useEntranceAnimation } from '../hooks/useEntranceAnimation';

export default function LandingScreen({ theme, isLandscape, onLogin, onSignUp }) {
  const animatedStyle = useEntranceAnimation({
    duration: 320,
    damping: 15,
    stiffness: 140,
  });
  const styles = createStyles(theme, isLandscape);

  return (
    <AuthBackdrop theme={theme}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Animated.View style={[styles.shell, animatedStyle]}>
          <HeroArtwork theme={theme} />

          <Text style={styles.title}>Sketch to floor plan, without the messy middle.</Text>
          <Text style={styles.subtitle}>
            Clean digital output, measured overlays, and a calmer workflow from the first upload.
          </Text>

          <Pressable style={styles.primaryButton} onPress={onLogin}>
            <Text style={styles.primaryButtonText}>Login</Text>
            <Ionicons name="chevron-forward" size={18} color="#FFFFFF" />
          </Pressable>

          <Pressable style={styles.secondaryRow} onPress={onSignUp}>
            <Text style={styles.secondaryText}>Don&apos;t have an account?</Text>
            <Text style={styles.secondaryLink}>Sign up</Text>
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
      justifyContent: 'center',
      paddingVertical: 28,
    },
    shell: {
      width: '100%',
      maxWidth: 470,
      alignSelf: 'center',
      paddingHorizontal: isLandscape ? 12 : 6,
    },
    title: {
      color: theme.colors.text,
      fontSize: isLandscape ? 34 : 31,
      lineHeight: isLandscape ? 40 : 36,
      fontWeight: '900',
      textAlign: 'center',
    },
    subtitle: {
      marginTop: 16,
      color: theme.colors.muted,
      fontSize: 16,
      lineHeight: 24,
      textAlign: 'center',
      paddingHorizontal: 10,
    },
    primaryButton: {
      marginTop: 28,
      minHeight: 58,
      borderRadius: 18,
      backgroundColor: theme.colors.authDark,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
      paddingHorizontal: 20,
    },
    primaryButtonText: {
      color: '#FFFFFF',
      fontSize: 16,
      fontWeight: '800',
    },
    secondaryRow: {
      marginTop: 18,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 6,
    },
    secondaryText: {
      color: theme.colors.muted,
      fontWeight: '600',
    },
    secondaryLink: {
      color: theme.colors.text,
      fontWeight: '800',
    },
  });
}
