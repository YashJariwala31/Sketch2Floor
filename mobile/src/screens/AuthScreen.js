import React, { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Animated,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

function Field({ label, value, onChangeText, secureTextEntry, autoCapitalize = 'none', keyboardType = 'default', styles, theme, placeholder }) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        style={styles.input}
        placeholder={placeholder}
        placeholderTextColor={theme.colors.softText}
        secureTextEntry={secureTextEntry}
        autoCapitalize={autoCapitalize}
        keyboardType={keyboardType}
      />
    </View>
  );
}

export default function AuthScreen({ busy, theme, mode, onSubmit, onBack, onSwitchMode }) {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const fade = useRef(new Animated.Value(0)).current;
  const rise = useRef(new Animated.Value(18)).current;
  const styles = createStyles(theme);
  const isSignUp = mode === 'signup';

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fade, {
        toValue: 1,
        duration: 320,
        useNativeDriver: true,
      }),
      Animated.spring(rise, {
        toValue: 0,
        useNativeDriver: true,
        damping: 15,
        stiffness: 140,
      }),
    ]).start();
  }, [fade, rise, mode]);

  useEffect(() => {
    setFullName('');
    setEmail('');
    setPassword('');
    setConfirmPassword('');
  }, [mode]);

  function handleSubmit() {
    const trimmedEmail = email.trim().toLowerCase();
    const trimmedName = fullName.trim();

    if (isSignUp && !trimmedName) {
      Alert.alert('Enter your name', 'Add your name to create an account.');
      return;
    }
    if (!trimmedEmail || !trimmedEmail.includes('@')) {
      Alert.alert('Enter a valid email', 'Use a valid email address.');
      return;
    }
    if (password.length < 6) {
      Alert.alert('Password too short', 'Use at least 6 characters.');
      return;
    }
    if (isSignUp && password !== confirmPassword) {
      Alert.alert('Passwords do not match', 'Please confirm your password again.');
      return;
    }

    onSubmit({
      email: trimmedEmail,
      password,
      fullName: trimmedName,
      mode,
    });
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Animated.View style={[styles.wrapper, { opacity: fade, transform: [{ translateY: rise }] }]}>
          <View style={styles.topBar}>
            <Pressable style={styles.backButton} onPress={onBack}>
              <Ionicons name="chevron-back" size={18} color={theme.colors.text} />
              <Text style={styles.backText}>Back</Text>
            </Pressable>

            <Pressable style={styles.switchButton} onPress={onSwitchMode}>
              <Text style={styles.switchButtonText}>{isSignUp ? 'Log in' : 'Sign up'}</Text>
            </Pressable>
          </View>

          <View style={styles.formCard}>
            <View style={styles.formHeader}>
              <Text style={styles.formTitle}>{isSignUp ? 'Create account' : 'Welcome back'}</Text>
              <Text style={styles.formText}>{isSignUp ? 'Start your first conversion.' : 'Log in to continue.'}</Text>
            </View>

            {isSignUp ? (
              <Field
                label="Name"
                value={fullName}
                onChangeText={setFullName}
                autoCapitalize="words"
                styles={styles}
                theme={theme}
                placeholder="Your name"
              />
            ) : null}

            <Field
              label="Email"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              styles={styles}
              theme={theme}
              placeholder="name@example.com"
            />

            <Field
              label="Password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              styles={styles}
              theme={theme}
              placeholder="Minimum 6 characters"
            />

            {isSignUp ? (
              <Field
                label="Confirm"
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                secureTextEntry
                styles={styles}
                theme={theme}
                placeholder="Repeat password"
              />
            ) : null}

            <Pressable style={[styles.submitButton, busy ? styles.submitButtonDisabled : null]} onPress={handleSubmit} disabled={busy}>
              <Text style={styles.submitButtonText}>{busy ? 'Please wait' : isSignUp ? 'Create Account' : 'Log In'}</Text>
            </Pressable>
          </View>
        </Animated.View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function createStyles(theme) {
  return StyleSheet.create({
    content: {
      flexGrow: 1,
      justifyContent: 'center',
      paddingVertical: 16,
    },
    wrapper: {
      width: '100%',
      maxWidth: 460,
      alignSelf: 'center',
    },
    topBar: {
      marginBottom: 16,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
    },
    backButton: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 6,
      paddingHorizontal: 12,
      paddingVertical: 10,
      borderRadius: 14,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.border,
    },
    backText: {
      color: theme.colors.text,
      fontWeight: '800',
    },
    switchButton: {
      paddingHorizontal: 14,
      paddingVertical: 10,
      borderRadius: 14,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.border,
    },
    switchButtonText: {
      color: theme.colors.text,
      fontWeight: '800',
    },
    formCard: {
      backgroundColor: theme.colors.surface,
      borderRadius: 30,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: 22,
      ...theme.shadow.card,
    },
    formHeader: {
      marginBottom: 18,
      alignItems: 'center',
    },
    formTitle: {
      color: theme.colors.text,
      fontSize: 28,
      fontWeight: '900',
      letterSpacing: -0.8,
      textAlign: 'center',
    },
    formText: {
      marginTop: 6,
      color: theme.colors.muted,
      fontWeight: '700',
      textAlign: 'center',
    },
    field: {
      marginBottom: 14,
    },
    fieldLabel: {
      color: theme.colors.softText,
      fontSize: 12,
      fontWeight: '800',
      textTransform: 'uppercase',
      letterSpacing: 0.9,
      marginBottom: 8,
    },
    input: {
      height: 56,
      borderRadius: 18,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      backgroundColor: theme.colors.surfaceElevated,
      paddingHorizontal: 16,
      color: theme.colors.text,
      fontWeight: '700',
    },
    submitButton: {
      marginTop: 10,
      height: 56,
      borderRadius: 18,
      backgroundColor: theme.colors.accent,
      alignItems: 'center',
      justifyContent: 'center',
    },
    submitButtonDisabled: {
      opacity: 0.72,
    },
    submitButtonText: {
      color: '#ffffff',
      fontWeight: '900',
      fontSize: 16,
    },
  });
}
