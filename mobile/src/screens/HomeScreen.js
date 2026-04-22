import React, { useEffect, useRef } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

function blueprint(styles) {
  return (
    <View style={styles.blueprintWrap}>
      <View style={styles.sheetBack} />
      <View style={styles.sheetFront}>
        <View style={styles.gridH1} />
        <View style={styles.gridH2} />
        <View style={styles.gridH3} />
        <View style={styles.gridV1} />
        <View style={styles.gridV2} />
        <View style={styles.gridV3} />
        <View style={styles.roomFillMain} />
        <View style={styles.roomFillSide} />
        <View style={styles.planWallTop} />
        <View style={styles.planWallLeft} />
        <View style={styles.planWallBottom} />
        <View style={styles.planWallInnerVertical} />
        <View style={styles.planWallInnerHorizontal} />
        <View style={styles.planWallRight} />
        <View style={styles.planWallCorner} />
        <View style={styles.planDoorArc} />
        <View style={styles.planNodeOne} />
        <View style={styles.planNodeTwo} />
        <View style={styles.planNodeThree} />
      </View>
      <View style={styles.floatingPreview}>
        <View style={styles.previewLineTop} />
        <View style={styles.previewLineLeft} />
        <View style={styles.previewLineBottom} />
      </View>
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
      width: '86%',
      height: '78%',
      position: 'relative',
    },
    sheetBack: {
      position: 'absolute',
      inset: 10,
      borderRadius: 26,
      backgroundColor: 'rgba(255,255,255,0.52)',
      borderWidth: 1,
      borderColor: 'rgba(211, 225, 255, 0.65)',
      transform: [{ translateX: -10 }, { translateY: 8 }],
    },
    sheetFront: {
      position: 'absolute',
      left: '8%',
      top: '10%',
      width: '70%',
      height: '74%',
      borderRadius: 24,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
      overflow: 'hidden',
    },
    gridH1: {
      position: 'absolute',
      left: 0,
      right: 0,
      top: '26%',
      height: 1,
      backgroundColor: theme.colors.canvasGrid,
    },
    gridH2: {
      position: 'absolute',
      left: 0,
      right: 0,
      top: '50%',
      height: 1,
      backgroundColor: theme.colors.canvasGrid,
    },
    gridH3: {
      position: 'absolute',
      left: 0,
      right: 0,
      top: '74%',
      height: 1,
      backgroundColor: theme.colors.canvasGrid,
    },
    gridV1: {
      position: 'absolute',
      top: 0,
      bottom: 0,
      left: '26%',
      width: 1,
      backgroundColor: theme.colors.canvasGrid,
    },
    gridV2: {
      position: 'absolute',
      top: 0,
      bottom: 0,
      left: '52%',
      width: 1,
      backgroundColor: theme.colors.canvasGrid,
    },
    gridV3: {
      position: 'absolute',
      top: 0,
      bottom: 0,
      left: '78%',
      width: 1,
      backgroundColor: theme.colors.canvasGrid,
    },
    roomFillMain: {
      position: 'absolute',
      left: '13%',
      top: '18%',
      width: '42%',
      height: '35%',
      borderRadius: 14,
      backgroundColor: theme.colors.accentSoft,
      opacity: 0.65,
    },
    roomFillSide: {
      position: 'absolute',
      right: '12%',
      top: '24%',
      width: '17%',
      height: '20%',
      borderRadius: 12,
      backgroundColor: theme.colors.heroTintStrong,
    },
    planWallTop: {
      position: 'absolute',
      left: '12%',
      top: '18%',
      width: '52%',
      height: 6,
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    planWallLeft: {
      position: 'absolute',
      left: '12%',
      top: '18%',
      width: 6,
      height: '48%',
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    planWallBottom: {
      position: 'absolute',
      left: '12%',
      bottom: '18%',
      width: '50%',
      height: 6,
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    planWallInnerVertical: {
      position: 'absolute',
      left: '46%',
      top: '18%',
      width: 6,
      height: '23%',
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    planWallInnerHorizontal: {
      position: 'absolute',
      left: '68%',
      top: '44%',
      width: '18%',
      height: 6,
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    planWallRight: {
      position: 'absolute',
      right: '14%',
      top: '18%',
      width: 6,
      height: '26%',
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    planWallCorner: {
      position: 'absolute',
      right: '14%',
      top: '39%',
      width: '13%',
      height: 6,
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    planDoorArc: {
      position: 'absolute',
      left: '48%',
      bottom: '18%',
      width: 42,
      height: 42,
      borderTopWidth: 3,
      borderRightWidth: 3,
      borderTopRightRadius: 42,
      borderColor: theme.colors.accentStrong,
      transform: [{ rotate: '90deg' }],
    },
    planNodeOne: {
      position: 'absolute',
      left: '10%',
      top: '15%',
      width: 10,
      height: 10,
      borderRadius: 999,
      backgroundColor: theme.colors.accent,
    },
    planNodeTwo: {
      position: 'absolute',
      left: '44%',
      top: '15%',
      width: 10,
      height: 10,
      borderRadius: 999,
      backgroundColor: theme.colors.accent,
    },
    planNodeThree: {
      position: 'absolute',
      right: '12%',
      top: '15%',
      width: 10,
      height: 10,
      borderRadius: 999,
      backgroundColor: theme.colors.accent,
    },
    floatingPreview: {
      position: 'absolute',
      right: '4%',
      bottom: '12%',
      width: '28%',
      height: '34%',
      borderRadius: 20,
      backgroundColor: theme.colors.surfaceElevated,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
      ...theme.shadow.soft,
    },
    previewLineTop: {
      position: 'absolute',
      left: '18%',
      top: '26%',
      width: '44%',
      height: 4,
      borderRadius: 999,
      backgroundColor: theme.colors.accent,
    },
    previewLineLeft: {
      position: 'absolute',
      left: '18%',
      top: '26%',
      width: 4,
      height: '34%',
      borderRadius: 999,
      backgroundColor: theme.colors.accent,
    },
    previewLineBottom: {
      position: 'absolute',
      left: '18%',
      bottom: '24%',
      width: '54%',
      height: 4,
      borderRadius: 999,
      backgroundColor: theme.colors.accentSoft,
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
