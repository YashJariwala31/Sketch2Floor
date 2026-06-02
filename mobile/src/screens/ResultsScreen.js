import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Animated, Image, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { ScrollView } from 'react-native-gesture-handler';
import { Ionicons } from '@expo/vector-icons';

import { AuthBackdrop } from '../components/auth/AuthVisuals';
import { useEntranceAnimation } from '../hooks/useEntranceAnimation';
import { saveJobAnnotations } from '../api/client';
import MeasurementEditorScreen from './MeasurementEditorScreen';
import { loadAnnotatedPreview, loadLocalAnnotationState, saveAnnotatedPreview, saveLocalAnnotations } from '../utils/annotationStorage';
import { getJobStatusMeta, getResultsScreenTitle, trimMultilineText } from '../utils/jobPresentation';

function Loader({ styles }) {
  const spin = useRef(new Animated.Value(0)).current;
  const ringSize = 184;
  const radius = 60;
  const dotSize = 12;

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
        const left = ringSize / 2 + Math.cos(angle) * radius - dotSize / 2;
        const top = ringSize / 2 + Math.sin(angle) * radius - dotSize / 2;
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
        <Ionicons name="sparkles" size={28} color={styles.loaderText.color} />
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

function InfoChip({ label, styles }) {
  return (
    <View style={styles.infoChip}>
      <Text style={styles.infoChipText}>{label}</Text>
    </View>
  );
}

function cloneAnnotations(list) {
  if (!Array.isArray(list)) {
    return [];
  }

  return list.map((item) => ({
    ...item,
    p1: item?.p1 ? { ...item.p1 } : item?.p1,
    p2: item?.p2 ? { ...item.p2 } : item?.p2,
  }));
}

export default function ResultsScreen({
  job,
  accountEmail,
  busy,
  error,
  onBack,
  onTryAnother,
  onRefresh,
  onStartJob,
  onDeleteJob,
  onSaveResult,
  theme,
  isLandscape,
}) {
  const animatedStyle = useEntranceAnimation({
    dependencies: [job?.id, job?.status],
    duration: 280,
  });
  const styles = createStyles(theme, isLandscape);
  const annotatorRef = useRef(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [annotations, setAnnotations] = useState([]);
  const [undoStack, setUndoStack] = useState([]);
  const [saveBusy, setSaveBusy] = useState(false);
  const [annotatedPreviewUri, setAnnotatedPreviewUri] = useState(null);

  useEffect(() => {
    let mounted = true;
    async function loadAnnotations() {
      setEditorOpen(false);
      setUndoStack([]);

      const fromBackend = Array.isArray(job?.annotations) ? cloneAnnotations(job.annotations) : null;
      const localState = await loadLocalAnnotationState(job?.id, accountEmail);
      const local = Array.isArray(localState?.annotations) ? cloneAnnotations(localState.annotations) : null;
      const preview = await loadAnnotatedPreview(job?.id, accountEmail);
      if (mounted) {
        setAnnotatedPreviewUri(preview);
      }

      if (Array.isArray(fromBackend) && fromBackend.length > 0) {
        if (mounted) setAnnotations(fromBackend);
        return;
      }

      if (Array.isArray(fromBackend) && fromBackend.length === 0) {
        if (localState?.backendSynced === false && Array.isArray(local) && local.length > 0) {
          if (mounted) setAnnotations(local);
          return;
        }

        if (mounted) setAnnotations([]);
        return;
      }

      if (Array.isArray(local) && local.length > 0) {
        if (mounted) setAnnotations(cloneAnnotations(local));
        return;
      }

      if (mounted) setAnnotations(Array.isArray(fromBackend) ? fromBackend : []);
    }

    if (job?.id) {
      loadAnnotations().catch(() => setAnnotations([]));
    }

    return () => {
      mounted = false;
    };
  }, [accountEmail, job?.id, job?.updated_at, job?.annotations]);

  if (!job) {
    return (
      <AuthBackdrop theme={theme}>
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No project selected.</Text>
        </View>
      </AuthBackdrop>
    );
  }

  const status = getJobStatusMeta(job.status, theme, {
    processing: 'AI scan active',
    queued: 'AI scan active',
  });
  const neutralStatus = {
    fill: theme.colors.authDark,
    text: '#FFFFFF',
    label: status.label,
  };
  const topTitle = getResultsScreenTitle(job.status);
  const primaryError = error || job.metadata?.error;
  const stderrPreview = trimMultilineText(job.metadata?.stderr);

  function pushUndoSnapshot(snapshot) {
    setUndoStack((stack) => [...stack.slice(-49), cloneAnnotations(snapshot)]);
  }

  function handleChangeAnnotations(next, options = {}) {
    const { trackHistory = true } = options;
    setAnnotations((prev) => {
      const resolved = typeof next === 'function' ? next(prev) : next;
      const normalized = Array.isArray(resolved) ? resolved : [];
      if (trackHistory) {
        pushUndoSnapshot(prev);
      }
      return normalized;
    });
  }

  function handleHistoryCheckpoint(snapshot = annotations) {
    pushUndoSnapshot(snapshot);
  }

  function handleUndo() {
    setUndoStack((stack) => {
      if (!stack.length) return stack;
      const nextStack = stack.slice(0, -1);
      const prev = cloneAnnotations(stack[stack.length - 1]);
      setAnnotations(prev);
      return nextStack;
    });
  }

  function handleDeleteSelected(measurementId) {
    if (!measurementId) return;
    handleChangeAnnotations((current) => (current || []).filter((m) => m?.id !== measurementId));
  }

  async function persistAnnotations({ showErrorAlert = true } = {}) {
    if (!job?.id) {
      return { ok: false, synced: false };
    }

    let savedLocally = false;

    try {
      setSaveBusy(true);
      const previewUri = await annotatorRef.current?.captureAnnotatedImage?.();
      if (!previewUri) {
        throw new Error('Preview is not ready to export yet.');
      }

      const storedPreviewUri = await saveAnnotatedPreview(job.id, previewUri, accountEmail);
      setAnnotatedPreviewUri(storedPreviewUri);

      await saveLocalAnnotations(job.id, annotations || [], { backendSynced: false, accountKey: accountEmail });
      savedLocally = true;
      await saveJobAnnotations(job.id, annotations || [], accountEmail);
      await saveLocalAnnotations(job.id, annotations || [], { backendSynced: true, accountKey: accountEmail });
      return { ok: true, synced: true };
    } catch (err) {
      if (job?.id && savedLocally) {
        await saveLocalAnnotations(job.id, annotations || [], { backendSynced: false, accountKey: accountEmail }).catch(() => undefined);
      }

      if (showErrorAlert) {
        const message = err.message || 'Unable to save measurements.';
        if (savedLocally && err?.message && err.message !== 'Preview is not ready to export yet.') {
          Alert.alert('Saved on this device', `${message}\n\nThe measurements are saved locally, but backend sync did not finish.`);
        } else {
          Alert.alert('Save failed', message);
        }
      }
      return { ok: savedLocally, synced: false };
    } finally {
      setSaveBusy(false);
    }
  }

  async function handleSaveAnnotations() {
    await persistAnnotations({ showErrorAlert: true });
  }

  async function handleDownloadResult() {
    const downloadSource = annotatedPreviewUri || job?.combined_overlay_url;
    if (!downloadSource) {
      Alert.alert('Download failed', 'No generated floor plan is available yet.');
      return;
    }
    if (annotations.length && !annotatedPreviewUri) {
      Alert.alert('Save measurements first', 'Open the measurement screen and tap Save before downloading the annotated image.');
      return;
    }

    await onSaveResult(downloadSource);
  }

  if (job.status === 'completed' && editorOpen) {
    return (
      <MeasurementEditorScreen
        job={job}
        annotatorRef={annotatorRef}
        annotations={annotations}
        onChangeAnnotations={handleChangeAnnotations}
        onRequestUndo={handleUndo}
        onRequestDeleteSelected={handleDeleteSelected}
        onRequestSave={handleSaveAnnotations}
        onRequestHistoryCheckpoint={handleHistoryCheckpoint}
        onBack={() => setEditorOpen(false)}
        busy={busy || saveBusy}
        theme={theme}
        isLandscape={isLandscape}
      />
    );
  }

  if (job.status === 'processing' || job.status === 'queued') {
    return (
      <AuthBackdrop theme={theme}>
        <Animated.View style={[styles.screen, animatedStyle]}>
          <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
            <View style={styles.headerRow}>
              <BackButton onBack={onBack} theme={theme} styles={styles} />
              <Text style={styles.screenTitle}>{topTitle}</Text>
              <StatusPill meta={neutralStatus} styles={styles} />
            </View>

            <View style={styles.processingCard}>
              <View style={styles.processingTop}>
                <Text style={styles.processingTitle}>Processing your floor plan</Text>
                <Text style={styles.processingSubtitle}>We are converting the sketch into a clean digital layout and checking the room structure.</Text>
              </View>

              <Loader styles={styles} />

              <View style={styles.progressTrack}>
                <View style={styles.progressFill} />
              </View>
            </View>
          </ScrollView>
        </Animated.View>
      </AuthBackdrop>
    );
  }

  if (job.status === 'completed') {
    return (
      <AuthBackdrop theme={theme}>
        <Animated.View style={[styles.screen, animatedStyle]}>
          <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
            <View style={styles.headerRow}>
              <BackButton onBack={onBack} theme={theme} styles={styles} />
              <Text style={styles.screenTitle}>{topTitle}</Text>
              <StatusPill meta={status} styles={styles} />
            </View>

            <View style={styles.resultCard}>
              <View style={styles.resultHeader}>
                <View style={styles.resultCopy}>
                  <Text style={styles.outputTitle}>Digital floor plan ready</Text>
                </View>
              </View>

              <View style={styles.previewFrame}>
                {job.combined_overlay_url ? (
                  <Image source={{ uri: annotatedPreviewUri || job.combined_overlay_url }} style={styles.previewImage} resizeMode="contain" />
                ) : (
                  <View style={styles.outputEmpty}>
                    <Ionicons name="image-outline" size={22} color={theme.colors.softText} />
                  </View>
                )}
              </View>

              <View style={styles.outputActionRow}>
                <Pressable
                  style={[styles.actionButton, styles.primaryActionButton, styles.primarySummaryAction]}
                  onPress={handleDownloadResult}
                  disabled={busy || saveBusy || !(annotatedPreviewUri || job.combined_overlay_url)}
                >
                  <Text style={styles.primaryActionText}>{busy || saveBusy ? 'Saving...' : 'Download'}</Text>
                </Pressable>
                <Pressable style={[styles.actionButton, styles.secondaryActionButton]} onPress={() => setEditorOpen(true)} disabled={!job.combined_overlay_url}>
                  <Text style={styles.secondaryActionText}>Add Measurements</Text>
                </Pressable>
              </View>

              <View style={styles.summaryFooter}>
                <Text style={styles.summaryFooterText}>
                  {annotations.length ? 'Saved measurements will appear in the downloaded image.' : 'No measurements added yet.'}
                </Text>
                <Pressable style={styles.summaryFooterLink} onPress={onTryAnother}>
                  <Text style={styles.summaryFooterLinkText}>Try Another</Text>
                </Pressable>
              </View>
            </View>
          </ScrollView>
        </Animated.View>
      </AuthBackdrop>
    );
  }

  return (
    <AuthBackdrop theme={theme}>
      <Animated.View style={[styles.screen, animatedStyle]}>
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
    </AuthBackdrop>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    screen: {
      flex: 1,
    },
    content: {
      flexGrow: 1,
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
      minHeight: isLandscape ? 520 : 560,
      borderRadius: 30,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: 'rgba(255,255,255,0.72)',
      alignItems: 'center',
      justifyContent: 'center',
      paddingHorizontal: 24,
      paddingVertical: 24,
      ...theme.shadow.card,
    },
    processingTop: {
      alignItems: 'center',
      marginBottom: 10,
    },
    loaderWrap: {
      width: 184,
      height: 184,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 18,
    },
    loaderRing: {
      position: 'absolute',
      width: 184,
      height: 184,
    },
    loaderDot: {
      position: 'absolute',
      width: 12,
      height: 12,
      borderRadius: 6,
      backgroundColor: '#2A3140',
    },
    loaderCenter: {
      width: 92,
      height: 92,
      borderRadius: 46,
      backgroundColor: theme.colors.authDark,
      borderWidth: 1,
      borderColor: theme.colors.authDark,
      alignItems: 'center',
      justifyContent: 'center',
    },
    loaderText: {
      color: '#FFFFFF',
      fontSize: 30,
      fontWeight: '900',
      letterSpacing: -0.8,
    },
    sectionEyebrow: {
      color: theme.colors.softText,
      fontSize: 12,
      fontWeight: '700',
      marginBottom: 8,
    },
    processingTitle: {
      color: theme.colors.text,
      fontSize: isLandscape ? 30 : 26,
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
    progressTrack: {
      width: 190,
      height: 8,
      borderRadius: 999,
      backgroundColor: theme.colors.authInputBorder,
      marginTop: 4,
      overflow: 'hidden',
    },
    progressFill: {
      width: '72%',
      height: '100%',
      borderRadius: 999,
      backgroundColor: theme.colors.authDark,
    },
    processingInfoRow: {
      marginTop: 18,
      flexDirection: 'row',
      flexWrap: 'wrap',
      justifyContent: 'center',
      gap: 8,
    },
    infoChip: {
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderRadius: 999,
      backgroundColor: theme.colors.surfaceAlt,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
    },
    infoChipText: {
      color: theme.colors.text,
      fontSize: 12,
      fontWeight: '700',
    },
    resultCard: {
      backgroundColor: theme.colors.surface,
      borderRadius: 30,
      borderWidth: 1,
      borderColor: 'rgba(255,255,255,0.72)',
      padding: 18,
      ...theme.shadow.card,
    },
    resultHeader: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      gap: 12,
      marginBottom: 16,
    },
    resultCopy: {
      flex: 1,
    },
    resultBadge: {
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderRadius: 999,
      backgroundColor: theme.colors.surfaceAlt,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
    },
    resultBadgeText: {
      color: theme.colors.text,
      fontSize: 12,
      fontWeight: '700',
    },
    previewFrame: {
      height: isLandscape ? 420 : 460,
      borderRadius: 22,
      overflow: 'hidden',
      backgroundColor: theme.colors.surfaceAlt,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
      marginBottom: 16,
      alignItems: 'center',
      justifyContent: 'center',
      padding: 14,
    },
    previewImage: {
      width: '100%',
      height: '100%',
    },
    outputActionRow: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: 10,
      marginBottom: 16,
    },
    primarySummaryAction: {
      flexGrow: 1,
    },
    outputEmpty: {
      flex: 1,
      width: '100%',
      height: '100%',
      borderRadius: 18,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: theme.colors.surface,
    },
    summaryFooter: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12,
    },
    summaryFooterText: {
      flex: 1,
      color: theme.colors.muted,
      fontSize: 13,
      lineHeight: 19,
      fontWeight: '600',
    },
    summaryFooterLink: {
      paddingHorizontal: 2,
      paddingVertical: 4,
    },
    summaryFooterLinkText: {
      color: theme.colors.text,
      fontSize: 13,
      fontWeight: '800',
    },
    actionRow: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: 10,
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
      backgroundColor: theme.colors.authDark,
      borderColor: theme.colors.authDark,
    },
    secondaryActionButton: {
      backgroundColor: theme.colors.surfaceAlt,
      borderColor: theme.colors.authInputBorder,
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
      fontSize: 24,
      fontWeight: '900',
    },
    outputSubtitle: {
      marginTop: 6,
      color: theme.colors.muted,
      fontWeight: '600',
      lineHeight: 21,
    },
    issueCard: {
      backgroundColor: theme.colors.surface,
      borderRadius: 30,
      borderWidth: 1,
      borderColor: 'rgba(255,255,255,0.72)',
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
