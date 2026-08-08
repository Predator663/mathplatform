import { create } from 'zustand';

interface PaletteEffectsState {
  matrixOn: boolean;
  glitchTick: number;
  soundOn: boolean;
  setMatrix: (on: boolean) => void;
  toggleMatrix: () => void;
  triggerGlitch: () => void;
  toggleSound: () => void;
}

/**
 * Deliberately separate from the palette component's own local state:
 * command handlers (in commands.ts) don't have React state to set, so
 * effects a command triggers (`matrix on`, `glitch`) go through this
 * tiny store instead, and CommandPalette.tsx just subscribes to it.
 */
export const usePaletteEffects = create<PaletteEffectsState>((set) => ({
  matrixOn: false,
  glitchTick: 0,
  soundOn: false,
  setMatrix: (on) => set({ matrixOn: on }),
  toggleMatrix: () => set((s) => ({ matrixOn: !s.matrixOn })),
  triggerGlitch: () => set((s) => ({ glitchTick: s.glitchTick + 1 })),
  toggleSound: () => set((s) => ({ soundOn: !s.soundOn })),
}));
