import React, { useEffect, useMemo, useRef } from 'react';
import { Alert, Animated, Image, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

function statusMeta(job, theme) {
  if (job.status === 'completed') {
    return { label: 'Ready', fill: theme.colors.successSoft, text: theme.colors.success };
  }
  if (job.status === 'processing' || job.status === 'queued') {
    return { label: 'AI scan active', fill: theme.colors.accentSoft, text: theme.colors.accent };
  }
  if (job.status === 'failed') {
    return { label: 'Issue', fill: theme.colors.errorBg, text: theme.colors.danger };
  }
  return { label: 'Draft', fill: theme.colors.panel, text: theme.colors.muted };
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

function Loader({ theme, styles }) {
  const spin = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(spin, {
        toValue: 1,
        duration: 2600,
        useNativeDriver: true,
      })
    );
    loop.start();
    return () => loop.stop();
  }, [spin]);

  const rotate = spin.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  const dots = useMemo(
    () =>
      Array.from({ length: 10 }, (_, index) => {
        const angle = (Math.PI * 2 * index) / 10;
        const left = 110 + Math.cos(angle) * 72 - 6;
        const top = 110 + Math.sin(angle) * 72 - 6;
        return (
          <View
            key={index}
            style={[
              styles.loaderDot,
              {
                left,
                top,
                opacity: 0.22 + index * 0.07,
              },
            ]}
          />
        );
      }),
    [styles]
  );

  return (
    <View style={styles.loaderWrap}>
      <Animated.View style={[styles.loaderRing, { transform: [{ rotate }] }]}>
        {dots}
      </Animated.View>
      <View style={styles.loaderCenter}>
        <Text style={styles.loaderText}>AI</Text>
      </View>
    </View>
  );
}

function BackButton({ onBack, theme, styles }) {
  return (
    <Pressable style={styles.backButton} onPress={onBack}>
      <Ionicons name="chevron-back" size={17} color={theme.colors.text} />
    </Pressable>
  );
}

function StatusPill({ meta, styles }) {
  return (
    <View style={[styles.statusPill, { backgroundColor: meta.fill }]}>
      <Text style={[styles.statusPillText, { color: meta.text }]}>{meta.label}</Text>
    </View>
  );
}

function ErrorPanel({ title, body, styles }) {
  if (!body) {
    return null;
  }

  return (
    <View style={styles.errorPanel}>
      <Text style={styles.errorPanelTitle}>{title}</Text>
      <Text style={styles.errorPanelBody}>{body}</Text>
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
        duration: 280,
        useNativeDriver: true,
      }),
      Animated.spring(rise, {
        toValue: 0,
        useNativeDriver: true,
        damping: 15,
        stiffness: 145,
      }),
    ]).start();
  }, [fade, rise, job?.id, job?.status]);

  if (!job) {
    return (
      <View style={styles.emptyState}>
        <Text style={styles.emptyText}>No project selected.</Text>
      </View>
    );
  }

  const status = statusMeta(job, theme);
  const topTitle = job.status === 'completed' ? 'Output' : job.status === 'failed' ? 'Issue' : 'Processing';
  const primaryError = error || job.metadata?.error;
  const stderrPreview = trimConsole(job.metadata?.stderr);

  if (job.status === 'processing' || job.status === 'queued') {
    return (
      <Animated.View style={{ flex: 1, opacity: fade, transform: [{ translateY: rise }] }}>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <View style={styles.headerRow}>
            <BackButton onBack={onBack} theme={theme} styles={styles} />
            <Text style={styles.screenTitle}>{topTitle}</Text>
            <StatusPill meta={status} styles={styles} />
          </View>

          <View style={styles.processingCard}>
            <Loader theme={theme} styles={styles} />
            <Text style={styles.processingTitle}>Processing your floor plan...</Text>
            <Text style={styles.processingSubtitle}>Detecting walls, doors, and layout</Text>
            <View style={styles.progressPill}>
              <Text style={styles.progressPillText}>AI scan active</Text>
            </View>
            <View style={styles.progressTrack}>
              <View style={styles.progressFill} />
            </View>
          </View>
        </ScrollView>
      </Animated.View>
    );
  }

  if (job.status === 'completed') {
    return (
      <Animated.View style={{ flex: 1, opacity: fade, transform: [{ translateY: rise }] }}>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <View style={styles.headerRow}>
            <BackButton onBack={onBack} theme={theme} styles={styles} />
            <Text style={styles.screenTitle}>{topTitle}</Text>
            <StatusPill meta={status} styles={styles} />
          </View>

          <View style={styles.outputCard}>
            <View style={styles.planFrame}>
              {job.combined_overlay_url ? (
                <Image source={{ uri: job.combined_overlay_url }} style={styles.outputImage} resizeMode="contain" />
              ) : (
                <View style={styles.outputEmpty}>
                  <Ionicons name="image-outline" size={22} color={theme.colors.softText} />
                </View>
              )}
              <View style={styles.zoomPill}>
                <Text style={styles.zoomText}>Zoom 125%</Text>
              </View>
            </View>

            <View style={styles.actionRow}>
              <Pressable style={[styles.actionButton, styles.primaryActionButton]} onPress={() => onSaveResult(job.combined_overlay_url)} disabled={busy || !job.combined_overlay_url}>
                <Text style={styles.primaryActionText}>{busy ? 'Saving' : 'Download'}</Text>
              </Pressable>
              <Pressable style={[styles.actionButton, styles.secondaryActionButton]} onPress={() => onSaveResult(job.combined_overlay_url)} disabled={busy || !job.combined_overlay_url}>
                <Text style={styles.secondaryActionText}>Save</Text>
              </Pressable>
              <Pressable style={[styles.actionButton, styles.secondaryActionButton, styles.tryAnotherButton]} onPress={onBack}>
                <Text style={styles.secondaryActionText}>Try Another</Text>
              </Pressable>
            </View>

            <Text style={styles.outputTitle}>Digital floor plan generated</Text>
            <Text style={styles.outputSubtitle}>Walls, openings, and layout are ready.</Text>
          </View>
        </ScrollView>
      </Animated.View>
    );
  }

  return (
    <Animated.View style={{ flex: 1, opacity: fade, transform: [{ translateY: rise }] }}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <BackButton onBack={onBack} theme={theme} styles={styles} />
          <Text style={styles.screenTitle}>{topTitle}</Text>
          <StatusPill meta={status} styles={styles} />
        </View>

        <View style={styles.issueCard}>
          <Text style={styles.issueTitle}>This project needs another try</Text>
          <Text style={styles.issueSubtitle}>Something interrupted the conversion.</Text>

          <View style={styles.actionRow}>
            <Pressable style={[styles.actionButton, styles.secondaryActionButton]} onPress={onRefresh}>
              <Text style={styles.secondaryActionText}>Refresh</Text>
            </Pressable>
            <Pressable style={[styles.actionButton, styles.primaryActionButton]} onPress={onStartJob} disabled={busy}>
              <Text style={styles.primaryActionText}>{busy ? 'Starting' : 'Retry'}</Text>
            </Pressable>
            <Pressable
              style={[styles.actionButton, styles.deleteButton]}
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

        <ErrorPanel title="Error" body={primaryError} styles={styles} />
        <ErrorPanel title="Details" body={stderrPreview} styles={styles} />
      </ScrollView>
    </Animated.View>
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
      marginBottom: 18,
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
    screenTitle: {
      flex: 1,
      color: theme.colors.text,
      fontSize: isLandscape ? 32 : 30,
      fontWeight: '900',
      letterSpacing: -0.9,
    },
    statusPill: {
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderRadius: 999,
    },
    statusPillText: {
      fontSize: 12,
      fontWeight: '800',
    },
    processingCard: {
      minHeight: isLandscape ? 540 : 620,
      borderRadius: theme.radius.xl,
      backgroundColor: theme.colors.surfaceElevated,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      alignItems: 'center',
      justifyContent: 'center',
      paddingHorizontal: 24,
      ...theme.shadow.card,
    },
    loaderWrap: {
      width: 220,
      height: 220,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 26,
    },
    loaderRing: {
      position: 'absolute',
      width: 220,
      height: 220,
    },
    loaderDot: {
      position: 'absolute',
      width: 12,
      height: 12,
      borderRadius: 6,
      backgroundColor: theme.colors.accent,
    },
    loaderCenter: {
      width: 108,
      height: 108,
      borderRadius: 54,
      backgroundColor: theme.colors.accentSoft,
      alignItems: 'center',
      justifyContent: 'center',
    },
    loaderText: {
      color: theme.colors.accent,
      fontSize: 34,
      fontWeight: '900',
      letterSpacing: -0.8,
    },
    processingTitle: {
      color: theme.colors.text,
      fontSize: isLandscape ? 30 : 28,
      fontWeight: '900',
      textAlign: 'center',
      letterSpacing: -0.8,
    },
    processingSubtitle: {
      marginTop: 10,
      color: theme.colors.muted,
      fontSize: 16,
      fontWeight: '600',
      textAlign: 'center',
    },
    progressPill: {
      marginTop: 22,
      paddingHorizontal: 14,
      paddingVertical: 8,
      borderRadius: 999,
      backgroundColor: theme.colors.accentSoft,
    },
    progressPillText: {
      color: theme.colors.accent,
      fontWeight: '800',
      fontSize: 12,
    },
    progressTrack: {
      width: 158,
      height: 8,
      borderRadius: 999,
      backgroundColor: theme.colors.noticeBorder,
      marginTop: 20,
      overflow: 'hidden',
    },
    progressFill: {
      width: '72%',
      height: '100%',
      borderRadius: 999,
      backgroundColor: theme.colors.accent,
    },
    outputCard: {
      backgroundColor: theme.colors.surfaceElevated,
      borderRadius: theme.radius.xl,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      padding: 16,
      ...theme.shadow.card,
    },
    planFrame: {
      height: isLandscape ? 420 : 360,
      borderRadius: 24,
      backgroundColor: theme.colors.heroTint,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
      padding: 14,
      marginBottom: 16,
      position: 'relative',
    },
    outputImage: {
      flex: 1,
      borderRadius: 20,
      backgroundColor: theme.colors.surface,
    },
    outputEmpty: {
      flex: 1,
      borderRadius: 20,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: theme.colors.surface,
    },
    zoomPill: {
      position: 'absolute',
      right: 20,
      top: 18,
      paddingHorizontal: 12,
      paddingVertical: 7,
      borderRadius: 999,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.border,
    },
    zoomText: {
      color: theme.colors.muted,
      fontSize: 12,
      fontWeight: '700',
    },
    actionRow: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: 10,
      marginBottom: 16,
    },
    actionButton: {
      minHeight: 48,
      borderRadius: 16,
      paddingHorizontal: 18,
      alignItems: 'center',
      justifyContent: 'center',
      borderWidth: 1,
    },
    primaryActionButton: {
      backgroundColor: theme.colors.accent,
      borderColor: theme.colors.accent,
    },
    secondaryActionButton: {
      backgroundColor: theme.colors.heroTint,
      borderColor: theme.colors.noticeBorder,
    },
    tryAnotherButton: {
      flexGrow: 1,
    },
    deleteButton: {
      backgroundColor: theme.colors.errorBg,
      borderColor: theme.colors.errorBorder,
    },
    primaryActionText: {
      color: '#ffffff',
      fontWeight: '800',
      fontSize: 15,
    },
    secondaryActionText: {
      color: theme.colors.text,
      fontWeight: '800',
      fontSize: 15,
    },
    deleteButtonText: {
      color: theme.colors.danger,
      fontWeight: '800',
      fontSize: 15,
    },
    outputTitle: {
      color: theme.colors.text,
      fontSize: 20,
      fontWeight: '800',
    },
    outputSubtitle: {
      marginTop: 6,
      color: theme.colors.muted,
      fontWeight: '600',
    },
    issueCard: {
      backgroundColor: theme.colors.surfaceElevated,
      borderRadius: theme.radius.xl,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      padding: 18,
      marginBottom: 14,
      ...theme.shadow.card,
    },
    issueTitle: {
      color: theme.colors.text,
      fontSize: 24,
      lineHeight: 30,
      fontWeight: '900',
      letterSpacing: -0.6,
    },
    issueSubtitle: {
      marginTop: 8,
      color: theme.colors.muted,
      fontWeight: '600',
      marginBottom: 16,
    },
    errorPanel: {
      backgroundColor: theme.colors.errorBg,
      borderRadius: 22,
      borderWidth: 1,
      borderColor: theme.colors.errorBorder,
      padding: 16,
      marginBottom: 12,
    },
    errorPanelTitle: {
      color: theme.colors.danger,
      fontSize: 20,
      fontWeight: '800',
      marginBottom: 10,
    },
    errorPanelBody: {
      color: theme.colors.muted,
      fontSize: 13,
      lineHeight: 19,
      fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    },
    emptyState: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
    },
    emptyText: {
      color: theme.colors.muted,
      fontWeight: '700',
    },
  });
}
