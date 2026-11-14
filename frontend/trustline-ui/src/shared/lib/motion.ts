/**
 * GSAP ease tokens shared across CSS, Motion, and GSAP.
 * Use these instead of hardcoded ease strings.
 */
export const EASE = {
  outQuint: 'power4.out',
  outCubic: 'power2.out',
  outExpo: 'expo.out',
  inOutCubic: 'power2.inOut',
  inOutQuint: 'power4.inOut',
  spring: 'elastic.out(1, 0.5)',
} as const;

export const DURATION = {
  instant: 0,
  micro: 0.15,
  fast: 0.25,
  normal: 0.4,
  slow: 0.6,
  dramatic: 1.0,
} as const;

export const STAGGER = {
  tight: 0.03,
  normal: 0.06,
  relaxed: 0.1,
  dramatic: 0.15,
} as const;
