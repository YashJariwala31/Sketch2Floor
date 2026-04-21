import React, { useEffect, useRef } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

function blueprint(styles) {
  return (
    <View style={styles.blueprintWrap}>
      <View style={styles.blueprintLineTop} />
      <View style={styles.blueprintLineLeft} />
      <View style={styles.blueprintLineBottom} />
      <View style={styles.blueprintLineInner} />
      <View style={styles.blueprintLineRight} />
      <View style={styles.blueprintLineShort} />
      <View style={styles.blueprintDoorArc} />
    </View>
  );
}

function Pill({ label, styles }) {
  return (
    <View style={styles.tipPill}>
      <Text style={styles.tipPillText}>{label}</Text>
    </View>
  );
}

export default function HomeScreen({ busy, onOpenUploadScreen, onCaptureImage, theme, isLandscape }) {
  const fade = useRef(new Animated.Value(0)).current;
  const rise = useRef(new Animated.Value(18)).current;
  const styles = createStyles(theme, isLandscape);

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fade, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }),
      Animated.spring(rise, {
        toValue: 0,
        useNativeDriver: true,
        damping: 15,
        stiffness: 145,
      }),
    ]).start();
  }, [fade, rise]);

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <Animated.View style={{ opacity: fade, transform: [{ translateY: rise }] }}>
        <Text style={styles.title}>Sketch2FloorPlan</Text>
        <Text style={styles.subtitle}>AI floor plan digitizer</Text>

        <View style={styles.heroCard}>
          <View style={styles.heroVisual}>{blueprint(styles)}</View>
          <Text style={styles.heroKicker}>New project</Text>
          <Text style={styles.heroTitle}>Upload or capture a hand-drawn sketch</Text>
        </View>

        <Pressable style={[styles.primaryButton, busy ? styles.buttonDisabled : null]} onPress={onOpenUploadScreen} disabled={busy}>
          <Text style={styles.primaryButtonText}>Upload Sketch</Text>
        </Pressable>

        <Pressable style={[styles.secondaryButton, busy ? styles.buttonDisabled : null]} onPress={onCaptureImage} disabled={busy}>
          <Text style={styles.secondaryButtonText}>{busy ? 'Opening Camera' : 'Capture Image'}</Text>
        </Pressable>

        <View style={styles.tipCard}>
          <Text style={styles.tipLabel}>Quick tip</Text>
          <Text style={styles.tipTitle}>Use a flat photo with clear walls</Text>
          <View style={styles.tipRow}>
            <Pill label="White paper" styles={styles} />
            <Pill label="Good light" styles={styles} />
            <Pill label="Straight angle" styles={styles} />
          </View>
        </View>
      </Animated.View>
    </ScrollView>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    content: {
      paddingBottom: 32,
    },
    title: {
      color: theme.colors.text,
      fontSize: isLandscape ? 32 : 30,
      fontWeight: '900',
      letterSpacing: -0.9,
    },
    subtitle: {
      marginTop: 6,
      marginBottom: 18,
      color: theme.colors.muted,
      fontWeight: '600',
    },
    heroCard: {
      backgroundColor: theme.colors.surfaceElevated,
      borderRadius: theme.radius.xl,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      padding: 16,
      marginBottom: 14,
      ...theme.shadow.card,
    },
    heroVisual: {
      height: isLandscape ? 210 : 160,
      borderRadius: 24,
      backgroundColor: theme.colors.heroTint,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 14,
      overflow: 'hidden',
    },
    blueprintWrap: {
      width: '84%',
      height: '74%',
      position: 'relative',
      opacity: 0.95,
    },
    blueprintLineTop: {
      position: 'absolute',
      left: '9%',
      top: '12%',
      width: '54%',
      height: 6,
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    blueprintLineLeft: {
      position: 'absolute',
      left: '9%',
      top: '12%',
      width: 6,
      height: '54%',
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    blueprintLineBottom: {
      position: 'absolute',
      left: '9%',
      bottom: '16%',
      width: '48%',
      height: 6,
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    blueprintLineInner: {
      position: 'absolute',
      left: '39%',
      top: '12%',
      width: 6,
      height: '28%',
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    blueprintLineRight: {
      position: 'absolute',
      right: '19%',
      top: '12%',
      width: 6,
      height: '28%',
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    blueprintLineShort: {
      position: 'absolute',
      right: '19%',
      top: '40%',
      width: '17%',
      height: 6,
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    blueprintDoorArc: {
      position: 'absolute',
      left: '41%',
      bottom: '16%',
      width: 34,
      height: 34,
      borderTopWidth: 4,
      borderRightWidth: 4,
      borderTopRightRadius: 34,
      borderColor: theme.colors.canvasLine,
      transform: [{ rotate: '90deg' }],
    },
    heroKicker: {
      color: theme.colors.muted,
      fontSize: 13,
      fontWeight: '800',
      textAlign: 'right',
    },
    heroTitle: {
      marginTop: 8,
      color: theme.colors.text,
      fontSize: isLandscape ? 32 : 28,
      lineHeight: isLandscape ? 38 : 34,
      fontWeight: '900',
      letterSpacing: -0.8,
      maxWidth: isLandscape ? '82%' : '100%',
    },
    primaryButton: {
      height: 58,
      borderRadius: 18,
      backgroundColor: theme.colors.accent,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 12,
      ...theme.shadow.soft,
    },
    primaryButtonText: {
      color: '#ffffff',
      fontSize: 17,
      fontWeight: '800',
    },
    secondaryButton: {
      height: 58,
      borderRadius: 18,
      backgroundColor: theme.colors.heroTint,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 18,
    },
    secondaryButtonText: {
      color: theme.colors.text,
      fontSize: 17,
      fontWeight: '800',
    },
    buttonDisabled: {
      opacity: 0.72,
    },
    tipCard: {
      backgroundColor: theme.colors.heroTint,
      borderRadius: 22,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
      padding: 16,
    },
    tipLabel: {
      color: theme.colors.muted,
      fontSize: 12,
      fontWeight: '800',
      textTransform: 'uppercase',
      letterSpacing: 0.8,
    },
    tipTitle: {
      marginTop: 10,
      color: theme.colors.text,
      fontSize: 22,
      lineHeight: 28,
      fontWeight: '800',
    },
    tipRow: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: 8,
      marginTop: 14,
    },
    tipPill: {
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderRadius: 999,
      backgroundColor: theme.colors.surfaceElevated,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
    },
    tipPillText: {
      color: theme.colors.muted,
      fontSize: 13,
      fontWeight: '700',
    },
  });
}
