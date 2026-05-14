import React, { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import { Animated, Image, Modal, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import Svg, { Circle, G, Line, Path, Rect, Text as SvgText } from 'react-native-svg';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import ViewShot from 'react-native-view-shot';

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

function intelligentNormal(p1, p2, center) {
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const nx = -dy / len;
  const ny = dx / len;

  const mid = midpoint(p1, p2);
  const toMidX = mid.x - center.x;
  const toMidY = mid.y - center.y;

  if (nx * toMidX + ny * toMidY < 0) {
    return { x: -nx, y: -ny };
  }
  return { x: nx, y: ny };
}

function architecturalTickPath(point, dir, size = 6) {
  const cos45 = Math.cos(Math.PI / 4);
  const sin45 = Math.sin(Math.PI / 4);
  const tx = dir.x * cos45 - dir.y * sin45;
  const ty = dir.x * sin45 + dir.y * cos45;

  const x1 = point.x + tx * size;
  const y1 = point.y + ty * size;
  const x2 = point.x - tx * size;
  const y2 = point.y - ty * size;

  return `M ${x1} ${y1} L ${x2} ${y2}`;
}

function distanceToSegment(point, start, end) {
  const vx = end.x - start.x;
  const vy = end.y - start.y;
  const denom = vx * vx + vy * vy;
  const t = denom > 1e-6 ? clamp(((point.x - start.x) * vx + (point.y - start.y) * vy) / denom, 0, 1) : 0;
  const projx = start.x + t * vx;
  const projy = start.y + t * vy;
  return Math.hypot(point.x - projx, point.y - projy);
}

function defaultMeasurementText(measurement, pixelsPerUnit = 1) {
  if (!measurement?.p1 || !measurement?.p2) return '';
  const value = dist(measurement.p1, measurement.p2) / (pixelsPerUnit || 1);
  return value.toFixed(2);
}

function makeLinearMeasurement(p1, p2) {
  return {
    id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
    type: 'linear',
    p1,
    p2,
    textOverride: '',
    createdAt: new Date().toISOString(),
  };
}

function hitTestMeasurement(measurement, point, center, thresholdPx = 18) {
  if (!measurement) return null;
  const p1 = measurement.p1;
  const p2 = measurement.p2;

  if (dist(point, p1) <= thresholdPx) return { part: 'p1' };
  if (dist(point, p2) <= thresholdPx) return { part: 'p2' };

  const normal = intelligentNormal(p1, p2, center);
  const offset = 36;
  const d1 = { x: p1.x + normal.x * offset, y: p1.y + normal.y * offset };
  const d2 = { x: p2.x + normal.x * offset, y: p2.y + normal.y * offset };

  if (distanceToSegment(point, d1, d2) <= thresholdPx) return { part: 'line' };
  if (distanceToSegment(point, p1, p2) <= thresholdPx) return { part: 'line' };

  return null;
}

function scaleMeasurement(measurement, scaleFactor) {
  return {
    ...measurement,
    p1: measurement?.p1
      ? { x: measurement.p1.x * scaleFactor, y: measurement.p1.y * scaleFactor }
      : measurement?.p1,
    p2: measurement?.p2
      ? { x: measurement.p2.x * scaleFactor, y: measurement.p2.y * scaleFactor }
      : measurement?.p2,
  };
}

function LabelEditModal({ visible, initialValue, onCancel, onSave, theme }) {
  const [value, setValue] = useState(initialValue || '');
  const s = useMemo(() => styles(theme), [theme]);

  useEffect(() => {
    if (visible) {
      setValue(initialValue || '');
    }
  }, [visible, initialValue]);

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={s.modalBackdrop}>
        <View style={s.modalCard}>
          <Text style={s.modalTitle}>Edit measurement</Text>
          <Text style={s.modalHint}>Enter a custom label like 5.00 or 2.50.</Text>
          <TextInput
            value={value}
            onChangeText={setValue}
            placeholder="5.00"
            placeholderTextColor={theme.colors.softText}
            autoCapitalize="none"
            autoCorrect={false}
            style={s.modalInput}
          />
          <View style={s.modalRow}>
            <Pressable style={[s.pillButton, s.pillSecondary]} onPress={onCancel}>
              <Text style={s.pillSecondaryText}>Cancel</Text>
            </Pressable>
            <Pressable style={[s.pillButton, s.pillPrimary]} onPress={() => onSave(value)}>
              <Text style={s.pillPrimaryText}>Save</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function EditorToolbar({
  measurementMode,
  onRequestToggleMeasurementMode,
  onRequestUndo,
  onRequestDeleteSelected,
  onRequestEditSelected,
  onRequestSave,
  busy,
  selectedMeasurement,
  theme,
}) {
  const s = useMemo(() => styles(theme), [theme]);
  const statusText = measurementMode
    ? selectedMeasurement
      ? 'Drag to adjust the selected measurement.'
      : ''
    : 'Preview mode.';

  return (
    <View style={s.toolbarCard}>
      <View style={s.toolbarRow}>
        <Pressable style={[s.pillButton, measurementMode ? s.pillPrimary : s.pillSecondary]} onPress={onRequestToggleMeasurementMode}>
          <Text style={measurementMode ? s.pillPrimaryText : s.pillSecondaryText}>{measurementMode ? 'Measure On' : 'Measure'}</Text>
        </Pressable>
        <Pressable style={[s.pillButton, s.pillSecondary]} onPress={onRequestUndo}>
          <Text style={s.pillSecondaryText}>Undo</Text>
        </Pressable>
        {selectedMeasurement ? (
          <>
            <Pressable style={[s.pillButton, s.pillSecondary]} onPress={onRequestEditSelected}>
              <Text style={s.pillSecondaryText}>Label</Text>
            </Pressable>
            <Pressable style={[s.pillButton, s.pillSecondary]} onPress={() => onRequestDeleteSelected?.(selectedMeasurement?.id || null)}>
              <Text style={s.pillSecondaryText}>Delete</Text>
            </Pressable>
          </>
        ) : null}
        <Pressable style={[s.pillButton, s.pillPrimary]} onPress={onRequestSave} disabled={busy}>
          <Text style={[s.pillPrimaryText, busy ? s.disabledPrimaryText : null]}>{busy ? 'Saving...' : 'Save'}</Text>
        </Pressable>
      </View>

      <Text style={s.toolbarHint}>{statusText}</Text>
    </View>
  );
}

const FloorplanAnnotator = forwardRef(function FloorplanAnnotator({
  imageUri,
  theme,
  annotations,
  onChangeAnnotations,
  measurementMode,
  onRequestToggleMeasurementMode,
  onRequestUndo,
  onRequestDeleteSelected,
  onRequestSave,
  onRequestHistoryCheckpoint,
  busy,
  pixelsPerUnit = 1,
}, ref) {
  const s = useMemo(() => styles(theme), [theme]);
  const [layout, setLayout] = useState({ w: 1, h: 1 });
  const [naturalSize, setNaturalSize] = useState(null);
  const [pendingStartPoint, setPendingStartPoint] = useState(null);
  const [pendingCurrentPoint, setPendingCurrentPoint] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [editModal, setEditModal] = useState({ open: false, id: null });

  const scale = useRef(1);
  const lastScale = useRef(1);
  const translate = useRef({ x: 0, y: 0 });
  const lastTranslate = useRef({ x: 0, y: 0 });
  const activeDrag = useRef(null);

  const animatedScale = useRef(new Animated.Value(1)).current;
  const animatedTranslateX = useRef(new Animated.Value(0)).current;
  const animatedTranslateY = useRef(new Animated.Value(0)).current;
  const exportShotRef = useRef(null);

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

  const exportScale = useMemo(() => {
    if (!fitted.w || !naturalSize?.w) {
      return 1;
    }
    return naturalSize.w / fitted.w;
  }, [fitted.w, naturalSize?.w]);

  useImperativeHandle(
    ref,
    () => ({
      async captureAnnotatedImage() {
        if (!exportShotRef.current?.capture) {
          throw new Error('Preview is not ready to export yet.');
        }
        await new Promise((resolve) => setTimeout(resolve, 80));
        return exportShotRef.current.capture();
      },
    }),
    []
  );

  function screenToImagePoint(evtX, evtY) {
    const localX = evtX - fitted.x;
    const localY = evtY - fitted.y;
    const tx = translate.current.x;
    const ty = translate.current.y;
    const sc = scale.current || 1;
    return { x: (localX - tx) / sc, y: (localY - ty) / sc };
  }

  function applyTransform(nextTranslate, nextScale) {
    translate.current = nextTranslate;
    scale.current = nextScale;
    animatedTranslateX.setValue(nextTranslate.x);
    animatedTranslateY.setValue(nextTranslate.y);
    animatedScale.setValue(nextScale);
  }

  useEffect(() => {
    if (!measurementMode) {
      setPendingStartPoint(null);
      setPendingCurrentPoint(null);
    }
  }, [measurementMode]);

  useEffect(() => {
    if (selectedId && !(annotations || []).some((item) => item?.id === selectedId)) {
      setSelectedId(null);
    }
  }, [annotations, selectedId]);

  function updateMeasurement(id, partial, options = {}) {
    const next = (annotations || []).map((item) => (item.id === id ? { ...item, ...partial } : item));
    onChangeAnnotations(next, options);
  }

  function addMeasurement(measurement) {
    const next = [...(annotations || []), measurement];
    onChangeAnnotations(next, { trackHistory: true });
    setSelectedId(measurement.id);
  }

  const tap = useMemo(() => {
    return Gesture.Tap()
      .maxDistance(12)
      .runOnJS(true)
      .onEnd((event) => {
        if (!measurementMode) return;
        const point = screenToImagePoint(event.x, event.y);
        const center = { x: fitted.w / 2, y: fitted.h / 2 };
        const hit = (annotations || [])
          .map((item) => ({ item, hit: hitTestMeasurement(item, point, center) }))
          .find((candidate) => candidate.hit);

        if (hit) {
          setSelectedId(hit.item.id);
          setPendingStartPoint(null);
          setPendingCurrentPoint(null);
          return;
        }

        if (!pendingStartPoint) {
          setPendingStartPoint(point);
          setSelectedId(null);
          return;
        }

        if (dist(pendingStartPoint, point) > 6) {
          addMeasurement(makeLinearMeasurement(pendingStartPoint, point));
        }

        setPendingStartPoint(null);
        setPendingCurrentPoint(null);
      });
  }, [measurementMode, annotations, pendingStartPoint, fitted]);

  const longPress = useMemo(() => {
    return Gesture.LongPress()
      .minDuration(420)
      .runOnJS(true)
      .onStart((event) => {
        if (!measurementMode) return;
        const point = screenToImagePoint(event.x, event.y);
        const center = { x: fitted.w / 2, y: fitted.h / 2 };
        const hit = (annotations || [])
          .map((item) => ({ item, hit: hitTestMeasurement(item, point, center) }))
          .find((candidate) => candidate.hit);
        if (hit) {
          setSelectedId(hit.item.id);
          setEditModal({ open: true, id: hit.item.id });
        }
      });
  }, [measurementMode, annotations, fitted]);

  const pan = useMemo(() => {
    return Gesture.Pan()
      .minDistance(3)
      .maxPointers(1)
      .runOnJS(true)
      .onStart((event) => {
        const startPoint = screenToImagePoint(event.x, event.y);

        if (measurementMode) {
          const center = { x: fitted.w / 2, y: fitted.h / 2 };
          const hit = (annotations || [])
            .map((item) => ({ item, hit: hitTestMeasurement(item, startPoint, center) }))
            .find((candidate) => candidate.hit);

          if (hit) {
            onRequestHistoryCheckpoint?.(annotations || []);
            activeDrag.current = {
              id: hit.item.id,
              part: hit.hit.part,
              startMeasurement: {
                ...hit.item,
                p1: { ...hit.item.p1 },
                p2: { ...hit.item.p2 },
              },
            };
            setSelectedId(hit.item.id);
            return;
          }

          if (pendingStartPoint) {
            activeDrag.current = { part: 'draw_preview' };
            setPendingCurrentPoint(startPoint);
            return;
          }
        }

        activeDrag.current = {
          part: 'pan',
          startTranslate: { ...translate.current },
        };
      })
      .onUpdate((event) => {
        const drag = activeDrag.current;
        if (!drag) return;

        if (drag.part === 'pan') {
          const startTranslate = drag.startTranslate || lastTranslate.current;
          applyTransform(
            { x: startTranslate.x + event.translationX, y: startTranslate.y + event.translationY },
            scale.current
          );
          return;
        }

        if (drag.part === 'draw_preview') {
          setPendingCurrentPoint(screenToImagePoint(event.x, event.y));
          return;
        }

        if (drag.id && drag.startMeasurement) {
          const sc = scale.current || 1;
          const dx = event.translationX / sc;
          const dy = event.translationY / sc;
          const base = drag.startMeasurement;

          if (drag.part === 'p1') {
            updateMeasurement(drag.id, { p1: { x: base.p1.x + dx, y: base.p1.y + dy } }, { trackHistory: false });
          } else if (drag.part === 'p2') {
            updateMeasurement(drag.id, { p2: { x: base.p2.x + dx, y: base.p2.y + dy } }, { trackHistory: false });
          } else if (drag.part === 'line') {
            updateMeasurement(
              drag.id,
              {
                p1: { x: base.p1.x + dx, y: base.p1.y + dy },
                p2: { x: base.p2.x + dx, y: base.p2.y + dy },
              },
              { trackHistory: false }
            );
          }
        }
      })
      .onEnd((event) => {
        const drag = activeDrag.current;
        if (drag?.part === 'pan') {
          lastTranslate.current = { ...translate.current };
        } else if (drag?.part === 'draw_preview') {
          const endPoint = screenToImagePoint(event.x, event.y);
          if (pendingStartPoint && dist(pendingStartPoint, endPoint) > 6) {
            addMeasurement(makeLinearMeasurement(pendingStartPoint, endPoint));
          }
          setPendingStartPoint(null);
          setPendingCurrentPoint(null);
        }
        activeDrag.current = null;
      });
  }, [measurementMode, annotations, pendingStartPoint, fitted]);

  const pinch = useMemo(() => {
    return Gesture.Pinch()
      .runOnJS(true)
      .onUpdate((event) => {
        const nextScale = clamp(lastScale.current * event.scale, 0.6, 6);
        applyTransform(translate.current, nextScale);
      })
      .onEnd(() => {
        lastScale.current = scale.current;
      });
  }, []);

  const composedGesture = useMemo(() => {
    const canvasInteraction = Gesture.Simultaneous(pan, pinch);
    return Gesture.Exclusive(canvasInteraction, tap, longPress);
  }, [pan, pinch, tap, longPress]);

  const renderedMeasurements = useMemo(() => {
    const list = Array.isArray(annotations) ? annotations : [];
    return list.filter((item) => item && item.type === 'linear' && item.p1 && item.p2);
  }, [annotations]);

  const exportMeasurements = useMemo(
    () => renderedMeasurements.map((measurement) => scaleMeasurement(measurement, exportScale)),
    [renderedMeasurements, exportScale]
  );

  function renderMeasurement(measurement, renderWidth = fitted.w, renderHeight = fitted.h, isExport = false) {
    const p1 = measurement.p1;
    const p2 = measurement.p2;
    const center = { x: renderWidth / 2, y: renderHeight / 2 };
    const normal = intelligentNormal(p1, p2, center);
    const offset = 36;
    const d1 = { x: p1.x + normal.x * offset, y: p1.y + normal.y * offset };
    const d2 = { x: p2.x + normal.x * offset, y: p2.y + normal.y * offset };

    const dx = d2.x - d1.x;
    const dy = d2.y - d1.y;
    const len = Math.sqrt(dx * dx + dy * dy) || 1;
    const dir = { x: dx / len, y: dy / len };

    const extGap = 6;
    const extOvershoot = 8;
    const e1Start = { x: p1.x + normal.x * extGap, y: p1.y + normal.y * extGap };
    const e1End = { x: d1.x + normal.x * extOvershoot, y: d1.y + normal.y * extOvershoot };
    const e2Start = { x: p2.x + normal.x * extGap, y: p2.y + normal.y * extGap };
    const e2End = { x: d2.x + normal.x * extOvershoot, y: d2.y + normal.y * extOvershoot };

    const isSelected = !isExport && selectedId === measurement.id;
    const stroke = isSelected ? theme.colors.accent : theme.colors.text;
    const helper = isSelected ? theme.colors.accentSoft : 'transparent';
    const strokeWidth = 1.5;
    const mid = midpoint(d1, d2);
    const text = (measurement.textOverride || '').trim() || defaultMeasurementText(measurement, pixelsPerUnit);

    let angle = Math.atan2(dy, dx) * (180 / Math.PI);
    if (angle > 90 || angle < -90) {
      angle += 180;
    }

    const textWidth = text.length * 9 + 14;
    const textHeight = 22;

    return (
      <G key={measurement.id}>
        <Line x1={d1.x} y1={d1.y} x2={d2.x} y2={d2.y} stroke={helper} strokeWidth={16} strokeLinecap="round" />
        <Line x1={e1Start.x} y1={e1Start.y} x2={e1End.x} y2={e1End.y} stroke={stroke} strokeWidth={strokeWidth} opacity={0.6} />
        <Line x1={e2Start.x} y1={e2Start.y} x2={e2End.x} y2={e2End.y} stroke={stroke} strokeWidth={strokeWidth} opacity={0.6} />
        <Line x1={d1.x} y1={d1.y} x2={d2.x} y2={d2.y} stroke={stroke} strokeWidth={strokeWidth} />
        <Path d={architecturalTickPath(d1, dir, 5)} stroke={stroke} strokeWidth={2} strokeLinecap="round" />
        <Path d={architecturalTickPath(d2, dir, 5)} stroke={stroke} strokeWidth={2} strokeLinecap="round" />
        <Circle cx={p1.x} cy={p1.y} r={isSelected ? 6 : 4} fill={theme.colors.surface} stroke={stroke} strokeWidth={isSelected ? 2 : 1.5} />
        <Circle cx={p2.x} cy={p2.y} r={isSelected ? 6 : 4} fill={theme.colors.surface} stroke={stroke} strokeWidth={isSelected ? 2 : 1.5} />
        <Rect
          x={mid.x - textWidth / 2}
          y={mid.y - textHeight / 2}
          width={textWidth}
          height={textHeight}
          rx={5}
          fill={theme.colors.surface}
          transform={`rotate(${angle}, ${mid.x}, ${mid.y})`}
        />
        <SvgText
          x={mid.x}
          y={mid.y + 1}
          fill={stroke}
          fontSize={13}
          fontWeight="700"
          textAnchor="middle"
          alignmentBaseline="central"
          transform={`rotate(${angle}, ${mid.x}, ${mid.y})`}
        >
          {text}
        </SvgText>
      </G>
    );
  }

  const selectedMeasurement = renderedMeasurements.find((item) => item.id === selectedId) || null;

  return (
    <View style={s.root} onLayout={(event) => setLayout({ w: event.nativeEvent.layout.width, h: event.nativeEvent.layout.height })}>
      {imageUri && naturalSize ? (
        <View style={s.exportSurface}>
          <ViewShot ref={exportShotRef} options={{ format: 'png', quality: 1, result: 'tmpfile' }}>
            <View style={{ width: naturalSize.w, height: naturalSize.h, backgroundColor: theme.colors.surface }}>
              <Image source={{ uri: imageUri }} style={{ width: naturalSize.w, height: naturalSize.h }} resizeMode="stretch" />
              <Svg width={naturalSize.w} height={naturalSize.h} style={StyleSheet.absoluteFill}>
                <Rect x={0} y={0} width={naturalSize.w} height={naturalSize.h} fill="transparent" />
                {exportMeasurements.map((measurement) => renderMeasurement(measurement, naturalSize.w, naturalSize.h, true))}
              </Svg>
            </View>
          </ViewShot>
        </View>
      ) : null}

      <EditorToolbar
        measurementMode={measurementMode}
        onRequestToggleMeasurementMode={onRequestToggleMeasurementMode}
        onRequestUndo={onRequestUndo}
        onRequestDeleteSelected={onRequestDeleteSelected}
        onRequestEditSelected={() => selectedMeasurement && setEditModal({ open: true, id: selectedMeasurement.id })}
        onRequestSave={onRequestSave}
        busy={busy}
        selectedMeasurement={selectedMeasurement}
        theme={theme}
      />

      {measurementMode ? (
        <Text style={s.hint}>Tap two points to measure. Drag to adjust. Save before downloading.</Text>
      ) : (
        <Text style={s.hint}>Pinch to zoom and drag to move around the plan.</Text>
      )}

      <View style={s.canvas}>
        <GestureDetector gesture={composedGesture}>
          <Animated.View style={StyleSheet.absoluteFill}>
            <Animated.View
              style={{
                position: 'absolute',
                left: fitted.x,
                top: fitted.y,
                width: fitted.w,
                height: fitted.h,
                transform: [{ translateX: animatedTranslateX }, { translateY: animatedTranslateY }, { scale: animatedScale }],
              }}
            >
              <View style={{ width: fitted.w, height: fitted.h, backgroundColor: theme.colors.surface }}>
                {imageUri ? <Image source={{ uri: imageUri }} style={{ width: fitted.w, height: fitted.h }} resizeMode="stretch" /> : null}
                <Svg width={fitted.w} height={fitted.h} style={StyleSheet.absoluteFill}>
                  <Rect x={0} y={0} width={fitted.w} height={fitted.h} fill="transparent" />
                  {renderedMeasurements.map(renderMeasurement)}

                  {measurementMode && pendingStartPoint ? (
                    <G>
                      <Circle cx={pendingStartPoint.x} cy={pendingStartPoint.y} r={6} fill={theme.colors.accent} stroke="#fff" strokeWidth={2} />
                      {pendingCurrentPoint ? (
                        <>
                          <Line
                            x1={pendingStartPoint.x}
                            y1={pendingStartPoint.y}
                            x2={pendingCurrentPoint.x}
                            y2={pendingCurrentPoint.y}
                            stroke={theme.colors.accent}
                            strokeWidth={2}
                            strokeDasharray="4 4"
                          />
                          <Circle cx={pendingCurrentPoint.x} cy={pendingCurrentPoint.y} r={6} fill={theme.colors.accent} stroke="#fff" strokeWidth={2} />
                        </>
                      ) : null}
                    </G>
                  ) : null}
                </Svg>
              </View>
            </Animated.View>
          </Animated.View>
        </GestureDetector>
      </View>

      <LabelEditModal
        visible={editModal.open}
        initialValue={selectedMeasurement?.textOverride || ''}
        onCancel={() => setEditModal({ open: false, id: null })}
        onSave={(value) => {
          const trimmed = (value || '').trim();
          const currentValue = (selectedMeasurement?.textOverride || '').trim();
          if (editModal.id && trimmed !== currentValue) {
            onRequestHistoryCheckpoint?.(annotations || []);
            updateMeasurement(editModal.id, { textOverride: trimmed }, { trackHistory: false });
          }
          setEditModal({ open: false, id: null });
        }}
        theme={theme}
      />
    </View>
  );
});

function styles(theme) {
  return StyleSheet.create({
    root: {
      flex: 1,
      position: 'relative',
    },
    exportSurface: {
      position: 'absolute',
      left: -10000,
      top: 0,
      opacity: 0.01,
      pointerEvents: 'none',
    },
    toolbarCard: {
      backgroundColor: theme.colors.surface,
      borderRadius: 16,
      borderWidth: 1,
      borderColor: theme.colors.authInputBorder,
      paddingHorizontal: 12,
      paddingVertical: 10,
      marginBottom: 10,
    },
    toolbarRow: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: 8,
      alignItems: 'center',
    },
    toolbarHint: {
      marginTop: 8,
      color: theme.colors.muted,
      fontSize: 11,
      lineHeight: 16,
      fontWeight: '600',
    },
    hint: {
      color: theme.colors.muted,
      fontWeight: '600',
      marginBottom: 8,
      lineHeight: 17,
      fontSize: 12,
    },
    canvas: {
      flex: 1,
      borderRadius: theme.radius.xl,
      backgroundColor: theme.colors.heroTint,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
      overflow: 'hidden',
    },
    toolbar: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: 8,
    },
    pillButton: {
      minHeight: 36,
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
    disabledText: {
      opacity: 0.35,
    },
    disabledPrimaryText: {
      opacity: 0.7,
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

export default FloorplanAnnotator;
