'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from './supabaseClient';

const AuthContext = createContext({
  user: null,
  profile: null,
  role: null, // 'manager' | 'partner' | null
  loading: true,
  signIn: async () => {},
  signUp: async () => {},
  signOut: async () => {},
  refreshProfile: async () => {},
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  // Helper to fetch or initialize user's profile from Supabase
  const loadUserProfile = async (supabaseUser) => {
    if (!supabaseUser) {
      setProfile(null);
      setLoading(false);
      return;
    }

    try {
      // 1. Try to fetch existing profile from public.profiles
      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', supabaseUser.id)
        .maybeSingle();

      if (error && error.code !== 'PGRST116') {
        console.warn('Error fetching user profile:', error.message);
      }

      if (data) {
        const userCity = data.city || supabaseUser.user_metadata?.city || (typeof window !== 'undefined' ? localStorage.getItem('swarm_registered_city') : null) || null;
        if (userCity && typeof window !== 'undefined') {
          localStorage.setItem('swarm_registered_city', userCity);
        }
        const meta = supabaseUser.user_metadata || {};
        setProfile({
          ...data,
          city: userCity,
          vehicle_model: meta.vehicle_model || data.vehicle_model || null,
          registration: meta.registration || data.registration || null,
          hub: meta.hub || data.hub || null,
          partner_id: meta.partner_id || data.vehicle_id || null,
        });
      } else {
        // Fallback or self-heal: create profile from user_metadata if absent
        const meta = supabaseUser.user_metadata || {};
        const userCity = meta.city || (typeof window !== 'undefined' ? localStorage.getItem('swarm_registered_city') : null) || null;
        if (userCity && typeof window !== 'undefined') {
          localStorage.setItem('swarm_registered_city', userCity);
        }
        const newProfile = {
          id: supabaseUser.id,
          email: supabaseUser.email,
          full_name: meta.full_name || supabaseUser.email?.split('@')[0] || 'User',
          role: meta.role || 'manager',
          phone: meta.phone || null,
          company_name: meta.company_name || 'Fleet Operations',
          partner_id: meta.partner_id || null,
          vehicle_id: meta.partner_id || null,
          vehicle_model: meta.vehicle_model || null,
          registration: meta.registration || null,
          hub: meta.hub || null,
          city: userCity,
        };

        let insertedProfile = null;
        const { data: inserted, error: insertError } = await supabase
          .from('profiles')
          .upsert(newProfile)
          .select()
          .maybeSingle();

        if (!insertError && inserted) {
          insertedProfile = inserted;
        } else if (insertError) {
          console.warn('Profile insert error, retrying without city column:', insertError);
          const { city: _, ...fallbackNewProfile } = newProfile;
          const { data: fallbackInserted } = await supabase
            .from('profiles')
            .upsert(fallbackNewProfile)
            .select()
            .maybeSingle();
          insertedProfile = fallbackInserted;
        }
        setProfile({ ...newProfile, ...(insertedProfile || {}) });
      }
    } catch (err) {
      console.error('Failed to load profile:', err);
      // Construct minimal fallback from user session metadata
      const meta = supabaseUser.user_metadata || {};
      const userCity = meta.city || (typeof window !== 'undefined' ? localStorage.getItem('swarm_registered_city') : null) || null;
      setProfile({
        id: supabaseUser.id,
        email: supabaseUser.email,
        full_name: meta.full_name || supabaseUser.email || 'User',
        role: meta.role || 'manager',
        partner_id: meta.partner_id || null,
        city: userCity,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Safety timeout so user is never stuck on loading screen
    const safetyTimer = setTimeout(() => {
      if (process.env.NEXT_PUBLIC_ENABLE_DEMO_LOGIN === 'true') {
        const demoUser = {
          id: 'DEMO_MANAGER_01',
          email: process.env.NEXT_PUBLIC_DEMO_MANAGER_EMAIL || 'manager@swarmroute.com',
          user_metadata: { role: 'manager', city: 'Maharashtra' },
        };
        setUser(demoUser);
        setProfile({
          id: 'DEMO_MANAGER_01',
          email: 'manager@swarmroute.com',
          role: 'manager',
          city: 'Maharashtra',
          full_name: 'Operations Manager',
        });
      }
      setLoading(false);
    }, 1200);

    // Check initial active session
    supabase.auth.getSession().then(({ data: { session } }) => {
      clearTimeout(safetyTimer);
      const currentUser = session?.user || null;
      setUser(currentUser);
      if (currentUser) {
        loadUserProfile(currentUser);
      } else if (process.env.NEXT_PUBLIC_ENABLE_DEMO_LOGIN === 'true') {
        const demoUser = {
          id: 'DEMO_MANAGER_01',
          email: process.env.NEXT_PUBLIC_DEMO_MANAGER_EMAIL || 'manager@swarmroute.com',
          user_metadata: { role: 'manager', city: 'Maharashtra' },
        };
        setUser(demoUser);
        setProfile({
          id: 'DEMO_MANAGER_01',
          email: 'manager@swarmroute.com',
          role: 'manager',
          city: 'Maharashtra',
          full_name: 'Operations Manager',
        });
        setLoading(false);
      } else {
        setLoading(false);
      }
    }).catch((err) => {
      clearTimeout(safetyTimer);
      console.warn("getSession error:", err);
      if (process.env.NEXT_PUBLIC_ENABLE_DEMO_LOGIN === 'true') {
        setUser({ id: 'DEMO_MANAGER_01', email: 'manager@swarmroute.com' });
        setProfile({ role: 'manager', city: 'Maharashtra', full_name: 'Operations Manager' });
      }
      setLoading(false);
    });

    // Listen to Supabase auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        const currentUser = session?.user || null;
        setUser(currentUser);
        if (currentUser) {
          await loadUserProfile(currentUser);
        } else if (process.env.NEXT_PUBLIC_ENABLE_DEMO_LOGIN === 'true') {
          setProfile({ role: 'manager', city: 'Maharashtra', full_name: 'Operations Manager' });
          setLoading(false);
        } else {
          setProfile(null);
          setLoading(false);
        }
      }
    );

    return () => {
      clearTimeout(safetyTimer);
      subscription.unsubscribe();
    };
  }, []);

  const signIn = async ({ email, password }) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw error;
    if (data?.user?.user_metadata?.city && typeof window !== 'undefined') {
      localStorage.setItem('swarm_registered_city', data.user.user_metadata.city);
    }
    return data;
  };

  const signUp = async ({
    email,
    password,
    fullName,
    role,
    phone,
    companyName,
    partnerId,
    city,
    vehicleModel,
    registration,
    hub,
  }) => {
    const userCity = city?.trim() || (typeof window !== 'undefined' ? localStorage.getItem('swarm_registered_city') : null) || null;
    if (userCity && typeof window !== 'undefined') {
      localStorage.setItem('swarm_registered_city', userCity);
    }

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: fullName,
          role: role || 'manager',
          phone: phone || null,
          company_name: companyName || null,
          partner_id: partnerId || null,
          vehicle_id: partnerId || null,
          vehicle_model: vehicleModel || null,
          registration: registration || null,
          hub: hub || null,
          city: userCity,
        },
      },
    });
    if (error) throw error;

    if (data.user) {
      // Upsert into public.profiles table
      const profileData = {
        id: data.user.id,
        email: data.user.email,
        full_name: fullName,
        role: role || 'manager',
        phone: phone || null,
        company_name: companyName || null,
        partner_id: partnerId || null,
        city: userCity,
      };

      const { error: insertErr } = await supabase.from('profiles').upsert(profileData);
      if (insertErr) {
        console.warn('Profiles upsert with city column returned error, retrying without city:', insertErr.message);
        const { city: _, ...fallbackData } = profileData;
        const { error: fallbackErr } = await supabase.from('profiles').upsert(fallbackData);
        if (fallbackErr) {
          console.warn('Secondary profile upsert error:', fallbackErr.message);
        }
      }
    }

    return data;
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
    setUser(null);
    setProfile(null);
  };

  const refreshProfile = async () => {
    if (user) {
      await loadUserProfile(user);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        role: profile?.role || user?.user_metadata?.role || null,
        loading,
        signIn,
        signUp,
        signOut,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
