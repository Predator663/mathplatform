import { useEffect, useRef } from 'react';

const CHARS = 'アイウエオカキクケコサシスセソ0123456789ABCDEFXYZ$#%&';

/**
 * Full-viewport canvas digital-rain effect. Rendered behind the terminal
 * window while the palette is open and `matrix on` has been run. Kept as
 * its own component so the animation loop only exists while mounted.
 */
export default function MatrixRain() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);
    const fontSize = 15;
    let columns = Math.floor(width / fontSize);
    let drops = new Array(columns).fill(1);

    const onResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
      columns = Math.floor(width / fontSize);
      drops = new Array(columns).fill(1);
    };
    window.addEventListener('resize', onResize);

    let raf = 0;
    const draw = () => {
      ctx.fillStyle = 'rgba(2, 6, 3, 0.12)';
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = '#39ff6a';
      ctx.font = `${fontSize}px monospace`;
      for (let i = 0; i < drops.length; i++) {
        const char = CHARS[Math.floor(Math.random() * CHARS.length)];
        ctx.fillText(char, i * fontSize, drops[i] * fontSize);
        if (drops[i] * fontSize > height && Math.random() > 0.975) drops[i] = 0;
        drops[i]++;
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none"
      style={{ opacity: 0.35, zIndex: 998 }}
    />
  );
}
