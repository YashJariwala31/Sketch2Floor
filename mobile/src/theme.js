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
  background: '#F3F7FC',
  backgroundAccent: '#EAF1F9',
  surface: '#FFFFFF',
  surfaceAlt: '#F7FAFE',
  surfaceElevated: '#FCFDFF',
  panel: '#EEF4FB',
  heroTint: '#EDF4FF',
  heroTintStrong: '#E4EEFB',
  card: '#FFFFFF',
  text: '#172538',
  muted: '#617388',
  softText: '#8FA0B4',
  accent: '#2D66F6',
  accentStrong: '#1F54D0',
  accentSoft: '#E3ECFF',
  border: '#D8E2EE',
  borderStrong: '#C3D0E0',
  shadow: '#122033',
  success: '#249E6C',
  successSoft: '#E6F6EE',
  warning: '#4A7FFF',
  warningSoft: '#E8F0FF',
  danger: '#D96A5C',
  noticeBg: '#EAF2FF',
  noticeBorder: '#D3E1FF',
  errorBg: '#FFF1EE',
  errorBorder: '#F3D3CF',
  destructiveSoft: '#FFF2EF',
  glow: 'rgba(45, 102, 246, 0.08)',
  glowStrong: 'rgba(45, 102, 246, 0.16)',
  canvasLine: 'rgba(33, 51, 74, 0.62)',
  canvasGrid: 'rgba(33, 51, 74, 0.12)',
  overlay: 'rgba(21, 36, 58, 0.04)',
};

function createShadow(colors) {
  return {
    card: {
      shadowColor: colors.shadow,
      shadowOffset: { width: 0, height: 14 },
      shadowOpacity: 0.075,
      shadowRadius: 30,
      elevation: 5,
    },
    soft: {
      shadowColor: colors.shadow,
      shadowOffset: { width: 0, height: 6 },
      shadowOpacity: 0.05,
      shadowRadius: 18,
      elevation: 2,
    },
    float: {
      shadowColor: colors.shadow,
      shadowOffset: { width: 0, height: 20 },
      shadowOpacity: 0.11,
      shadowRadius: 36,
      elevation: 7,
    },
  };
}

export function getTheme() {
  const colors = lightColors;
  return {
    colors,
    spacing: shared.spacing,
    radius: shared.radius,
    shadow: createShadow(colors),
    isDark: false,
  };
}

export const theme = getTheme();
