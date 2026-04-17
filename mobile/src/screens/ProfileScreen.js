import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

export default function ProfileScreen({ connection, onRefreshConnection, theme, isLandscape }) {
  const connectionOk = connection?.ok;
  const styles = createStyles(theme, isLandscape);

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <View style={styles.sectionCard}>
        <Text style={styles.sectionTitle}>Connection Status</Text>
        <View style={styles.statusRow}>
          <View style={[styles.statusDot, { backgroundColor: connectionOk ? theme.colors.success : theme.colors.danger }]} />
          <Text style={styles.statusText}>{connectionOk ? 'Backend connected' : 'Backend unavailable'}</Text>
        </View>
        <Text style={styles.detailLabel}>API URL</Text>
        <Text style={styles.detailValue}>{connection?.apiBaseUrl || 'Unavailable'}</Text>
        <Text style={styles.detailLabel}>Message</Text>
        <Text style={styles.detailValue}>
          {connectionOk ? 'Your phone should be able to upload images now.' : connection?.error || 'No connection check yet.'}
        </Text>
        <Pressable style={styles.primaryButton} onPress={onRefreshConnection}>
          <Text style={styles.primaryButtonText}>Check Connection Again</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    content: {
      paddingBottom: 34,
      paddingHorizontal: isLandscape ? 8 : 0,
    },
    sectionCard: {
      backgroundColor: theme.colors.surface,
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
    statusRow: {
      flexDirection: 'row',
      alignItems: 'center',
      marginBottom: 14,
    },
    statusDot: {
      width: 10,
      height: 10,
      borderRadius: 5,
      marginRight: 10,
    },
    statusText: {
      color: theme.colors.text,
      fontWeight: '800',
    },
    detailLabel: {
      color: theme.colors.softText,
      fontWeight: '700',
      marginTop: 10,
    },
    detailValue: {
      color: theme.colors.text,
      marginTop: 4,
      lineHeight: 21,
    },
    primaryButton: {
      marginTop: 18,
      backgroundColor: theme.colors.accent,
      borderRadius: theme.radius.pill,
      paddingVertical: 14,
      alignItems: 'center',
    },
    primaryButtonText: {
      color: '#ffffff',
      fontWeight: '800',
    },
  });
}
