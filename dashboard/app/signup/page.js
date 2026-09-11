'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from "../../lib/AuthContext";
import { supabase } from "../../lib/supabaseClient";

const HUBS = [
  { name: 'Koramangala South Hub', lat: 12.9352, lon: 77.6245 },
  { name: 'Indiranagar Metro Hub', lat: 12.9784, lon: 77.6408 },
  { name: 'Whitefield ITPL Hub', lat: 12.9698, lon: 77.7499 },
  { name: 'Electronic City Phase 1 Hub', lat: 12.8399, lon: 77.6770 },
  { name: 'HSR Layout Sector 2 Hub', lat: 12.9116, lon: 77.6534 },
];

const VEHICLE_PRESETS = [
  { name: 'Tata Ace EV (Mini Truck)', capacityKg: 600, batteryKwh: 21.3, rangeKm: 154, type: '4-Wheeler EV' },
  { name: 'Mahindra Zor Grand (3W Cargo)', capacityKg: 450, batteryKwh: 10.2, rangeKm: 120, type: '3-Wheeler EV' },
  { name: 'Euler HiLoad EV (3W Heavy)', capacityKg: 688, batteryKwh: 12.4, rangeKm: 129, type: '3-Wheeler EV' },
  { name: 'Ather 450X (2W Hyperlocal)', capacityKg: 35, batteryKwh: 3.7, rangeKm: 110, type: '2-Wheeler EV' },
  { name: 'Hero Electric Nyx (2W Cargo)', capacityKg: 50, batteryKwh: 3.0, rangeKm: 85, type: '2-Wheeler EV' },
];

function SignupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { signUp } = useAuth();

  const initialRole = searchParams.get('role') === 'partner' ? 'partner' : 'manager';
  const [role, setRole] = useState(initialRole);

  // Common Fields
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');

  // Manager specific
  const [companyName, setCompanyName] = useState('');
  const [operationsCity, setOperationsCity] = useState('Bengaluru');

  // Partner specific
  const [vehicleModel, setVehicleModel] = useState(VEHICLE_PRESETS[0].name);
  const [registrationPlate, setRegistrationPlate] = useState('');
  const [selectedHub, setSelectedHub] = useState(HUBS[0].name);
  const [capacityKg, setCapacityKg] = useState(VEHICLE_PRESETS[0].capacityKg);
  const [batteryKwh, setBatteryKwh] = useState(VEHICLE_PRESETS[0].batteryKwh);

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    const matched = VEHICLE_PRESETS.find((v) => v.name === vehicleModel);
    if (matched) {
      setCapacityKg(matched.capacityKg);
      setBatteryKwh(matched.batteryKwh);
    }
  }, [vehicleModel]);

  const handleSignup = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');
    setLoading(true);

    try {
      let createdPartnerId = null;

      // 1. If role is partner, generate a unique partner ID and insert into delivery_partners
      if (role === 'partner') {
        const cleanReg = registrationPlate.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
        createdPartnerId = `PTR_${cleanReg || Date.now().toString().slice(-6)}`;

        const hub = HUBS.find((h) => h.name === selectedHub) || HUBS[0];

        // Insert into public.delivery_partners
        const { error: partnerInsertErr } = await supabase.from('delivery_partners').upsert({
          id: createdPartnerId,
          name: fullName,
          phone: phone,
          vehicle_model: vehicleModel,
          registration_plate: registrationPlate.trim().toUpperCase(),
          battery_pct: 95.0,
          current_lat: hub.lat,
          current_lon: hub.lon,
          status: 'AVAILABLE',
          capacity_kg: parseFloat(capacityKg) || 500,
          assigned_order_count: 0,
          total_completed_trips: 0,
          total_payout_inr: 0.0,
          rating: 5.0,
        });

        if (partnerInsertErr) {
          console.error('Failed to register vehicle in delivery_partners:', partnerInsertErr);
          // Continue if already exists or non-fatal
        }
      }

      // 2. Sign up user via Supabase Auth
      await signUp({
        email,
        password,
        fullName,
        role,
        phone,
        companyName: role === 'manager' ? companyName : 'Independent Fleet Contractor',
        partnerId: createdPartnerId,
      });

      setSuccessMessage('Account registered successfully! Redirecting...');

      setTimeout(() => {
        if (role === 'partner') {
          router.push('/partner');
        } else {
          router.push('/');
        }
      }, 1200);
    } catch (err) {
      console.error('Signup error:', err);
      setErrorMessage(err.message || 'Failed to create account');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-center items-center px-4 py-12 relative overflow-hidden">
      {/* Glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] bg-gradient-to-tr from-cyan-500/10 via-emerald-500/10 to-indigo-500/10 blur-[140px] rounded-full pointer-events-none -z-10" />

      <div className="w-full max-w-xl">
        {/* Header Branding */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/90 border border-slate-800 text-cyan-400 text-xs font-semibold uppercase tracking-wider mb-3">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            SWARMRoute Decentralized Mesh Onboarding
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            Create an Account
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Join the autonomous green logistics network across India
          </p>
        </div>

        {/* Role Switcher Tabs */}
        <div className="grid grid-cols-2 p-1.5 mb-6 bg-slate-900/80 border border-slate-800 rounded-xl backdrop-blur-md">
          <button
            type="button"
            onClick={() => { setRole('manager'); setErrorMessage(''); }}
            className={`py-2.5 px-4 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2 ${
              role === 'manager'
                ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>🏢</span>
            <span>Company Manager (Admin)</span>
          </button>
          <button
            type="button"
            onClick={() => { setRole('partner'); setErrorMessage(''); }}
            className={`py-2.5 px-4 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2 ${
              role === 'partner'
                ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-md shadow-emerald-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>🛵</span>
            <span>Delivery Partner (User)</span>
          </button>
        </div>

        {/* Form Container */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 sm:p-8 backdrop-blur-xl shadow-2xl">
          <div className="mb-6">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              {role === 'manager' ? (
                <>
                  <span className="text-cyan-400">🏢</span> Enterprise Dispatch Manager Registration
                </>
              ) : (
                <>
                  <span className="text-emerald-400">🛵</span> Electric Vehicle Partner Onboarding
                </>
              )}
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              {role === 'manager'
                ? 'Create an administrative profile to assign orders, trigger AI optimization, and monitor hub metrics.'
                : 'Register your electric vehicle to receive optimized stops, execute deliveries, and receive instant INR payouts.'}
            </p>
          </div>

          {errorMessage && (
            <div className="mb-5 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
              <span className="text-rose-400 mt-0.5">⚠️</span>
              <div>{errorMessage}</div>
            </div>
          )}

          {successMessage && (
            <div className="mb-5 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-start gap-2">
              <span className="text-emerald-400 mt-0.5">✓</span>
              <div>{successMessage}</div>
            </div>
          )}

          <form onSubmit={handleSignup} className="space-y-4">
            {/* Common Info */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder={role === 'manager' ? 'Aarav Sharma' : 'Rajesh Kumar'}
                  className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
                  Phone Number
                </label>
                <input
                  type="tel"
                  required
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+91 98765 43210"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
                  Email Address
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
                  Password
                </label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min 6 characters"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                />
              </div>
            </div>

            {/* Role Specific Section: MANAGER */}
            {role === 'manager' && (
              <div className="pt-2 border-t border-slate-800 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
                      Company / Organization Name
                    </label>
                    <input
                      type="text"
                      required
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      placeholder="e.g. Zepto Express / SWARM Logistics"
                      className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
                      Operations City
                    </label>
                    <input
                      type="text"
                      value={operationsCity}
                      onChange={(e) => setOperationsCity(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Role Specific Section: DELIVERY PARTNER */}
            {role === 'partner' && (
              <div className="pt-2 border-t border-slate-800 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
                      Vehicle Model
                    </label>
                    <select
                      value={vehicleModel}
                      onChange={(e) => setVehicleModel(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                    >
                      {VEHICLE_PRESETS.map((v) => (
                        <option key={v.name} value={v.name} className="bg-slate-900 text-slate-100">
                          {v.name} ({v.type})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
                      Registration Plate Number
                    </label>
                    <input
                      type="text"
                      required
                      value={registrationPlate}
                      onChange={(e) => setRegistrationPlate(e.target.value)}
                      placeholder="e.g. KA-01-EQ-5544"
                      className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-slate-100 placeholder-slate-500 text-sm uppercase focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="sm:col-span-1">
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
                      Max Payload (kg)
                    </label>
                    <input
                      type="number"
                      required
                      value={capacityKg}
                      onChange={(e) => setCapacityKg(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>

                  <div className="sm:col-span-2">
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
                      Home Base Hub (Bengaluru)
                    </label>
                    <select
                      value={selectedHub}
                      onChange={(e) => setSelectedHub(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                    >
                      {HUBS.map((h) => (
                        <option key={h.name} value={h.name} className="bg-slate-900 text-slate-100">
                          {h.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className={`w-full mt-4 py-3 px-4 rounded-xl font-bold text-sm tracking-wide text-white transition-all shadow-lg flex items-center justify-center gap-2 ${
                role === 'manager'
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
                  <span>Registering to Supabase...</span>
                </>
              ) : (
                <span>Complete Registration & Launch</span>
              )}
            </button>
          </form>
        </div>

        {/* Footer Navigation */}
        <p className="text-center text-xs text-slate-400 mt-6">
          Already have an account?{' '}
          <Link
            href="/login"
            className="text-cyan-400 hover:text-cyan-300 font-semibold underline underline-offset-4"
          >
            Log in here
          </Link>
        </p>
      </div>
    </main>
  );
}

export default function SignupPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400 font-mono text-sm">
          Loading Registration Portal...
        </main>
      }
    >
      <SignupForm />
    </Suspense>
  );
}
