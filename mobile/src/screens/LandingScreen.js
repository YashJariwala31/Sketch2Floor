import React, { useEffect, useRef } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function LandingScreen({ theme, isLandscape, onLogin, onSignUp }) {
  const fade = useRef(new Animated.Value(0)).current;
  const rise = useRef(new Animated.Value(18)).current;
  const styles = createStyles(theme, isLandscape);

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fade, {
        toValue: 1,
        duration: 320,
        useNativeDriver: true,
      }),
      Animated.spring(rise, {
        toValue: 0,
        useNativeDriver: true,
        damping: 15,
        stiffness: 140,
      }),
    ]).start();
  }, [fade, rise]);

  return (
    <View style={styles.screen}>
      <View style={styles.topBar}>
        <View style={styles.brandRow}>
          <View style={styles.logoWrap}>
            <Ionicons name="sparkles-outline" size={18} color="#ffffff" />
          </View>
          <Text style={styles.brand}>Sketch2FloorPlan</Text>
        </View>

        <View style={styles.navRow}>
          <Pressable style={styles.ghostButton} onPress={onLogin}>
            <Text style={styles.ghostButtonText}>Log in</Text>
          </Pressable>
          <Pressable style={styles.primaryButton} onPress={onSignUp}>
            <Text style={styles.primaryButtonText}>Sign up</Text>
          </Pressable>
        </View>
      </View>

      <Animated.View style={[styles.heroWrap, { opacity: fade, transform: [{ translateY: rise }] }]}>
        <Text style={styles.heroLine}>
          <Text style={styles.heroPrimary}>Turn Sketches</Text>
        </Text>
        <Text style={styles.heroLine}>
          <Text style={styles.heroPrimary}>into</Text>
        </Text>
        <Text style={styles.heroLine}>
          <Text style={styles.heroAccent}>Floor Plans </Text>
          <Text style={styles.heroPrimary}>in</Text>
        </Text>
        <Text style={styles.heroLine}>
          <Text style={styles.heroHighlight}>Seconds</Text>
        </Text>

        <Text style={styles.heroCopy}>
          The AI-powered CAD tool for students, designers, and builders. Upload a hand-drawn sketch and turn it into a clean digital plan.
        </Text>
      </Animated.View>
    </View>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    screen: {
      flex: 1,
    },
    topBar: {
      paddingTop: 8,
      paddingBottom: 18,
      borderBottomWidth: 1,
      borderBottomColor: theme.colors.border,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12,
    },
    brandRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 10,
      flexShrink: 1,
    },
    logoWrap: {
      width: 34,
      height: 34,
      borderRadius: 17,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#23b8ff',
    },
    brand: {
      color: theme.colors.text,
      fontSize: 20,
      fontWeight: '900',
      letterSpacing: -0.7,
    },
    navRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
    },
    ghostButton: {
      paddingHorizontal: 12,
      paddingVertical: 10,
      borderRadius: 14,
    },
    ghostButtonText: {
      color: theme.colors.text,
      fontWeight: '800',
    },
    primaryButton: {
      paddingHorizontal: 16,
      paddingVertical: 11,
      borderRadius: 14,
      backgroundColor: theme.colors.text,
    },
    primaryButtonText: {
      color: '#ffffff',
      fontWeight: '900',
    },
    heroWrap: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      width: '100%',
      maxWidth: 460,
      alignSelf: 'center',
      paddingTop: 20,
      paddingBottom: 20,
    },
    heroLine: {
      textAlign: 'center',
      marginBottom: 2,
    },
    heroPrimary: {
      color: theme.colors.text,
      fontSize: isLandscape ? 46 : 40,
      fontWeight: '900',
      letterSpacing: -1.4,
      lineHeight: isLandscape ? 50 : 44,
    },
    heroAccent: {
      color: '#4d8cff',
      fontSize: isLandscape ? 46 : 40,
      fontWeight: '900',
      letterSpacing: -1.4,
      lineHeight: isLandscape ? 50 : 44,
    },
    heroHighlight: {
      color: '#2bd0e8',
      fontSize: isLandscape ? 46 : 40,
      fontWeight: '900',
      letterSpacing: -1.4,
      lineHeight: isLandscape ? 50 : 44,
    },
    heroCopy: {
      marginTop: 22,
      color: theme.colors.muted,
      fontSize: 17,
      lineHeight: 29,
      textAlign: 'center',
      width: '100%',
      maxWidth: 420,
      paddingHorizontal: 8,
    },
  });
}
