import { useEffect, useRef } from 'react';
import { Animated } from 'react-native';

export function useEntranceAnimation({
  dependencies = [],
  distance = 18,
  duration = 300,
  damping = 15,
  stiffness = 145,
} = {}) {
  const fade = useRef(new Animated.Value(0)).current;
  const rise = useRef(new Animated.Value(distance)).current;

  useEffect(() => {
    fade.setValue(0);
    rise.setValue(distance);

    const animation = Animated.parallel([
      Animated.timing(fade, {
        toValue: 1,
        duration,
        useNativeDriver: true,
      }),
      Animated.spring(rise, {
        toValue: 0,
        useNativeDriver: true,
        damping,
        stiffness,
      }),
    ]);

    animation.start();

    return () => animation.stop();
  }, [fade, rise, distance, duration, damping, stiffness, ...dependencies]);

  return {
    opacity: fade,
    transform: [{ translateY: rise }],
  };
}
