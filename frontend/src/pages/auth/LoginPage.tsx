import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import { authApi } from '../../api';
import api from '../../api';
import { useAuthStore } from '../../store/auth';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { Button, Input } from '../../components/ui';
import type { LoginResponse } from '../../types';

interface LoginForm {
  email: string;
  password: string;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const { settings, setSettings } = useSiteSettingsStore();
  const [loading, setLoading] = useState(false);

  // Fetch site settings so login page reflects branding changes
  useEffect(() => {
    api.get('/auth/settings/').then(r => {
      setSettings(r.data);
      if (r.data.favicon_url) {
        let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']");
        if (!link) { link = document.createElement('link'); link.rel = 'icon'; document.head.appendChild(link); }
        link.href = r.data.favicon_url;
      }
      if (r.data.platform_name) {
        document.title = r.data.platform_subtitle
          ? `${r.data.platform_name} — ${r.data.platform_subtitle}`
          : r.data.platform_name;
      }
    }).catch(() => {});
  }, []);

  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>();

  const onSubmit = async (data: LoginForm) => {
    setLoading(true);
    try {
      const res = await authApi.login(data.email, data.password);
      const { access, refresh, user } = res.data as LoginResponse;
      setAuth(user, access, refresh);
      toast.success(`Welcome back, ${user.first_name}!`);
      navigate('/dashboard');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      toast.error(error?.response?.data?.detail || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  const platformName = settings.platform_name || 'MathPlatform';
  const logoLetter  = settings.logo_letter  || 'Σ';
  const tagline     = settings.login_tagline || 'Student Performance Analytics';
  const welcome     = settings.login_welcome || 'Sign in to your account';
  const showGlow    = settings.login_bg_gradient !== false;

  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center p-4">
      {/* Ambient glow */}
      {showGlow && (
        <div className="fixed top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-azure-500/10 rounded-full blur-3xl pointer-events-none" />
      )}

      <div className="relative w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          {settings.logo_url ? (
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl shadow-glow-blue mb-4 bg-surface-800 border border-surface overflow-hidden">
              <img
                src={settings.logo_url}
                alt={platformName}
                className="w-full h-full object-contain"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
            </div>
          ) : (
            <div className="inline-flex items-center justify-center w-14 h-14 bg-azure-500 rounded-2xl shadow-glow-blue mb-4">
              <span className="font-display font-black text-2xl text-white">{logoLetter}</span>
            </div>
          )}
          <h1 className="font-display font-bold text-2xl text-primary">{platformName}</h1>
          <p className="text-secondary mt-1 text-sm">{tagline}</p>
        </div>

        {/* Card */}
        <div className="card p-8">
          <h2 className="font-display font-semibold text-lg text-primary mb-6">{welcome}</h2>

          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
            <Input
              label="Email address"
              type="email"
              placeholder="you@mathplatform.edu"
              error={errors.email?.message}
              {...register('email', {
                required: 'Email is required',
                pattern: { value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: 'Invalid email' },
              })}
            />

            <Input
              label="Password"
              type="password"
              placeholder="••••••••"
              error={errors.password?.message}
              {...register('password', { required: 'Password is required' })}
            />

            <Button type="submit" loading={loading} className="w-full mt-2">
              Sign In
            </Button>
          </form>
        </div>

        {settings.footer_text && (
          <p className="text-center text-xs text-secondary mt-6 px-2">{settings.footer_text}</p>
        )}
      </div>
    </div>
  );
}
