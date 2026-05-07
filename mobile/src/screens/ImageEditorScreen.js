import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Animated, Image, PanResponder, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useEntranceAnimation } from '../hooks/useEntranceAnimation';
import { clamp, estimateOutputSize, exportEditedAsset, fitCropBox, getDisplayedImageSize, resolveImageSize } from '../utils/imageEditing';

const ASPECT_PRESETS = [
  { id: 'original', label: 'Original' },
  { id: 'square', label: '1:1', ratio: 1 },
  { id: 'classic', label: '4:3', ratio: 4 / 3 },
  { id: 'portrait', label: '3:4', ratio: 3 / 4 },
  { id: 'wide', label: '16:9', ratio: 16 / 9 },
  { id: 'story', label: '9:16', ratio: 9 / 16 },
];

const OUTPUT_PRESETS = [
  { id: 'original', label: 'Original', maxEdge: null },
  { id: 'xl', label: '2048 px', maxEdge: 2048 },
  { id: 'lg', label: '1600 px', maxEdge: 1600 },
  { id: 'md', label: '1200 px', maxEdge: 1200 },
];

const HANDLE_KINDS = ['topLeft', 'top', 'topRight', 'right', 'bottomRight', 'bottom', 'bottomLeft', 'left'];

function getTouchDistance(touches) {
  if (!touches || touches.length < 2) {
    return 0;
  }

  const [first, second] = touches;
  const dx = second.pageX - first.pageX;
  const dy = second.pageY - first.pageY;
  return Math.sqrt(dx * dx + dy * dy);
}

function clampFrameOffset(frameOffset, stageSize, cropBox) {
  const maxX = Math.max(0, (stageSize.width - cropBox.width) / 2);
  const maxY = Math.max(0, (stageSize.height - cropBox.height) / 2);

  return {
    x: clamp(frameOffset.x, -maxX, maxX),
    y: clamp(frameOffset.y, -maxY, maxY),
  };
}

function getFramePosition(stageSize, cropBox, frameOffset) {
  const clampedOffset = clampFrameOffset(frameOffset, stageSize, cropBox);

  return {
    left: Math.max(0, (stageSize.width - cropBox.width) / 2 + clampedOffset.x),
    top: Math.max(0, (stageSize.height - cropBox.height) / 2 + clampedOffset.y),
    offset: clampedOffset,
  };
}

function getImagePanBounds(displayedSize, stageSize, cropBox, framePosition) {
  if (!displayedSize.width || !displayedSize.height || !stageSize.width || !stageSize.height) {
    return {
      xMin: 0,
      xMax: 0,
      yMin: 0,
      yMax: 0,
    };
  }

  const baseLeft = (stageSize.width - displayedSize.width) / 2;
  const baseTop = (stageSize.height - displayedSize.height) / 2;
  const cropRight = framePosition.left + cropBox.width;
  const cropBottom = framePosition.top + cropBox.height;

  return {
    xMin: cropRight - baseLeft - displayedSize.width,
    xMax: framePosition.left - baseLeft,
    yMin: cropBottom - baseTop - displayedSize.height,
    yMax: framePosition.top - baseTop,
  };
}

function clampImageOffsets(offsets, bounds) {
  return {
    x: clamp(offsets.x, bounds.xMin, bounds.xMax),
    y: clamp(offsets.y, bounds.yMin, bounds.yMax),
  };
}

function calculateCropRect({ imageSize, displayedSize, stageSize, offsets, cropBox, framePosition }) {
  if (!imageSize?.width || !imageSize?.height || !displayedSize?.width || !displayedSize?.height) {
    return null;
  }

  const imageLeft = (stageSize.width - displayedSize.width) / 2 + offsets.x;
  const imageTop = (stageSize.height - displayedSize.height) / 2 + offsets.y;

  const originX = clamp(Math.round(((framePosition.left - imageLeft) / displayedSize.width) * imageSize.width), 0, imageSize.width - 1);
  const originY = clamp(Math.round(((framePosition.top - imageTop) / displayedSize.height) * imageSize.height), 0, imageSize.height - 1);
  const width = clamp(Math.round((cropBox.width / displayedSize.width) * imageSize.width), 1, imageSize.width - originX);
  const height = clamp(Math.round((cropBox.height / displayedSize.height) * imageSize.height), 1, imageSize.height - originY);

  return { originX, originY, width, height };
}

function IconButton({ icon, label, onPress, styles, theme, disabled = false }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      style={[styles.iconButton, disabled ? styles.disabledButton : null]}
      onPress={onPress}
      disabled={disabled}
    >
      <Ionicons name={icon} size={18} color={theme.colors.text} />
    </Pressable>
  );
}

function ChoiceChip({ label, selected, onPress, styles }) {
  return (
    <Pressable style={[styles.choiceChip, selected ? styles.choiceChipActive : null]} onPress={onPress}>
      <Text style={[styles.choiceChipText, selected ? styles.choiceChipTextActive : null]}>{label}</Text>
    </Pressable>
  );
}

function MetricBadge({ label, value, styles }) {
  return (
    <View style={styles.metricBadge}>
      <Text style={styles.metricBadgeLabel}>{label}</Text>
      <Text style={styles.metricBadgeValue}>{value}</Text>
    </View>
  );
}

function CropHandle({ kind, responder, styles }) {
  const handleStyles = {
    topLeft: styles.handleTopLeft,
    top: styles.handleTop,
    topRight: styles.handleTopRight,
    right: styles.handleRight,
    bottomRight: styles.handleBottomRight,
    bottom: styles.handleBottom,
    bottomLeft: styles.handleBottomLeft,
    left: styles.handleLeft,
  };

  return <View style={[styles.handleBase, handleStyles[kind]]} {...responder.panHandlers} />;
}

export default function ImageEditorScreen({ asset, busy, onBack, onConfirm, theme, isLandscape }) {
  const animatedStyle = useEntranceAnimation({ distance: 18, duration: 280, damping: 16, stiffness: 150 });
  const styles = useMemo(() => createStyles(theme, isLandscape), [theme, isLandscape]);

  const [imageSize, setImageSize] = useState(null);
  const [selectedAspect, setSelectedAspect] = useState('original');
  const [selectedOutput, setSelectedOutput] = useState('lg');
  const [frameScale, setFrameScale] = useState(0.88);
  const [zoom, setZoom] = useState(1);
  const [offsets, setOffsets] = useState({ x: 0, y: 0 });
  const [frameOffset, setFrameOffset] = useState({ x: 0, y: 0 });
  const [stageSize, setStageSize] = useState({ width: 0, height: 0 });
  const [preparing, setPreparing] = useState(false);

  const offsetsRef = useRef(offsets);
  const frameOffsetRef = useRef(frameOffset);
  const panOriginRef = useRef(offsets);
  const frameOriginRef = useRef(frameOffset);
  const gestureModeRef = useRef('pan');
  const pinchStartDistanceRef = useRef(0);
  const pinchStartZoomRef = useRef(zoom);
  const resizeStartScaleRef = useRef(frameScale);
  const imagePanBoundsRef = useRef({ xMin: 0, xMax: 0, yMin: 0, yMax: 0 });

  useEffect(() => {
    offsetsRef.current = offsets;
  }, [offsets]);

  useEffect(() => {
    frameOffsetRef.current = frameOffset;
  }, [frameOffset]);

  useEffect(() => {
    let active = true;

    resolveImageSize(asset)
      .then((nextSize) => {
        if (active) {
          setImageSize(nextSize);
        }
      })
      .catch((error) => {
        if (active) {
          Alert.alert('Image issue', error.message || 'Unable to load image for editing.');
          onBack();
        }
      });

    return () => {
      active = false;
    };
  }, [asset, onBack]);

  const aspectRatio = useMemo(() => {
    if (!imageSize) {
      return 1;
    }

    const preset = ASPECT_PRESETS.find((item) => item.id === selectedAspect);
    if (!preset || preset.id === 'original') {
      return imageSize.width / imageSize.height;
    }

    return preset.ratio;
  }, [imageSize, selectedAspect]);

  const cropBox = useMemo(() => fitCropBox(stageSize.width, stageSize.height, aspectRatio, frameScale), [aspectRatio, frameScale, stageSize.height, stageSize.width]);
  const displayedSize = useMemo(() => getDisplayedImageSize(imageSize, cropBox, zoom), [cropBox, imageSize, zoom]);
  const framePosition = useMemo(() => getFramePosition(stageSize, cropBox, frameOffset), [cropBox, frameOffset, stageSize]);
  const imagePanBounds = useMemo(() => getImagePanBounds(displayedSize, stageSize, cropBox, framePosition), [cropBox, displayedSize, framePosition, stageSize]);

  useEffect(() => {
    imagePanBoundsRef.current = imagePanBounds;
    setOffsets((current) => clampImageOffsets(current, imagePanBounds));
  }, [imagePanBounds]);

  useEffect(() => {
    setFrameOffset((current) => clampFrameOffset(current, stageSize, cropBox));
  }, [cropBox, stageSize]);

  const cropRect = useMemo(
    () =>
      calculateCropRect({
        imageSize,
        displayedSize,
        stageSize,
        offsets,
        cropBox,
        framePosition,
      }),
    [cropBox, displayedSize, framePosition, imageSize, offsets, stageSize]
  );

  const outputPreset = OUTPUT_PRESETS.find((item) => item.id === selectedOutput) || OUTPUT_PRESETS[2];
  const outputSize = useMemo(() => estimateOutputSize(cropRect, outputPreset.maxEdge), [cropRect, outputPreset.maxEdge]);

  const imageLeft = (stageSize.width - displayedSize.width) / 2 + offsets.x;
  const imageTop = (stageSize.height - displayedSize.height) / 2 + offsets.y;

  const imageResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => !busy && !preparing,
        onMoveShouldSetPanResponder: () => !busy && !preparing,
        onPanResponderGrant: (event) => {
          const touches = event.nativeEvent.touches || [];

          if (touches.length >= 2) {
            gestureModeRef.current = 'pinch';
            pinchStartDistanceRef.current = getTouchDistance(touches);
            pinchStartZoomRef.current = zoom;
            return;
          }

          gestureModeRef.current = 'pan';
          panOriginRef.current = offsetsRef.current;
        },
        onPanResponderMove: (event, gestureState) => {
          const touches = event.nativeEvent.touches || [];

          if (touches.length >= 2) {
            const distance = getTouchDistance(touches);

            if (gestureModeRef.current !== 'pinch' || !pinchStartDistanceRef.current) {
              gestureModeRef.current = 'pinch';
              pinchStartDistanceRef.current = distance;
              pinchStartZoomRef.current = zoom;
            }

            if (!pinchStartDistanceRef.current) {
              return;
            }

            const nextZoom = clamp((pinchStartZoomRef.current * distance) / pinchStartDistanceRef.current, 1, 4);
            setZoom(nextZoom);
            return;
          }

          if (gestureModeRef.current === 'pinch') {
            gestureModeRef.current = 'pan';
            panOriginRef.current = offsetsRef.current;
          }

          const nextOffsets = clampImageOffsets(
            {
              x: panOriginRef.current.x + gestureState.dx,
              y: panOriginRef.current.y + gestureState.dy,
            },
            imagePanBoundsRef.current
          );

          offsetsRef.current = nextOffsets;
          setOffsets(nextOffsets);
        },
        onPanResponderRelease: () => {
          pinchStartDistanceRef.current = 0;
          pinchStartZoomRef.current = zoom;
          panOriginRef.current = offsetsRef.current;
        },
      }),
    [busy, preparing, zoom]
  );

  const frameResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => !busy && !preparing,
        onMoveShouldSetPanResponder: () => !busy && !preparing,
        onPanResponderGrant: () => {
          frameOriginRef.current = frameOffsetRef.current;
        },
        onPanResponderMove: (_, gestureState) => {
          const nextFrameOffset = clampFrameOffset(
            {
              x: frameOriginRef.current.x + gestureState.dx,
              y: frameOriginRef.current.y + gestureState.dy,
            },
            stageSize,
            cropBox
          );

          frameOffsetRef.current = nextFrameOffset;
          setFrameOffset(nextFrameOffset);
        },
      }),
    [busy, cropBox, preparing, stageSize]
  );

  const resizeResponders = useMemo(() => {
    const denominator = Math.max(180, Math.min(stageSize.width || 320, stageSize.height || 320) * 0.72);

    const buildScaleDelta = (kind, dx, dy) => {
      switch (kind) {
        case 'left':
          return -dx / denominator;
        case 'right':
          return dx / denominator;
        case 'top':
          return -dy / denominator;
        case 'bottom':
          return dy / denominator;
        case 'topLeft':
          return (-dx - dy) / (denominator * 1.7);
        case 'topRight':
          return (dx - dy) / (denominator * 1.7);
        case 'bottomRight':
          return (dx + dy) / (denominator * 1.7);
        case 'bottomLeft':
          return (-dx + dy) / (denominator * 1.7);
        default:
          return 0;
      }
    };

    return HANDLE_KINDS.reduce((accumulator, kind) => {
      accumulator[kind] = PanResponder.create({
        onStartShouldSetPanResponder: () => !busy && !preparing,
        onMoveShouldSetPanResponder: () => !busy && !preparing,
        onPanResponderGrant: () => {
          resizeStartScaleRef.current = frameScale;
        },
        onPanResponderMove: (_, gestureState) => {
          const scaleDelta = buildScaleDelta(kind, gestureState.dx, gestureState.dy);
          const nextScale = clamp(resizeStartScaleRef.current + scaleDelta, 0.46, 0.96);
          setFrameScale(nextScale);
        },
      });

      return accumulator;
    }, {});
  }, [busy, frameScale, preparing, stageSize.height, stageSize.width]);

  function resetEditor() {
    setZoom(1);
    setFrameScale(0.88);
    setOffsets({ x: 0, y: 0 });
    setFrameOffset({ x: 0, y: 0 });
  }

  async function handleConfirm() {
    if (!cropRect) {
      Alert.alert('Editor not ready', 'Please wait for the image to finish loading.');
      return;
    }

    try {
      setPreparing(true);
      const editedAsset = await exportEditedAsset({
        asset,
        cropRect,
        maxEdge: outputPreset.maxEdge,
      });
      await onConfirm(editedAsset);
    } catch (error) {
      Alert.alert('Unable to prepare image', error.message || 'Please try adjusting the crop and retry.');
    } finally {
      setPreparing(false);
    }
  }

  const previewWidth = isLandscape ? 104 : 88;
  const previewHeight = cropBox.width ? Math.max(70, Math.round((cropBox.height / cropBox.width) * previewWidth)) : 76;
  const previewScale = cropBox.width ? previewWidth / cropBox.width : 1;
  const previewImageWidth = displayedSize.width * previewScale;
  const previewImageHeight = displayedSize.height * previewScale;
  const previewLeft = (imageLeft - framePosition.left) * previewScale;
  const previewTop = (imageTop - framePosition.top) * previewScale;

  const outputLabel = outputSize ? `${outputSize.width} × ${outputSize.height}` : '...';
  const cropLabel = cropRect ? `${cropRect.width} × ${cropRect.height}` : '...';
  const zoomLabel = `${Math.round(zoom * 100)}%`;

  return (
    <Animated.View style={[styles.container, animatedStyle]}>
      <View style={styles.header}>
        <IconButton icon="close" label="Close editor" onPress={onBack} styles={styles} theme={theme} disabled={busy || preparing} />

        <View style={styles.headerCopy}>
          <Text style={styles.title}>Edit photo</Text>
          <Text style={styles.subtitle}>Pinch the image, drag it into place, and resize the crop like a gallery app.</Text>
        </View>

        <IconButton icon="refresh" label="Reset crop" onPress={resetEditor} styles={styles} theme={theme} disabled={busy || preparing} />
      </View>

      <View style={styles.stageShell}>
        <View style={styles.stageHint}>
          <Ionicons name="scan-outline" size={14} color={theme.colors.surface} />
          <Text style={styles.stageHintText}>Pinch image • Drag image • Move or resize frame</Text>
        </View>

        <View
          style={styles.stage}
          onLayout={(event) => {
            const { width, height } = event.nativeEvent.layout;
            setStageSize({ width, height });
          }}
        >
          {displayedSize.width ? (
            <Image
              source={{ uri: asset.uri }}
              style={[
                styles.editImage,
                {
                  width: displayedSize.width,
                  height: displayedSize.height,
                  left: imageLeft,
                  top: imageTop,
                },
              ]}
              resizeMode="cover"
              {...imageResponder.panHandlers}
            />
          ) : null}

          <View style={[styles.overlayMask, { left: 0, right: 0, top: 0, height: framePosition.top }]} pointerEvents="none" />
          <View style={[styles.overlayMask, { left: 0, width: framePosition.left, top: framePosition.top, height: cropBox.height }]} pointerEvents="none" />
          <View
            style={[
              styles.overlayMask,
              {
                left: framePosition.left + cropBox.width,
                right: 0,
                top: framePosition.top,
                height: cropBox.height,
              },
            ]}
            pointerEvents="none"
          />
          <View
            style={[
              styles.overlayMask,
              {
                left: 0,
                right: 0,
                top: framePosition.top + cropBox.height,
                bottom: 0,
              },
            ]}
            pointerEvents="none"
          />

          {cropBox.width ? (
            <View
              pointerEvents="box-none"
              style={[
                styles.cropFrameOverlay,
                {
                  left: framePosition.left,
                  top: framePosition.top,
                  width: cropBox.width,
                  height: cropBox.height,
                },
              ]}
            >
              <View pointerEvents="none" style={styles.cropFrame} />
              <View pointerEvents="none" style={styles.gridLineVerticalOne} />
              <View pointerEvents="none" style={styles.gridLineVerticalTwo} />
              <View pointerEvents="none" style={styles.gridLineHorizontalOne} />
              <View pointerEvents="none" style={styles.gridLineHorizontalTwo} />

              <View style={styles.frameMoveHandle} {...frameResponder.panHandlers}>
                <Ionicons name="move-outline" size={14} color={theme.colors.text} />
                <Text style={styles.frameMoveText}>Move frame</Text>
              </View>

              {HANDLE_KINDS.map((kind) => (
                <CropHandle key={kind} kind={kind} responder={resizeResponders[kind]} styles={styles} />
              ))}
            </View>
          ) : (
            <View style={styles.loadingCanvas}>
              <Ionicons name="image-outline" size={24} color={theme.colors.softText} />
              <Text style={styles.loadingCanvasText}>Loading editor...</Text>
            </View>
          )}
        </View>
      </View>

      <View style={styles.bottomDock}>
        <View style={styles.previewRow}>
          <View style={styles.previewPanel}>
            <Text style={styles.sectionEyebrow}>Live preview</Text>
            <View style={[styles.previewFrame, { width: previewWidth, height: previewHeight }]}>
              <Image
                source={{ uri: asset.uri }}
                style={[
                  styles.previewImage,
                  {
                    width: previewImageWidth,
                    height: previewImageHeight,
                    left: previewLeft,
                    top: previewTop,
                  },
                ]}
                resizeMode="cover"
              />
            </View>
          </View>

          <View style={styles.metricColumn}>
            <MetricBadge label="Crop" value={cropLabel} styles={styles} />
            <MetricBadge label="Export" value={outputLabel} styles={styles} />
            <MetricBadge label="Zoom" value={zoomLabel} styles={styles} />
          </View>
        </View>

        <View style={styles.sectionBlock}>
          <Text style={styles.sectionTitle}>Aspect ratio</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.choiceStrip}>
            {ASPECT_PRESETS.map((preset) => (
              <ChoiceChip
                key={preset.id}
                label={preset.label}
                selected={selectedAspect === preset.id}
                onPress={() => {
                  setSelectedAspect(preset.id);
                  setOffsets({ x: 0, y: 0 });
                  setFrameOffset({ x: 0, y: 0 });
                  setFrameScale(0.88);
                }}
                styles={styles}
              />
            ))}
          </ScrollView>
        </View>

        <View style={styles.sectionBlock}>
          <Text style={styles.sectionTitle}>Export size</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.choiceStrip}>
            {OUTPUT_PRESETS.map((preset) => (
              <ChoiceChip key={preset.id} label={preset.label} selected={selectedOutput === preset.id} onPress={() => setSelectedOutput(preset.id)} styles={styles} />
            ))}
          </ScrollView>
        </View>

        <View style={styles.actionRow}>
          <Pressable style={[styles.secondaryButton, busy || preparing ? styles.disabledButton : null]} onPress={onBack} disabled={busy || preparing}>
            <Text style={styles.secondaryButtonText}>Pick another</Text>
          </Pressable>
          <Pressable style={[styles.primaryButton, busy || preparing ? styles.disabledButton : null]} onPress={handleConfirm} disabled={busy || preparing}>
            <Text style={styles.primaryButtonText}>{busy || preparing ? 'Preparing...' : 'Use this image'}</Text>
          </Pressable>
        </View>
      </View>
    </Animated.View>
  );
}

function createStyles(theme, isLandscape) {
  return StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: theme.colors.background,
    },
    header: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 14,
      paddingTop: 4,
      paddingBottom: 14,
    },
    iconButton: {
      width: 44,
      height: 44,
      borderRadius: 22,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.border,
      alignItems: 'center',
      justifyContent: 'center',
      ...theme.shadow.soft,
    },
    disabledButton: {
      opacity: 0.58,
    },
    headerCopy: {
      flex: 1,
    },
    title: {
      color: theme.colors.text,
      fontSize: isLandscape ? 30 : 28,
      fontWeight: '900',
      letterSpacing: -0.8,
    },
    subtitle: {
      marginTop: 6,
      color: theme.colors.muted,
      fontSize: 15,
      lineHeight: 22,
      fontWeight: '700',
    },
    stageShell: {
      flex: 1,
      position: 'relative',
      marginBottom: 16,
    },
    stageHint: {
      position: 'absolute',
      top: 16,
      left: 16,
      right: 16,
      zIndex: 4,
      borderRadius: 999,
      paddingHorizontal: 14,
      paddingVertical: 10,
      backgroundColor: 'rgba(14, 30, 58, 0.68)',
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      alignSelf: 'center',
    },
    stageHintText: {
      color: theme.colors.surface,
      fontSize: 12,
      fontWeight: '800',
      letterSpacing: 0.2,
    },
    stage: {
      flex: 1,
      minHeight: isLandscape ? 300 : 380,
      borderRadius: 34,
      overflow: 'hidden',
      backgroundColor: '#CAD4E4',
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      ...theme.shadow.card,
    },
    editImage: {
      position: 'absolute',
      zIndex: 1,
    },
    overlayMask: {
      position: 'absolute',
      backgroundColor: 'rgba(38, 54, 82, 0.38)',
      zIndex: 2,
    },
    cropFrameOverlay: {
      position: 'absolute',
      zIndex: 3,
    },
    cropFrame: {
      ...StyleSheet.absoluteFillObject,
      borderWidth: 2,
      borderRadius: 26,
      borderColor: '#FFFFFF',
    },
    gridLineVerticalOne: {
      position: 'absolute',
      top: 0,
      bottom: 0,
      left: '33.333%',
      width: 1,
      backgroundColor: 'rgba(255,255,255,0.28)',
    },
    gridLineVerticalTwo: {
      position: 'absolute',
      top: 0,
      bottom: 0,
      left: '66.666%',
      width: 1,
      backgroundColor: 'rgba(255,255,255,0.28)',
    },
    gridLineHorizontalOne: {
      position: 'absolute',
      left: 0,
      right: 0,
      top: '33.333%',
      height: 1,
      backgroundColor: 'rgba(255,255,255,0.28)',
    },
    gridLineHorizontalTwo: {
      position: 'absolute',
      left: 0,
      right: 0,
      top: '66.666%',
      height: 1,
      backgroundColor: 'rgba(255,255,255,0.28)',
    },
    frameMoveHandle: {
      position: 'absolute',
      top: 14,
      left: '50%',
      transform: [{ translateX: -54 }],
      width: 108,
      height: 30,
      borderRadius: 999,
      backgroundColor: 'rgba(255,255,255,0.94)',
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 6,
      ...theme.shadow.soft,
    },
    frameMoveText: {
      color: theme.colors.text,
      fontSize: 11,
      fontWeight: '800',
    },
    handleBase: {
      position: 'absolute',
      width: 24,
      height: 24,
      borderRadius: 12,
      backgroundColor: '#FFFFFF',
      borderWidth: 2,
      borderColor: theme.colors.accent,
      ...theme.shadow.soft,
    },
    handleTopLeft: {
      left: -12,
      top: -12,
    },
    handleTop: {
      top: -12,
      left: '50%',
      marginLeft: -12,
    },
    handleTopRight: {
      right: -12,
      top: -12,
    },
    handleRight: {
      right: -12,
      top: '50%',
      marginTop: -12,
    },
    handleBottomRight: {
      right: -12,
      bottom: -12,
    },
    handleBottom: {
      bottom: -12,
      left: '50%',
      marginLeft: -12,
    },
    handleBottomLeft: {
      left: -12,
      bottom: -12,
    },
    handleLeft: {
      left: -12,
      top: '50%',
      marginTop: -12,
    },
    loadingCanvas: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      gap: 10,
    },
    loadingCanvasText: {
      color: theme.colors.muted,
      fontWeight: '700',
    },
    bottomDock: {
      borderRadius: 28,
      backgroundColor: theme.colors.surfaceElevated,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      paddingHorizontal: 16,
      paddingTop: 16,
      paddingBottom: 16,
      ...theme.shadow.card,
    },
    previewRow: {
      flexDirection: isLandscape ? 'row' : 'row',
      alignItems: 'center',
      gap: 12,
      marginBottom: 16,
    },
    previewPanel: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 12,
      flex: 1,
    },
    sectionEyebrow: {
      color: theme.colors.softText,
      fontSize: 12,
      fontWeight: '800',
      textTransform: 'uppercase',
      letterSpacing: 0.8,
      marginBottom: 8,
    },
    previewFrame: {
      borderRadius: 18,
      overflow: 'hidden',
      backgroundColor: theme.colors.heroTint,
      borderWidth: 1,
      borderColor: theme.colors.borderStrong,
      position: 'relative',
    },
    previewImage: {
      position: 'absolute',
    },
    metricColumn: {
      width: isLandscape ? 280 : 152,
      gap: 8,
    },
    metricBadge: {
      borderRadius: 18,
      paddingHorizontal: 12,
      paddingVertical: 10,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.border,
    },
    metricBadgeLabel: {
      color: theme.colors.softText,
      fontSize: 11,
      fontWeight: '800',
      textTransform: 'uppercase',
      letterSpacing: 0.7,
    },
    metricBadgeValue: {
      marginTop: 4,
      color: theme.colors.text,
      fontSize: 14,
      fontWeight: '800',
    },
    sectionBlock: {
      marginBottom: 14,
    },
    sectionTitle: {
      color: theme.colors.text,
      fontSize: 16,
      fontWeight: '800',
      marginBottom: 10,
    },
    choiceStrip: {
      paddingRight: 6,
      gap: 10,
    },
    choiceChip: {
      paddingHorizontal: 15,
      paddingVertical: 11,
      borderRadius: 999,
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.border,
    },
    choiceChipActive: {
      backgroundColor: theme.colors.accentSoft,
      borderColor: theme.colors.accent,
    },
    choiceChipText: {
      color: theme.colors.muted,
      fontWeight: '700',
      fontSize: 13,
    },
    choiceChipTextActive: {
      color: theme.colors.accent,
      fontWeight: '800',
    },
    actionRow: {
      flexDirection: isLandscape ? 'row' : 'row',
      gap: 12,
      marginTop: 4,
    },
    secondaryButton: {
      flex: 1,
      minHeight: 54,
      borderRadius: 18,
      borderWidth: 1,
      borderColor: theme.colors.noticeBorder,
      backgroundColor: theme.colors.heroTint,
      alignItems: 'center',
      justifyContent: 'center',
      paddingHorizontal: 18,
    },
    secondaryButtonText: {
      color: theme.colors.text,
      fontWeight: '800',
      fontSize: 15,
    },
    primaryButton: {
      flex: 1.2,
      minHeight: 54,
      borderRadius: 18,
      backgroundColor: theme.colors.accent,
      alignItems: 'center',
      justifyContent: 'center',
      paddingHorizontal: 18,
      ...theme.shadow.soft,
    },
    primaryButtonText: {
      color: theme.colors.surface,
      fontWeight: '800',
      fontSize: 16,
    },
  });
}
