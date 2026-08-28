import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Cross, Mail, Lock, Eye, EyeOff, ArrowRight, AlertCircle, ShieldCheck, KeyRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import Modal from '../components/ui/Modal';

const GOLD = '#E8C468';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, changePassword, demoProfiles } = useAuth();

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // First-time login: Must change temporary password modal
  const [mustChangeModalOpen, setMustChangeModalOpen] = useState(false);
  const [currentTempPwd, setCurrentTempPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confirmPwd, setConfirmPwd] = useState('');
  const [changePwdLoading, setChangePwdLoading] = useState(false);
  const [changePwdError, setChangePwdError] = useState(null);

  const fromPath = location.state?.from?.pathname || '/';

  async function executeLogin(idVal, pwdVal) {
    setLoading(true);
    setErrorMessage(null);
    try {
      const user = await login(idVal, pwdVal);
      if (user.must_change_password) {
        setCurrentTempPwd(pwdVal);
        setMustChangeModalOpen(true);
      } else {
        navigate(fromPath, { replace: true });
      }
    } catch (err) {
      console.error('Login error:', err);
      setErrorMessage(err.message || 'Invalid Email / User ID or Password.');
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e) {
    if (e) e.preventDefault();
    if (!identifier.trim() || !password) {
      setErrorMessage('Please enter your Email or User ID, and Password.');
      return;
    }
    executeLogin(identifier.trim(), password);
  }

  function handleQuickFill(profile) {
    setIdentifier(profile.identifier);
    setPassword(profile.password);
    setErrorMessage(null);
  }

  async function handleChangePasswordSubmit(e) {
    if (e) e.preventDefault();
    if (newPwd.length < 6) {
      setChangePwdError('New password must be at least 6 characters in length.');
      return;
    }
    if (newPwd !== confirmPwd) {
      setChangePwdError('New password and confirmation do not match.');
      return;
    }

    setChangePwdLoading(true);
    setChangePwdError(null);
    try {
      await changePassword(currentTempPwd, newPwd);
      setMustChangeModalOpen(false);
      navigate(fromPath, { replace: true });
    } catch (err) {
      setChangePwdError(err.message || 'Failed to change password. Please verify current temporary password.');
    } finally {
      setChangePwdLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex bg-cream font-sans text-ink-900">
      {/* Left: dashboard-preview scene */}
      <div className="hidden lg:flex flex-1 relative overflow-hidden flex-col">
        <div className="relative flex-1 overflow-hidden bg-gradient-to-br from-forest-500 via-forest-700 to-forest-900">
          {/* Subtle dot texture */}
          <div
            className="absolute inset-0 opacity-[0.06]"
            style={{ backgroundImage: 'radial-gradient(#DCE9E1 1px, transparent 1px)', backgroundSize: '24px 24px' }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/25 via-transparent to-white/5" />

          {/* Top bar */}
          <div className="relative z-10 flex items-center px-8 pt-6">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-md bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-sm shadow-emerald-950/50">
                <Cross size={14} className="text-white fill-white" />
              </div>
              <div>
                <div className="text-[13.5px] font-semibold leading-tight tracking-tight text-white">
                  MedCare Pharma
                </div>
                <div className="text-[10px] text-emerald-300/80 tracking-wide font-medium">Control Tower Platform</div>
              </div>
            </div>
          </div>

          {/* Headline */}
          <div className="relative z-10 px-8 pt-10">
            <h2 className="text-[30px] xl:text-[36px] font-extrabold uppercase tracking-tight leading-[1.05] text-white font-sans">
              Plan smarter.<br />Execute faster.<br />Deliver better.
            </h2>
          </div>

          {/* Conveyor + box scene */}
          <div className="relative h-48 mt-10 px-8">
            <div className="absolute right-8 top-1/2 -translate-y-1/2 w-32 h-28 z-10">
              <svg viewBox="0 0 160 140" className="w-full h-full drop-shadow-[0_12px_20px_rgba(0,0,0,0.35)]">
                <rect x="10" y="20" width="140" height="100" rx="4" fill="#0B4A3A" stroke="#1E9270" strokeWidth="2" />
                <rect x="18" y="28" width="124" height="84" rx="2" fill="#062E24" />
                {Array.from({ length: 6 }).map((_, i) => (
                  <line key={i} x1={30 + i * 20} y1="28" x2={30 + i * 20} y2="112" stroke="#123A2D" strokeWidth="2" />
                ))}
                <text x="80" y="16" textAnchor="middle" fill={GOLD} fontSize="11" fontWeight="700" fontFamily="'Plus Jakarta Sans', sans-serif" letterSpacing="0.05em">
                  MEDCARE
                </text>
              </svg>
            </div>

            {/* Belt */}
            <div className="absolute left-8 right-[160px] bottom-6 h-3 rounded-full overflow-hidden bg-forest-800 shadow-inner">
              <div
                className="h-full w-[200%] animate-belt-scroll"
                style={{
                  backgroundImage: 'repeating-linear-gradient(90deg, #1E9270 0px, #1E9270 16px, transparent 16px, transparent 32px)',
                }}
              />
            </div>

            {/* Box track — spans exactly from the belt start to the container mouth */}
            <div className="absolute left-8 right-[160px] bottom-9 h-10 overflow-visible pointer-events-none">
              <div className="absolute bottom-0 w-9 h-9 rounded-sm bg-gold-500 border-2 border-gold-700 animate-box-move-1 shadow-[0_6px_12px_rgba(0,0,0,0.3)] flex flex-col justify-between p-0.5">
                <div className="w-full h-1 bg-gold-700/40 rounded-t-xs" />
                <div className="w-full h-[2px] bg-gold-700/60 my-auto" />
              </div>
              <div className="absolute bottom-0 w-8 h-8 rounded-sm bg-gold-600 border-2 border-gold-700 animate-box-move-2 shadow-[0_6px_12px_rgba(0,0,0,0.3)] flex flex-col justify-between p-0.5">
                <div className="w-full h-1 bg-gold-700/40 rounded-t-xs" />
                <div className="w-full h-[2px] bg-gold-700/60 my-auto" />
              </div>
              <div className="absolute bottom-0 w-10 h-7 rounded-sm bg-gold-500 border-2 border-gold-700 animate-box-move-3 shadow-[0_6px_12px_rgba(0,0,0,0.3)] flex flex-col justify-between p-0.5">
                <div className="w-full h-1 bg-gold-700/40 rounded-t-xs" />
                <div className="w-full h-[2px] bg-gold-700/60 my-auto" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right: form */}
      <div className="w-full lg:w-[440px] xl:w-[460px] flex flex-col justify-center px-8 sm:px-14 py-12 shrink-0">
        <Link to="/" className="flex items-center gap-2.5 mb-10 group">
          <div className="w-9 h-9 rounded-md bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-sm shadow-emerald-950/40">
            <Cross size={16} className="text-white fill-white" />
          </div>
          <div>
            <div className="text-[16px] font-bold leading-tight tracking-tight text-ink-900">
              MedCare <span className="font-light text-forest-700">Pharma</span>
            </div>
            <div className="text-[11px] text-ink-500 tracking-wide font-medium">Control Tower Platform</div>
          </div>
        </Link>

        <h1 className="text-[26px] font-semibold text-ink-900 tracking-tight mb-2">Welcome back</h1>
        <p className="text-[13.5px] text-ink-500 mb-6">Sign in to your supply chain control tower.</p>

        {/* Error message banner */}
        {errorMessage && (
          <div className="mb-5 p-3 bg-brick-100 border border-brick-200 text-brick-700 text-[12.5px] rounded-md flex items-start gap-2">
            <AlertCircle size={15} className="text-brick-600 shrink-0 mt-0.5" />
            <div className="leading-snug">{errorMessage}</div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-[12px] font-medium text-ink-700 block mb-1.5">Email or User ID</label>
            <div className="relative">
              <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-300" />
              <input
                type="text"
                required
                autoFocus
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="you@medcarepharma.com or User ID"
                className="w-full pl-9 pr-3 py-2.5 text-[13.5px] bg-white border border-ink-100 rounded-md focus:outline-none focus:ring-2 focus:ring-forest-500/25 focus:border-forest-600 transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="text-[12px] font-medium text-ink-700 block mb-1.5">Password</label>
            <div className="relative">
              <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-300" />
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-9 py-2.5 text-[13.5px] bg-white border border-ink-100 rounded-md focus:outline-none focus:ring-2 focus:ring-forest-500/25 focus:border-forest-600 transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-300 hover:text-ink-600 cursor-pointer p-1"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-1.5 text-[13.5px] font-medium bg-forest-700 text-white rounded-md py-2.5 hover:bg-forest-600 transition-colors disabled:opacity-60 cursor-pointer shadow-sm mt-2"
          >
            {loading ? 'Authenticating...' : (
              <>
                Sign In <ArrowRight size={14} />
              </>
            )}
          </button>
        </form>

        {/* Demo Quick-Fill Credentials */}
        {demoProfiles && demoProfiles.length > 0 && (
          <div className="mt-6 pt-5 border-t border-ink-100">
            <div className="text-[11.5px] font-medium text-ink-500 mb-2">Quick demo access:</div>
            <div className="flex flex-wrap gap-2">
              {demoProfiles.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => handleQuickFill(p)}
                  className="px-2.5 py-1 text-[11.5px] bg-cream-200/80 hover:bg-cream-200 border border-ink-100 hover:border-forest-500/40 rounded text-ink-700 font-medium transition-colors cursor-pointer"
                >
                  {p.name.split(' ')[0]} ({p.role})
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="mt-8 pt-4 border-t border-ink-100 flex items-center justify-center gap-1.5 text-[11px] text-ink-400">
          <ShieldCheck size={13} className="text-forest-600 shrink-0" />
          <span>Role-Based Access Control & Audit Trail Active</span>
        </div>
      </div>

      {/* Modal: Must Change Temporary Password */}
      <Modal
        open={mustChangeModalOpen}
        onClose={() => {}}
        title="First-Time Login: Set Permanent Password"
      >
        <form onSubmit={handleChangePasswordSubmit} className="space-y-3.5 text-[13px]">
          <div className="p-3 bg-amber2-100 border border-amber2-600/20 rounded-md text-amber2-700 text-[12px] flex items-start gap-2">
            <KeyRound size={15} className="text-amber2-700 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Password Reset Required:</span> You have logged in using a temporary password. Please set a secure permanent password to continue.
            </div>
          </div>

          {changePwdError && (
            <div className="p-2.5 bg-brick-100 text-brick-700 text-[12px] rounded-md border border-brick-200 flex items-center gap-2">
              <AlertCircle size={14} className="shrink-0" />
              <span>{changePwdError}</span>
            </div>
          )}

          <div>
            <label className="block text-[11.5px] font-semibold text-ink-700">New Password</label>
            <input
              type="password"
              required
              minLength={6}
              placeholder="Minimum 6 characters"
              value={newPwd}
              onChange={(e) => setNewPwd(e.target.value)}
              className="w-full mt-1 px-3 py-1.5 border border-ink-200 rounded-md text-[12.5px] focus:outline-none focus:ring-1 focus:ring-forest-600 bg-white"
            />
          </div>

          <div>
            <label className="block text-[11.5px] font-semibold text-ink-700">Confirm New Password</label>
            <input
              type="password"
              required
              minLength={6}
              placeholder="Re-enter new password"
              value={confirmPwd}
              onChange={(e) => setConfirmPwd(e.target.value)}
              className="w-full mt-1 px-3 py-1.5 border border-ink-200 rounded-md text-[12.5px] focus:outline-none focus:ring-1 focus:ring-forest-600 bg-white"
            />
          </div>

          <button
            type="submit"
            disabled={changePwdLoading}
            className="w-full py-2 bg-forest-700 hover:bg-forest-600 text-white rounded-md text-[13px] font-medium transition-colors shadow-sm cursor-pointer mt-2 disabled:opacity-60"
          >
            {changePwdLoading ? 'Saving Password...' : 'Save Password & Enter Dashboard'}
          </button>
        </form>
      </Modal>
    </div>
  );
}
