import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Users } from 'lucide-react';
import { studentsApi } from '../../api';
import { LoadingPage } from '../../components/ui';
import type { ParentStudentLink, PaginatedResponse } from '../../types';
import StudentHomeDashboard from './StudentHomeDashboard';

export default function ParentDashboard() {
  const { data, isLoading } = useQuery<PaginatedResponse<ParentStudentLink>>({
    queryKey: ['my-linked-children'],
    queryFn: () => studentsApi.myLinkedChildren().then(r => r.data),
  });
  const children = data?.results ?? [];
  const [selected, setSelected] = useState<number | null>(null);
  const activeLink = children.find(c => c.student === selected) ?? children[0];

  if (isLoading) return <LoadingPage />;

  if (children.length === 0) {
    return (
      <div className="card p-8 text-center flex flex-col items-center gap-2">
        <Users size={28} className="text-muted" />
        <p className="font-display font-semibold text-primary">No linked students yet</p>
        <p className="text-sm text-secondary max-w-sm">
          Ask the school admin to link your account to your child's student profile — once linked, their progress will show here.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {children.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap">
          {children.map(c => (
            <button
              key={c.id}
              onClick={() => setSelected(c.student)}
              className={`px-3 py-1.5 rounded-full text-sm font-display font-semibold border transition-colors ${
                (activeLink?.student === c.student)
                  ? 'bg-azure-500/15 text-azure-400 border-azure-500/30'
                  : 'text-secondary border-surface hover:border-azure-500/30'
              }`}
            >
              {c.student_name}
            </button>
          ))}
        </div>
      )}
      {activeLink && (
        <StudentHomeDashboard
          studentId={activeLink.student}
          viewerRole="guardian"
          childLabel={`${activeLink.student_name}'s Progress`}
        />
      )}
    </div>
  );
}
