import React, { useMemo, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import JobCard from '../components/JobCard';

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'completed', label: 'Saved' },
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
      <Text style={styles.title}>History</Text>
      <Text style={styles.subtitle}>Previous conversions</Text>

      <View style={styles.filterRow}>
        {FILTERS.map((item) => {
          const active = item.key === filter;
          return (
            <Pressable key={item.key} style={[styles.filterPill, active ? styles.filterPillActive : null]} onPress={() => setFilter(item.key)}>
              <Text style={[styles.filterText, active ? styles.filterTextActive : null]}>{item.label}</Text>
            </Pressable>
          );
        })}
      </View>

      {loading ? <Text style={styles.message}>Loading history...</Text> : null}
      {error ? <Text style={[styles.message, styles.error]}>{error}</Text> : null}

      {!loading && !error && visibleJobs.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyTitle}>No floor plans yet</Text>
          <Text style={styles.emptyText}>Your completed scans will appear here.</Text>
        </View>
      ) : null}

      {visibleJobs.map((job) => (
        <JobCard
          key={job.id}
          job={job}
          theme={theme}
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
      paddingBottom: 30,
    },
    title: {
      color: theme.colors.text,
      fontSize: isLandscape ? 32 : 30,
      fontWeight: '900',
      letterSpacing: -0.9,
    },
    subtitle: {
      marginTop: 6,
      color: theme.colors.muted,
      fontWeight: '600',
      marginBottom: 18,
    },
    filterRow: {
      flexDirection: 'row',
      gap: 10,
      marginBottom: 18,
    },
    filterPill: {
      paddingHorizontal: 14,
      paddingVertical: 9,
      borderRadius: 999,
      backgroundColor: theme.colors.surfaceElevated,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
    },
    filterPillActive: {
      backgroundColor: theme.colors.heroTint,
      borderColor: theme.colors.noticeBorder,
    },
    filterText: {
      color: theme.colors.muted,
      fontWeight: '700',
      fontSize: 13,
    },
    filterTextActive: {
      color: theme.colors.accent,
    },
    message: {
      color: theme.colors.muted,
      marginBottom: 16,
      fontWeight: '700',
    },
    error: {
      color: theme.colors.danger,
    },
    emptyState: {
      minHeight: 220,
      borderRadius: 24,
      backgroundColor: theme.colors.surfaceElevated,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      alignItems: 'center',
      justifyContent: 'center',
      paddingHorizontal: 22,
      ...theme.shadow.soft,
    },
    emptyTitle: {
      color: theme.colors.text,
      fontSize: 23,
      fontWeight: '800',
      textAlign: 'center',
    },
    emptyText: {
      marginTop: 8,
      color: theme.colors.muted,
      textAlign: 'center',
      fontWeight: '600',
    },
  });
}
