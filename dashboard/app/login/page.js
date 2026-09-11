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
    <main className="min-h-screen bg-slate-50 flex flex-col justify-center items-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Header Branding */}
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Welcome Back
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            Sign in to manage fleet operations or access your delivery cockpit
          </p>
        </div>

        {/* Role Tab Switcher */}
        <div className="grid grid-cols-2 p-1 mb-6 bg-slate-100 border border-slate-200 rounded-lg">
          <button
            type="button"
            onClick={() => { setActiveTab('manager'); setErrorMessage(''); }}
            className={`py-2 px-3 text-xs font-semibold rounded-md transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'manager'
                ? 'bg-white text-blue-700 shadow-xs border border-slate-200 font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>🏢</span>
            <span>Company Manager</span>
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab('partner'); setErrorMessage(''); }}
            className={`py-2 px-3 text-xs font-semibold rounded-md transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'partner'
                ? 'bg-white text-emerald-700 shadow-xs border border-slate-200 font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>🛵</span>
            <span>Delivery Partner</span>
          </button>
        </div>

        {/* Card Form */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 sm:p-8 shadow-sm">
          <div className="mb-5 pb-4 border-b border-slate-100">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              {activeTab === 'manager' ? (
                <>
                  <span>🏢</span> Manager Command Console
                </>
              ) : (
                <>
                  <span>🛵</span> Delivery Partner Cockpit
                </>
              )}
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              {activeTab === 'manager'
                ? 'Allocate orders, monitor live battery mesh, coordinate dispatches.'
                : 'View assigned stops, accept P2P reassigned parcels, earn payouts.'}
            </p>
          </div>

          {errorMessage && (
            <div className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
              <span className="text-rose-600 font-bold mt-0.5">⚠️</span>
              <div>{errorMessage}</div>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={activeTab === 'manager' ? 'ops.manager@company.in' : 'partner@delivery.in'}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs font-semibold text-slate-700">
                  Password
                </label>
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className={`w-full mt-2 py-2.5 px-4 rounded-lg font-bold text-xs tracking-wide text-white transition shadow-xs flex items-center justify-center gap-2 ${
                activeTab === 'manager'
                  ? 'bg-blue-600 hover:bg-blue-700'
                  : 'bg-emerald-600 hover:bg-emerald-700'
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
              <div className="relative my-5">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-100" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-white px-2.5 text-slate-400 font-mono text-[11px]">Instant Demo Access</span>
                </div>
              </div>

              <div className="space-y-2">
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => handleQuickDemoLogin(activeTab)}
                  className="w-full py-2 px-3 rounded-lg bg-slate-50 hover:bg-slate-100 border border-slate-200 text-xs font-semibold text-slate-700 flex items-center justify-center gap-2 transition"
                >
                  <span>⚡</span>
                  <span>1-Click Demo {activeTab === 'manager' ? 'Manager' : 'Partner'}</span>
                </button>
              </div>
            </>
          )}
        </div>

        {/* Footer Navigation */}
        <p className="text-center text-xs text-slate-500 mt-5">
          Don't have an account yet?{' '}
          <Link
            href={`/signup?role=${activeTab}`}
            className="text-blue-600 hover:text-blue-700 font-semibold underline underline-offset-2"
          >
            Sign up for SWARMRoute
          </Link>
        </p>
      </div>
    </main>
  );
}
