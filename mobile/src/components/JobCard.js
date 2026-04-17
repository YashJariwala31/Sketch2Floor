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

function getStatusCopy(status) {
  if (status === 'completed') {
    return 'Ready to open';
  }
  if (status === 'failed') {
    return 'Needs attention';
  }
  if (status === 'processing') {
    return 'Pipeline is running';
  }
  if (status === 'queued') {
    return 'Waiting to start';
  }
  return 'Draft created';
}

export default function JobCard({ job, onPress, onDelete, theme, isLandscape }) {
  const fade = useRef(new Animated.Value(0)).current;
  const rise = useRef(new Animated.Value(14)).current;
  const styles = createStyles(theme, isLandscape);

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fade, {
        toValue: 1,
        duration: 350,
        useNativeDriver: true,
      }),
      Animated.timing(rise, {
        toValue: 0,
        duration: 350,
        useNativeDriver: true,
      }),
    ]).start();
  }, [fade, rise]);

  const statusColor = getStatusColor(job.status, theme);

  return (
    <Animated.View style={{ opacity: fade, transform: [{ translateY: rise }] }}>
      <Pressable style={styles.card} onPress={onPress}>
        {job.combined_overlay_url || job.original_image_url ? (
          <Image
            source={{ uri: job.combined_overlay_url || job.original_image_url }}
            style={styles.preview}
            resizeMode="cover"
          />
        ) : (
          <View style={styles.previewPlaceholder}>
            <Text style={styles.previewPlaceholderText}>Floorplan preview</Text>
          </View>
        )}

        <View style={styles.topRow}>
          <View style={[styles.dotWrap, { backgroundColor: `${statusColor}12` }]}>
            <View style={[styles.dot, { backgroundColor: statusColor }]} />
          </View>
          <View style={styles.textWrap}>
            <Text style={styles.title}>{job.name || 'Untitled Project'}</Text>
            <Text style={styles.subtitle}>{job.original_filename || 'Captured floorplan sketch'}</Text>
          </View>
          <View style={[styles.badge, { backgroundColor: `${statusColor}14` }]}>
            <Text style={[styles.badgeText, { color: statusColor }]}>{job.status}</Text>
          </View>
        </View>

        <Text style={styles.description}>
          {job.description || 'Open this project to view the latest floorplan result.'}
        </Text>

        <View style={styles.footer}>
          <Text style={styles.footerLabel}>{getStatusCopy(job.status)}</Text>
          <View style={styles.footerActions}>
            {onDelete ? (
              <Pressable style={styles.deleteButton} onPress={onDelete}>
                <Ionicons name="trash-outline" size={16} color={theme.colors.danger} />
                <Text style={styles.deleteText}>Delete</Text>
              </Pressable>
            ) : null}
            <Text style={styles.footerLink}>View project</Text>
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
      borderRadius: theme.radius.md,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: theme.spacing.md,
      marginBottom: theme.spacing.md,
      ...theme.shadow.card,
    },
    preview: {
      width: '100%',
      height: isLandscape ? 190 : 148,
      borderRadius: 16,
      marginBottom: 14,
      backgroundColor: theme.colors.surfaceAlt,
    },
    previewPlaceholder: {
      width: '100%',
      height: 128,
      borderRadius: 16,
      marginBottom: 14,
      backgroundColor: theme.colors.surfaceAlt,
      alignItems: 'center',
      justifyContent: 'center',
    },
    previewPlaceholderText: {
      color: theme.colors.softText,
      fontWeight: '700',
    },
    topRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 12,
      marginBottom: 12,
    },
    dotWrap: {
      width: 40,
      height: 40,
      borderRadius: 20,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: theme.colors.surfaceAlt,
    },
    dot: {
      width: 10,
      height: 10,
      borderRadius: 5,
    },
    textWrap: {
      flex: 1,
    },
    title: {
      color: theme.colors.text,
      fontSize: 17,
      fontWeight: '800',
    },
    subtitle: {
      color: theme.colors.softText,
      marginTop: 4,
      fontSize: 13,
    },
    badge: {
      borderRadius: theme.radius.pill,
      paddingHorizontal: 12,
      paddingVertical: 7,
    },
    badgeText: {
      textTransform: 'capitalize',
      fontWeight: '800',
      fontSize: 12,
    },
    description: {
      color: theme.colors.muted,
      lineHeight: 21,
    },
    footer: {
      marginTop: 14,
      paddingTop: 14,
      borderTopWidth: 1,
      borderTopColor: theme.colors.border,
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
    },
    footerActions: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 14,
    },
    footerLabel: {
      color: theme.colors.softText,
      fontWeight: '700',
    },
    deleteButton: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
    },
    deleteText: {
      color: theme.colors.danger,
      fontWeight: '800',
    },
    footerLink: {
      color: theme.colors.accentStrong,
      fontWeight: '800',
    },
  });
}
