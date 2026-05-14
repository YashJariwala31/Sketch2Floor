import React from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { formatJobDate, getJobStatusMeta } from '../utils/jobPresentation';

function Placeholder({ styles, theme }) {
  return (
    <View style={styles.previewPlaceholder}>
      <View style={styles.previewPlaceholderInset}>
        <View style={styles.previewTopLine} />
        <View style={styles.previewLeftLine} />
        <View style={styles.previewBottomLine} />
      </View>
      <Ionicons name="document-outline" size={20} color={theme.colors.borderStrong} />
    </View>
  );
}

export default function JobCard({ job, onPress, onDelete, theme }) {
  const styles = createStyles(theme);
  const previewUri = job.combined_overlay_url || job.original_image_url;
  const status = getJobStatusMeta(job.status, theme);

  return (
    <Pressable style={styles.card} onPress={onPress}>
      <View style={styles.thumbWrap}>
        {previewUri ? (
          <Image source={{ uri: previewUri }} style={styles.thumb} resizeMode="cover" />
        ) : (
          <Placeholder styles={styles} theme={theme} />
        )}
      </View>

      <View style={styles.copy}>
        <View style={styles.topRow}>
          <Text style={styles.title} numberOfLines={1}>
            {job.name || 'Untitled project'}
          </Text>
          <View style={[styles.statusPill, { backgroundColor: status.fill }]}>
            <Text style={[styles.statusText, { color: status.text }]}>{status.label}</Text>
          </View>
        </View>

        <Text style={styles.subtitle}>Digital floor plan</Text>
        <Text style={styles.date}>{formatJobDate(job.created_at)}</Text>
      </View>

      {onDelete ? (
        <Pressable
          style={styles.deleteButton}
          onPress={(event) => {
            event.stopPropagation?.();
            onDelete();
          }}
        >
          <Ionicons name="trash-outline" size={16} color={theme.colors.danger} />
        </Pressable>
      ) : null}
    </Pressable>
  );
}

function createStyles(theme) {
  return StyleSheet.create({
    card: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 14,
      backgroundColor: theme.colors.surface,
      borderRadius: 26,
      borderWidth: 1,
      borderColor: 'rgba(255,255,255,0.72)',
      padding: 15,
      marginBottom: 12,
      ...theme.shadow.card,
    },
    thumbWrap: {
      width: 72,
      height: 72,
      borderRadius: 18,
      overflow: 'hidden',
      backgroundColor: theme.colors.surfaceAlt,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
    },
    thumb: {
      width: '100%',
      height: '100%',
    },
    previewPlaceholder: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
    },
    previewPlaceholderInset: {
      position: 'absolute',
      left: 12,
      right: 12,
      top: 12,
      bottom: 12,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
    },
    previewTopLine: {
      position: 'absolute',
      left: 10,
      top: 10,
      width: 26,
      height: 4,
      borderRadius: 999,
      backgroundColor: theme.colors.borderStrong,
    },
    previewLeftLine: {
      position: 'absolute',
      left: 10,
      top: 10,
      width: 4,
      height: 24,
      borderRadius: 999,
      backgroundColor: theme.colors.borderStrong,
    },
    previewBottomLine: {
      position: 'absolute',
      left: 10,
      bottom: 12,
      width: 20,
      height: 4,
      borderRadius: 999,
      backgroundColor: theme.colors.borderStrong,
    },
    copy: {
      flex: 1,
    },
    topRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 10,
    },
    title: {
      flex: 1,
      color: theme.colors.text,
      fontSize: 21,
      fontWeight: '800',
      letterSpacing: -0.5,
    },
    statusPill: {
      paddingHorizontal: 10,
      paddingVertical: 6,
      borderRadius: 999,
    },
    statusText: {
      fontSize: 12,
      fontWeight: '800',
    },
    subtitle: {
      marginTop: 4,
      color: theme.colors.muted,
      fontWeight: '700',
    },
    date: {
      marginTop: 6,
      color: theme.colors.softText,
      fontSize: 13,
      fontWeight: '700',
    },
    deleteButton: {
      width: 34,
      height: 34,
      borderRadius: 17,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: theme.colors.surfaceAlt,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
    },
  });
}
