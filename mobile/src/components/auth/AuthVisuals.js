import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export function AuthBackdrop({ children, theme }) {
  const styles = createStyles(theme);

  return (
    <View style={styles.screen}>
      <View style={[styles.wash, styles.washTopLeft]} />
      <View style={[styles.wash, styles.washTopRight]} />
      <View style={[styles.wash, styles.washBottomLeft]} />
      <View style={[styles.wash, styles.washBottomRight]} />
      {children}
    </View>
  );
}

export function IridescentCube({ size = 72, theme, dark = false }) {
  const styles = createStyles(theme);
  const iconSize = Math.round(size * 0.82);
  const iconColor = dark ? '#FFFFFF' : theme.colors.authDark;

  return (
    <View style={[styles.iconShell, { width: size, height: size }]}>
      <Ionicons
        name="cube-outline"
        size={iconSize}
        color={theme.colors.authIridescentBlue}
        style={[styles.iconLayer, { transform: [{ translateX: -4 }, { translateY: -2 }] }]}
      />
      <Ionicons
        name="cube-outline"
        size={iconSize}
        color={theme.colors.authIridescentPurple}
        style={[styles.iconLayer, { transform: [{ translateX: 4 }, { translateY: -4 }] }]}
      />
      <Ionicons
        name="cube-outline"
        size={iconSize}
        color={theme.colors.authIridescentPink}
        style={[styles.iconLayer, { transform: [{ translateX: 2 }, { translateY: 4 }] }]}
      />
      <Ionicons name="cube" size={iconSize} color={iconColor} style={styles.iconLayer} />
    </View>
  );
}

export function HeroArtwork({ theme }) {
  const styles = createStyles(theme);

  return (
    <View style={styles.heroArtwork}>
      <View style={styles.heroTop}>
        <View style={[styles.heroGlow, styles.heroGlowBlue]} />
        <View style={[styles.heroGlow, styles.heroGlowPurple]} />
        <View style={[styles.heroGlow, styles.heroGlowPink]} />
      </View>

      <View style={styles.heroBadge}>
        <IridescentCube size={128} theme={theme} />
      </View>
    </View>
  );
}

function createStyles(theme) {
  return StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: theme.colors.authBackdrop,
      position: 'relative',
      overflow: 'hidden',
    },
    wash: {
      position: 'absolute',
      borderRadius: 56,
      opacity: 1,
    },
    washTopLeft: {
      width: 220,
      height: 220,
      top: -26,
      left: -48,
      backgroundColor: theme.colors.authMistBlue,
      transform: [{ rotate: '-16deg' }],
    },
    washTopRight: {
      width: 200,
      height: 200,
      top: 22,
      right: -44,
      backgroundColor: theme.colors.authMistWarm,
      transform: [{ rotate: '12deg' }],
    },
    washBottomLeft: {
      width: 220,
      height: 220,
      bottom: 46,
      left: -72,
      backgroundColor: theme.colors.authMistLavender,
      transform: [{ rotate: '24deg' }],
    },
    washBottomRight: {
      width: 230,
      height: 230,
      bottom: -34,
      right: -74,
      backgroundColor: theme.colors.authMistPink,
      transform: [{ rotate: '-18deg' }],
    },
    iconShell: {
      alignItems: 'center',
      justifyContent: 'center',
    },
    iconLayer: {
      position: 'absolute',
    },
    heroArtwork: {
      alignItems: 'center',
      marginBottom: 26,
    },
    heroTop: {
      width: '100%',
      minHeight: 248,
      borderRadius: 42,
      backgroundColor: theme.colors.authHeroTop,
      overflow: 'hidden',
      marginBottom: -56,
    },
    heroGlow: {
      position: 'absolute',
      borderRadius: 999,
      opacity: 1,
    },
    heroGlowBlue: {
      width: 180,
      height: 180,
      top: 28,
      left: 18,
      backgroundColor: theme.colors.authHeroBlue,
    },
    heroGlowPurple: {
      width: 190,
      height: 190,
      top: 40,
      right: 12,
      backgroundColor: theme.colors.authHeroPurple,
    },
    heroGlowPink: {
      width: 120,
      height: 120,
      bottom: 22,
      left: '38%',
      backgroundColor: theme.colors.authHeroPink,
    },
    heroBadge: {
      width: 180,
      height: 180,
      borderRadius: 42,
      backgroundColor: '#FFFFFF',
      alignItems: 'center',
      justifyContent: 'center',
      shadowColor: theme.colors.authCardShadow,
      shadowOffset: { width: 0, height: 18 },
      shadowOpacity: 0.18,
      shadowRadius: 36,
      elevation: 10,
    },
  });
}
