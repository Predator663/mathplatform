import type { ReactNode } from 'react';
import { motion } from 'framer-motion';

interface RevealProps {
  children: ReactNode;
  /** Stagger index — multiplied by a small delay so lists cascade in. */
  index?: number;
  className?: string;
  style?: React.CSSProperties;
  /** 'up' slides in from below (default); 'scale' pops in slightly larger. */
  variant?: 'up' | 'scale';
}

/**
 * Fades/slides an element in once it scrolls into view, using an
 * easeOutExpo-style curve for the soft deceleration Apple's marketing
 * pages use. Animates only once per mount so re-scrolling doesn't replay it.
 */
export function Reveal({ children, index = 0, className, style, variant = 'up' }: RevealProps) {
  const initial = variant === 'scale'
    ? { opacity: 0, scale: 0.92 }
    : { opacity: 0, y: 16 };

  return (
    <motion.div
      className={className}
      style={style}
      initial={initial}
      whileInView={{ opacity: 1, y: 0, scale: 1 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{
        duration: 0.5,
        delay: Math.min(index * 0.05, 0.4),
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      {children}
    </motion.div>
  );
}
