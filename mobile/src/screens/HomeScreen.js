import React, { useEffect, useRef } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function HomeScreen({ busy, onUploadImage, onPickFromGallery, theme, isLandscape }) {
  const headerFade = useRef(new Animated.Value(0)).current;
  const headerRise = useRef(new Animated.Value(24)).current;
  const styles = createStyles(theme, isLandscape);

  useEffect(() => {
    Animated.parallel([
      Animated.timing(headerFade, {
        toValue: 1,
        duration: 420,
        useNativeDriver: true,
      }),
      Animated.spring(headerRise, {
        toValue: 0,
        useNativeDriver: true,
        damping: 15,
        stiffness: 140,
      }),
    ]).start();
  }, [headerFade, headerRise]);

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <Animated.View
        style={[
          styles.heroCard,
          {
            opacity: headerFade,
            transform: [{ translateY: headerRise }],
          },
        ]}
      >
        <Text style={styles.heroTitle}>Create a new floorplan</Text>
        <Text style={styles.heroText}>Choose how you want to add your sketch.</Text>

        <View style={styles.actionGrid}>
          <Pressable style={[styles.actionCard, styles.primaryCard]} onPress={onUploadImage} disabled={busy}>
            <View style={styles.actionIconWrap}>
              <Ionicons name="camera" size={24} color="#ffffff" />
            </View>
            <Text style={styles.primaryActionTitle}>{busy ? 'Opening camera...' : 'Capture With Camera'}</Text>
          </Pressable>

          <Pressable style={styles.actionCard} onPress={onPickFromGallery} disabled={busy}>
            <View style={styles.secondaryIconWrap}>
              <Ionicons name="images-outline" size={24} color={theme.colors.accentStrong} />
            </View>
            <Text style={styles.actionTitle}>Choose From Phone</Text>
          </Pressable>
        </View>
      </Animated.View>
    </ScrollView>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    content: {
      paddingBottom: 28,
      paddingHorizontal: isLandscape ? 8 : 0,
    },
    heroCard: {
      backgroundColor: theme.colors.surface,
      borderRadius: theme.radius.lg,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: isLandscape ? theme.spacing.lg : theme.spacing.xl,
      marginBottom: theme.spacing.lg,
      ...theme.shadow.card,
    },
    heroTitle: {
      color: theme.colors.text,
      fontSize: isLandscape ? 28 : 30,
      fontWeight: '900',
      letterSpacing: -0.8,
    },
    heroText: {
      marginTop: 8,
      color: theme.colors.muted,
      lineHeight: 22,
    },
    actionGrid: {
      gap: 14,
      marginTop: 24,
      flexDirection: isLandscape ? 'row' : 'column',
    },
    actionCard: {
      flex: 1,
      backgroundColor: theme.colors.surfaceAlt,
      borderRadius: 24,
      padding: 18,
      borderWidth: 1,
      borderColor: theme.colors.border,
      minHeight: isLandscape ? 180 : undefined,
      justifyContent: 'center',
    },
    primaryCard: {
      backgroundColor: theme.colors.accent,
      borderColor: theme.colors.accent,
    },
    actionIconWrap: {
      width: 48,
      height: 48,
      borderRadius: 24,
      backgroundColor: 'rgba(255,255,255,0.18)',
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 14,
    },
    secondaryIconWrap: {
      width: 48,
      height: 48,
      borderRadius: 24,
      backgroundColor: theme.colors.surface,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 14,
    },
    primaryActionTitle: {
      color: '#ffffff',
      fontWeight: '800',
      fontSize: 18,
    },
    actionTitle: {
      color: theme.colors.text,
      fontWeight: '800',
      fontSize: 18,
    },
  });
}
