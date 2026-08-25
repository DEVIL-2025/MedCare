import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, ShieldCheck, ArrowRight, Sparkles, Building2, User, Key } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const navigate = useNavigate();
  const { login, demoUsers } = useAuth();
  const [email, setEmail] = useState('aditi.rao@medcarepharma.com');
  const [password, setPassword] = useState('••••••••••••');
  const [loading, setLoading] = useState(false);

  function handleDirectLogin(e) {
    if (e) e.preventDefault();
    setLoading(true);
    setTimeout(() => {
      login(demoUsers[0]);
      navigate('/');
    }, 400);
  }

  function handleSelectRole(u) {
    login(u);
    navigate('/');
  }

  return (
    <div className="min-h-screen bg-cream-100 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        {/* Brand Header */}
        <div className="flex items-center justify-center gap-2 mb-3">
          <div className="w-10 h-10 rounded-lg bg-forest-700 flex items-center justify-center shadow-md">
            <Activity className="text-white w-6 h-6" />
          </div>
          <div>
            <span className="text-xl font-bold text-ink-900 tracking-tight">MedCare</span>
            <span className="text-xl font-light text-forest-700 ml-1">Pharma</span>
          </div>
        </div>
        <h2 className="text-center text-xl font-bold text-ink-900">
          Supply Chain Control Tower
        </h2>
        <p className="mt-1 text-center text-[13px] text-ink-500">
          Cognizant NPN SCM Hackathon Prototype (E1 + P1)
        </p>
      </div>

      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-6 px-4 shadow-card sm:rounded-lg sm:px-8 border border-ink-100 space-y-5">
          {/* Quick Demo 1-Click Role Logins */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-bold text-forest-800 uppercase tracking-wide flex items-center gap-1">
                <Sparkles size={12} className="text-forest-600" />
                Instant Role Access (1-Click)
              </span>
              <span className="text-[10.5px] text-ink-400">Demo Profiles</span>
            </div>
            <div className="space-y-2">
              {demoUsers.map((u) => (
                <button
                  key={u.id}
                  onClick={() => handleSelectRole(u)}
                  className="w-full flex items-center justify-between p-2.5 rounded-md border border-ink-100 hover:border-forest-600 hover:bg-forest-100/30 text-left transition-all group"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-full bg-forest-700 text-white flex items-center justify-center font-bold text-xs">
                      {u.avatar}
                    </div>
                    <div>
                      <div className="text-[13px] font-semibold text-ink-900 group-hover:text-forest-800">{u.name}</div>
                      <div className="text-[11px] text-ink-500">{u.role}</div>
                    </div>
                  </div>
                  <ArrowRight size={14} className="text-ink-400 group-hover:text-forest-700 transition-transform group-hover:translate-x-0.5" />
                </button>
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-ink-100" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-white px-2 text-ink-400 uppercase tracking-wider">or sign in with credentials</span>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleDirectLogin} className="space-y-3.5">
            <div>
              <label className="block text-[11px] font-medium text-ink-600">Email Address</label>
              <div className="mt-1 relative">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full text-[13px] border border-ink-100 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-forest-600"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-ink-600">Password</label>
              <div className="mt-1 relative">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full text-[13px] border border-ink-100 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-forest-600"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex justify-center items-center gap-2 py-2 px-4 border border-transparent rounded-md shadow-sm text-[13px] font-medium text-white bg-forest-700 hover:bg-forest-600 focus:outline-none transition-colors"
            >
              {loading ? 'Entering...' : 'Enter Control Tower Dashboard'}
            </button>
          </form>

          <div className="pt-2 border-t border-ink-100 text-center">
            <span className="text-[11px] text-ink-400 flex items-center justify-center gap-1">
              <ShieldCheck size={13} className="text-forest-600" />
              MedCare Pharma Multi-Echelon SCM Platform
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
