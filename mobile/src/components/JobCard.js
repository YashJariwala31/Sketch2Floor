import React, { useEffect, useRef } from 'react';
import { Animated, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

function getStatusColor(status, theme) {
  if (status === 'completed') {
    return theme.colors.success;
  }
  if (status === 'failed') {
    return theme.colors.danger;
  }
  if (status === 'processing') {
    return theme.colors.warning;
  }
  return theme.colors.accent;
}

function getStatusLabel(status) {
  if (status === 'completed') {
    return 'Ready';
  }
  if (status === 'failed') {
    return 'Issue';
  }
  if (status === 'processing') {
    return 'Live';
  }
  if (status === 'queued') {
    return 'Queued';
  }
  return 'Draft';
}

function formatDate(value) {
  if (!value) {
    return 'Just now';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Just now';
  }

  return date.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
  });
}

export default function JobCard({ job, onPress, onDelete, theme, isLandscape }) {
  const fade = useRef(new Animated.Value(0)).current;
  const rise = useRef(new Animated.Value(14)).current;
  const styles = createStyles(theme, isLandscape);

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fade, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }),
      Animated.timing(rise, {
        toValue: 0,
        duration: 300,
        useNativeDriver: true,
      }),
    ]).start();
  }, [fade, rise]);

  const statusColor = getStatusColor(job.status, theme);
  const previewUri = job.combined_overlay_url || job.original_image_url;

  return (
    <Animated.View style={{ opacity: fade, transform: [{ translateY: rise }] }}>
      <Pressable style={[styles.card, isLandscape ? styles.cardLandscape : null]} onPress={onPress}>
        <View style={[styles.previewWrap, isLandscape ? styles.previewWrapLandscape : null]}>
          {previewUri ? (
            <Image source={{ uri: previewUri }} style={styles.preview} resizeMode="cover" />
          ) : (
            <View style={styles.previewPlaceholder}>
              <View style={styles.placeholderLineLong} />
              <View style={styles.placeholderLineShort} />
              <View style={styles.placeholderBox} />
            </View>
          )}

          <View style={[styles.statusPill, { backgroundColor: `${statusColor}18` }]}>
            <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
            <Text style={[styles.statusText, { color: statusColor }]}>{getStatusLabel(job.status)}</Text>
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
        </View>

        <View style={styles.content}>
          <View style={styles.titleRow}>
            <Text style={styles.title} numberOfLines={1}>
              {job.name || 'Untitled'}
            </Text>
            <Ionicons name="arrow-forward" size={18} color={theme.colors.softText} />
          </View>

          <View style={styles.metaRow}>
            <Text style={styles.metaText}>{formatDate(job.created_at)}</Text>
            <Text style={styles.metaDivider}>/</Text>
            <Text style={styles.metaText} numberOfLines={1}>
              {job.original_filename || 'Sketch'}
            </Text>
          </View>
        </View>
      </Pressable>
    </Animated.View>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    card: {
      backgroundColor: theme.colors.card,
      borderRadius: 30,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: 13,
      marginBottom: theme.spacing.md,
      overflow: 'hidden',
      ...theme.shadow.card,
    },
    cardLandscape: {
      flexDirection: 'row',
      gap: 14,
      alignItems: 'stretch',
    },
    previewWrap: {
      position: 'relative',
      marginBottom: 12,
    },
    previewWrapLandscape: {
      width: '42%',
      marginBottom: 0,
    },
    preview: {
      width: '100%',
      height: isLandscape ? 172 : 208,
      borderRadius: 24,
      backgroundColor: theme.colors.surfaceAlt,
    },
    previewPlaceholder: {
      width: '100%',
      height: isLandscape ? 172 : 208,
      borderRadius: 24,
      backgroundColor: theme.colors.heroTint,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: 18,
      justifyContent: 'space-between',
    },
    placeholderLineLong: {
      width: '58%',
      height: 8,
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    placeholderLineShort: {
      width: '34%',
      height: 8,
      borderRadius: 999,
      backgroundColor: theme.colors.canvasLine,
    },
    placeholderBox: {
      width: '38%',
      height: '34%',
      alignSelf: 'flex-end',
      borderRadius: 18,
      borderWidth: 2,
      borderColor: theme.colors.canvasLine,
    },
    statusPill: {
      position: 'absolute',
      left: 10,
      top: 10,
      flexDirection: 'row',
      alignItems: 'center',
      gap: 7,
      paddingHorizontal: 11,
      paddingVertical: 8,
      borderRadius: theme.radius.pill,
      borderWidth: 1,
      borderColor: theme.colors.border,
      backgroundColor: theme.colors.surface,
    },
    statusDot: {
      width: 8,
      height: 8,
      borderRadius: 4,
    },
    statusText: {
      fontSize: 12,
      fontWeight: '900',
    },
    deleteButton: {
      position: 'absolute',
      right: 10,
      top: 10,
      width: 36,
      height: 36,
      borderRadius: 18,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.border,
    },
    content: {
      flex: 1,
      justifyContent: 'center',
      paddingHorizontal: isLandscape ? 4 : 2,
    },
    titleRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 12,
      marginBottom: 8,
    },
    title: {
      flex: 1,
      color: theme.colors.text,
      fontSize: 21,
      fontWeight: '900',
      letterSpacing: -0.5,
    },
    metaRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
    },
    metaText: {
      color: theme.colors.muted,
      fontWeight: '700',
      fontSize: 13,
      flexShrink: 1,
    },
    metaDivider: {
      color: theme.colors.softText,
      fontWeight: '700',
    },
  });
}
