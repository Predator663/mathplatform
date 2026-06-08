import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { Users, Plus, Search } from 'lucide-react';
import toast from 'react-hot-toast';
import { authApi } from '../../api';
import { LoadingPage, Table, Tr, Td, EmptyState, Button, Modal, Input, Select, Pagination } from '../../components/ui';
import { formatDate } from '../../utils';
import type { User, PaginatedResponse } from '../../types';
import { useAuthStore } from '../../store/auth';
import { useSiteSettingsStore } from '../../store/siteSettings';

interface CreateUserForm {
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  phone: string;
  password: string;
  confirm_password: string;
}

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super Admin',
  teacher: 'Teacher',
  student: 'Student',
  parent: 'Parent',
};

const ROLE_BADGE: Record<string, string> = {
  super_admin: 'badge-rose',
  teacher: 'badge-blue',
  student: 'badge-green',
  parent: 'badge-violet',
};

export default function UsersPage() {
  const { user: currentUser } = useAuthStore();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [page, setPage] = useState(1);
  const { getPage } = useSiteSettingsStore();
  const pageSize = getPage('users').page_size;

  const { data, isLoading } = useQuery<PaginatedResponse<User> | User[]>({
    queryKey: ['users', search, roleFilter, page, pageSize],
    queryFn: () => authApi.users({
      search: search || undefined,
      role: roleFilter || undefined,
      page,
      page_size: pageSize,
    }).then(r => r.data),
  });
  const users: User[] = Array.isArray(data) ? data : (data as PaginatedResponse<User>)?.results ?? [];
  const total: number = Array.isArray(data) ? data.length : (data as PaginatedResponse<User>)?.count ?? 0;

  const { register, handleSubmit, reset, formState: { errors }, watch } = useForm<CreateUserForm>();
  const password = watch('password');

  const createMutation = useMutation({
    mutationFn: (d: CreateUserForm) => authApi.register(d),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('User created!');
      setShowCreate(false);
      reset();
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: Record<string, string[]> } };
      const msgs = error?.response?.data;
      if (msgs) Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      else toast.error('Failed to create user');
    },
  });

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
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="page-title">User Management</h1>
          <p className="text-muted mt-1">{total} users in the system</p>
        </div>
        <Button onClick={() => setShowCreate(true)} size="sm">
          <Plus size={15} /> <span className="hidden sm:inline">Create </span>User
        </Button>
      </div>

      <div className="card p-6">
        {/* Filters */}
        <div className="flex flex-wrap gap-3 mb-5">
          <div className="relative flex-1 max-w-sm">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary" />
            <input
              className="input pl-9"
              placeholder="Search by name or email..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <select
            className="input w-40"
            value={roleFilter}
            onChange={e => setRoleFilter(e.target.value)}
          >
            <option value="">All Roles</option>
            <option value="super_admin">Super Admin</option>
            <option value="teacher">Teacher</option>
            <option value="student">Student</option>
            <option value="parent">Parent</option>
          </select>
        </div>

        {isLoading ? <LoadingPage /> : users.length === 0 ? (
          <EmptyState icon={<Users size={40} />} title="No users found" />
        ) : (
          <>
          <Table headers={['Name', 'Email', 'Role', 'Status', 'Joined', '']}>
            {users.map(u => (
              <Tr key={u.id}>
                <Td>
                  <div className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-azure-500 to-violet-500 flex items-center justify-center text-[10px] font-display font-bold text-primary flex-shrink-0">
                      {u.first_name?.[0]}{u.last_name?.[0]}
                    </div>
                    <span className="font-medium text-primary">{u.full_name}</span>
                    {u.id === currentUser?.id && (
                      <span className="badge badge-blue text-[10px] px-1.5 py-0">you</span>
                    )}
                  </div>
                </Td>
                <Td className="text-secondary text-xs">{u.email}</Td>
                <Td>
                  <span className={`badge ${ROLE_BADGE[u.role] ?? 'badge-blue'}`}>
                    {ROLE_LABELS[u.role] ?? u.role}
                  </span>
                </Td>
                <Td>
                  <span className={`badge ${u.is_active ? 'badge-green' : 'badge-rose'}`}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </Td>
                <Td className="text-secondary text-xs">{formatDate(u.date_joined)}</Td>
                <Td className="text-secondary text-xs">{u.phone || '—'}</Td>
              </Tr>
            ))}
          </Table>
          <Pagination page={page} pageSize={pageSize} total={total} onChange={setPage} className="mt-2" />
          </>
        )}
      </div>

      {/* Create User Modal */}
      <Modal
        open={showCreate}
        onClose={() => { setShowCreate(false); reset(); }}
        title="Create New User"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => { setShowCreate(false); reset(); }}>Cancel</Button>
            <Button
              loading={createMutation.isPending}
              onClick={handleSubmit(d => createMutation.mutate(d))}
            >
              Create User
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="First Name"
              error={errors.first_name?.message}
              {...register('first_name', { required: 'Required' })}
            />
            <Input
              label="Last Name"
              error={errors.last_name?.message}
              {...register('last_name', { required: 'Required' })}
            />
          </div>
          <Input
            label="Email"
            type="email"
            error={errors.email?.message}
            {...register('email', { required: 'Required' })}
          />
          <Select
            label="Role"
            options={[
              { value: 'teacher', label: 'Teacher' },
              { value: 'student', label: 'Student' },
              { value: 'parent', label: 'Parent' },
              { value: 'super_admin', label: 'Super Admin' },
            ]}
            {...register('role', { required: true })}
          />
          <Input
            label="Phone (optional)"
            type="tel"
            {...register('phone')}
          />
          <Input
            label="Password"
            type="password"
            error={errors.password?.message}
            {...register('password', { required: 'Required', minLength: { value: 8, message: 'Min 8 characters' } })}
          />
          <Input
            label="Confirm Password"
            type="password"
            error={errors.confirm_password?.message}
            {...register('confirm_password', {
              required: 'Required',
              validate: val => val === password || 'Passwords do not match',
            })}
          />
        </div>
      </Modal>
    </div>
  );
}
