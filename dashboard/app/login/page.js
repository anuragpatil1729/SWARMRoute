'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from "../../lib/AuthContext";
import { supabase } from "../../lib/supabaseClient";

export default function LoginPage() {
  const router = useRouter();
  const { signIn } = useAuth();

  const [activeTab, setActiveTab] = useState('manager'); // 'manager' | 'partner'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setLoading(true);

    try {
      const data = await signIn({ email, password });
      
      // Determine destination route based on user profile or metadata
      const role = data.user?.user_metadata?.role || activeTab;
      if (role === 'partner') {
        router.push('/partner');
      } else {
        router.push('/');
      }
    } catch (err) {
      console.error('Login error:', err);
      // Give clear, friendly error messages
      if (err.message.includes('Invalid login credentials')) {
        setErrorMessage('Invalid email or password. If this is your first time, please Sign Up or use Demo Quick Login.');
      } else {
        setErrorMessage(err.message || 'Failed to sign in');
      }
    } finally {
      setLoading(false);
    }
  };

  const isDemoEnabled = process.env.NEXT_PUBLIC_ENABLE_DEMO_LOGIN === 'true';

  // Quick Demo Logins for evaluation (gated behind NEXT_PUBLIC_ENABLE_DEMO_LOGIN)
  const handleQuickDemoLogin = async (roleType) => {
    if (!isDemoEnabled) {
      setErrorMessage('Quick demo login is disabled in this deployment.');
      return;
    }
    setLoading(true);
    setErrorMessage('');

    const demoEmail = roleType === 'manager'
      ? process.env.NEXT_PUBLIC_DEMO_MANAGER_EMAIL
      : process.env.NEXT_PUBLIC_DEMO_PARTNER_EMAIL;
    const demoPassword = process.env.NEXT_PUBLIC_DEMO_PASSWORD;

    if (!demoEmail || !demoPassword) {
      setErrorMessage('Demo credentials not configured in environment variables (NEXT_PUBLIC_DEMO_...).');
      setLoading(false);
      return;
    }

    try {
      const data = await signIn({ email: demoEmail, password: demoPassword });
      const role = data.user?.user_metadata?.role || roleType;
      if (role === 'partner') {
        router.push('/partner');
      } else {
        router.push('/');
      }
    } catch (err) {
      console.error('Demo login error:', err);
      setErrorMessage(err.message || 'Demo authentication failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-center items-center px-4 py-12 relative overflow-hidden">
      {/* Dynamic Background Glows */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-tr from-cyan-500/10 via-indigo-500/10 to-violet-500/10 blur-[130px] rounded-full pointer-events-none -z-10" />
      
      <div className="w-full max-w-md">
        {/* Header Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full bg-slate-900/90 border border-cyan-500/30 text-cyan-400 text-xs font-semibold uppercase tracking-wider mb-4 shadow-lg shadow-cyan-950/40">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            SWARMRoute Supabase Cloud Auth
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            Welcome Back
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Log in to manage hyperlocal fleet mesh or access delivery cockpit
          </p>
        </div>

        {/* Role Tab Switcher */}
        <div className="grid grid-cols-2 p-1.5 mb-6 bg-slate-900/80 border border-slate-800 rounded-xl backdrop-blur-md">
          <button
            type="button"
            onClick={() => { setActiveTab('manager'); setErrorMessage(''); }}
            className={`py-2.5 px-4 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2 ${
              activeTab === 'manager'
                ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>🏢</span>
            <span>Company Manager</span>
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab('partner'); setErrorMessage(''); }}
            className={`py-2.5 px-4 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2 ${
              activeTab === 'partner'
                ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-md shadow-emerald-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>🛵</span>
            <span>Delivery Partner</span>
          </button>
        </div>

        {/* Card Form */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 sm:p-8 backdrop-blur-xl shadow-2xl relative">
          <div className="mb-4">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              {activeTab === 'manager' ? (
                <>
                  <span className="text-cyan-400">🏢</span> Manager Command Console
                </>
              ) : (
                <>
                  <span className="text-emerald-400">🛵</span> Delivery Partner Cockpit
                </>
              )}
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              {activeTab === 'manager'
                ? 'Allocate orders, monitor live battery mesh, coordinate dispatches.'
                : 'View assigned stops, accept P2P reassigned parcels, earn payouts.'}
            </p>
          </div>

          {errorMessage && (
            <div className="mb-5 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
              <span className="text-rose-400 mt-0.5">⚠️</span>
              <div>{errorMessage}</div>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
                Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={activeTab === 'manager' ? 'ops.manager@company.in' : 'partner@delivery.in'}
                className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wide">
                  Password
                </label>
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className={`w-full py-3 px-4 rounded-xl font-bold text-sm tracking-wide text-white transition-all shadow-lg flex items-center justify-center gap-2 ${
                activeTab === 'manager'
                  ? 'bg-gradient-to-r from-cyan-500 hover:from-cyan-400 to-blue-600 hover:to-blue-500 shadow-cyan-500/25'
                  : 'bg-gradient-to-r from-emerald-500 hover:from-emerald-400 to-teal-600 hover:to-teal-500 shadow-emerald-500/25'
              } ${loading ? 'opacity-70 cursor-not-allowed' : ''}`}
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Authenticating...</span>
                </>
              ) : (
                <span>Sign In as {activeTab === 'manager' ? 'Company Manager' : 'Delivery Partner'}</span>
              )}
            </button>
          </form>

          {/* Demo Login (Only rendered when NEXT_PUBLIC_ENABLE_DEMO_LOGIN === 'true') */}
          {isDemoEnabled && (
            <>
              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-800" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-slate-900/90 px-3 text-slate-500 font-mono">Or Instant Demo Access</span>
                </div>
              </div>

              <div className="space-y-2">
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => handleQuickDemoLogin(activeTab)}
                  className="w-full py-2.5 px-3 rounded-lg bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 text-xs font-semibold text-slate-200 flex items-center justify-center gap-2 transition-colors"
                >
                  <span>⚡</span>
                  <span>1-Click Demo {activeTab === 'manager' ? 'Manager' : 'Partner'}</span>
                </button>
              </div>
            </>
          )}
        </div>

        {/* Footer Navigation */}
        <p className="text-center text-xs text-slate-400 mt-6">
          Don't have an account yet?{' '}
          <Link
            href={`/signup?role=${activeTab}`}
            className="text-cyan-400 hover:text-cyan-300 font-semibold underline underline-offset-4"
          >
            Sign up for SWARMRoute
          </Link>
        </p>
      </div>
    </main>
  );
}
