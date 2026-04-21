import React, { useEffect, useRef } from 'react';
import { Alert, Animated, Image, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

function statusMeta(job, theme) {
  if (job.status === 'completed') {
    return { color: theme.colors.success, label: 'Ready' };
  }
  if (job.status === 'processing') {
    return { color: theme.colors.warning, label: 'Processing' };
  }
  if (job.status === 'queued') {
    return { color: theme.colors.accent, label: 'Queued' };
  }
  if (job.status === 'failed') {
    return { color: theme.colors.danger, label: 'Failed' };
  }
  return { color: theme.colors.accent, label: 'Draft' };
}

function trimConsole(text) {
  if (!text) {
    return '';
  }

  return text
    .split('\n')
    .filter(Boolean)
    .slice(0, 8)
    .join('\n');
}

function PreviewCard({ title, imageUrl, emptyLabel, resizeMode, height, styles, theme }) {
  return (
    <View style={styles.previewCard}>
      <Text style={styles.previewLabel}>{title}</Text>
      {imageUrl ? (
        <Image source={{ uri: imageUrl }} style={[styles.previewImage, { height }]} resizeMode={resizeMode} />
      ) : (
        <View style={[styles.previewEmpty, { height }]}>
          <Ionicons name="image-outline" size={22} color={theme.colors.softText} />
          <Text style={styles.previewEmptyText}>{emptyLabel}</Text>
        </View>
      )}
    </View>
  );
}

function ConsoleCard({ title, body, styles }) {
  if (!body) {
    return null;
  }

  return (
    <View style={styles.consoleCard}>
      <Text style={styles.consoleTitle}>{title}</Text>
      <Text style={styles.consoleBody}>{body}</Text>
    </View>
  );
}

export default function ResultsScreen({
  job,
  busy,
  error,
  onBack,
  onRefresh,
  onStartJob,
  onDeleteJob,
  onSaveResult,
  theme,
  isLandscape,
}) {
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
        stiffness: 140,
      }),
    ]).start();
  }, [fade, rise, job?.id]);

  if (!job) {
    return (
      <View style={styles.emptyState}>
        <Text style={styles.emptyTitle}>No project</Text>
        <Pressable onPress={onBack}>
          <Text style={styles.emptyAction}>Back</Text>
        </Pressable>
      </View>
    );
  }

  const status = statusMeta(job, theme);
  const mainPreview = job.combined_overlay_url || job.original_image_url;
  const mainTitle = job.combined_overlay_url ? 'Floorplan' : job.status === 'failed' ? 'Sketch' : 'Preview';
  const primaryError = error || job.metadata?.error;
  const stderrPreview = trimConsole(job.metadata?.stderr);

  return (
    <Animated.View style={{ flex: 1, opacity: fade, transform: [{ translateY: rise }] }}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.toolbar}>
          <Pressable style={styles.backButton} onPress={onBack}>
            <Ionicons name="chevron-back" size={16} color={theme.colors.text} />
            <Text style={styles.backText}>Back</Text>
          </Pressable>

          <View style={[styles.statusBadge, { backgroundColor: `${status.color}18` }]}>
            <View style={[styles.statusDot, { backgroundColor: status.color }]} />
            <Text style={[styles.statusText, { color: status.color }]}>{status.label}</Text>
          </View>
        </View>

        <Text style={styles.title} numberOfLines={2}>
          {job.name || 'Floorplan'}
        </Text>

        <View style={styles.heroPanel}>
          <PreviewCard
            title={mainTitle}
            imageUrl={mainPreview}
            emptyLabel={job.status === 'failed' ? 'Retry needed' : 'Rendering'}
            resizeMode={job.combined_overlay_url ? 'contain' : 'cover'}
            height={isLandscape ? 360 : 430}
            styles={styles}
            theme={theme}
          />

          <View style={styles.actionRow}>
            <Pressable style={styles.secondaryAction} onPress={onRefresh}>
              <Ionicons name="refresh" size={16} color={theme.colors.text} />
              <Text style={styles.secondaryActionText}>Refresh</Text>
            </Pressable>

            {job.combined_overlay_url ? (
              <Pressable style={styles.primaryAction} onPress={() => onSaveResult(job.combined_overlay_url)} disabled={busy}>
                <Ionicons name="download-outline" size={16} color="#ffffff" />
                <Text style={styles.primaryActionText}>{busy ? 'Preparing' : 'Download'}</Text>
              </Pressable>
            ) : null}

            {(job.status === 'draft' || job.status === 'failed') ? (
              <Pressable style={styles.primaryAction} onPress={onStartJob} disabled={busy}>
                <Ionicons name="play-outline" size={16} color="#ffffff" />
                <Text style={styles.primaryActionText}>{busy ? 'Starting' : 'Retry'}</Text>
              </Pressable>
            ) : null}

            <Pressable
              style={styles.deleteAction}
              onPress={() =>
                Alert.alert('Delete project', 'Remove this floorplan project permanently?', [
                  { text: 'Cancel', style: 'cancel' },
                  { text: 'Delete', style: 'destructive', onPress: () => onDeleteJob(job) },
                ])
              }
            >
              <Ionicons name="trash-outline" size={16} color={theme.colors.danger} />
            </Pressable>
          </View>
        </View>

        <View style={[styles.bottomSection, isLandscape ? styles.bottomSectionLandscape : null]}>
          <PreviewCard
            title="Source"
            imageUrl={job.original_image_url}
            emptyLabel="No image"
            resizeMode="cover"
            height={isLandscape ? 230 : 210}
            styles={styles}
            theme={theme}
          />

          <View style={styles.consoleStack}>
            <ConsoleCard title="Error" body={primaryError} styles={styles} />
            <ConsoleCard title="Details" body={stderrPreview} styles={styles} />
          </View>
        </View>
      </ScrollView>
    </Animated.View>
  );
}

function createStyles(theme, isLandscape) {
  const styles = StyleSheet.create({
    content: {
      paddingBottom: 30,
    },
    toolbar: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 16,
    },
    backButton: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 6,
      paddingHorizontal: 14,
      paddingVertical: 10,
      borderRadius: theme.radius.pill,
      backgroundColor: theme.colors.surfaceElevated,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
    },
    backText: {
      color: theme.colors.text,
      fontWeight: '800',
    },
    statusBadge: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      paddingHorizontal: 12,
      paddingVertical: 9,
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
      fontWeight: '900',
      fontSize: 12,
    },
    title: {
      color: theme.colors.text,
      fontSize: isLandscape ? 35 : 32,
      fontWeight: '900',
      letterSpacing: -1,
      marginBottom: 18,
    },
    heroPanel: {
      backgroundColor: theme.colors.surface,
      borderRadius: theme.radius.xl,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: 14,
      marginBottom: 16,
      ...theme.shadow.float,
    },
    previewCard: {
      flex: 1,
      backgroundColor: theme.colors.heroTint,
      borderRadius: 26,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: 12,
      overflow: 'hidden',
    },
    previewLabel: {
      color: theme.colors.softText,
      fontWeight: '800',
      fontSize: 12,
      textTransform: 'uppercase',
      letterSpacing: 1,
      marginBottom: 12,
    },
    previewImage: {
      width: '100%',
      borderRadius: 20,
      backgroundColor: theme.colors.surface,
    },
    previewEmpty: {
      borderRadius: 20,
      backgroundColor: theme.colors.surface,
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
    },
    previewEmptyText: {
      color: theme.colors.softText,
      fontWeight: '800',
    },
    actionRow: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: 10,
      marginTop: 14,
    },
    primaryAction: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      paddingHorizontal: 18,
      paddingVertical: 13,
      borderRadius: theme.radius.pill,
      backgroundColor: theme.colors.accent,
    },
    primaryActionText: {
      color: '#ffffff',
      fontWeight: '900',
    },
    secondaryAction: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      paddingHorizontal: 16,
      paddingVertical: 13,
      borderRadius: theme.radius.pill,
      backgroundColor: theme.colors.surfaceElevated,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
    },
    secondaryActionText: {
      color: theme.colors.text,
      fontWeight: '800',
    },
    deleteAction: {
      width: 44,
      height: 44,
      borderRadius: 22,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: theme.colors.destructiveSoft,
      borderWidth: 1,
      borderColor: theme.colors.errorBorder,
    },
    bottomSection: {
      gap: 16,
    },
    bottomSectionLandscape: {
      flexDirection: 'row',
      alignItems: 'flex-start',
    },
    consoleStack: {
      flex: isLandscape ? 0.9 : 1,
      gap: 12,
    },
    consoleCard: {
      backgroundColor: theme.colors.surfaceAlt,
      borderRadius: 24,
      borderWidth: 1,
      borderColor: theme.colors.errorBorder,
      padding: 16,
    },
    consoleTitle: {
      color: theme.colors.danger,
      fontWeight: '900',
      marginBottom: 10,
    },
    consoleBody: {
      color: theme.colors.muted,
      fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
      fontSize: 12,
      lineHeight: 18,
    },
    emptyState: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      padding: theme.spacing.xl,
    },
    emptyTitle: {
      color: theme.colors.text,
      fontSize: 22,
      fontWeight: '900',
      marginBottom: 10,
    },
    emptyAction: {
      color: theme.colors.accentStrong,
      fontWeight: '800',
    },
  });

  return styles;
}
