import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { TAB_META } from '../../constants/navigation';

function TabButton({ active, tab, onPress, theme }) {
  const styles = createStyles(theme);
  const meta = TAB_META[tab];

  return (
    <Pressable style={[styles.tabButton, active ? styles.tabButtonActive : null]} onPress={onPress}>
      <Ionicons name={active ? meta.activeIcon : meta.icon} size={19} color={active ? theme.colors.accent : theme.colors.softText} />
      <Text style={[styles.tabLabel, active ? styles.tabLabelActive : null]}>{meta.label}</Text>
    </Pressable>
  );
}

export default function BottomTabBar({ activeTab, onSelectTab, tabs, theme }) {
  const styles = createStyles(theme);

  return (
    <View style={styles.bottomNav}>
      {tabs.map((tab) => (
        <TabButton key={tab} active={activeTab === tab} tab={tab} onPress={() => onSelectTab(tab)} theme={theme} />
      ))}
    </View>
  );
}

function createStyles(theme) {
  return StyleSheet.create({
    bottomNav: {
      marginTop: 12,
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: theme.colors.surfaceElevated,
      borderRadius: 22,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      paddingHorizontal: 7,
      paddingVertical: 7,
      ...theme.shadow.card,
    },
    tabButton: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      gap: 6,
      paddingVertical: 11,
      borderRadius: 18,
    },
    tabButtonActive: {
      backgroundColor: theme.colors.heroTint,
    },
    tabLabel: {
      color: theme.colors.softText,
      fontWeight: '800',
      fontSize: 12,
    },
    tabLabelActive: {
      color: theme.colors.accent,
    },
  });
}
