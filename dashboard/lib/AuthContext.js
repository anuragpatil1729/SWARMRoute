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
        const userCity = data.city || supabaseUser.user_metadata?.city || (typeof window !== 'undefined' ? localStorage.getItem('swarm_registered_city') : null) || 'Bengaluru';
        if (typeof window !== 'undefined') {
          localStorage.setItem('swarm_registered_city', userCity);
        }
        setProfile({ ...data, city: userCity });
      } else {
        // Fallback or self-heal: create profile from user_metadata if absent
        const meta = supabaseUser.user_metadata || {};
        const userCity = meta.city || (typeof window !== 'undefined' ? localStorage.getItem('swarm_registered_city') : null) || 'Bengaluru';
        if (typeof window !== 'undefined') {
          localStorage.setItem('swarm_registered_city', userCity);
        }
        const newProfile = {
          id: supabaseUser.id,
          email: supabaseUser.email,
          full_name: meta.full_name || supabaseUser.email?.split('@')[0] || 'User',
          role: meta.role || 'manager',
          phone: meta.phone || null,
          company_name: meta.company_name || 'SWARM Logistics',
          partner_id: meta.partner_id || null,
          city: userCity,
        };

        const { data: inserted, error: insertError } = await supabase
          .from('profiles')
          .upsert(newProfile)
          .select()
          .maybeSingle();

        if (!insertError && inserted) {
          setProfile(inserted);
        } else {
          setProfile(newProfile);
        }
      }
    } catch (err) {
      console.error('Failed to load profile:', err);
      // Construct minimal fallback from user session metadata
      const meta = supabaseUser.user_metadata || {};
      const userCity = meta.city || (typeof window !== 'undefined' ? localStorage.getItem('swarm_registered_city') : null) || 'Bengaluru';
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
    // Check initial active session
    supabase.auth.getSession().then(({ data: { session } }) => {
      const currentUser = session?.user || null;
      setUser(currentUser);
      if (currentUser) {
        loadUserProfile(currentUser);
      } else {
        setLoading(false);
      }
    });

    // Listen to Supabase auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        const currentUser = session?.user || null;
        setUser(currentUser);
        if (currentUser) {
          await loadUserProfile(currentUser);
        } else {
          setProfile(null);
          setLoading(false);
        }
      }
    );

    return () => {
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

  const signUp = async ({ email, password, fullName, role, phone, companyName, partnerId, city }) => {
    const userCity = city?.trim() || (typeof window !== 'undefined' ? localStorage.getItem('swarm_registered_city') : null) || 'Bengaluru';
    if (typeof window !== 'undefined') {
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
          city: userCity,
        },
      },
    });
    if (error) throw error;

    if (data.user) {
      // Upsert into public.profiles table
      try {
        await supabase.from('profiles').upsert({
          id: data.user.id,
          email: data.user.email,
          full_name: fullName,
          role: role || 'manager',
          phone: phone || null,
          company_name: companyName || null,
          partner_id: partnerId || null,
          city: userCity,
        });
      } catch (upsertErr) {
        console.warn('Profiles upsert with city error, retrying without:', upsertErr);
        await supabase.from('profiles').upsert({
          id: data.user.id,
          email: data.user.email,
          full_name: fullName,
          role: role || 'manager',
          phone: phone || null,
          company_name: companyName || null,
          partner_id: partnerId || null,
        }).catch((e) => console.warn('Secondary profile upsert error:', e));
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
