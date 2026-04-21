import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

function DetailRow({ label, value, styles }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue} numberOfLines={2}>
        {value}
      </Text>
    </View>
  );
}

export default function ProfileScreen({ connection, session, onRefreshConnection, onSignOut, theme, isLandscape }) {
  const connectionOk = connection?.ok;
  const styles = createStyles(theme, isLandscape);

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.title}>Profile</Text>
          <Text style={styles.subtitle}>App settings</Text>
        </View>

        <View style={[styles.statePill, connectionOk ? styles.statePillOk : styles.statePillError]}>
          <View style={[styles.stateDot, { backgroundColor: connectionOk ? theme.colors.success : theme.colors.danger }]} />
          <Text style={[styles.stateText, { color: connectionOk ? theme.colors.success : theme.colors.danger }]}>
            {connectionOk ? 'Connected' : 'Offline'}
          </Text>
        </View>
      </View>

      <View style={styles.panel}>
        <View style={styles.iconWrap}>
          <Ionicons name="sparkles-outline" size={18} color={theme.colors.accentStrong} />
        </View>

        <DetailRow label="Name" value={session?.name || 'Guest'} styles={styles} />
        <DetailRow label="Email" value={session?.email || 'Unavailable'} styles={styles} />
        <DetailRow label="Backend" value={connection?.apiBaseUrl || 'Unavailable'} styles={styles} />
        <DetailRow label="Theme" value="Light studio" styles={styles} />
        <DetailRow label="Downloads" value="Phone storage" styles={styles} />

        <Pressable style={styles.primaryButton} onPress={onRefreshConnection}>
          <Ionicons name="refresh" size={16} color="#ffffff" />
          <Text style={styles.primaryButtonText}>Refresh</Text>
        </Pressable>

        <Pressable style={styles.secondaryButton} onPress={onSignOut}>
          <Ionicons name="log-out-outline" size={16} color={theme.colors.text} />
          <Text style={styles.secondaryButtonText}>Sign Out</Text>
        </Pressable>
      </View>
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
      gap: 12,
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
    statePill: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      paddingHorizontal: 12,
      paddingVertical: 9,
      borderRadius: theme.radius.pill,
      borderWidth: 1,
    },
    statePillOk: {
      backgroundColor: theme.colors.successSoft,
      borderColor: theme.colors.border,
    },
    statePillError: {
      backgroundColor: theme.colors.errorBg,
      borderColor: theme.colors.errorBorder,
    },
    stateDot: {
      width: 8,
      height: 8,
      borderRadius: 4,
    },
    stateText: {
      fontWeight: '900',
      fontSize: 12,
    },
    panel: {
      backgroundColor: theme.colors.surfaceElevated,
      borderRadius: theme.radius.xl,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      padding: theme.spacing.lg,
      ...theme.shadow.card,
    },
    iconWrap: {
      width: 44,
      height: 44,
      borderRadius: 22,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: theme.colors.accentSoft,
      marginBottom: 18,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
    },
    detailRow: {
      paddingVertical: 14,
      borderBottomWidth: 1,
      borderBottomColor: theme.colors.border,
      gap: 6,
    },
    detailLabel: {
      color: theme.colors.softText,
      fontWeight: '800',
      fontSize: 12,
      textTransform: 'uppercase',
      letterSpacing: 1,
    },
    detailValue: {
      color: theme.colors.text,
      fontWeight: '700',
      lineHeight: 21,
    },
    primaryButton: {
      marginTop: 20,
      backgroundColor: theme.colors.accent,
      borderRadius: theme.radius.pill,
      paddingVertical: 14,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
    },
    primaryButtonText: {
      color: '#ffffff',
      fontWeight: '900',
    },
    secondaryButton: {
      marginTop: 10,
      borderRadius: theme.radius.pill,
      paddingVertical: 14,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
      backgroundColor: theme.colors.heroTint,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
    },
    secondaryButtonText: {
      color: theme.colors.text,
      fontWeight: '900',
    },
  });
}
