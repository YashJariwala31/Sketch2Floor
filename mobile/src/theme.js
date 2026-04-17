const shared = {
  spacing: {
    xs: 6,
    sm: 10,
    md: 16,
    lg: 20,
    xl: 28,
    xxl: 36,
  },
  radius: {
    sm: 12,
    md: 20,
    lg: 28,
    pill: 999,
  },
};

const lightColors = {
  background: '#f7f9fc',
  surface: '#ffffff',
  surfaceAlt: '#f1f5fb',
  panel: '#eef4ff',
  card: '#ffffff',
  text: '#111827',
  muted: '#5b6472',
  softText: '#8a94a6',
  accent: '#246bff',
  accentStrong: '#1147ba',
  accentSoft: '#dce8ff',
  border: '#e5ebf5',
  shadow: '#0f172a',
  success: '#1f9d69',
  warning: '#d99124',
  danger: '#d14343',
  noticeBg: '#eef4ff',
  noticeBorder: '#d8e5ff',
  errorBg: '#fff2f2',
  errorBorder: '#ffd7d7',
  destructiveSoft: '#fff2f2',
};

const darkColors = {
  background: '#0b1220',
  surface: '#111a2b',
  surfaceAlt: '#162033',
  panel: '#10233f',
  card: '#111a2b',
  text: '#f3f7ff',
  muted: '#b5c0d3',
  softText: '#8d9bb1',
  accent: '#4c8dff',
  accentStrong: '#83adff',
  accentSoft: '#16345f',
  border: '#22314a',
  shadow: '#000000',
  success: '#34c98b',
  warning: '#ffbe55',
  danger: '#ff7f7f',
  noticeBg: '#10233f',
  noticeBorder: '#1f3f6e',
  errorBg: '#331b24',
  errorBorder: '#6a3340',
  destructiveSoft: '#331b24',
};

function createShadow(colors) {
  return {
    card: {
      shadowColor: colors.shadow,
      shadowOffset: { width: 0, height: 12 },
      shadowOpacity: colors.shadow === '#000000' ? 0.24 : 0.08,
      shadowRadius: 22,
      elevation: 4,
    },
    soft: {
      shadowColor: colors.shadow,
      shadowOffset: { width: 0, height: 8 },
      shadowOpacity: colors.shadow === '#000000' ? 0.18 : 0.05,
      shadowRadius: 16,
      elevation: 3,
    },
  };
}

export function getTheme(scheme) {
  const colors = scheme === 'dark' ? darkColors : lightColors;
  return {
    colors,
    spacing: shared.spacing,
    radius: shared.radius,
    shadow: createShadow(colors),
    isDark: scheme === 'dark',
  };
}

export const theme = getTheme('light');
