import { Moon, Sun } from 'lucide-react';
import { useThemeStore } from '../../store/theme';

interface ThemeToggleProps {
  className?: string;
}

export default function ThemeToggle({ className = '' }: ThemeToggleProps) {
  const { theme, toggleTheme } = useThemeStore();
  const isDark = theme === 'dark';

  return (
    <button
      onClick={toggleTheme}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className={`relative w-11 h-6 rounded-full transition-colors duration-300 focus:outline-none focus:ring-2 focus:ring-azure-500/50 flex-shrink-0 ${
        isDark ? 'bg-surface-600' : 'bg-azure-500/30'
      } ${className}`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full flex items-center justify-center transition-all duration-300 shadow-md ${
          isDark
            ? 'translate-x-0 bg-surface-500'
            : 'translate-x-5 bg-azure-500'
        }`}
      >
        {isDark
          ? <Moon size={11} className="text-white" />
          : <Sun  size={11} className="text-white" />
        }
      </span>
    </button>
  );
}
