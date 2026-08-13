import { useRef } from 'react';
import type { ReactNode, MouseEvent } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { cn } from '../../utils';

interface TiltCardProps {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
  onClick?: () => void;
  /** Max tilt rotation in degrees. Keep subtle — this mirrors the restrained,
   *  physical feel of Apple's product cards rather than a gimmicky effect. */
  maxTilt?: number;
  /** Disable on touch/coarse-pointer devices automatically; set false to force on. */
  glare?: boolean;
  /** Accessible name — recommended whenever onClick is set, since the card
   *  renders as a div with role="button" rather than a native <button>. */
  'aria-label'?: string;
}

/**
 * A card that tilts in 3D toward the cursor and springs back on release,
 * with an optional soft light "glare" that follows the pointer. Respects
 * prefers-reduced-motion by skipping the tilt transform entirely.
 */
export function TiltCard({ children, className, style, onClick, maxTilt = 8, glare = true, 'aria-label': ariaLabel }: TiltCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const prefersReducedMotion = typeof window !== 'undefined'
    && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  const x = useMotionValue(0.5);
  const y = useMotionValue(0.5);
  const springCfg = { stiffness: 300, damping: 25, mass: 0.5 };
  const sx = useSpring(x, springCfg);
  const sy = useSpring(y, springCfg);

  const rotateX = useTransform(sy, [0, 1], [maxTilt, -maxTilt]);
  const rotateY = useTransform(sx, [0, 1], [-maxTilt, maxTilt]);
  const glareX = useTransform(sx, [0, 1], ['0%', '100%']);
  const glareY = useTransform(sy, [0, 1], ['0%', '100%']);

  function handleMouseMove(e: MouseEvent<HTMLDivElement>) {
    if (prefersReducedMotion || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    x.set((e.clientX - rect.left) / rect.width);
    y.set((e.clientY - rect.top) / rect.height);
  }

  function handleMouseLeave() {
    x.set(0.5);
    y.set(0.5);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (!onClick) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  }

  return (
    <motion.div
      ref={ref}
      onClick={onClick}
      onKeyDown={onClick ? handleKeyDown : undefined}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      aria-label={ariaLabel}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        ...style,
        perspective: 800,
        rotateX: prefersReducedMotion ? 0 : rotateX,
        rotateY: prefersReducedMotion ? 0 : rotateY,
        transformStyle: 'preserve-3d',
      }}
      whileHover={prefersReducedMotion ? undefined : { scale: 1.02, y: -3 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 300, damping: 22 }}
      className={cn(
        'card relative overflow-hidden',
        onClick && 'cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-azure-500/60',
        className,
      )}
    >
      {glare && !prefersReducedMotion && (
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background: `radial-gradient(circle at ${glareX} ${glareY}, rgba(255,255,255,0.10), transparent 55%)`,
          }}
        />
      )}
      <div style={{ transform: 'translateZ(24px)' }}>{children}</div>
    </motion.div>
  );
}
