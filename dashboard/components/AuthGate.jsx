'use client';

import React, { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '../lib/AuthContext';

// Pages that redirect already-authenticated users to their dashboard
const AUTH_ROUTES = ['/login', '/signup'];

// Public pages accessible to all users (guests, fleet managers, and delivery partners)
const PUBLIC_OPEN_ROUTES = ['/customer'];

// Routes accessible to delivery partners
const PARTNER_ALLOWED_ROUTES = ['/partner', '/network'];

export default function AuthGate({ children }) {
  const { user, role, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const isAuthRoute = AUTH_ROUTES.includes(pathname);
  const isOpenRoute = PUBLIC_OPEN_ROUTES.includes(pathname);
  const isProtectedRoute = !isAuthRoute && !isOpenRoute;

  useEffect(() => {
    if (loading) return;

    if (!user && isProtectedRoute) {
      // Unauthenticated access to protected route: redirect immediately to /login
      router.replace('/login');
    } else if (user && isAuthRoute) {
      // Authenticated user on /login or /signup: redirect to appropriate home
      if (role === 'partner') {
        router.replace('/partner');
      } else {
        router.replace('/');
      }
    } else if (user && role === 'partner' && !PARTNER_ALLOWED_ROUTES.includes(pathname) && !isOpenRoute) {
      // Delivery partner attempting to access manager/admin screens: redirect to partner cockpit
      router.replace('/partner');
    }
  }, [user, role, loading, pathname, isAuthRoute, isOpenRoute, isProtectedRoute, router]);

  // While checking auth state for a protected route, show loader
  if (loading && isProtectedRoute) {
    return (
      <div className="min-h-[50vh] flex flex-col items-center justify-center space-y-4">
        <div className="w-9 h-9 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
        <div className="text-center">
          <p className="text-xs font-semibold text-slate-700">Verifying session credentials...</p>
          <p className="text-[11px] font-mono text-slate-400 mt-0.5">SWARMRoute Autonomous Security Mesh</p>
        </div>
      </div>
    );
  }

  // If unauthenticated and on a protected route, block rendering until router.replace finishes
  if (!user && isProtectedRoute) {
    return (
      <div className="min-h-[50vh] flex flex-col items-center justify-center space-y-4">
        <div className="w-9 h-9 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
        <div className="text-center">
          <p className="text-xs font-semibold text-slate-700">Authentication Required</p>
          <p className="text-[11px] font-mono text-slate-400 mt-0.5">Redirecting to Sign In...</p>
        </div>
      </div>
    );
  }

  // If authenticated user is on /login or /signup, block until redirect completes
  if (user && isAuthRoute) {
    return (
      <div className="min-h-[50vh] flex flex-col items-center justify-center space-y-4">
        <div className="w-9 h-9 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin"></div>
        <div className="text-center">
          <p className="text-xs font-semibold text-slate-700">
            Authenticated as {role === 'partner' ? 'Delivery Partner' : 'Fleet Manager'}
          </p>
          <p className="text-[11px] font-mono text-slate-400 mt-0.5">Redirecting to operational console...</p>
        </div>
      </div>
    );
  }

  // If partner user on admin route, block until redirected to partner cockpit
  if (user && role === 'partner' && !PARTNER_ALLOWED_ROUTES.includes(pathname) && !isOpenRoute) {
    return (
      <div className="min-h-[50vh] flex flex-col items-center justify-center space-y-4">
        <div className="w-9 h-9 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin"></div>
        <div className="text-center">
          <p className="text-xs font-semibold text-slate-700">Redirecting to Delivery Cockpit...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
