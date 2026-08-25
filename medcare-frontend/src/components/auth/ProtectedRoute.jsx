import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { ShieldAlert, ArrowLeft } from 'lucide-react';
import LoadingState from '../ui/LoadingState';

export default function ProtectedRoute({ children, requireAdmin = false }) {
  const { user, loading, isAuthenticated, isAdmin } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen bg-cream-100 flex items-center justify-center">
        <LoadingState message="Verifying secure authentication session with PostgreSQL..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requireAdmin && !isAdmin) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center p-6 text-center">
        <div className="w-14 h-14 rounded-full bg-brick-100 flex items-center justify-center text-brick-600 mb-4 shadow-sm">
          <ShieldAlert size={28} />
        </div>
        <h2 className="text-xl font-bold text-ink-900 mb-1">403 Forbidden — Access Denied</h2>
        <p className="text-[13px] text-ink-500 max-w-md mb-6">
          You are currently signed in as a <span className="font-semibold text-forest-700">{user?.roleLabel || user?.role}</span>.
          This module is restricted strictly to Administrator privileges.
        </p>
        <a
          href="/"
          className="inline-flex items-center gap-2 px-4 py-2 bg-forest-700 hover:bg-forest-800 text-white text-[13px] font-medium rounded-md transition-colors shadow-sm"
        >
          <ArrowLeft size={15} /> Return to Operational Dashboard
        </a>
      </div>
    );
  }

  return children;
}
