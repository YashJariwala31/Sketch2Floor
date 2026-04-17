import React, { useEffect, useRef } from 'react';
import { Alert, Animated, Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

function statusMeta(job, theme) {
  if (job.status === 'completed') {
    return {
      color: theme.colors.success,
      title: 'Your floorplan is ready',
      text: 'The cleaned digital layout is available below and stays inside the app.',
    };
  }
  if (job.status === 'processing') {
    return {
      color: theme.colors.warning,
      title: 'We are refining your sketch',
      text: 'Your upload is being processed now. This screen refreshes automatically while it runs.',
    };
  }
  if (job.status === 'queued') {
    return {
      color: theme.colors.accent,
      title: 'Your job is queued',
      text: 'The conversion is lined up and should begin shortly.',
    };
  }
  if (job.status === 'failed') {
    return {
      color: theme.colors.danger,
      title: 'This project needs another try',
      text: 'Something interrupted the conversion. Review the message below and try again.',
    };
  }
  return {
    color: theme.colors.accent,
    title: 'Ready to create your floorplan',
    text: 'Start processing when you want the app to turn this sketch into a cleaner layout.',
  };
}

export default function ResultsScreen({ job, busy, error, onBack, onRefresh, onStartJob, onDeleteJob, theme, isLandscape }) {
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
  }, [fade, rise, job?.id]);

  if (!job) {
    return (
      <View style={styles.emptyState}>
        <Text style={styles.emptyTitle}>No floorplan selected</Text>
        <Text style={styles.emptyText} onPress={onBack}>
          Go back to choose a result.
        </Text>
      </View>
    );
  }

  const meta = statusMeta(job, theme);

  return (
    <Animated.View style={{ flex: 1, opacity: fade, transform: [{ translateY: rise }] }}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.heroCard}>
          <View style={styles.heroTop}>
            <Pressable style={styles.backButton} onPress={onBack}>
              <Text style={styles.backButtonText}>Back</Text>
            </Pressable>
            <View style={[styles.statusPill, { backgroundColor: `${meta.color}14` }]}>
              <View style={[styles.statusDot, { backgroundColor: meta.color }]} />
              <Text style={[styles.statusText, { color: meta.color }]}>{job.status}</Text>
            </View>
          </View>

          <Text style={styles.title}>{job.name || `Job #${job.id}`}</Text>
          <Text style={styles.heroSubtitle}>{meta.title}</Text>
          <Text style={styles.heroText}>{meta.text}</Text>

          <View style={styles.actions}>
            <Pressable style={styles.primaryButton} onPress={onRefresh}>
              <Text style={styles.primaryButtonText}>Refresh</Text>
            </Pressable>
            {job.status === 'draft' || job.status === 'failed' ? (
              <Pressable style={styles.secondaryButton} onPress={onStartJob} disabled={busy}>
                <Text style={styles.secondaryButtonText}>
                  {busy ? 'Starting...' : job.status === 'failed' ? 'Try Again' : 'Start Processing'}
                </Text>
              </Pressable>
            ) : null}
            <Pressable
              style={styles.deleteButton}
              onPress={() =>
                Alert.alert('Delete project', 'Remove this floorplan project permanently?', [
                  { text: 'Cancel', style: 'cancel' },
                  { text: 'Delete', style: 'destructive', onPress: () => onDeleteJob(job) },
                ])
              }
            >
              <Text style={styles.deleteButtonText}>Delete</Text>
            </Pressable>
          </View>
        </View>

        {error ? (
          <View style={styles.errorCard}>
            <Text style={styles.errorTitle}>Something needs attention</Text>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        {job.status === 'failed' && job.metadata?.error ? (
          <View style={styles.errorCard}>
            <Text style={styles.errorTitle}>Processing error</Text>
            <Text style={styles.errorText}>{job.metadata.error}</Text>
          </View>
        ) : null}

        {job.status === 'failed' && job.metadata?.stderr ? (
          <View style={styles.errorCard}>
            <Text style={styles.errorTitle}>Backend details</Text>
            <Text style={styles.errorText}>{job.metadata.stderr}</Text>
          </View>
        ) : null}

        {job.original_image_url ? (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Captured Sketch</Text>
            <Image source={{ uri: job.original_image_url }} style={styles.previewImage} resizeMode="cover" />
            <Text style={styles.caption}>The original sketch captured from your camera.</Text>
          </View>
        ) : null}

        {job.combined_overlay_url ? (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Final Floorplan</Text>
            <Image source={{ uri: job.combined_overlay_url }} style={styles.previewImageLarge} resizeMode="contain" />
            <Text style={styles.caption}>Your final result is shown here inside the app.</Text>
          </View>
        ) : null}

        {!job.combined_overlay_url ? (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>{job.status === 'failed' ? 'Conversion paused' : 'Your result is on the way'}</Text>
            <Text style={styles.heroText}>
              {job.status === 'failed'
                ? 'The backend reported a problem while creating the final floorplan. You can retry after checking the error above.'
                : 'We are refining your sketch into a cleaner floorplan view. Refresh in a moment to check the latest result.'}
            </Text>
          </View>
        ) : null}
      </ScrollView>
    </Animated.View>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    content: {
      paddingBottom: 28,
      paddingHorizontal: isLandscape ? 8 : 0,
    },
    heroCard: {
      backgroundColor: theme.colors.surface,
      borderRadius: theme.radius.lg,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: theme.spacing.xl,
      marginBottom: theme.spacing.md,
      ...theme.shadow.card,
    },
    heroTop: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: 16,
    },
    backButton: {
      backgroundColor: theme.colors.surfaceAlt,
      borderRadius: theme.radius.pill,
      paddingHorizontal: 14,
      paddingVertical: 10,
      borderWidth: 1,
      borderColor: theme.colors.border,
    },
    backButtonText: {
      color: theme.colors.text,
      fontWeight: '800',
    },
    statusPill: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      borderRadius: theme.radius.pill,
      paddingHorizontal: 12,
      paddingVertical: 8,
    },
    statusDot: {
      width: 8,
      height: 8,
      borderRadius: 4,
    },
    statusText: {
      fontWeight: '800',
      textTransform: 'capitalize',
    },
    title: {
      color: theme.colors.text,
      fontSize: isLandscape ? 26 : 28,
      fontWeight: '900',
      letterSpacing: -0.6,
    },
    heroSubtitle: {
      marginTop: 10,
      color: theme.colors.text,
      fontSize: 17,
      fontWeight: '800',
    },
    heroText: {
      marginTop: 8,
      color: theme.colors.muted,
      lineHeight: 22,
    },
    actions: {
      flexDirection: 'row',
      gap: 12,
      marginTop: 20,
      flexWrap: 'wrap',
    },
    primaryButton: {
      backgroundColor: theme.colors.accent,
      paddingHorizontal: 18,
      paddingVertical: 14,
      borderRadius: theme.radius.pill,
      ...theme.shadow.soft,
    },
    primaryButtonText: {
      color: '#ffffff',
      fontWeight: '800',
    },
    secondaryButton: {
      backgroundColor: theme.colors.surfaceAlt,
      paddingHorizontal: 18,
      paddingVertical: 14,
      borderRadius: theme.radius.pill,
    },
    secondaryButtonText: {
      color: theme.colors.text,
      fontWeight: '800',
    },
    deleteButton: {
      backgroundColor: theme.colors.destructiveSoft,
      paddingHorizontal: 18,
      paddingVertical: 14,
      borderRadius: theme.radius.pill,
    },
    deleteButtonText: {
      color: theme.colors.danger,
      fontWeight: '800',
    },
    card: {
      backgroundColor: theme.colors.card,
      borderRadius: theme.radius.md,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: theme.spacing.lg,
      marginBottom: theme.spacing.md,
      ...theme.shadow.soft,
    },
    sectionTitle: {
      color: theme.colors.text,
      fontSize: 19,
      fontWeight: '900',
      marginBottom: 14,
    },
    previewImage: {
      width: '100%',
      height: isLandscape ? 260 : 220,
      borderRadius: 22,
      backgroundColor: theme.colors.surfaceAlt,
    },
    previewImageLarge: {
      width: '100%',
      height: isLandscape ? 400 : 320,
      borderRadius: 22,
      backgroundColor: theme.colors.surfaceAlt,
    },
    caption: {
      marginTop: 12,
      color: theme.colors.softText,
      lineHeight: 20,
    },
    errorCard: {
      backgroundColor: theme.colors.errorBg,
      borderRadius: theme.radius.md,
      borderWidth: 1,
      borderColor: theme.colors.errorBorder,
      padding: theme.spacing.lg,
      marginBottom: theme.spacing.md,
    },
    errorTitle: {
      color: theme.colors.danger,
      fontWeight: '900',
      marginBottom: 6,
    },
    errorText: {
      color: theme.colors.danger,
      lineHeight: 20,
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
    emptyText: {
      color: theme.colors.accentStrong,
      fontWeight: '800',
    },
  });
}
