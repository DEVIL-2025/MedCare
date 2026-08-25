import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Activity, ShieldCheck, AlertCircle, KeyRound, Lock, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import Modal from '../components/ui/Modal';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, changePassword } = useAuth();

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // Must change password modal
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
      setErrorMessage('Please enter your User ID or Email, and Password.');
      return;
    }
    executeLogin(identifier.trim(), password);
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
          Enterprise Multi-Echelon SCM Platform
        </p>
      </div>

      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-6 px-4 shadow-card sm:rounded-lg sm:px-8 border border-ink-100 space-y-5">
          {/* Error Banner */}
          {errorMessage && (
            <div className="p-3 bg-brick-100 border border-brick-200 text-brick-800 text-[12.5px] rounded-md flex items-start gap-2">
              <AlertCircle size={15} className="text-brick-600 shrink-0 mt-0.5" />
              <div>{errorMessage}</div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[12px] font-semibold text-ink-700">
                Email Address or User ID
              </label>
              <div className="mt-1 relative">
                <input
                  type="text"
                  required
                  autoFocus
                  placeholder="Enter User ID or Email"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  className="w-full text-[13px] border border-ink-200 rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-forest-600 bg-white"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label className="block text-[12px] font-semibold text-ink-700">Password</label>
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-[11px] text-ink-400 hover:text-ink-600 flex items-center gap-1 cursor-pointer"
                >
                  {showPassword ? <EyeOff size={12} /> : <Eye size={12} />}
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              <div className="mt-1 relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full text-[13px] border border-ink-200 rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-forest-600 bg-white"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex justify-center items-center gap-2 py-2.5 px-4 border border-transparent rounded-md shadow-sm text-[13px] font-medium text-white bg-forest-700 hover:bg-forest-600 focus:outline-none transition-colors cursor-pointer disabled:opacity-60 mt-2"
            >
              {loading ? 'Authenticating...' : 'Sign In to Control Tower'}
            </button>
          </form>

          <div className="pt-3 border-t border-ink-100 text-center">
            <span className="text-[11px] text-ink-400 flex items-center justify-center gap-1">
              <ShieldCheck size={13} className="text-forest-600" />
              Role-Based Access Control & Persistent Audit Logging Active
            </span>
          </div>
        </div>
      </div>

      {/* Modal: Must Change Temporary Password */}
      <Modal
        open={mustChangeModalOpen}
        onClose={() => {}}
        title="First-Time Login: Set Permanent Password"
      >
        <form onSubmit={handleChangePasswordSubmit} className="space-y-3.5 text-[13px]">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-md text-amber-900 text-[12px] flex items-start gap-2">
            <KeyRound size={15} className="text-amber-700 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Password Reset Required:</span> You have logged in using a temporary password. Please set a secure permanent password to continue.
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
              className="w-full mt-1 px-3 py-1.5 border border-ink-200 rounded-md text-[12.5px] focus:outline-none focus:ring-1 focus:ring-forest-600"
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
              className="w-full mt-1 px-3 py-1.5 border border-ink-200 rounded-md text-[12.5px] focus:outline-none focus:ring-1 focus:ring-forest-600"
            />
          </div>

          <button
            type="submit"
            disabled={changePwdLoading}
            className="w-full py-2 bg-forest-700 hover:bg-forest-600 text-white rounded-md text-[13px] font-medium transition-colors shadow-sm cursor-pointer mt-2"
          >
            {changePwdLoading ? 'Saving Password...' : 'Save Password & Enter Dashboard'}
          </button>
        </form>
      </Modal>
    </div>
  );
}
