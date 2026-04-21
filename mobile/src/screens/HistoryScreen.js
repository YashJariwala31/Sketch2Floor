import React, { useMemo, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import JobCard from '../components/JobCard';

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'completed', label: 'Ready' },
  { key: 'processing', label: 'Live' },
  { key: 'failed', label: 'Issues' },
];

export default function HistoryScreen({ jobs, loading, error, onSelectJob, onDeleteJob, theme, isLandscape }) {
  const [filter, setFilter] = useState('all');
  const styles = createStyles(theme, isLandscape);

  const visibleJobs = useMemo(() => {
    if (filter === 'all') {
      return jobs;
    }
    return jobs.filter((job) => job.status === filter);
  }, [filter, jobs]);

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.title}>Library</Text>
          <Text style={styles.subtitle}>Saved scans</Text>
        </View>

        <View style={styles.countPill}>
          <Text style={styles.countText}>{jobs.length}</Text>
        </View>
      </View>

      <View style={styles.filterRail}>
        {FILTERS.map((item) => {
          const active = item.key === filter;
          return (
            <Pressable key={item.key} style={[styles.filterPill, active ? styles.filterPillActive : null]} onPress={() => setFilter(item.key)}>
              <Text style={[styles.filterText, active ? styles.filterTextActive : null]}>{item.label}</Text>
            </Pressable>
          );
        })}
      </View>

      {loading ? <Text style={styles.message}>Loading...</Text> : null}
      {error ? <Text style={[styles.message, styles.error]}>{error}</Text> : null}

      {!loading && !error && visibleJobs.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyTitle}>No scans</Text>
          <Text style={styles.emptyText}>Capture one to start.</Text>
        </View>
      ) : null}

      {visibleJobs.map((job) => (
        <JobCard
          key={job.id}
          job={job}
          theme={theme}
          isLandscape={isLandscape}
          onPress={() => onSelectJob(job)}
          onDelete={() =>
            Alert.alert('Delete project', 'Remove this floorplan project permanently?', [
              { text: 'Cancel', style: 'cancel' },
              { text: 'Delete', style: 'destructive', onPress: () => onDeleteJob(job) },
            ])
          }
        />
      ))}
    </ScrollView>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    content: {
      paddingBottom: 34,
    },
    headerRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      marginBottom: 18,
    },
    title: {
      color: theme.colors.text,
      fontSize: isLandscape ? 34 : 31,
      fontWeight: '900',
      letterSpacing: -1,
    },
    subtitle: {
      marginTop: 6,
      color: theme.colors.muted,
      fontWeight: '700',
    },
    countPill: {
      minWidth: 42,
      height: 42,
      paddingHorizontal: 12,
      borderRadius: 21,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: theme.colors.panel,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
    },
    countText: {
      color: theme.colors.text,
      fontWeight: '900',
      fontSize: 16,
    },
    filterRail: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: 10,
      marginBottom: 20,
      padding: 8,
      borderRadius: 22,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.border,
      ...theme.shadow.soft,
    },
    filterPill: {
      paddingHorizontal: 14,
      paddingVertical: 10,
      borderRadius: theme.radius.pill,
      backgroundColor: 'transparent',
    },
    filterPillActive: {
      backgroundColor: theme.colors.panel,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
    },
    filterText: {
      color: theme.colors.softText,
      fontWeight: '800',
    },
    filterTextActive: {
      color: theme.colors.text,
    },
    message: {
      color: theme.colors.muted,
      marginBottom: theme.spacing.md,
    },
    error: {
      color: theme.colors.danger,
    },
    emptyState: {
      minHeight: 260,
      borderRadius: theme.radius.xl,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.border,
      alignItems: 'center',
      justifyContent: 'center',
      gap: 10,
      marginBottom: theme.spacing.md,
      overflow: 'hidden',
      ...theme.shadow.card,
    },
    emptyTitle: {
      color: theme.colors.text,
      fontSize: 24,
      fontWeight: '900',
      letterSpacing: -0.6,
    },
    emptyText: {
      color: theme.colors.muted,
      fontWeight: '700',
    },
  });
}
