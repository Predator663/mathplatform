import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { Users, Plus, Search, Edit2, Trash2, ToggleLeft, ToggleRight } from 'lucide-react';
import toast from 'react-hot-toast';
import { authApi } from '../../api';
import { LoadingPage, Table, Tr, Td, EmptyState, Button, Modal, Input, Select, Pagination } from '../../components/ui';
import { formatDate } from '../../utils';
import type { User, PaginatedResponse } from '../../types';
import { useAuthStore } from '../../store/auth';
import { useSiteSettingsStore } from '../../store/siteSettings';

interface UserForm {
  email: string; first_name: string; last_name: string;
  role: string; phone: string; password: string; confirm_password: string;
}
interface EditForm { first_name: string; last_name: string; role: string; phone: string; }

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super Admin', teacher: 'Teacher', student: 'Student', parent: 'Parent',
};
const ROLE_BADGE: Record<string, string> = {
  super_admin: 'badge-rose', teacher: 'badge-blue', student: 'badge-green', parent: 'badge-violet',
};
const ROLE_OPTIONS = [
  { value: 'teacher', label: 'Teacher' },
  { value: 'student', label: 'Student' },
  { value: 'parent', label: 'Parent' },
  { value: 'super_admin', label: 'Super Admin' },
];

export default function UsersPage() {
  const { user: currentUser } = useAuthStore();
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [editTarget, setEditTarget] = useState<User | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  const { getPage } = useSiteSettingsStore();
  const pageSize = getPage('users').page_size;

  const { data, isLoading } = useQuery<PaginatedResponse<User> | User[]>({
    queryKey: ['users', search, roleFilter, page, pageSize],
    queryFn: () => authApi.users({ search: search || undefined, role: roleFilter || undefined, page, page_size: pageSize }).then(r => r.data),
  });
  const users: User[] = Array.isArray(data) ? data : (data as PaginatedResponse<User>)?.results ?? [];
  const total: number = Array.isArray(data) ? data.length : (data as PaginatedResponse<User>)?.count ?? 0;

  // Create
  const { register, handleSubmit, reset, formState: { errors }, watch } = useForm<UserForm>();
  const pw = watch('password');
  const createMut = useMutation({
    mutationFn: (d: UserForm) => authApi.register(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); toast.success('User created'); setShowCreate(false); reset(); },
    onError: (err: unknown) => {
      const msgs = (err as { response?: { data?: Record<string, string[]> } })?.response?.data;
      if (msgs) Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      else toast.error('Failed to create user');
    },
  });

  // Edit
  const { register: regE, handleSubmit: handleE, reset: resetE, formState: { errors: eErr } } = useForm<EditForm>();
  const editMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: EditForm }) => authApi.updateUser(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); toast.success('User updated'); setEditTarget(null); },
    onError: () => toast.error('Failed to update user'),
  });

  // Toggle active
  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) => authApi.updateUser(id, { is_active }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['users'] });
      toast.success(vars.is_active ? 'User reactivated' : 'User deactivated');
    },
    onError: () => toast.error('Failed to update status'),
  });

  // Delete
  const deleteMut = useMutation({
    mutationFn: (id: number) => authApi.deleteUser(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); toast.success('User deleted'); setDeleteTarget(null); },
    onError: () => toast.error('Failed to delete user'),
  });

  const openEdit = (u: User) => {
    resetE({ first_name: u.first_name, last_name: u.last_name, role: u.role, phone: u.phone ?? '' });
    setEditTarget(u);
  };

  if (currentUser?.role !== 'super_admin') {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <p className="font-display font-semibold text-primary">Access Denied</p>
        <p className="text-muted">Only Super Admins can manage users.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 page-enter">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title">User Management</h1>
          <p className="text-muted mt-1">{total} users</p>
        </div>
        <Button onClick={() => setShowCreate(true)}><Plus size={15} /> Create User</Button>
      </div>

      <div className="card p-6">
        <div className="flex gap-3 mb-5 flex-wrap">
          <div className="relative flex-1 min-w-48">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary" />
            <input className="input pl-9 w-full" placeholder="Search name or email…" value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }} />
          </div>
          <select className="input w-40" value={roleFilter} onChange={e => { setRoleFilter(e.target.value); setPage(1); }}>
            <option value="">All Roles</option>
            {ROLE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {isLoading ? <LoadingPage /> : users.length === 0 ? (
          <EmptyState icon={<Users size={40} />} title="No users found" />
        ) : (
          <>
            <Table headers={['Name', 'Email', 'Role', 'Status', 'Joined', 'Actions']}>
              {users.map(u => (
                <Tr key={u.id}>
                  <Td>
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-azure-500 to-violet-500 flex items-center justify-center text-[10px] font-bold text-primary flex-shrink-0">
                        {u.first_name?.[0]}{u.last_name?.[0]}
                      </div>
                      <span className="font-medium text-primary">{u.full_name}</span>
                      {u.id === currentUser?.id && <span className="badge badge-blue text-[10px] px-1.5 py-0">you</span>}
                    </div>
                  </Td>
                  <Td className="text-secondary text-xs">{u.email}</Td>
                  <Td><span className={`badge ${ROLE_BADGE[u.role] ?? 'badge-blue'}`}>{ROLE_LABELS[u.role] ?? u.role}</span></Td>
                  <Td><span className={`badge ${u.is_active ? 'badge-green' : 'badge-rose'}`}>{u.is_active ? 'Active' : 'Inactive'}</span></Td>
                  <Td className="text-secondary text-xs">{formatDate(u.date_joined)}</Td>
                  <Td>
                    <div className="flex items-center gap-1">
                      <button onClick={() => openEdit(u)}
                        className="p-1.5 rounded-lg text-secondary hover:text-azure-400 hover:bg-azure-500/10 transition-colors" title="Edit">
                        <Edit2 size={13} />
                      </button>
                      {u.id !== currentUser?.id && (
                        <>
                          <button
                            onClick={() => toggleMut.mutate({ id: u.id, is_active: !u.is_active })}
                            className={`p-1.5 rounded-lg transition-colors ${u.is_active ? 'text-secondary hover:text-amber-400 hover:bg-amber-500/10' : 'text-secondary hover:text-emerald-400 hover:bg-emerald-500/10'}`}
                            title={u.is_active ? 'Deactivate' : 'Reactivate'}
                          >
                            {u.is_active ? <ToggleRight size={13} /> : <ToggleLeft size={13} />}
                          </button>
                          <button onClick={() => setDeleteTarget(u)}
                            className="p-1.5 rounded-lg text-secondary hover:text-rose-400 hover:bg-rose-500/10 transition-colors" title="Delete">
                            <Trash2 size={13} />
                          </button>
                        </>
                      )}
                    </div>
                  </Td>
                </Tr>
              ))}
            </Table>
            <Pagination page={page} pageSize={pageSize} total={total} onChange={setPage} className="mt-2" />
          </>
        )}
      </div>

      {/* Create modal */}
      <Modal open={showCreate} onClose={() => { setShowCreate(false); reset(); }} title="Create New User" size="md"
        footer={<><Button variant="secondary" onClick={() => { setShowCreate(false); reset(); }}>Cancel</Button>
          <Button loading={createMut.isPending} onClick={handleSubmit(d => createMut.mutate(d))}>Create User</Button></>}>
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input label="First Name" error={errors.first_name?.message} {...register('first_name', { required: 'Required' })} />
            <Input label="Last Name" error={errors.last_name?.message} {...register('last_name', { required: 'Required' })} />
          </div>
          <Input label="Email" type="email" error={errors.email?.message} {...register('email', { required: 'Required' })} />
          <Select label="Role" options={ROLE_OPTIONS} {...register('role', { required: true })} />
          <Input label="Phone (optional)" type="tel" {...register('phone')} />
          <Input label="Password" type="password" error={errors.password?.message}
            {...register('password', { required: 'Required', minLength: { value: 8, message: 'Min 8 characters' } })} />
          <Input label="Confirm Password" type="password" error={errors.confirm_password?.message}
            {...register('confirm_password', { required: 'Required', validate: v => v === pw || 'Passwords do not match' })} />
        </div>
      </Modal>

      {/* Edit modal */}
      <Modal open={!!editTarget} onClose={() => setEditTarget(null)} title={`Edit ${editTarget?.full_name}`} size="md"
        footer={<><Button variant="secondary" onClick={() => setEditTarget(null)}>Cancel</Button>
          <Button loading={editMut.isPending} onClick={handleE(d => editMut.mutate({ id: editTarget!.id, data: d }))}>Save Changes</Button></>}>
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input label="First Name" error={eErr.first_name?.message} {...regE('first_name', { required: 'Required' })} />
            <Input label="Last Name" error={eErr.last_name?.message} {...regE('last_name', { required: 'Required' })} />
          </div>
          <Select label="Role" options={ROLE_OPTIONS} {...regE('role', { required: true })} />
          <Input label="Phone" type="tel" {...regE('phone')} />
          <p className="text-xs text-secondary">To change the password, ask the user to use the Change Password option in their own Settings page.</p>
        </div>
      </Modal>

      {/* Delete confirm modal */}
      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete User"
        footer={<><Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button loading={deleteMut.isPending} onClick={() => deleteMut.mutate(deleteTarget!.id)}
            className="!bg-rose-500 !text-white hover:!bg-rose-600">Delete</Button></>}>
        <p className="text-sm text-secondary">
          Are you sure you want to permanently delete <strong className="text-primary">{deleteTarget?.full_name}</strong>?
          This will remove all their data. This cannot be undone.
        </p>
      </Modal>
    </div>
  );
}
