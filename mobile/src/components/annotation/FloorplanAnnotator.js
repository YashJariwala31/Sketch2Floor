import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, Image, Modal, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import Svg, { Circle, G, Line, Path, Rect, Text as SvgText } from 'react-native-svg';
import {
  LongPressGestureHandler,
  PanGestureHandler,
  PinchGestureHandler,
  State,
  TapGestureHandler,
} from 'react-native-gesture-handler';

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function dist(a, b) {
  const dx = (a?.x ?? 0) - (b?.x ?? 0);
  const dy = (a?.y ?? 0) - (b?.y ?? 0);
  return Math.sqrt(dx * dx + dy * dy);
}

function midpoint(a, b) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

function unitNormal(a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  // Perpendicular vector
  return { x: -dy / len, y: dx / len };
}

function arrowHeadPath(end, direction, size = 10, spread = 0.55) {
  // direction: normalized vector pointing ALONG the dimension line (from start->end)
  const dx = direction.x;
  const dy = direction.y;
  const bx = end.x - dx * size;
  const by = end.y - dy * size;

  // perpendicular
  const px = -dy;
  const py = dx;

  const l1x = bx + px * size * spread;
  const l1y = by + py * size * spread;
  const l2x = bx - px * size * spread;
  const l2y = by - py * size * spread;

  return `M ${end.x} ${end.y} L ${l1x} ${l1y} L ${l2x} ${l2y} Z`;
}

function defaultMeasurementText(measurement, pixelsPerUnit = 1) {
  if (!measurement?.p1 || !measurement?.p2) return '';
  const value = dist(measurement.p1, measurement.p2) / (pixelsPerUnit || 1);
  return value.toFixed(2);
}

function makeLinearMeasurement(p1, p2) {
  const id = `${Date.now()}_${Math.random().toString(16).slice(2)}`;
  const normal = unitNormal(p1, p2);
  const offset = 18; // image-space px
  const mid = midpoint(p1, p2);
  const label = { x: mid.x + normal.x * (offset + 10), y: mid.y + normal.y * (offset + 10) };

  return {
    id,
    type: 'linear',
    p1,
    p2,
    offset,
    label,
    textOverride: '',
    createdAt: new Date().toISOString(),
  };
}

function hitTestMeasurement(measurement, point, thresholdPx = 18) {
  if (!measurement) return null;
  const p1 = measurement.p1;
  const p2 = measurement.p2;
  const label = measurement.label;

  if (dist(point, p1) <= thresholdPx) return { part: 'p1' };
  if (dist(point, p2) <= thresholdPx) return { part: 'p2' };
  if (label && dist(point, label) <= thresholdPx * 1.1) return { part: 'label' };

  // Distance-to-segment for selecting line
  const ax = p1.x;
  const ay = p1.y;
  const bx = p2.x;
  const by = p2.y;
  const px = point.x;
  const py = point.y;
  const vx = bx - ax;
  const vy = by - ay;
  const denom = vx * vx + vy * vy;
  const t = denom > 1e-6 ? clamp(((px - ax) * vx + (py - ay) * vy) / denom, 0, 1) : 0;
  const projx = ax + t * vx;
  const projy = ay + t * vy;
  const d = Math.hypot(px - projx, py - projy);
  if (d <= thresholdPx) return { part: 'line' };

  return null;
}

function LabelEditModal({ visible, initialValue, onCancel, onSave, theme }) {
  const [value, setValue] = useState(initialValue || '');

  useEffect(() => {
    if (visible) setValue(initialValue || '');
  }, [visible, initialValue]);

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={styles(theme).modalBackdrop}>
        <View style={styles(theme).modalCard}>
          <Text style={styles(theme).modalTitle}>Edit measurement</Text>
          <Text style={styles(theme).modalHint}>Example: 5.00, 2.50, Ø1.00</Text>
          <TextInput
            value={value}
            onChangeText={setValue}
            placeholder="5.00"
            placeholderTextColor={theme.colors.softText}
            autoCapitalize="none"
            autoCorrect={false}
            style={styles(theme).modalInput}
          />
          <View style={styles(theme).modalRow}>
            <Pressable style={[styles(theme).pillButton, styles(theme).pillSecondary]} onPress={onCancel}>
              <Text style={styles(theme).pillSecondaryText}>Cancel</Text>
            </Pressable>
            <Pressable style={[styles(theme).pillButton, styles(theme).pillPrimary]} onPress={() => onSave(value)}>
              <Text style={styles(theme).pillPrimaryText}>Save</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

export default function FloorplanAnnotator({
  imageUri,
  theme,
  annotations,
  onChangeAnnotations,
  measurementMode,
  onRequestToggleMeasurementMode,
  onRequestUndo,
  onRequestDeleteSelected,
  onRequestSave,
  busy,
  pixelsPerUnit = 1,
}) {
  const s = useMemo(() => styles(theme), [theme]);

  const [layout, setLayout] = useState({ w: 1, h: 1 });
  const [naturalSize, setNaturalSize] = useState(null);
  const [pendingStartPoint, setPendingStartPoint] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [editModal, setEditModal] = useState({ open: false, id: null });

  // Zoom/pan state (JS-driven, stable in Expo)
  const scale = useRef(1);
  const lastScale = useRef(1);
  const translate = useRef({ x: 0, y: 0 });
  const lastTranslate = useRef({ x: 0, y: 0 });

  const animatedScale = useRef(new Animated.Value(1)).current;
  const animatedTranslateX = useRef(new Animated.Value(0)).current;
  const animatedTranslateY = useRef(new Animated.Value(0)).current;

  const activeDrag = useRef(null); // { id, part, startPointImage, startMeasurement, startTranslate }

  useEffect(() => {
    if (!imageUri) return;
    Image.getSize(
      imageUri,
      (w, h) => setNaturalSize({ w, h }),
      () => setNaturalSize(null)
    );
  }, [imageUri]);

  const fitted = useMemo(() => {
    const containerW = layout.w || 1;
    const containerH = layout.h || 1;
    const imgW = naturalSize?.w || containerW;
    const imgH = naturalSize?.h || containerH;
    const fit = Math.min(containerW / imgW, containerH / imgH);
    const w = imgW * fit;
    const h = imgH * fit;
    const x = (containerW - w) / 2;
    const y = (containerH - h) / 2;
    return { x, y, w, h };
  }, [layout, naturalSize]);

  function screenToImagePoint(evt) {
    const { x, y } = evt.nativeEvent;
    // Convert screen point into image-space point (relative to fitted image top-left)
    const localX = x - fitted.x;
    const localY = y - fitted.y;
    const tx = translate.current.x;
    const ty = translate.current.y;
    const sc = scale.current || 1;
    const imgX = (localX - tx) / sc;
    const imgY = (localY - ty) / sc;
    return { x: imgX, y: imgY };
  }

  function applyTransform(nextTranslate, nextScale) {
    translate.current = nextTranslate;
    scale.current = nextScale;
    animatedTranslateX.setValue(nextTranslate.x);
    animatedTranslateY.setValue(nextTranslate.y);
    animatedScale.setValue(nextScale);
  }

  function resetPendingIfNeeded() {
    if (!measurementMode) {
      setPendingStartPoint(null);
    }
  }

  useEffect(() => resetPendingIfNeeded(), [measurementMode]);

  function updateMeasurement(id, partial) {
    const next = (annotations || []).map((m) => (m.id === id ? { ...m, ...partial } : m));
    onChangeAnnotations(next);
  }

  function addMeasurement(measurement) {
    const next = [...(annotations || []), measurement];
    onChangeAnnotations(next);
    setSelectedId(measurement.id);
  }

  function handleTap(evt) {
    if (!measurementMode) return;

    const point = screenToImagePoint(evt);
    if (point.x < 0 || point.y < 0 || point.x > fitted.w || point.y > fitted.h) return;

    // If tapping on an existing measurement, just select it.
    const hit = (annotations || [])
      .map((m) => ({ m, hit: hitTestMeasurement(m, point) }))
      .find((item) => item.hit);
    if (hit) {
      setSelectedId(hit.m.id);
      setPendingStartPoint(null);
      return;
    }

    if (!pendingStartPoint) {
      setPendingStartPoint(point);
      setSelectedId(null);
      return;
    }

    if (dist(pendingStartPoint, point) < 6) {
      // Ignore ultra-short measurements.
      setPendingStartPoint(null);
      return;
    }

    addMeasurement(makeLinearMeasurement(pendingStartPoint, point));
    setPendingStartPoint(null);
  }

  function handleLongPress(evt) {
    if (!measurementMode) return;
    const point = screenToImagePoint(evt);
    const hit = (annotations || [])
      .map((m) => ({ m, hit: hitTestMeasurement(m, point) }))
      .find((item) => item.hit);
    if (!hit) return;
    setSelectedId(hit.m.id);
    setEditModal({ open: true, id: hit.m.id });
  }

  function onPanStateChange(evt) {
    const { state } = evt.nativeEvent;
    if (state === State.BEGAN) {
      const startPoint = screenToImagePoint(evt);
      const candidates = (annotations || [])
        .map((m) => ({ m, hit: hitTestMeasurement(m, startPoint) }))
        .filter((x) => Boolean(x.hit));

      if (measurementMode && candidates.length > 0) {
        const target = candidates[0];
        activeDrag.current = {
          id: target.m.id,
          part: target.hit.part,
          startPointImage: startPoint,
          startMeasurement: target.m,
        };
        setSelectedId(target.m.id);
        return;
      }

      activeDrag.current = {
        id: null,
        part: 'pan',
        startPointImage: startPoint,
        startTranslate: { ...translate.current },
      };
      setSelectedId((prev) => prev);
      return;
    }

    if (state === State.END || state === State.CANCELLED || state === State.FAILED) {
      lastTranslate.current = { ...translate.current };
      lastScale.current = scale.current;
      activeDrag.current = null;
    }
  }

  function onPanGestureEvent(evt) {
    const { translationX, translationY } = evt.nativeEvent;
    const drag = activeDrag.current;

    if (drag?.part === 'pan') {
      const startT = drag.startTranslate || lastTranslate.current;
      const nextT = { x: startT.x + translationX, y: startT.y + translationY };
      applyTransform(nextT, scale.current);
      return;
    }

    if (drag?.id && (drag.part === 'p1' || drag.part === 'p2' || drag.part === 'label')) {
      const sc = scale.current || 1;
      const dx = translationX / sc;
      const dy = translationY / sc;
      const base = drag.startMeasurement;
      if (!base) return;

      if (drag.part === 'p1') {
        updateMeasurement(drag.id, { p1: { x: base.p1.x + dx, y: base.p1.y + dy } });
      } else if (drag.part === 'p2') {
        updateMeasurement(drag.id, { p2: { x: base.p2.x + dx, y: base.p2.y + dy } });
      } else if (drag.part === 'label') {
        updateMeasurement(drag.id, { label: { x: base.label.x + dx, y: base.label.y + dy } });
      }
    }
  }

  function onPinchStateChange(evt) {
    const { state } = evt.nativeEvent;
    if (state === State.END || state === State.CANCELLED || state === State.FAILED) {
      lastScale.current = scale.current;
    }
  }

  function onPinchGestureEvent(evt) {
    // scale factor is relative to start of gesture
    const next = clamp(lastScale.current * (evt.nativeEvent.scale || 1), 0.6, 6);
    applyTransform(translate.current, next);
  }

  const renderedMeasurements = useMemo(() => {
    const list = Array.isArray(annotations) ? annotations : [];
    return list.filter((m) => m && m.type === 'linear' && m.p1 && m.p2);
  }, [annotations]);

  function renderMeasurement(m) {
    const p1 = m.p1;
    const p2 = m.p2;
    const normal = unitNormal(p1, p2);
    const offset = typeof m.offset === 'number' ? m.offset : 18;

    const d1 = { x: p1.x + normal.x * offset, y: p1.y + normal.y * offset };
    const d2 = { x: p2.x + normal.x * offset, y: p2.y + normal.y * offset };

    const dx = d2.x - d1.x;
    const dy = d2.y - d1.y;
    const len = Math.sqrt(dx * dx + dy * dy) || 1;
    const dir = { x: dx / len, y: dy / len };

    const isSelected = selectedId === m.id;
    const stroke = isSelected ? theme.colors.accent : '#111111';
    const helper = isSelected ? theme.colors.accentSoft : 'transparent';

    const label = m.label || midpoint(d1, d2);
    const text = (m.textOverride || '').trim() || defaultMeasurementText(m, pixelsPerUnit);

    return (
      <G key={m.id}>
        {/* selection halo */}
        <Line x1={d1.x} y1={d1.y} x2={d2.x} y2={d2.y} stroke={helper} strokeWidth={12} strokeLinecap="round" />

        {/* extension lines */}
        <Line x1={p1.x} y1={p1.y} x2={d1.x} y2={d1.y} stroke={stroke} strokeWidth={2} />
        <Line x1={p2.x} y1={p2.y} x2={d2.x} y2={d2.y} stroke={stroke} strokeWidth={2} />

        {/* dimension line */}
        <Line x1={d1.x} y1={d1.y} x2={d2.x} y2={d2.y} stroke={stroke} strokeWidth={2.2} />

        {/* arrowheads */}
        <Path d={arrowHeadPath(d1, { x: -dir.x, y: -dir.y }, 10)} fill={stroke} />
        <Path d={arrowHeadPath(d2, dir, 10)} fill={stroke} />

        {/* endpoint handles */}
        <Circle cx={p1.x} cy={p1.y} r={6} fill={theme.colors.surface} stroke={stroke} strokeWidth={2} />
        <Circle cx={p2.x} cy={p2.y} r={6} fill={theme.colors.surface} stroke={stroke} strokeWidth={2} />

        {/* label handle */}
        <Circle cx={label.x} cy={label.y} r={7} fill={theme.colors.surface} stroke={stroke} strokeWidth={2} />

        {/* label text */}
        <SvgText
          x={label.x}
          y={label.y - 12}
          fill={stroke}
          fontSize={16}
          fontWeight="700"
          textAnchor="middle"
          alignmentBaseline="central"
        >
          {text}
        </SvgText>
      </G>
    );
  }

  const selectedMeasurement = renderedMeasurements.find((m) => m.id === selectedId) || null;

  return (
    <View style={s.root} onLayout={(e) => setLayout({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })}>
      {/* Toolbar */}
      <View style={s.toolbar}>
        <Pressable style={[s.pillButton, measurementMode ? s.pillPrimary : s.pillSecondary]} onPress={onRequestToggleMeasurementMode}>
          <Text style={measurementMode ? s.pillPrimaryText : s.pillSecondaryText}>{measurementMode ? 'Measuring' : 'Measure'}</Text>
        </Pressable>
        <Pressable style={[s.pillButton, s.pillSecondary]} onPress={onRequestUndo}>
          <Text style={s.pillSecondaryText}>Undo</Text>
        </Pressable>
        <Pressable
          style={[s.pillButton, s.pillSecondary]}
          onPress={() => onRequestDeleteSelected?.(selectedMeasurement?.id || null)}
          disabled={!selectedMeasurement}
        >
          <Text style={[s.pillSecondaryText, !selectedMeasurement ? { opacity: 0.35 } : null]}>Delete</Text>
        </Pressable>
        <Pressable style={[s.pillButton, s.pillPrimary]} onPress={onRequestSave} disabled={busy}>
          <Text style={[s.pillPrimaryText, busy ? { opacity: 0.7 } : null]}>{busy ? 'Saving…' : 'Save'}</Text>
        </Pressable>
      </View>

      {/* hint */}
      {measurementMode ? (
        <Text style={s.hint}>
          Tap two points to add a dimension. Drag endpoints/label to adjust. Long-press a label to edit text.
        </Text>
      ) : (
        <Text style={s.hint}>Pinch to zoom, drag to pan.</Text>
      )}

      <View style={s.canvas}>
        <PinchGestureHandler onGestureEvent={onPinchGestureEvent} onHandlerStateChange={onPinchStateChange}>
          <Animated.View style={StyleSheet.absoluteFill}>
            <PanGestureHandler onGestureEvent={onPanGestureEvent} onHandlerStateChange={onPanStateChange} minDist={3}>
              <Animated.View style={StyleSheet.absoluteFill}>
                <LongPressGestureHandler
                  minDurationMs={420}
                  onHandlerStateChange={(e) => {
                    if (e.nativeEvent.state === State.ACTIVE) handleLongPress(e);
                  }}
                >
                  <Animated.View style={StyleSheet.absoluteFill}>
                    <TapGestureHandler
                      maxDist={12}
                      onHandlerStateChange={(e) => {
                        if (e.nativeEvent.state === State.END) handleTap(e);
                      }}
                    >
                      <Animated.View style={StyleSheet.absoluteFill}>
                        {/* Content layer (image + SVG) */}
                        <Animated.View
                          style={[
                            {
                              position: 'absolute',
                              left: fitted.x,
                              top: fitted.y,
                              width: fitted.w,
                              height: fitted.h,
                              transform: [{ translateX: animatedTranslateX }, { translateY: animatedTranslateY }, { scale: animatedScale }],
                            },
                          ]}
                        >
                          <View style={{ width: fitted.w, height: fitted.h, backgroundColor: theme.colors.surface }}>
                            {imageUri ? <Image source={{ uri: imageUri }} style={{ width: fitted.w, height: fitted.h }} resizeMode="stretch" /> : null}
                            <Svg width={fitted.w} height={fitted.h} style={StyleSheet.absoluteFill}>
                              <Rect x={0} y={0} width={fitted.w} height={fitted.h} fill="transparent" />
                              {renderedMeasurements.map(renderMeasurement)}

                              {/* pending measurement preview */}
                              {measurementMode && pendingStartPoint ? (
                                <G>
                                  <Circle cx={pendingStartPoint.x} cy={pendingStartPoint.y} r={6} fill={theme.colors.accent} />
                                </G>
                              ) : null}
                            </Svg>
                          </View>
                        </Animated.View>
                      </Animated.View>
                    </TapGestureHandler>
                  </Animated.View>
                </LongPressGestureHandler>
              </Animated.View>
            </PanGestureHandler>
          </Animated.View>
        </PinchGestureHandler>
      </View>

      <LabelEditModal
        visible={editModal.open}
        initialValue={selectedMeasurement?.textOverride || ''}
        onCancel={() => setEditModal({ open: false, id: null })}
        onSave={(value) => {
          if (editModal.id) updateMeasurement(editModal.id, { textOverride: value });
          setEditModal({ open: false, id: null });
        }}
        theme={theme}
      />
    </View>
  );
}

function styles(theme) {
  return StyleSheet.create({
    root: {
      flex: 1,
    },
    toolbar: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: 10,
      marginBottom: 10,
    },
    hint: {
      color: theme.colors.muted,
      fontWeight: '600',
      marginBottom: 10,
    },
    canvas: {
      flex: 1,
      borderRadius: theme.radius.xl,
      backgroundColor: theme.colors.heroTint,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
      overflow: 'hidden',
    },
    pillButton: {
      minHeight: 40,
      borderRadius: 999,
      paddingHorizontal: 14,
      alignItems: 'center',
      justifyContent: 'center',
      borderWidth: 1,
    },
    pillPrimary: {
      backgroundColor: theme.colors.accent,
      borderColor: theme.colors.accent,
    },
    pillPrimaryText: {
      color: '#ffffff',
      fontWeight: '800',
    },
    pillSecondary: {
      backgroundColor: theme.colors.surface,
      borderColor: theme.colors.border,
    },
    pillSecondaryText: {
      color: theme.colors.text,
      fontWeight: '800',
    },

    modalBackdrop: {
      flex: 1,
      backgroundColor: 'rgba(0,0,0,0.45)',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 18,
    },
    modalCard: {
      width: '100%',
      maxWidth: 440,
      backgroundColor: theme.colors.surface,
      borderRadius: 20,
      borderWidth: 1,
      borderColor: theme.colors.border,
      padding: 16,
    },
    modalTitle: {
      fontSize: 18,
      fontWeight: '900',
      color: theme.colors.text,
      marginBottom: 6,
    },
    modalHint: {
      color: theme.colors.muted,
      fontWeight: '600',
      marginBottom: 12,
    },
    modalInput: {
      borderWidth: 1,
      borderColor: theme.colors.border,
      borderRadius: 14,
      paddingHorizontal: 12,
      paddingVertical: 10,
      color: theme.colors.text,
      fontWeight: '700',
      marginBottom: 12,
    },
    modalRow: {
      flexDirection: 'row',
      justifyContent: 'flex-end',
      gap: 10,
    },
  });
}
