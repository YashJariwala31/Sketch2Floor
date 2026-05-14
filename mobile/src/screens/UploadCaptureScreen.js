import React from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { AuthBackdrop } from '../components/auth/AuthVisuals';
import { useEntranceAnimation } from '../hooks/useEntranceAnimation';

function SourceRow({ icon, title, body, primary, onPress, disabled, styles, theme }) {
  return (
    <Pressable
      style={[
        styles.sourceRow,
        primary ? styles.sourceRowPrimary : styles.sourceRowSecondary,
        disabled ? styles.sourceRowDisabled : null,
      ]}
      onPress={onPress}
      disabled={disabled}
    >
      <View style={[styles.sourceIconWrap, primary ? styles.sourceIconWrapPrimary : styles.sourceIconWrapSecondary]}>
        <Ionicons name={icon} size={20} color={primary ? '#FFFFFF' : theme.colors.text} />
      </View>

      <View style={styles.sourceCopy}>
        <Text style={[styles.sourceTitle, primary ? styles.sourceTitlePrimary : null]}>{title}</Text>
        <Text style={[styles.sourceBody, primary ? styles.sourceBodyPrimary : null]}>{body}</Text>
      </View>

      <Ionicons
        name="chevron-forward"
        size={18}
        color={primary ? 'rgba(255,255,255,0.92)' : theme.colors.softText}
      />
    </Pressable>
  );
}

function FormatPill({ label, styles }) {
  return (
    <View style={styles.formatPill}>
      <Text style={styles.formatPillText}>{label}</Text>
    </View>
  );
}

export default function UploadCaptureScreen({ busy, onPickFromGallery, onOpenCamera, onBack, theme, isLandscape }) {
  const animatedStyle = useEntranceAnimation({
    distance: 16,
    duration: 280,
    damping: 16,
    stiffness: 150,
  });
  const styles = createStyles(theme, isLandscape);

  return (
    <AuthBackdrop theme={theme}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Animated.View style={animatedStyle}>
          <View style={styles.headerRow}>
            <Pressable style={styles.backButton} onPress={onBack}>
              <Ionicons name="chevron-back" size={18} color={theme.colors.text} />
            </Pressable>

            <View style={styles.headerCopy}>
              <Text style={styles.title}>Upload sketch</Text>
            </View>
          </View>

          <View style={styles.panel}>
            <View style={styles.previewCard}>
              <View style={styles.previewIcon}>
                <Ionicons name="document-text-outline" size={30} color={theme.colors.accent} />
              </View>

              <Text style={styles.previewTitle}>Floor plan image</Text>
              <Text style={styles.previewBody}>
                Use a clear top-down sketch or photo with visible walls and minimal shadows.
              </Text>

              <View style={styles.formatRow}>
                <FormatPill label="JPG" styles={styles} />
                <FormatPill label="PNG" styles={styles} />
              </View>
            </View>

            <View style={styles.sourcesBlock}>

              <SourceRow
                icon="images-outline"
                title={busy ? 'Opening gallery' : 'Choose from Gallery'}
                body="Select an existing image from your device."
                primary
                onPress={onPickFromGallery}
                disabled={busy}
                styles={styles}
                theme={theme}
              />

              <SourceRow
                icon="camera-outline"
                title={busy ? 'Opening camera' : 'Open Camera'}
                body="Take a new photo and upload it directly."
                onPress={onOpenCamera}
                disabled={busy}
                styles={styles}
                theme={theme}
              />
            </View>
          </View>
        </Animated.View>
      </ScrollView>
    </AuthBackdrop>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    content: {
      flexGrow: 1,
      paddingBottom: 24,
    },
    headerRow: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      gap: 12,
      marginBottom: 18,
    },
    backButton: {
      width: 42,
      height: 42,
      borderRadius: 21,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
      ...theme.shadow.soft,
    },
    headerCopy: {
      flex: 1,
      paddingTop: 2,
    },
    title: {
      color: theme.colors.text,
      fontSize: isLandscape ? 33 : 30,
      fontWeight: '900',
      letterSpacing: -0.9,
    },
    subtitle: {
      marginTop: 6,
      color: theme.colors.muted,
      fontSize: 14,
      lineHeight: 20,
      fontWeight: '600',
      maxWidth: 330,
    },
    panel: {
      backgroundColor: theme.colors.surface,
      borderRadius: 30,
      borderWidth: 1,
      borderColor: 'rgba(255,255,255,0.72)',
      padding: 16,
      ...theme.shadow.card,
    },
    previewCard: {
      backgroundColor: theme.colors.surfaceAlt,
      borderRadius: 24,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
      paddingHorizontal: 18,
      paddingVertical: 22,
      alignItems: 'center',
      marginBottom: 16,
    },
    previewIcon: {
      width: 58,
      height: 58,
      borderRadius: 18,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 16,
    },
    previewTitle: {
      color: theme.colors.text,
      fontSize: 21,
      fontWeight: '800',
      textAlign: 'center',
    },
    previewBody: {
      marginTop: 8,
      color: theme.colors.muted,
      fontSize: 14,
      lineHeight: 21,
      fontWeight: '600',
      textAlign: 'center',
      maxWidth: 290,
    },
    formatRow: {
      flexDirection: 'row',
      gap: 8,
      marginTop: 16,
    },
    formatPill: {
      paddingHorizontal: 12,
      paddingVertical: 7,
      borderRadius: 999,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
    },
    formatPillText: {
      color: theme.colors.muted,
      fontSize: 12,
      fontWeight: '700',
    },
    sourcesBlock: {
      gap: 10,
    },
    sectionLabel: {
      color: theme.colors.softText,
      fontSize: 12,
      fontWeight: '700',
      marginBottom: 2,
    },
    sourceRow: {
      minHeight: 84,
      borderRadius: 22,
      borderWidth: 1,
      paddingHorizontal: 14,
      paddingVertical: 14,
      flexDirection: 'row',
      alignItems: 'center',
      gap: 12,
    },
    sourceRowPrimary: {
      backgroundColor: theme.colors.authDark,
      borderColor: theme.colors.authDark,
    },
    sourceRowSecondary: {
      backgroundColor: theme.colors.surfaceAlt,
      borderColor: theme.colors.authInputBorder,
    },
    sourceRowDisabled: {
      opacity: 0.72,
    },
    sourceIconWrap: {
      width: 42,
      height: 42,
      borderRadius: 14,
      alignItems: 'center',
      justifyContent: 'center',
    },
    sourceIconWrapPrimary: {
      backgroundColor: 'rgba(255,255,255,0.14)',
    },
    sourceIconWrapSecondary: {
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
    },
    sourceCopy: {
      flex: 1,
    },
    sourceTitle: {
      color: theme.colors.text,
      fontSize: 17,
      fontWeight: '800',
    },
    sourceTitlePrimary: {
      color: '#FFFFFF',
    },
    sourceBody: {
      marginTop: 5,
      color: theme.colors.muted,
      fontSize: 13,
      lineHeight: 18,
      fontWeight: '600',
    },
    sourceBodyPrimary: {
      color: 'rgba(255,255,255,0.72)',
    },
    noteRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      paddingHorizontal: 6,
      marginTop: 14,
    },
    noteText: {
      flex: 1,
      color: theme.colors.softText,
      fontSize: 12,
      lineHeight: 18,
      fontWeight: '600',
    },
  });
}
