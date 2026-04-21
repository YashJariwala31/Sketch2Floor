import React, { useEffect, useRef } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

function ActionButton({ icon, label, primary, onPress, disabled, styles, theme }) {
  return (
    <Pressable
      style={[styles.actionButton, primary ? styles.actionButtonPrimary : styles.actionButtonSecondary, disabled ? styles.actionButtonDisabled : null]}
      onPress={onPress}
      disabled={disabled}
    >
      <View style={[styles.actionIcon, primary ? styles.actionIconPrimary : styles.actionIconSecondary]}>
        <Ionicons name={icon} size={22} color={primary ? '#ffffff' : theme.colors.text} />
      </View>
      <Text style={[styles.actionLabel, primary ? styles.actionLabelPrimary : null]}>{label}</Text>
    </Pressable>
  );
}

function UploadPreview({ styles, theme }) {
  return (
    <View style={styles.previewShell}>
      <View style={styles.previewStage}>
        <View style={styles.dashedFrame} />
        <View style={styles.uploadBadge}>
          <Ionicons name="arrow-up-outline" size={22} color={theme.colors.accent} />
        </View>
        <Text style={styles.previewTitle}>Drop image or preview here</Text>
        <Text style={styles.previewSubtitle}>JPEG or PNG</Text>
      </View>
    </View>
  );
}

export default function UploadCaptureScreen({ busy, onPickFromGallery, onOpenCamera, onBack, theme, isLandscape }) {
  const fade = useRef(new Animated.Value(0)).current;
  const rise = useRef(new Animated.Value(16)).current;
  const styles = createStyles(theme, isLandscape);

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fade, {
        toValue: 1,
        duration: 280,
        useNativeDriver: true,
      }),
      Animated.spring(rise, {
        toValue: 0,
        useNativeDriver: true,
        damping: 16,
        stiffness: 150,
      }),
    ]).start();
  }, [fade, rise]);

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <Animated.View style={{ opacity: fade, transform: [{ translateY: rise }] }}>
        <View style={styles.headerRow}>
          <Pressable style={styles.backButton} onPress={onBack}>
            <Ionicons name="chevron-back" size={18} color={theme.colors.text} />
          </Pressable>

          <View style={styles.headerCopy}>
            <Text style={styles.title}>Upload sketch</Text>
            <Text style={styles.subtitle}>Choose a source image</Text>
          </View>
        </View>

        <View style={styles.stage}>
          <UploadPreview styles={styles} theme={theme} />

          <View style={styles.actions}>
            <ActionButton
              icon="arrow-up-outline"
              label={busy ? 'Opening Gallery' : 'Choose from Gallery'}
              primary
              onPress={onPickFromGallery}
              disabled={busy}
              styles={styles}
              theme={theme}
            />
            <ActionButton
              icon="camera-outline"
              label={busy ? 'Opening Camera' : 'Open Camera'}
              onPress={onOpenCamera}
              disabled={busy}
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
      paddingBottom: 30,
    },
    headerRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 12,
      marginBottom: 16,
    },
    backButton: {
      width: 38,
      height: 38,
      borderRadius: 19,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.border,
    },
    headerCopy: {
      flex: 1,
    },
    title: {
      color: theme.colors.text,
      fontSize: isLandscape ? 34 : 31,
      fontWeight: '900',
      letterSpacing: -0.9,
    },
    subtitle: {
      marginTop: 6,
      color: theme.colors.muted,
      fontWeight: '700',
    },
    stage: {
      backgroundColor: theme.colors.surfaceElevated,
      borderRadius: theme.radius.xl,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      padding: 16,
      ...theme.shadow.card,
    },
    previewShell: {
      backgroundColor: theme.colors.heroTint,
      borderRadius: 28,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
      padding: 14,
      marginBottom: 16,
    },
    previewStage: {
      minHeight: isLandscape ? 290 : 340,
      borderRadius: 24,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      alignItems: 'center',
      justifyContent: 'center',
      overflow: 'hidden',
      padding: 20,
    },
    dashedFrame: {
      position: 'absolute',
      left: 16,
      right: 16,
      top: 16,
      bottom: 16,
      borderRadius: 20,
      borderWidth: 1.5,
      borderStyle: 'dashed',
      borderColor: theme.colors.noticeBorder,
    },
    uploadBadge: {
      width: 56,
      height: 56,
      borderRadius: 18,
      backgroundColor: theme.colors.accentSoft,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 18,
    },
    previewTitle: {
      color: theme.colors.text,
      fontSize: 20,
      fontWeight: '800',
      textAlign: 'center',
    },
    previewSubtitle: {
      marginTop: 8,
      color: theme.colors.muted,
      fontWeight: '700',
      textAlign: 'center',
    },
    actions: {
      gap: 12,
    },
    actionButton: {
      minHeight: 58,
      borderRadius: 18,
      paddingHorizontal: 18,
      flexDirection: 'row',
      alignItems: 'center',
      gap: 12,
      borderWidth: 1,
    },
    actionButtonPrimary: {
      backgroundColor: theme.colors.accent,
      borderColor: theme.colors.accent,
    },
    actionButtonSecondary: {
      backgroundColor: theme.colors.heroTint,
      borderColor: theme.colors.noticeBorder,
    },
    actionButtonDisabled: {
      opacity: 0.72,
    },
    actionIcon: {
      width: 34,
      height: 34,
      borderRadius: 12,
      alignItems: 'center',
      justifyContent: 'center',
    },
    actionIconPrimary: {
      backgroundColor: 'rgba(255,255,255,0.16)',
    },
    actionIconSecondary: {
      backgroundColor: theme.colors.panel,
    },
    actionLabel: {
      color: theme.colors.text,
      fontSize: 17,
      fontWeight: '800',
    },
    actionLabelPrimary: {
      color: '#ffffff',
    },
  });
}
