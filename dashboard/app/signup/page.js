'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from "../../lib/AuthContext";
import { supabase } from "../../lib/supabaseClient";

const CITY_HUBS = {
  Maharashtra: [
    'BKC Central Freight Hub (Mumbai)',
    'Hinjawadi Phase 1 Logistics Hub (Pune)',
    'Andheri MIDC Cargo Terminal (Mumbai)',
    'Thane Wagle Estate Hub (Thane)',
    'Vashi APMC Market Hub (Navi Mumbai)',
    'Bhosari MIDC Hub (Pune)',
  ],
  Mumbai: [
    'BKC Central Freight Hub',
    'Andheri MIDC Cargo Terminal',
    'Vashi APMC Market Hub',
    'Powai Tech Logistics Point',
    'Thane Wagle Estate Hub',
  ],
  Delhi: [
    'Okhla Phase 2 Logistics Depot',
    'Connaught Place Central Hub',
    'Nehru Place Commercial Hub',
    'Noida Sector 62 IT Hub',
    'Gurugram Cyber City Freight Point',
  ],
  Hyderabad: [
    'HITEC City Logistics Gateway',
    'Gachibowli Cargo Terminal',
    'Sanathnagar Industrial Hub',
    'Secunderabad Rail Freight Depot',
    'Kukatpally Commercial Hub',
  ],
  Pune: [
    'Hinjawadi Phase 1 Logistics Hub',
    'Shivaji Nagar Central Terminal',
    'Hadapsar Magarpatta City Hub',
    'Kothrud Transit Point',
    'Bhosari MIDC Hub',
  ],
  Chennai: [
    'Guindy Industrial Terminal',
    'Ambattur Industrial Hub',
    'OMR IT Corridor Hub',
    'T Nagar Commercial Center',
    'Sriperumbudur Freight Park',
  ],
  Kolkata: [
    'Salt Lake Sector V Hub',
    'Rajarhat New Town Center',
    'Burrabazar Freight Hub',
    'Howrah Rail Depot',
    'Taratala Industrial Terminal',
  ],
  Ahmedabad: [
    'Sanand Industrial Freight Hub',
    'Changodar Logistics Park',
    'SG Highway Commercial Node',
    'Naroda GIDC Hub',
  ],
};

function getHubsForCity(cityName) {
  if (!cityName) return ['Central Logistics Hub', 'North Depot', 'South Hub', 'East Hub', 'West Terminal'];
  const clean = cityName.trim();
  for (const [k, list] of Object.entries(CITY_HUBS)) {
    if (k.toLowerCase() === clean.toLowerCase() || clean.toLowerCase().includes(k.toLowerCase()) || k.toLowerCase().includes(clean.toLowerCase())) {
      return list;
    }
  }
  return [
    `${clean} Central Logistics Hub`,
    `${clean} North Sector Depot`,
    `${clean} South Industrial Hub`,
    `${clean} East Commercial Terminal`,
  ];
}

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
  const [operationsCity, setOperationsCity] = useState('');

  // Partner specific
  const [partnerCity, setPartnerCity] = useState('');
  const [vehicleModel, setVehicleModel] = useState(VEHICLE_PRESETS[0].name);
  const [registrationPlate, setRegistrationPlate] = useState('');
  const [selectedHub, setSelectedHub] = useState('Central Logistics Hub');
  const [capacityKg, setCapacityKg] = useState(VEHICLE_PRESETS[0].capacityKg);
  const [batteryKwh, setBatteryKwh] = useState(VEHICLE_PRESETS[0].batteryKwh);

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('swarm_registered_city');
      if (stored) {
        setPartnerCity(stored);
        setOperationsCity(stored);
        const hubs = getHubsForCity(stored);
        if (hubs.length > 0) setSelectedHub(hubs[0]);
      }
    }
  }, []);

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
      const registeredCity = (role === 'manager' ? operationsCity.trim() : (partnerCity.trim() || operationsCity.trim() || 'Operations')) || 'Operations';

      // 1. If role is partner, generate a unique partner ID and insert into delivery_partners
      if (role === 'partner') {
        const cleanReg = registrationPlate.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
        createdPartnerId = `PTR_${cleanReg || Date.now().toString().slice(-6)}`;

        // Insert into public.delivery_partners matching database schema
        const { error: partnerInsertErr } = await supabase.from('delivery_partners').upsert({
          id: createdPartnerId,
          name: fullName,
          phone: phone,
          vehicle_model: vehicleModel,
          registration: registrationPlate.trim().toUpperCase(),
          hub: selectedHub,
          city: registeredCity,
          rating: null,
          completed_deliveries: 0,
          avatar: '🚚',
          status: 'AVAILABLE',
          current_load: 0.0,
          max_weight: parseFloat(capacityKg) || null,
          fuel_level: 100.0,
          speed_kmh: 0.0,
          location_x: null,
          location_y: null,
        });

        if (partnerInsertErr) {
          console.error('Failed to register vehicle in delivery_partners:', partnerInsertErr.message);
        }
      }

      if (typeof window !== 'undefined') {
        localStorage.setItem('swarm_registered_city', registeredCity);
      }

      // Sync registered city with simulation engine
      try {
        await fetch('/api/simulation/city', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ city: registeredCity }),
        });
      } catch (cityErr) {
        console.warn('Could not sync city with simulation runner:', cityErr);
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
        city: registeredCity,
        vehicleModel: role === 'partner' ? vehicleModel : null,
        registration: role === 'partner' ? registrationPlate.trim().toUpperCase() : null,
        hub: role === 'partner' ? selectedHub : null,
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
    <div className="w-full flex flex-col justify-center items-center py-6">
      <div className="w-full max-w-xl">
        {/* Header Branding */}
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Create an Account
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            Join the autonomous fleet dispatch and dynamic mesh network
          </p>
        </div>

        {/* Role Switcher Tabs */}
        <div className="grid grid-cols-2 p-1 mb-6 bg-slate-100 border border-slate-200 rounded-lg">
          <button
            type="button"
            onClick={() => { setRole('manager'); setErrorMessage(''); }}
            className={`py-2 px-3 text-xs font-semibold rounded-md transition-all flex items-center justify-center gap-1.5 ${
              role === 'manager'
                ? 'bg-white text-blue-700 shadow-xs border border-slate-200 font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>🏢</span>
            <span>Company Manager</span>
          </button>
          <button
            type="button"
            onClick={() => { setRole('partner'); setErrorMessage(''); }}
            className={`py-2 px-3 text-xs font-semibold rounded-md transition-all flex items-center justify-center gap-1.5 ${
              role === 'partner'
                ? 'bg-white text-emerald-700 shadow-xs border border-slate-200 font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>🛵</span>
            <span>Delivery Partner</span>
          </button>
        </div>

        {/* Form Container */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 sm:p-8 shadow-sm">
          <div className="mb-5 pb-4 border-b border-slate-100">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              {role === 'manager' ? (
                <>
                  <span>🏢</span> Enterprise Dispatch Manager Registration
                </>
              ) : (
                <>
                  <span>🛵</span> Delivery Vehicle Partner Onboarding
                </>
              )}
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              {role === 'manager'
                ? 'Create an administrative profile to assign orders, trigger AI optimization, and monitor hub metrics.'
                : 'Register your delivery vehicle to receive optimized stops, execute deliveries, and receive payouts.'}
            </p>
          </div>

          {errorMessage && (
            <div className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
              <span className="text-rose-600 font-bold mt-0.5">⚠️</span>
              <div>{errorMessage}</div>
            </div>
          )}

          {successMessage && (
            <div className="mb-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs flex items-start gap-2">
              <span className="text-emerald-600 font-bold mt-0.5">✓</span>
              <div>{successMessage}</div>
            </div>
          )}

          <form onSubmit={handleSignup} className="space-y-4">
            {/* Common Info */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Enter your full name"
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Phone Number
                </label>
                <input
                  type="tel"
                  required
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+91 98765 43210"
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min 6 characters"
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
              </div>
            </div>

            {/* Role Specific Section: MANAGER */}
            {role === 'manager' && (
              <div className="pt-2 border-t border-slate-100 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Company / Organization Name
                    </label>
                    <input
                      type="text"
                      required
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      placeholder="e.g. Zepto Express / SWARM Logistics"
                      className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Operations City
                    </label>
                    <input
                      type="text"
                      required
                      value={operationsCity}
                      onChange={(e) => setOperationsCity(e.target.value)}
                      placeholder="e.g. Mumbai, Delhi, Bengaluru, Pune"
                      className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Role Specific Section: DELIVERY PARTNER */}
            {role === 'partner' && (
              <div className="pt-2 border-t border-slate-100 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Operating City
                    </label>
                    <input
                      type="text"
                      required
                      value={partnerCity}
                      onChange={(e) => {
                        const val = e.target.value;
                        setPartnerCity(val);
                        const hubs = getHubsForCity(val);
                        if (hubs.length > 0) setSelectedHub(hubs[0]);
                      }}
                      placeholder="e.g. Mumbai, Delhi, Bengaluru, Pune"
                      className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Vehicle Model
                    </label>
                    <select
                      value={vehicleModel}
                      onChange={(e) => setVehicleModel(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                    >
                      {VEHICLE_PRESETS.map((v) => (
                        <option key={v.name} value={v.name}>
                          {v.name} ({v.type})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Registration Plate Number
                    </label>
                    <input
                      type="text"
                      required
                      value={registrationPlate}
                      onChange={(e) => setRegistrationPlate(e.target.value)}
                      placeholder="e.g. MH-01-AB-1234"
                      className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder-slate-400 text-sm uppercase focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Max Payload (kg)
                    </label>
                    <input
                      type="number"
                      required
                      value={capacityKg}
                      onChange={(e) => setCapacityKg(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Home Base Hub
                    </label>
                    <select
                      value={selectedHub}
                      onChange={(e) => setSelectedHub(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                    >
                      {getHubsForCity(partnerCity || operationsCity).map((h) => (
                        <option key={h} value={h}>
                          {h}
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
              className={`w-full mt-5 py-2.5 px-4 rounded-lg font-bold text-xs tracking-wide text-white transition shadow-xs flex items-center justify-center gap-2 ${
                role === 'manager'
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
                  <span>Registering...</span>
                </>
              ) : (
                <span>Complete Registration & Launch</span>
              )}
            </button>
          </form>
        </div>

        {/* Footer Navigation */}
        <p className="text-center text-xs text-slate-500 mt-5">
          Already have an account?{' '}
          <Link
            href="/login"
            className="text-blue-600 hover:text-blue-700 font-semibold underline underline-offset-2"
          >
            Log in here
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense
      fallback={
        <div className="w-full py-12 flex items-center justify-center text-slate-400 font-mono text-xs">
          Loading Registration Portal...
        </div>
      }
    >
      <SignupForm />
    </Suspense>
  );
}
