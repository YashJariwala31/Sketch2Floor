export function getJobStatusMeta(status, theme, labelOverrides = {}) {
  const defaults = {
    completed: { label: 'Ready', fill: theme.colors.successSoft, text: theme.colors.success },
    failed: { label: 'Issue', fill: theme.colors.errorBg, text: theme.colors.danger },
    processing: { label: 'Live', fill: theme.colors.accentSoft, text: theme.colors.accent },
    queued: { label: 'Queued', fill: theme.colors.panel, text: theme.colors.muted },
    draft: { label: 'Draft', fill: theme.colors.panel, text: theme.colors.muted },
  };

  const meta = defaults[status] || defaults.draft;
  return {
    ...meta,
    label: labelOverrides[status] || meta.label,
  };
}

export function getResultsScreenTitle(status) {
  if (status === 'completed') {
    return 'Output';
  }

  if (status === 'failed') {
    return 'Issue';
  }

  return 'Processing';
}

export function formatJobDate(value) {
  if (!value) {
    return 'Recently';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Recently';
  }

  return date.toLocaleDateString('en-IN', {
    month: 'short',
    year: 'numeric',
  });
}

export function trimMultilineText(value, maxLines = 8) {
  if (!value) {
    return '';
  }

  return value
    .split('\n')
    .filter(Boolean)
    .slice(0, maxLines)
    .join('\n');
}
