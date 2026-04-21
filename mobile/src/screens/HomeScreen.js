import React, { useEffect, useRef } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

function ActionButton({ icon, label, detail, primary, disabled, onPress, styles, theme }) {
  return (
    <Pressable
      style={[styles.actionButton, primary ? styles.actionButtonPrimary : styles.actionButtonSecondary, disabled ? styles.actionButtonDisabled : null]}
      onPress={onPress}
      disabled={disabled}
    >
      <View style={[styles.actionIcon, primary ? styles.actionIconPrimary : styles.actionIconSecondary]}>
        <Ionicons name={icon} size={20} color={primary ? '#ffffff' : theme.colors.text} />
      </View>

      <View style={styles.actionCopy}>
        <Text style={[styles.actionLabel, primary ? styles.actionLabelPrimary : null]}>{label}</Text>
        <Text style={[styles.actionDetail, primary ? styles.actionDetailPrimary : null]}>{detail}</Text>
      </View>

      <Ionicons name="arrow-forward" size={18} color={primary ? '#ffffff' : theme.colors.text} />
    </Pressable>
  );
}

function SketchPlaceholder({ styles, theme }) {
  return (
    <View style={styles.placeholderSurface}>
      <View style={styles.sheet} />

      <View style={styles.plan}>
        <View style={styles.planTop} />
        <View style={styles.planLeft} />
        <View style={styles.planRight} />
        <View style={styles.planBottom} />
        <View style={styles.planMiddle} />
        <View style={styles.planInset} />
        <View style={[styles.planDoor, { borderColor: theme.colors.text }]} />
      </View>
    </View>
  );
}

export default function HomeScreen({ busy, onUploadImage, onPickFromGallery, theme, isLandscape }) {
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
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <Animated.View style={[styles.screen, { opacity: fade, transform: [{ translateY: rise }] }]}>
        <View style={styles.hero}>
          <Text style={styles.title}>New floorplan</Text>
          <Text style={styles.subtitle}>Choose a sketch source.</Text>
        </View>

        <View style={[styles.stage, isLandscape ? styles.stageLandscape : null]}>
          <View style={styles.previewBlock}>
            <SketchPlaceholder styles={styles} theme={theme} />
            <View style={styles.previewMeta}>
              <Text style={styles.previewTitle}>Ready for upload</Text>
              <Text style={styles.previewText}>No sketch selected</Text>
            </View>
          </View>

          <View style={styles.actions}>
            <ActionButton
              icon="camera"
              label={busy ? 'Opening' : 'Camera'}
              detail="Capture"
              primary
              disabled={busy}
              onPress={onUploadImage}
              styles={styles}
              theme={theme}
            />

            <ActionButton
              icon="image-outline"
              label={busy ? 'Opening' : 'Import'}
              detail="From phone"
              disabled={busy}
              onPress={onPickFromGallery}
              styles={styles}
              theme={theme}
            />
          </View>
        </View>
      </Animated.View>
    </ScrollView>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    content: {
      flexGrow: 1,
      paddingBottom: 28,
    },
    screen: {
      gap: 18,
      paddingBottom: 4,
    },
    hero: {
      alignItems: 'center',
      paddingTop: isLandscape ? 4 : 10,
    },
    title: {
      color: theme.colors.text,
      fontSize: isLandscape ? 34 : 32,
      fontWeight: '900',
      letterSpacing: -1,
      textAlign: 'center',
    },
    subtitle: {
      marginTop: 8,
      color: theme.colors.muted,
      fontSize: 15,
      fontWeight: '700',
      textAlign: 'center',
    },
    stage: {
      backgroundColor: theme.colors.surface,
      borderRadius: 30,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: isLandscape ? 18 : 16,
      gap: 16,
      ...theme.shadow.card,
    },
    stageLandscape: {
      flexDirection: 'row',
      alignItems: 'stretch',
    },
    previewBlock: {
      flex: 1,
      gap: 12,
    },
    placeholderSurface: {
      minHeight: isLandscape ? 320 : 360,
      borderRadius: 26,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      backgroundColor: theme.colors.heroTint,
      overflow: 'hidden',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 22,
    },
    sheet: {
      position: 'absolute',
      width: '82%',
      height: '78%',
      borderRadius: 24,
      borderWidth: 1,
      borderColor: theme.colors.border,
      backgroundColor: theme.colors.surface,
      transform: [{ rotate: '-5deg' }],
      opacity: 0.7,
    },
    plan: {
      width: '88%',
      height: '82%',
      borderRadius: 24,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      backgroundColor: theme.colors.surface,
      position: 'relative',
      overflow: 'hidden',
    },
    planTop: {
      position: 'absolute',
      left: '16%',
      top: '18%',
      width: '54%',
      height: 7,
      borderRadius: 6,
      backgroundColor: theme.colors.canvasLine,
    },
    planLeft: {
      position: 'absolute',
      left: '16%',
      top: '18%',
      width: 7,
      height: '48%',
      borderRadius: 6,
      backgroundColor: theme.colors.canvasLine,
    },
    planRight: {
      position: 'absolute',
      right: '18%',
      top: '18%',
      width: 7,
      height: '26%',
      borderRadius: 6,
      backgroundColor: theme.colors.canvasLine,
    },
    planBottom: {
      position: 'absolute',
      left: '16%',
      bottom: '18%',
      width: '46%',
      height: 7,
      borderRadius: 6,
      backgroundColor: theme.colors.canvasLine,
    },
    planMiddle: {
      position: 'absolute',
      left: '43%',
      top: '36%',
      width: 7,
      height: '28%',
      borderRadius: 6,
      backgroundColor: theme.colors.canvasLine,
    },
    planInset: {
      position: 'absolute',
      right: '32%',
      bottom: '18%',
      width: '18%',
      height: 7,
      borderRadius: 6,
      backgroundColor: theme.colors.canvasLine,
    },
    planDoor: {
      position: 'absolute',
      left: '28%',
      bottom: '18.2%',
      width: 44,
      height: 44,
      borderTopWidth: 5,
      borderRightWidth: 5,
      borderTopRightRadius: 44,
      transform: [{ rotate: '90deg' }],
    },
    previewMeta: {
      alignItems: 'center',
      gap: 4,
      paddingBottom: 4,
    },
    previewTitle: {
      color: theme.colors.text,
      fontSize: 17,
      fontWeight: '900',
      letterSpacing: -0.4,
    },
    previewText: {
      color: theme.colors.softText,
      fontWeight: '700',
    },
    actions: {
      gap: 12,
      width: isLandscape ? 300 : '100%',
      justifyContent: 'center',
    },
    actionButton: {
      minHeight: 84,
      borderRadius: 24,
      paddingHorizontal: 18,
      paddingVertical: 16,
      flexDirection: 'row',
      alignItems: 'center',
      gap: 14,
    },
    actionButtonPrimary: {
      backgroundColor: theme.colors.text,
    },
    actionButtonSecondary: {
      backgroundColor: theme.colors.surfaceElevated,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
    },
    actionButtonDisabled: {
      opacity: 0.74,
    },
    actionIcon: {
      width: 48,
      height: 48,
      borderRadius: 24,
      alignItems: 'center',
      justifyContent: 'center',
    },
    actionIconPrimary: {
      backgroundColor: 'rgba(255,255,255,0.14)',
    },
    actionIconSecondary: {
      backgroundColor: theme.colors.surface,
    },
    actionCopy: {
      flex: 1,
    },
    actionLabel: {
      color: theme.colors.text,
      fontSize: 19,
      fontWeight: '900',
      letterSpacing: -0.3,
    },
    actionLabelPrimary: {
      color: '#ffffff',
    },
    actionDetail: {
      marginTop: 4,
      color: theme.colors.softText,
      fontWeight: '700',
    },
    actionDetailPrimary: {
      color: 'rgba(255,255,255,0.74)',
    },
  });
}
