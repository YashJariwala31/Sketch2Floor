import React, { useEffect, useState } from 'react';
import {
  Alert,
  Animated,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { AuthBackdrop, IridescentCube } from '../components/auth/AuthVisuals';
import { useEntranceAnimation } from '../hooks/useEntranceAnimation';

function Field({
  label,
  value,
  onChangeText,
  secureTextEntry,
  showVisibilityToggle,
  visible,
  onToggleVisibility,
  autoCapitalize = 'none',
  keyboardType = 'default',
  styles,
  theme,
  placeholder,
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.inputShell}>
        <TextInput
          value={value}
          onChangeText={onChangeText}
          style={styles.input}
          placeholder={placeholder}
          placeholderTextColor={theme.colors.softText}
          secureTextEntry={secureTextEntry && !visible}
          autoCapitalize={autoCapitalize}
          keyboardType={keyboardType}
          autoCorrect={false}
        />
        {showVisibilityToggle ? (
          <Pressable style={styles.inputAction} onPress={onToggleVisibility}>
            <Ionicons
              name={visible ? 'eye-off-outline' : 'eye-outline'}
              size={18}
              color={theme.colors.softText}
            />
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

function ToggleRow({ label, value, onValueChange, styles, theme }) {
  return (
    <View style={styles.toggleRow}>
      <Text style={styles.toggleLabel}>{label}</Text>
      <Switch
        value={value}
        onValueChange={onValueChange}
        trackColor={{ false: '#D9DEEB', true: theme.colors.authToggle }}
        thumbColor="#FFFFFF"
        ios_backgroundColor="#D9DEEB"
      />
    </View>
  );
}

export default function AuthScreen({ busy, theme, mode, onSubmit, onBack, onSwitchMode }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const animatedStyle = useEntranceAnimation({
    dependencies: [mode],
    duration: 320,
    damping: 15,
    stiffness: 140,
  });
  const styles = createStyles(theme);
  const isSignUp = mode === 'signup';

  useEffect(() => {
    setEmail('');
    setPassword('');
    setRememberMe(true);
    setPasswordVisible(false);
  }, [mode]);

  function handleSubmit() {
    const trimmedEmail = email.trim().toLowerCase();

    if (!trimmedEmail || !trimmedEmail.includes('@')) {
      Alert.alert('Enter a valid email', 'Use a valid email address.');
      return;
    }
    if (password.length < 6) {
      Alert.alert('Password too short', 'Use at least 6 characters.');
      return;
    }
    onSubmit({
      email: trimmedEmail,
      password,
      fullName: '',
      mode,
    });
  }

  function handleForgotPassword() {
    Alert.alert('Coming soon', 'Password recovery is not connected yet.');
  }

  return (
    <AuthBackdrop theme={theme}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <Animated.View style={[styles.sheet, animatedStyle]}>
            <View style={styles.topRow}>
              <Pressable style={styles.iconButton} onPress={onBack}>
                <Ionicons name="arrow-back" size={20} color={theme.colors.text} />
              </Pressable>

              {!isSignUp ? (
                <Pressable onPress={handleForgotPassword}>
                  <Text style={styles.topLink}>Forgot password?</Text>
                </Pressable>
              ) : (
                <View style={styles.topSpacer} />
              )}
            </View>

            {!isSignUp ? (
              <View style={styles.loginHeader}>
                <View style={styles.markWrap}>
                  <IridescentCube size={82} theme={theme} />
                </View>
              </View>
            ) : (
              <View style={styles.signupHeader}>
                <Text style={styles.headerTitle}>Let&apos;s Get Started</Text>
                <Text style={styles.headerSubtitle}>Fill the form to continue</Text>
              </View>
            )}

            <Field
              label={isSignUp ? 'Your Email Address' : 'Email Address'}
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              styles={styles}
              theme={theme}
              placeholder="john.doe@gmail.com"
            />

            <Field
              label={isSignUp ? 'Choose a Password' : 'Password'}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              showVisibilityToggle
              visible={passwordVisible}
              onToggleVisibility={() => setPasswordVisible((current) => !current)}
              styles={styles}
              theme={theme}
              placeholder={isSignUp ? 'min. 6 characters' : '...........'}
            />

            {isSignUp ? null : (
              <ToggleRow
                label="Remember me next time"
                value={rememberMe}
                onValueChange={setRememberMe}
                styles={styles}
                theme={theme}
              />
            )}

            <Pressable
              style={[styles.primaryButton, busy ? styles.primaryButtonDisabled : null]}
              onPress={handleSubmit}
              disabled={busy}
            >
              <Text style={styles.primaryButtonText}>
                {busy ? 'Please wait' : isSignUp ? 'Sign Up' : 'Login'}
              </Text>
            </Pressable>

            <Pressable style={styles.footerRow} onPress={onSwitchMode}>
              <Text style={styles.footerText}>
                {isSignUp ? 'Already have an account?' : "Don't have an account?"}
              </Text>
              <Text style={styles.footerLink}>{isSignUp ? 'Login' : 'Sign up'}</Text>
            </Pressable>
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
    </AuthBackdrop>
  );
}

function createStyles(theme) {
  return StyleSheet.create({
    content: {
      flexGrow: 1,
      justifyContent: 'center',
      paddingVertical: 24,
    },
    sheet: {
      width: '100%',
      maxWidth: 430,
      alignSelf: 'center',
      backgroundColor: theme.colors.surface,
      borderRadius: 34,
      paddingHorizontal: 18,
      paddingTop: 18,
      paddingBottom: 28,
      borderWidth: 1,
      borderColor: 'rgba(255,255,255,0.72)',
      ...theme.shadow.card,
    },
    topRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: 8,
    },
    iconButton: {
      width: 36,
      height: 36,
      alignItems: 'center',
      justifyContent: 'center',
    },
    topLink: {
      color: theme.colors.muted,
      fontSize: 12,
      fontWeight: '600',
    },
    topSpacer: {
      width: 36,
      height: 36,
    },
    loginHeader: {
      alignItems: 'center',
      marginBottom: 24,
      marginTop: 12,
    },
    markWrap: {
      width: 108,
      height: 108,
      alignItems: 'center',
      justifyContent: 'center',
    },
    signupHeader: {
      marginTop: 6,
      marginBottom: 24,
    },
    headerTitle: {
      color: theme.colors.text,
      fontSize: 31,
      fontWeight: '900',
      lineHeight: 36,
    },
    headerSubtitle: {
      marginTop: 6,
      color: theme.colors.muted,
      fontSize: 14,
      fontWeight: '500',
    },
    field: {
      marginBottom: 16,
    },
    fieldLabel: {
      color: theme.colors.text,
      fontSize: 13,
      fontWeight: '700',
      marginBottom: 9,
    },
    inputShell: {
      minHeight: 58,
      borderRadius: 16,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
      backgroundColor: theme.colors.authInputFill,
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: 16,
    },
    input: {
      flex: 1,
      color: theme.colors.text,
      fontSize: 14,
      fontWeight: '500',
      paddingVertical: 16,
    },
    inputAction: {
      marginLeft: 10,
      width: 24,
      height: 24,
      alignItems: 'center',
      justifyContent: 'center',
    },
    toggleRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12,
      marginTop: 2,
      marginBottom: 20,
    },
    toggleLabel: {
      flex: 1,
      color: theme.colors.text,
      fontSize: 13,
      fontWeight: '600',
    },
    primaryButton: {
      minHeight: 56,
      borderRadius: 15,
      backgroundColor: theme.colors.authDark,
      alignItems: 'center',
      justifyContent: 'center',
    },
    primaryButtonDisabled: {
      opacity: 0.72,
    },
    primaryButtonText: {
      color: '#FFFFFF',
      fontSize: 15,
      fontWeight: '800',
    },
    footerRow: {
      marginTop: 22,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 6,
    },
    footerText: {
      color: theme.colors.muted,
      fontSize: 13,
      fontWeight: '500',
    },
    footerLink: {
      color: theme.colors.text,
      fontSize: 13,
      fontWeight: '800',
    },
  });
}
