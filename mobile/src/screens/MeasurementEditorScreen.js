import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import FloorplanAnnotator from '../components/annotation/FloorplanAnnotator';
import { AuthBackdrop } from '../components/auth/AuthVisuals';

function BackButton({ onBack, theme, styles }) {
  return (
    <Pressable style={styles.backButton} onPress={onBack}>
      <Ionicons name="chevron-back" size={17} color={theme.colors.text} />
    </Pressable>
  );
}

export default function MeasurementEditorScreen({
  job,
  annotatorRef,
  annotations,
  onChangeAnnotations,
  onRequestUndo,
  onRequestDeleteSelected,
  onRequestSave,
  onRequestHistoryCheckpoint,
  onBack,
  busy,
  theme,
  isLandscape,
}) {
  const styles = useMemo(() => createStyles(theme, isLandscape), [theme, isLandscape]);
  const [measurementMode, setMeasurementMode] = useState(true);

  return (
    <AuthBackdrop theme={theme}>
      <View style={styles.screen}>
        <View style={styles.headerRow}>
          <BackButton onBack={onBack} theme={theme} styles={styles} />
          <View style={styles.headerCopy}>
            <Text style={styles.screenTitle}>Measurements</Text>
          </View>
        </View>

        <View style={styles.editorCard}>
          {job?.combined_overlay_url ? (
            <FloorplanAnnotator
              ref={annotatorRef}
              imageUri={job.combined_overlay_url}
              theme={theme}
              annotations={annotations}
              onChangeAnnotations={onChangeAnnotations}
              measurementMode={measurementMode}
              onRequestToggleMeasurementMode={() => setMeasurementMode((value) => !value)}
              onRequestUndo={onRequestUndo}
              onRequestDeleteSelected={onRequestDeleteSelected}
              onRequestSave={onRequestSave}
              onRequestHistoryCheckpoint={onRequestHistoryCheckpoint}
              busy={busy}
            />
          ) : (
            <View style={styles.emptyState}>
              <Ionicons name="image-outline" size={22} color={theme.colors.softText} />
              <Text style={styles.emptyText}>No image available for measurement.</Text>
            </View>
          )}
        </View>
      </View>
    </AuthBackdrop>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    screen: {
      flex: 1,
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
    screenTitle: {
      color: theme.colors.text,
      fontSize: isLandscape ? 30 : 28,
      fontWeight: '900',
      letterSpacing: -0.8,
    },
    screenSubtitle: {
      marginTop: 4,
      color: theme.colors.muted,
      fontSize: 13,
      lineHeight: 19,
      fontWeight: '600',
    },
    editorCard: {
      flex: 1,
      backgroundColor: theme.colors.surface,
      borderRadius: 28,
      borderWidth: 1,
      borderColor: 'rgba(255,255,255,0.72)',
      padding: 14,
      overflow: 'hidden',
      ...theme.shadow.card,
    },
    emptyState: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
    },
    emptyText: {
      color: theme.colors.muted,
      fontWeight: '700',
    },
  });
}
