import React, { useMemo, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import JobCard from '../components/JobCard';

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'completed', label: 'Ready' },
  { key: 'processing', label: 'Processing' },
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
      <View style={styles.heroCard}>
        <Text style={styles.eyebrow}>History</Text>
        <Text style={styles.title}>Your previous floorplans</Text>
        <Text style={styles.text}>Browse, reopen, or remove your older conversions here.</Text>
      </View>

      <View style={styles.filterRow}>
        {FILTERS.map((item) => {
          const active = item.key === filter;
          return (
            <Pressable
              key={item.key}
              style={[styles.filterPill, active ? styles.filterPillActive : null]}
              onPress={() => setFilter(item.key)}
            >
              <Text style={[styles.filterText, active ? styles.filterTextActive : null]}>{item.label}</Text>
            </Pressable>
          );
        })}
      </View>

      {loading ? <Text style={styles.message}>Loading your conversions...</Text> : null}
      {error ? <Text style={[styles.message, styles.error]}>{error}</Text> : null}
      {!loading && !error && visibleJobs.length === 0 ? (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyTitle}>Nothing here yet</Text>
          <Text style={styles.emptyText}>Once you convert sketches, they will appear in this history section.</Text>
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
      paddingHorizontal: isLandscape ? 8 : 0,
    },
    heroCard: {
      backgroundColor: theme.colors.surface,
      borderRadius: theme.radius.lg,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: theme.spacing.xl,
      marginBottom: theme.spacing.lg,
      ...theme.shadow.card,
    },
    eyebrow: {
      color: theme.colors.accentStrong,
      fontSize: 12,
      fontWeight: '800',
      textTransform: 'uppercase',
      letterSpacing: 1.1,
      marginBottom: 10,
    },
    title: {
      color: theme.colors.text,
      fontSize: isLandscape ? 27 : 29,
      fontWeight: '900',
      letterSpacing: -0.8,
    },
    text: {
      color: theme.colors.muted,
      lineHeight: 22,
      marginTop: 10,
    },
    filterRow: {
      flexDirection: 'row',
      gap: 10,
      marginBottom: theme.spacing.lg,
      flexWrap: 'wrap',
    },
    filterPill: {
      paddingHorizontal: 14,
      paddingVertical: 10,
      borderRadius: theme.radius.pill,
      backgroundColor: theme.colors.surfaceAlt,
    },
    filterPillActive: {
      backgroundColor: theme.colors.accent,
    },
    filterText: {
      color: theme.colors.text,
      fontWeight: '700',
    },
    filterTextActive: {
      color: '#ffffff',
    },
    message: {
      color: theme.colors.muted,
      marginBottom: theme.spacing.md,
    },
    error: {
      color: theme.colors.danger,
    },
    emptyCard: {
      backgroundColor: theme.colors.surface,
      borderRadius: theme.radius.md,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: theme.spacing.xl,
      alignItems: 'center',
      marginBottom: theme.spacing.md,
      ...theme.shadow.soft,
    },
    emptyTitle: {
      color: theme.colors.text,
      fontSize: 20,
      fontWeight: '800',
      marginBottom: 8,
    },
    emptyText: {
      color: theme.colors.muted,
      lineHeight: 22,
      textAlign: 'center',
    },
  });
}
