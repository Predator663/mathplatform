import { useState, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Upload, Download, CheckCircle, XCircle, AlertCircle, FileText, Users, BookOpen } from 'lucide-react';
import toast from 'react-hot-toast';
import { examsApi } from '../../api';
import { Button, Select } from '../../components/ui';
import { downloadBlob, EXAM_TYPE_LABELS, formatDate } from '../../utils';
import type { Exam, PaginatedResponse } from '../../types';
import api from '../../api';

type ImportMode = 'students' | 'scores';

interface ImportResult {
  created?: number;
  skipped?: number;
  errors_count?: number;
  students?: { row: number; student_id: string; name: string; email: string; generated_password: string }[];
  skipped_detail?: { row: number; email?: string; student_id?: string; reason: string }[];
  errors?: { row?: number; error: string; student_id?: string }[];
  updated?: number;
}

export default function BulkImportPage() {
  const [mode, setMode] = useState<ImportMode>('students');
  const [selectedExam, setSelectedExam] = useState('');
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: examsData } = useQuery<PaginatedResponse<Exam> | Exam[]>({
    queryKey: ['exams-all'],
    queryFn: () => examsApi.exams({ page_size: 200 }).then(r => r.data),
  });
  const exams: Exam[] = Array.isArray(examsData)
    ? examsData
    : (examsData as PaginatedResponse<Exam>)?.results ?? [];

  const handleFile = (f: File) => {
    if (!f.name.endsWith('.csv')) {
      toast.error('Only CSV files are accepted');
      return;
    }
    setFile(f);
    setResult(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const downloadStudentTemplate = async () => {
    try {
      const res = await api.get('/students/profiles/import_template/', { responseType: 'blob' });
      downloadBlob(res.data as Blob, 'student_import_template.csv');
      toast.success('Template downloaded');
    } catch { toast.error('Download failed'); }
  };

  const downloadScoresTemplate = async () => {
    if (!selectedExam) { toast.error('Select an exam first'); return; }
    try {
      const res = await api.get(`/exams/exams/${selectedExam}/scores_template/`, { responseType: 'blob' });
      downloadBlob(res.data as Blob, `scores_template_exam_${selectedExam}.csv`);
      toast.success('Template downloaded — fill in the score column and upload');
    } catch { toast.error('Download failed'); }
  };

  const handleImport = async () => {
    if (!file) { toast.error('Please select a CSV file'); return; }
    if (mode === 'scores' && !selectedExam) { toast.error('Please select an exam'); return; }

    setLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      let res;
      if (mode === 'students') {
        res = await api.post('/students/profiles/bulk_import/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      } else {
        res = await api.post(`/exams/exams/${selectedExam}/bulk_scores_csv/`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      }

      setResult(res.data as ImportResult);
      const d = res.data as ImportResult;
      const created = d.created ?? 0;
      const updated = d.updated ?? 0;
      const errs = d.errors_count ?? d.errors?.length ?? 0;

      if (mode === 'students') {
        toast.success(`Imported ${created} students${errs ? `, ${errs} errors` : ''}`);
      } else {
        toast.success(`Updated ${created + updated} scores${errs ? `, ${errs} errors` : ''}`);
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? 'Import failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-3xl page-enter">
      <div>
        <h1 className="page-title">Bulk Import</h1>
        <p className="text-muted mt-1">Import students or exam scores from CSV files.</p>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-1 bg-surface-900 p-1 rounded-xl w-fit">
        {([
          { id: 'students', label: 'Import Students', icon: Users },
          { id: 'scores',   label: 'Import Scores',   icon: BookOpen },
        ] as { id: ImportMode; label: string; icon: typeof Users }[]).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => { setMode(id); setFile(null); setResult(null); }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-display font-medium transition-all ${
              mode === id ? 'bg-surface-700 text-primary shadow' : 'text-secondary hover:text-primary'
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Exam selector (scores mode) */}
      {mode === 'scores' && (
        <div className="card p-5">
          <Select
            label="Select Exam"
            options={[
              { value: '', label: 'Choose an exam…' },
              ...exams.map(e => ({
                value: e.id,
                label: `${e.title} (${EXAM_TYPE_LABELS[e.exam_type]} · ${formatDate(e.exam_date)})`,
              })),
            ]}
            value={selectedExam}
            onChange={e => setSelectedExam(e.target.value)}
          />
        </div>
      )}

      {/* Instructions */}
      <div className="card p-5 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="section-title">
            {mode === 'students' ? 'Student Import Format' : 'Score Import Format'}
          </h2>
          <Button
            variant="secondary"
            size="sm"
            onClick={mode === 'students' ? downloadStudentTemplate : downloadScoresTemplate}
          >
            <Download size={13} />
            Download Template
          </Button>
        </div>

        {mode === 'students' ? (
          <div>
            <p className="text-muted text-sm mb-3">Required columns:</p>
            <div className="font-mono text-xs bg-surface-900 rounded-xl p-3 text-emerald-400">
              first_name, last_name, email, student_id, classroom_id, date_of_birth, notes
            </div>
            <ul className="mt-3 text-xs text-secondary flex flex-col gap-1.5">
              <li>• <b className="text-primary">first_name, last_name, email, student_id</b> — required</li>
              <li>• <b className="text-primary">classroom_id</b> — optional, use the classroom's numeric ID</li>
              <li>• <b className="text-primary">date_of_birth</b> — optional, format YYYY-MM-DD</li>
              <li>• Passwords are auto-generated and shown in the results</li>
              <li>• Duplicate emails and student IDs are skipped</li>
            </ul>
          </div>
        ) : (
          <div>
            <p className="text-muted text-sm mb-3">Required columns:</p>
            <div className="font-mono text-xs bg-surface-900 rounded-xl p-3 text-emerald-400">
              student_id, score, is_absent, remarks
            </div>
            <ul className="mt-3 text-xs text-secondary flex flex-col gap-1.5">
              <li>• <b className="text-primary">student_id</b> — required, must match existing student IDs</li>
              <li>• <b className="text-primary">score</b> — required unless is_absent is true</li>
              <li>• <b className="text-primary">is_absent</b> — optional, true/false (default false)</li>
              <li>• <b className="text-primary">remarks</b> — optional</li>
              <li>• Existing scores are updated; new ones are created</li>
            </ul>
          </div>
        )}
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all ${
          dragging
            ? 'border-azure-500 bg-azure-500/10'
            : file
              ? 'border-emerald-500/50 bg-emerald-500/5'
              : 'border-surface hover:border-azure-500/50 hover:bg-surface-800/50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
        />

        {file ? (
          <div className="flex flex-col items-center gap-2">
            <FileText size={32} className="text-emerald-400" />
            <p className="font-display font-semibold text-primary">{file.name}</p>
            <p className="text-muted text-sm">{(file.size / 1024).toFixed(1)} KB · Click to change</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload size={32} className="text-secondary" />
            <p className="font-display font-semibold text-primary">Drop CSV here or click to browse</p>
            <p className="text-muted text-sm">CSV files only</p>
          </div>
        )}
      </div>

      {/* Import button */}
      <div className="flex justify-end">
        <Button
          onClick={handleImport}
          loading={loading}
          disabled={!file || (mode === 'scores' && !selectedExam)}
          size="lg"
        >
          <Upload size={15} />
          {loading ? 'Importing…' : `Import ${mode === 'students' ? 'Students' : 'Scores'}`}
        </Button>
      </div>

      {/* Results */}
      {result && (
        <div className="flex flex-col gap-4">
          {/* Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="card p-4 text-center border-emerald-500/20">
              <p className="label">Created</p>
              <p className="font-display font-bold text-2xl text-emerald-400 mt-1">{result.created ?? 0}</p>
            </div>
            {mode === 'scores' && (
              <div className="card p-4 text-center border-azure-500/20">
                <p className="label">Updated</p>
                <p className="font-display font-bold text-2xl text-azure-400 mt-1">{result.updated ?? 0}</p>
              </div>
            )}
            {mode === 'students' && (
              <div className="card p-4 text-center border-amber-500/20">
                <p className="label">Skipped</p>
                <p className="font-display font-bold text-2xl text-amber-400 mt-1">{result.skipped ?? 0}</p>
              </div>
            )}
            <div className="card p-4 text-center border-rose-500/20">
              <p className="label">Errors</p>
              <p className="font-display font-bold text-2xl text-rose-400 mt-1">
                {result.errors_count ?? result.errors?.length ?? 0}
              </p>
            </div>
          </div>

          {/* Created students with generated passwords */}
          {mode === 'students' && result.students && result.students.length > 0 && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="section-title text-emerald-400">
                  <CheckCircle size={15} className="inline mr-1" />
                  Created Students & Passwords
                </h3>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    const csv = ['Name,Student ID,Email,Password',
                      ...result.students!.map(s => `${s.name},${s.student_id},${s.email},${s.generated_password}`)
                    ].join('\n');
                    downloadBlob(new Blob([csv], { type: 'text/csv' }), 'new_students_credentials.csv');
                  }}
                >
                  <Download size={13} /> Save Credentials
                </Button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-surface">
                      {['Name', 'Student ID', 'Email', 'Generated Password'].map(h => (
                        <th key={h} className="text-left py-2 px-3 text-secondary font-display font-semibold uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.students.map((s, i) => (
                      <tr key={i} className="border-b border-surface">
                        <td className="py-2 px-3 text-primary font-medium">{s.name}</td>
                        <td className="py-2 px-3 font-mono text-secondary">{s.student_id}</td>
                        <td className="py-2 px-3 text-secondary">{s.email}</td>
                        <td className="py-2 px-3">
                          <code className="bg-surface-900 px-2 py-0.5 rounded text-emerald-400 font-mono">{s.generated_password}</code>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Skipped */}
          {result.skipped_detail && result.skipped_detail.length > 0 && (
            <div className="card p-5 border-amber-500/20">
              <h3 className="section-title text-amber-400 mb-3">
                <AlertCircle size={15} className="inline mr-1" />
                Skipped ({result.skipped_detail.length})
              </h3>
              <div className="flex flex-col gap-1.5">
                {result.skipped_detail.map((s, i) => (
                  <div key={i} className="flex items-center justify-between text-xs bg-surface-900 rounded-lg px-3 py-2">
                    <span className="text-secondary">Row {s.row}: {s.email ?? s.student_id}</span>
                    <span className="text-amber-400">{s.reason}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Errors */}
          {result.errors && result.errors.length > 0 && (
            <div className="card p-5 border-rose-500/20">
              <h3 className="section-title text-rose-400 mb-3">
                <XCircle size={15} className="inline mr-1" />
                Errors ({result.errors.length})
              </h3>
              <div className="flex flex-col gap-1.5 max-h-64 overflow-y-auto">
                {result.errors.map((e, i) => (
                  <div key={i} className="flex items-start justify-between gap-3 text-xs bg-surface-900 rounded-lg px-3 py-2">
                    <span className="text-secondary flex-shrink-0">
                      {e.row != null ? `Row ${e.row}` : ''}
                      {e.student_id ? ` · ${e.student_id}` : ''}
                    </span>
                    <span className="text-rose-400 text-right">{e.error}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
