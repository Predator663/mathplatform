import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Subject } from '../types';

interface SubjectStore {
  activeSubjectId: number | null;
  subjects: Subject[];
  setActiveSubject: (id: number | null) => void;
  setSubjects: (subjects: Subject[]) => void;
  getActiveSubject: () => Subject | null;
}

export const useSubjectStore = create<SubjectStore>()(
  persist(
    (set, get) => ({
      activeSubjectId: null,
      subjects: [],
      setActiveSubject: (id) => set({ activeSubjectId: id }),
      setSubjects: (subjects) => set({ subjects }),
      getActiveSubject: () => {
        const { activeSubjectId, subjects } = get();
        return subjects.find((s) => s.id === activeSubjectId) ?? null;
      },
    }),
    { name: 'subject-store' }
  )
);
