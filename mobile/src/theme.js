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
    sm: 10,
    md: 16,
    lg: 22,
    xl: 28,
    pill: 999,
  },
};

const lightColors = {
  background: '#ffffff',
  backgroundAccent: '#fafafa',
  surface: '#ffffff',
  surfaceAlt: '#f6f6f7',
  surfaceElevated: '#fcfcfc',
  panel: '#f4f4f5',
  heroTint: '#fafafa',
  heroTintStrong: '#f2f2f3',
  card: '#ffffff',
  text: '#111111',
  muted: '#6b7280',
  softText: '#9ca3af',
  accent: '#111111',
  accentStrong: '#111111',
  accentSoft: '#f1f1f1',
  border: '#ebebed',
  borderStrong: '#dddddf',
  shadow: '#0f172a',
  success: '#18a57a',
  successSoft: '#e7f8f1',
  warning: '#d88e33',
  warningSoft: '#fff4e6',
  danger: '#df6761',
  noticeBg: '#f7f7f8',
  noticeBorder: '#e5e7eb',
  errorBg: '#fff1f1',
  errorBorder: '#f3d1d1',
  destructiveSoft: '#fff1f1',
  glow: 'rgba(17, 17, 17, 0.03)',
  glowStrong: 'rgba(17, 17, 17, 0.06)',
  canvasLine: 'rgba(17, 17, 17, 0.18)',
  canvasGrid: 'rgba(17, 17, 17, 0.08)',
  overlay: 'rgba(17, 17, 17, 0.02)',
};

function createShadow(colors, isDark) {
  return {
    card: {
      shadowColor: colors.shadow,
      shadowOffset: { width: 0, height: 14 },
      shadowOpacity: isDark ? 0.24 : 0.07,
      shadowRadius: 26,
      elevation: isDark ? 5 : 4,
    },
    soft: {
      shadowColor: colors.shadow,
      shadowOffset: { width: 0, height: 6 },
      shadowOpacity: isDark ? 0.18 : 0.04,
      shadowRadius: 14,
      elevation: isDark ? 2 : 1,
    },
    float: {
      shadowColor: colors.shadow,
      shadowOffset: { width: 0, height: 20 },
      shadowOpacity: isDark ? 0.28 : 0.09,
      shadowRadius: 30,
      elevation: isDark ? 8 : 5,
    },
  };
}

export function getTheme(scheme) {
  const isDark = false;
  const colors = lightColors;
  return {
    colors,
    spacing: shared.spacing,
    radius: shared.radius,
    shadow: createShadow(colors, isDark),
    isDark,
  };
}

export const theme = getTheme('light');
