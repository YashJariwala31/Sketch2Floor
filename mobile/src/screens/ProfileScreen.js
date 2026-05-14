import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Linking, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { AuthBackdrop } from '../components/auth/AuthVisuals';

function ProfileCharacter({ theme, styles }) {
  return (
    <View style={styles.characterStage}>
      <View style={[styles.characterGlow, styles.characterGlowBlue]} />
      <View style={[styles.characterGlow, styles.characterGlowPink]} />
      <View style={[styles.characterGlow, styles.characterGlowLavender]} />

      <View style={styles.characterShell}>
        <Ionicons
          name="person-circle"
          size={102}
          color={theme.colors.authIridescentBlue}
          style={[styles.characterLayer, { transform: [{ translateX: -6 }, { translateY: -2 }] }]}
        />
        <Ionicons
          name="person-circle"
          size={102}
          color={theme.colors.authIridescentPurple}
          style={[styles.characterLayer, { transform: [{ translateX: 6 }, { translateY: -4 }] }]}
        />
        <Ionicons
          name="person-circle"
          size={102}
          color={theme.colors.authIridescentPink}
          style={[styles.characterLayer, { transform: [{ translateX: 2 }, { translateY: 5 }] }]}
        />
        <Ionicons name="person-circle" size={102} color={theme.colors.authDark} style={styles.characterLayer} />
      </View>

      <View style={styles.characterBadge}>
        <Ionicons name="sparkles" size={16} color="#FFFFFF" />
      </View>
    </View>
  );
}

function ActionRow({ icon, title, subtitle, onPress, styles, theme }) {
  return (
    <Pressable style={styles.actionRow} onPress={onPress}>
      <View style={styles.actionIconWrap}>
        <Ionicons name={icon} size={18} color={theme.colors.text} />
      </View>
      <View style={styles.actionCopy}>
        <Text style={styles.actionTitle}>{title}</Text>
        <Text style={styles.actionSubtitle}>{subtitle}</Text>
      </View>
      <Ionicons name="chevron-forward" size={18} color={theme.colors.softText} />
    </Pressable>
  );
}

function ProfileModal({ visible, title, onClose, onSave, saveLabel = 'Save', children, theme, busy = false }) {
  const styles = useMemo(() => createStyles(theme, false), [theme]);

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>{title}</Text>
          <View style={styles.modalBody}>{children}</View>
          <View style={styles.modalActions}>
            <Pressable style={styles.modalSecondaryButton} onPress={onClose}>
              <Text style={styles.modalSecondaryText}>Cancel</Text>
            </Pressable>
            <Pressable style={[styles.modalPrimaryButton, busy ? { opacity: 0.72 } : null]} onPress={onSave} disabled={busy}>
              <Text style={styles.modalPrimaryText}>{saveLabel}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

export default function ProfileScreen({ session, onUpdateProfileName, onChangePassword, onSignOut, theme, isLandscape }) {
  const styles = createStyles(theme, isLandscape);
  const name = session?.name || 'Guest';
  const email = session?.email || 'Unavailable';
  const [nameModalOpen, setNameModalOpen] = useState(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [draftName, setDraftName] = useState(name);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [savingName, setSavingName] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    setDraftName(name);
  }, [name]);

  async function handleSupportEmail() {
    const subject = encodeURIComponent('Sketch2FloorPlan support request');
    const body = encodeURIComponent(`Hi,\n\nI need help with Sketch2FloorPlan.\n\nAccount: ${email}\n\nIssue:\n`);
    const mailtoUrl = `mailto:support@sketch2floorplan.app?subject=${subject}&body=${body}`;

    try {
      const supported = await Linking.canOpenURL(mailtoUrl);
      if (!supported) {
        throw new Error('No email app is available on this device.');
      }
      await Linking.openURL(mailtoUrl);
    } catch (err) {
      Alert.alert('Email not available', err.message || 'Unable to open your email app.');
    }
  }

  function resetPasswordFields() {
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
  }

  function openNameModal() {
    setDraftName(name);
    setNameModalOpen(true);
  }

  function openPasswordModal() {
    resetPasswordFields();
    setPasswordModalOpen(true);
  }

  async function saveName() {
    try {
      setSavingName(true);
      onUpdateProfileName(draftName);
      setNameModalOpen(false);
      Alert.alert('Username updated', 'Your profile name has been changed.');
    } catch (err) {
      Alert.alert('Update failed', err.message || 'Unable to update your username.');
    } finally {
      setSavingName(false);
    }
  }

  async function savePassword() {
    if (newPassword !== confirmPassword) {
      Alert.alert('Passwords do not match', 'Please re-enter the new password.');
      return;
    }

    try {
      setSavingPassword(true);
      onChangePassword({ currentPassword, newPassword });
      setPasswordModalOpen(false);
      resetPasswordFields();
      Alert.alert('Password updated', 'Your password has been changed.');
    } catch (err) {
      Alert.alert('Update failed', err.message || 'Unable to change your password.');
    } finally {
      setSavingPassword(false);
    }
  }

  return (
    <AuthBackdrop theme={theme}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.heroCard}>
          <ProfileCharacter theme={theme} styles={styles} />
          <Text style={styles.name}>{name}</Text>
          <Text style={styles.email}>{email}</Text>
        </View>

        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>Your details</Text>

          <ActionRow
            icon="person-outline"
            title="Username"
            subtitle={name}
            onPress={openNameModal}
            styles={styles}
            theme={theme}
          />
          <ActionRow
            icon="mail-outline"
            title="Email"
            subtitle={email}
            onPress={() => Alert.alert('Account email', email)}
            styles={styles}
            theme={theme}
          />
          <ActionRow
            icon="shield-checkmark-outline"
            title="Password & security"
            subtitle="Change your password and keep your account secure"
            onPress={openPasswordModal}
            styles={styles}
            theme={theme}
          />
        </View>

        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>About</Text>
          <Text style={styles.aboutCopy}>
            Sketch2FloorPlan helps turn rough sketches into clean digital floor plans with a faster, calmer workflow for review and sharing.
          </Text>
          <View style={styles.aboutMetaRow}>
            <Text style={styles.aboutMetaLabel}>Version</Text>
            <Text style={styles.aboutMetaValue}>1.0.0 mobile preview</Text>
          </View>
        </View>

        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>Help & support</Text>

          <ActionRow
            icon="mail-open-outline"
            title="Email support"
            subtitle="Send us an email if you need help"
            onPress={handleSupportEmail}
            styles={styles}
            theme={theme}
          />
        </View>

        <Pressable style={styles.signOutButton} onPress={onSignOut}>
          <Ionicons name="log-out-outline" size={18} color="#FFFFFF" />
          <Text style={styles.signOutButtonText}>Sign Out</Text>
        </Pressable>
      </ScrollView>

      <ProfileModal
        visible={nameModalOpen}
        title="Change username"
        onClose={() => setNameModalOpen(false)}
        onSave={saveName}
        theme={theme}
        busy={savingName}
      >
        <TextInput
          value={draftName}
          onChangeText={setDraftName}
          placeholder="Enter your username"
          placeholderTextColor={theme.colors.softText}
          style={styles.modalInput}
          autoCapitalize="words"
        />
      </ProfileModal>

      <ProfileModal
        visible={passwordModalOpen}
        title="Change password"
        onClose={() => setPasswordModalOpen(false)}
        onSave={savePassword}
        saveLabel="Update"
        theme={theme}
        busy={savingPassword}
      >
        <TextInput
          value={currentPassword}
          onChangeText={setCurrentPassword}
          placeholder="Current password"
          placeholderTextColor={theme.colors.softText}
          style={styles.modalInput}
          secureTextEntry
        />
        <TextInput
          value={newPassword}
          onChangeText={setNewPassword}
          placeholder="New password"
          placeholderTextColor={theme.colors.softText}
          style={styles.modalInput}
          secureTextEntry
        />
        <TextInput
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          placeholder="Confirm new password"
          placeholderTextColor={theme.colors.softText}
          style={styles.modalInput}
          secureTextEntry
        />
      </ProfileModal>
    </AuthBackdrop>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    content: {
      flexGrow: 1,
      paddingBottom: 26,
    },
    heroCard: {
      backgroundColor: theme.colors.surface,
      borderRadius: 32,
      borderWidth: 1,
      borderColor: 'rgba(255,255,255,0.72)',
      paddingHorizontal: 18,
      paddingTop: 22,
      paddingBottom: 20,
      alignItems: 'center',
      marginBottom: 14,
      ...theme.shadow.card,
    },
    characterStage: {
      width: 164,
      height: 164,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 14,
      position: 'relative',
    },
    characterGlow: {
      position: 'absolute',
      borderRadius: 999,
    },
    characterGlowBlue: {
      width: 116,
      height: 116,
      left: 8,
      top: 20,
      backgroundColor: theme.colors.authMistBlue,
    },
    characterGlowPink: {
      width: 108,
      height: 108,
      right: 10,
      top: 14,
      backgroundColor: theme.colors.authMistPink,
    },
    characterGlowLavender: {
      width: 90,
      height: 90,
      bottom: 14,
      left: 42,
      backgroundColor: theme.colors.authMistLavender,
    },
    characterShell: {
      width: 124,
      height: 124,
      borderRadius: 62,
      backgroundColor: theme.colors.surfaceAlt,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
      alignItems: 'center',
      justifyContent: 'center',
      shadowColor: theme.colors.authCardShadow,
      shadowOffset: { width: 0, height: 16 },
      shadowOpacity: 0.16,
      shadowRadius: 28,
      elevation: 8,
    },
    characterLayer: {
      position: 'absolute',
    },
    characterBadge: {
      position: 'absolute',
      right: 24,
      bottom: 26,
      width: 34,
      height: 34,
      borderRadius: 17,
      backgroundColor: theme.colors.authDark,
      alignItems: 'center',
      justifyContent: 'center',
    },
    name: {
      color: theme.colors.text,
      fontSize: isLandscape ? 32 : 28,
      fontWeight: '900',
      textAlign: 'center',
    },
    email: {
      marginTop: 6,
      color: theme.colors.muted,
      fontSize: 15,
      fontWeight: '600',
      textAlign: 'center',
    },
    sectionCard: {
      backgroundColor: theme.colors.surface,
      borderRadius: 28,
      borderWidth: 1,
      borderColor: 'rgba(255,255,255,0.72)',
      paddingHorizontal: 16,
      paddingTop: 16,
      paddingBottom: 6,
      marginBottom: 12,
      ...theme.shadow.soft,
    },
    sectionTitle: {
      color: theme.colors.text,
      fontSize: 18,
      fontWeight: '800',
      marginBottom: 8,
    },
    actionRow: {
      minHeight: 72,
      flexDirection: 'row',
      alignItems: 'center',
      gap: 12,
      paddingVertical: 10,
      borderTopWidth: 1,
      borderTopColor: theme.colors.authInputBorder,
    },
    actionIconWrap: {
      width: 42,
      height: 42,
      borderRadius: 21,
      backgroundColor: theme.colors.surfaceAlt,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
      alignItems: 'center',
      justifyContent: 'center',
    },
    actionCopy: {
      flex: 1,
      gap: 4,
    },
    actionTitle: {
      color: theme.colors.text,
      fontSize: 15,
      fontWeight: '700',
    },
    actionSubtitle: {
      color: theme.colors.muted,
      fontSize: 13,
      lineHeight: 18,
    },
    aboutCopy: {
      color: theme.colors.muted,
      fontSize: 14,
      lineHeight: 21,
      marginBottom: 14,
    },
    aboutMetaRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      borderTopWidth: 1,
      borderTopColor: theme.colors.authInputBorder,
      paddingTop: 12,
      paddingBottom: 8,
      gap: 12,
    },
    aboutMetaLabel: {
      color: theme.colors.softText,
      fontSize: 12,
      fontWeight: '700',
    },
    aboutMetaValue: {
      color: theme.colors.text,
      fontSize: 13,
      fontWeight: '700',
    },
    signOutButton: {
      minHeight: 56,
      borderRadius: 18,
      backgroundColor: theme.colors.authDark,
      alignItems: 'center',
      justifyContent: 'center',
      flexDirection: 'row',
      gap: 8,
      marginTop: 4,
    },
    signOutButtonText: {
      color: '#FFFFFF',
      fontSize: 15,
      fontWeight: '800',
    },
    modalBackdrop: {
      flex: 1,
      backgroundColor: 'rgba(18, 32, 51, 0.24)',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 18,
    },
    modalCard: {
      width: '100%',
      maxWidth: 420,
      backgroundColor: theme.colors.surface,
      borderRadius: 28,
      borderWidth: 1,
      borderColor: 'rgba(255,255,255,0.72)',
      padding: 18,
      ...theme.shadow.card,
    },
    modalTitle: {
      color: theme.colors.text,
      fontSize: 22,
      fontWeight: '800',
      marginBottom: 14,
    },
    modalBody: {
      gap: 10,
    },
    modalInput: {
      minHeight: 54,
      borderRadius: 16,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
      backgroundColor: theme.colors.authInputFill,
      paddingHorizontal: 14,
      color: theme.colors.text,
      fontSize: 14,
      fontWeight: '500',
    },
    modalActions: {
      flexDirection: 'row',
      justifyContent: 'flex-end',
      gap: 10,
      marginTop: 18,
    },
    modalPrimaryButton: {
      minHeight: 46,
      borderRadius: 14,
      backgroundColor: theme.colors.authDark,
      alignItems: 'center',
      justifyContent: 'center',
      paddingHorizontal: 18,
    },
    modalPrimaryText: {
      color: '#FFFFFF',
      fontWeight: '800',
    },
    modalSecondaryButton: {
      minHeight: 46,
      borderRadius: 14,
      backgroundColor: theme.colors.surfaceAlt,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
      alignItems: 'center',
      justifyContent: 'center',
      paddingHorizontal: 18,
    },
    modalSecondaryText: {
      color: theme.colors.text,
      fontWeight: '700',
    },
  });
}
