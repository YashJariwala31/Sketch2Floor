const fs = require('fs');
const path = require('path');

const WIDTH = 2400;
const HEIGHT = 1320;

const colors = {
  board: '#F6F8FB',
  white: '#FFFFFF',
  ink: '#122033',
  muted: '#6B7A8B',
  lightText: '#8D9AAA',
  border: '#DCE5EE',
  panel: '#F4F7FA',
  line: '#BFCBDA',
  blue: '#2F6BFF',
  blueSoft: '#EAF1FF',
  blueMuted: '#DCE7FF',
  success: '#1C9A63',
  successSoft: '#E6F7EF',
  issue: '#D86A5C',
  issueSoft: '#FFF0EE',
};

const root = path.resolve(__dirname);
const outSvg = path.join(root, 'sketch2floorplan-ui-showcase.svg');

function esc(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function text(x, y, value, options = {}) {
  const {
    size = 24,
    weight = 600,
    fill = colors.ink,
    anchor = 'start',
    opacity,
    letterSpacing,
  } = options;
  return `<text x="${x}" y="${y}" font-family="Inter, Roboto, Arial, sans-serif" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}"${opacity ? ` opacity="${opacity}"` : ''}${letterSpacing ? ` letter-spacing="${letterSpacing}"` : ''}>${esc(value)}</text>`;
}

function roundRect(x, y, w, h, r, options = {}) {
  const {
    fill = 'none',
    stroke = 'none',
    strokeWidth = 1,
    opacity,
  } = options;
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"${opacity ? ` opacity="${opacity}"` : ''} />`;
}

function line(x1, y1, x2, y2, options = {}) {
  const {
    stroke = colors.line,
    strokeWidth = 4,
    opacity,
    dash,
    linecap = 'round',
  } = options;
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${strokeWidth}" stroke-linecap="${linecap}"${opacity ? ` opacity="${opacity}"` : ''}${dash ? ` stroke-dasharray="${dash}"` : ''} />`;
}

function circle(cx, cy, r, options = {}) {
  const {
    fill = 'none',
    stroke = 'none',
    strokeWidth = 1,
    opacity,
  } = options;
  return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"${opacity ? ` opacity="${opacity}"` : ''} />`;
}

function phoneFrame(x, y, w, h, inner) {
  return `
    <g>
      <rect x="${x + 12}" y="${y + 26}" width="${w}" height="${h}" rx="44" fill="#B7C6D8" opacity="0.08" />
      <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="44" fill="${colors.white}" stroke="${colors.border}" stroke-width="2" />
      <rect x="${x + w / 2 - 72}" y="${y + 18}" width="144" height="24" rx="12" fill="${colors.ink}" opacity="0.96" />
      <g>${inner}</g>
    </g>
  `;
}

function screenHeader(x, y, w, title, right = '') {
  return `
    ${text(x, y, title, { size: 27, weight: 800 })}
    ${right ? text(x + w, y, right, { size: 16, weight: 700, fill: colors.muted, anchor: 'end' }) : ''}
  `;
}

function blueprintMini(x, y, scale = 1, stroke = colors.line, opacity = 1) {
  return `
    <g opacity="${opacity}">
      ${line(x + 8 * scale, y + 22 * scale, x + 124 * scale, y + 22 * scale, { stroke, strokeWidth: 5 * scale })}
      ${line(x + 8 * scale, y + 22 * scale, x + 8 * scale, y + 128 * scale, { stroke, strokeWidth: 5 * scale })}
      ${line(x + 8 * scale, y + 128 * scale, x + 92 * scale, y + 128 * scale, { stroke, strokeWidth: 5 * scale })}
      ${line(x + 92 * scale, y + 128 * scale, x + 92 * scale, y + 70 * scale, { stroke, strokeWidth: 5 * scale })}
      ${line(x + 92 * scale, y + 70 * scale, x + 150 * scale, y + 70 * scale, { stroke, strokeWidth: 5 * scale })}
      ${line(x + 150 * scale, y + 70 * scale, x + 150 * scale, y + 22 * scale, { stroke, strokeWidth: 5 * scale })}
      ${line(x + 58 * scale, y + 22 * scale, x + 58 * scale, y + 76 * scale, { stroke, strokeWidth: 5 * scale })}
      <path d="M ${x + 92 * scale} ${y + 128 * scale} A ${28 * scale} ${28 * scale} 0 0 0 ${x + 120 * scale} ${y + 100 * scale}" fill="none" stroke="${stroke}" stroke-width="${4 * scale}" stroke-linecap="round" />
    </g>
  `;
}

function uploadIcon(x, y, color = colors.blue) {
  return `
    ${roundRect(x, y, 56, 56, 16, { fill: colors.blueSoft, stroke: colors.blueMuted })}
    ${line(x + 28, y + 18, x + 28, y + 37, { stroke: color, strokeWidth: 4 })}
    ${line(x + 20, y + 26, x + 28, y + 18, { stroke: color, strokeWidth: 4 })}
    ${line(x + 36, y + 26, x + 28, y + 18, { stroke: color, strokeWidth: 4 })}
    ${line(x + 18, y + 40, x + 38, y + 40, { stroke: color, strokeWidth: 4 })}
  `;
}

function cameraIcon(x, y, color = colors.ink) {
  return `
    ${roundRect(x, y, 56, 56, 16, { fill: colors.panel, stroke: colors.border })}
    ${roundRect(x + 13, y + 18, 30, 22, 8, { fill: colors.white, stroke: color, strokeWidth: 2 })}
    ${circle(x + 28, y + 29, 7, { fill: 'none', stroke: color, strokeWidth: 2 })}
    ${roundRect(x + 18, y + 14, 10, 6, 3, { fill: color })}
  `;
}

function aiLoader(x, y) {
  const cx = x + 110;
  const cy = y + 110;
  const pieces = [];
  for (let i = 0; i < 10; i += 1) {
    const angle = (Math.PI * 2 * i) / 10;
    const px = cx + Math.cos(angle) * 72;
    const py = cy + Math.sin(angle) * 72;
    const opacity = 0.18 + i * 0.08;
    pieces.push(circle(px, py, 8, { fill: colors.blue, opacity }));
  }
  return `
    ${circle(cx, cy, 78, { fill: 'none', stroke: colors.blueMuted, strokeWidth: 10 })}
    ${circle(cx, cy, 52, { fill: colors.blueSoft, stroke: 'none' })}
    ${pieces.join('')}
    ${text(cx, cy + 8, 'AI', { size: 34, weight: 900, fill: colors.blue, anchor: 'middle' })}
  `;
}

function pill(x, y, label, options = {}) {
  const {
    fill = colors.panel,
    stroke = colors.border,
    textFill = colors.muted,
    width = 88,
  } = options;
  return `
    ${roundRect(x, y, width, 34, 17, { fill, stroke })}
    ${text(x + width / 2, y + 23, label, { size: 14, weight: 800, fill: textFill, anchor: 'middle' })}
  `;
}

function button(x, y, w, h, label, options = {}) {
  const {
    primary = false,
    icon = '',
  } = options;
  const fill = primary ? colors.blue : colors.white;
  const stroke = primary ? colors.blue : colors.border;
  const textFill = primary ? colors.white : colors.ink;
  return `
    ${roundRect(x, y, w, h, 18, { fill, stroke, strokeWidth: 1.5 })}
    ${icon}
    ${text(x + w / 2, y + h / 2 + 8, label, { size: 18, weight: 800, fill: textFill, anchor: 'middle' })}
  `;
}

function historyItem(x, y, w, titleValue, statusLabel, statusFill, statusTextFill) {
  return `
    ${roundRect(x, y, w, 104, 22, { fill: colors.white, stroke: colors.border })}
    ${roundRect(x + 18, y + 16, 72, 72, 18, { fill: colors.panel, stroke: colors.border })}
    ${blueprintMini(x + 28, y + 26, 0.34, colors.line, 0.9)}
    ${text(x + 108, y + 39, titleValue, { size: 20, weight: 800 })}
    ${text(x + 108, y + 66, 'Digital floor plan', { size: 15, weight: 600, fill: colors.muted })}
    ${roundRect(x + w - 118, y + 18, 92, 30, 15, { fill: statusFill, stroke: 'none' })}
    ${text(x + w - 72, y + 39, statusLabel, { size: 13, weight: 800, fill: statusTextFill, anchor: 'middle' })}
    ${text(x + 108, y + 88, 'April 2026', { size: 14, weight: 600, fill: colors.lightText })}
  `;
}

function homeScreen(x, y, w, h) {
  const px = x + 28;
  const py = y + 64;
  const innerW = w - 56;
  return phoneFrame(x, y, w, h, `
    ${screenHeader(px, py, innerW, 'Sketch2FloorPlan')}
    ${text(px, py + 34, 'AI floor plan digitizer', { size: 16, weight: 600, fill: colors.muted })}
    ${roundRect(px, py + 74, innerW, 212, 28, { fill: colors.white, stroke: colors.border })}
    ${roundRect(px + 18, py + 94, innerW - 36, 132, 24, { fill: colors.panel, stroke: colors.border })}
    ${blueprintMini(px + 42, py + 116, 0.8, colors.line, 0.55)}
    ${text(px + innerW - 28, py + 136, 'New project', { size: 15, weight: 800, fill: colors.muted, anchor: 'end' })}
    ${text(px + innerW - 28, py + 176, 'Upload or capture', { size: 28, weight: 900, fill: colors.ink, anchor: 'end' })}
    ${text(px + innerW - 28, py + 206, 'a hand-drawn sketch', { size: 28, weight: 900, fill: colors.ink, anchor: 'end' })}
    ${button(px, py + 316, innerW, 66, 'Upload Sketch', { primary: true })}
    ${button(px, py + 398, innerW, 66, 'Capture Image')}
    ${roundRect(px, py + 496, innerW, 136, 24, { fill: colors.panel, stroke: colors.border })}
    ${text(px + 20, py + 525, 'Quick tip', { size: 14, weight: 800, fill: colors.muted })}
    ${text(px + 20, py + 562, 'Use a flat photo with clear walls', { size: 22, weight: 800 })}
    ${pill(px + 20, py + 586, 'White paper', { width: 102 })}
    ${pill(px + 134, py + 586, 'Good light', { width: 94 })}
    ${pill(px + 240, py + 586, 'Straight angle', { width: 114 })}
  `);
}

function uploadScreen(x, y, w, h) {
  const px = x + 28;
  const py = y + 64;
  const innerW = w - 56;
  return phoneFrame(x, y, w, h, `
    ${screenHeader(px, py, innerW, 'Upload sketch')}
    ${text(px, py + 34, 'Choose a source image', { size: 16, weight: 600, fill: colors.muted })}
    ${roundRect(px, py + 82, innerW, 310, 28, { fill: colors.panel, stroke: colors.border, strokeWidth: 1.5 })}
    ${roundRect(px + 18, py + 100, innerW - 36, 274, 24, { fill: colors.white, stroke: colors.blueMuted, strokeWidth: 2 })}
    ${line(px + 34, py + 116, px + innerW - 34, py + 116, { stroke: colors.blueMuted, strokeWidth: 2, dash: '8 10' })}
    ${line(px + 34, py + 356, px + innerW - 34, py + 356, { stroke: colors.blueMuted, strokeWidth: 2, dash: '8 10' })}
    ${line(px + 34, py + 116, px + 34, py + 356, { stroke: colors.blueMuted, strokeWidth: 2, dash: '8 10' })}
    ${line(px + innerW - 34, py + 116, px + innerW - 34, py + 356, { stroke: colors.blueMuted, strokeWidth: 2, dash: '8 10' })}
    ${uploadIcon(px + innerW / 2 - 28, py + 182)}
    ${text(px + innerW / 2, py + 274, 'Drop image or preview here', { size: 20, weight: 800, fill: colors.ink, anchor: 'middle' })}
    ${text(px + innerW / 2, py + 306, 'JPEG or PNG', { size: 15, weight: 600, fill: colors.muted, anchor: 'middle' })}
    ${button(px, py + 428, innerW, 66, 'Choose from Gallery', { primary: true })}
    ${button(px, py + 510, innerW, 66, 'Open Camera')}
    ${uploadIcon(px + 20, py + 434)}
    ${cameraIcon(px + 20, py + 516)}
  `);
}

function processingScreen(x, y, w, h) {
  const px = x + 28;
  const py = y + 64;
  const innerW = w - 56;
  return phoneFrame(x, y, w, h, `
    ${screenHeader(px, py, innerW, 'Processing')}
    ${roundRect(px, py + 82, innerW, 628, 28, { fill: colors.white, stroke: colors.border })}
    ${aiLoader(px + innerW / 2 - 110, py + 182)}
    ${text(px + innerW / 2, py + 450, 'Processing your floor plan...', { size: 28, weight: 900, anchor: 'middle' })}
    ${text(px + innerW / 2, py + 486, 'Detecting walls, doors, and layout', { size: 17, weight: 600, fill: colors.muted, anchor: 'middle' })}
    ${pill(px + innerW / 2 - 66, py + 534, 'AI scan active', { width: 132, fill: colors.blueSoft, stroke: colors.blueMuted, textFill: colors.blue })}
    ${roundRect(px + 34, py + 602, innerW - 68, 10, 5, { fill: colors.blueMuted, stroke: 'none' })}
    ${roundRect(px + 34, py + 602, innerW * 0.58, 10, 5, { fill: colors.blue, stroke: 'none' })}
  `);
}

function outputScreen(x, y, w, h) {
  const px = x + 28;
  const py = y + 64;
  const innerW = w - 56;
  return phoneFrame(x, y, w, h, `
    ${screenHeader(px, py, innerW, 'Output')}
    ${pill(px + innerW - 104, py - 10, 'Ready', { width: 90, fill: colors.successSoft, stroke: 'none', textFill: colors.success })}
    ${roundRect(px, py + 82, innerW, 420, 28, { fill: colors.white, stroke: colors.border })}
    ${roundRect(px + 18, py + 100, innerW - 36, 384, 24, { fill: colors.panel, stroke: colors.border })}
    ${blueprintMini(px + 74, py + 162, 1.18, colors.ink, 0.82)}
    ${pill(px + innerW - 142, py + 118, 'Zoom 125%', { width: 110 })}
    ${button(px, py + 530, 114, 58, 'Download', { primary: true })}
    ${button(px + 128, py + 530, 92, 58, 'Save')}
    ${button(px + 234, py + 530, 144, 58, 'Try Another')}
    ${text(px, py + 636, 'Digital floor plan generated', { size: 19, weight: 800 })}
    ${text(px, py + 664, 'Walls, openings, and layout are ready.', { size: 15, weight: 600, fill: colors.muted })}
  `);
}

function historyScreen(x, y, w, h) {
  const px = x + 28;
  const py = y + 64;
  const innerW = w - 56;
  return phoneFrame(x, y, w, h, `
    ${screenHeader(px, py, innerW, 'History')}
    ${text(px, py + 34, 'Previous conversions', { size: 16, weight: 600, fill: colors.muted })}
    ${pill(px, py + 78, 'All', { width: 64, fill: colors.blueSoft, stroke: colors.blueMuted, textFill: colors.blue })}
    ${pill(px + 76, py + 78, 'Saved', { width: 78 })}
    ${pill(px + 166, py + 78, 'Issues', { width: 78 })}
    ${historyItem(px, py + 132, innerW, 'Site plan A', 'Ready', colors.successSoft, colors.success)}
    ${historyItem(px, py + 252, innerW, 'Basement sketch', 'Saved', colors.blueSoft, colors.blue)}
    ${historyItem(px, py + 372, innerW, 'Office layout', 'Issue', colors.issueSoft, colors.issue)}
    ${historyItem(px, py + 492, innerW, 'Residence plan', 'Ready', colors.successSoft, colors.success)}
  `);
}

const board = `
<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}">
  <defs>
    <filter id="shadowCard" x="-20%" y="-20%" width="140%" height="160%">
      <feDropShadow dx="0" dy="18" stdDeviation="24" flood-color="#16304A" flood-opacity="0.08"/>
    </filter>
  </defs>
  ${roundRect(0, 0, WIDTH, HEIGHT, 0, { fill: colors.board })}
  ${text(120, 120, 'Sketch2FloorPlan', { size: 64, weight: 900 })}
  ${text(120, 166, 'Mobile UI showcase for an AI-powered floor plan conversion app', { size: 24, weight: 600, fill: colors.muted })}
  ${text(120, 206, 'Minimal engineering-style interface • white background • blue and gray accents • presentation-ready', { size: 20, weight: 500, fill: colors.lightText })}

  <g filter="url(#shadowCard)">
    ${homeScreen(120, 240, 390, 844)}
    ${uploadScreen(555, 240, 390, 844)}
    ${processingScreen(990, 240, 390, 844)}
    ${outputScreen(1425, 240, 390, 844)}
    ${historyScreen(1860, 240, 390, 844)}
  </g>

  ${text(120, 1168, 'Home', { size: 18, weight: 800, fill: colors.muted })}
  ${text(555, 1168, 'Upload / Capture', { size: 18, weight: 800, fill: colors.muted })}
  ${text(990, 1168, 'Processing', { size: 18, weight: 800, fill: colors.muted })}
  ${text(1425, 1168, 'Output', { size: 18, weight: 800, fill: colors.muted })}
  ${text(1860, 1168, 'History', { size: 18, weight: 800, fill: colors.muted })}
</svg>
`;

fs.mkdirSync(root, { recursive: true });
fs.writeFileSync(outSvg, board, 'utf8');
console.log(`Wrote ${outSvg}`);
