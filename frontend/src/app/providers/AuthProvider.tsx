import React, { useEffect, useState } from 'react';
import { AuthContext } from './AuthContext';
import { authService } from '../../features/auth/services/authService';
import { LoginPayload, RegisterPayload, UserProfile } from '../../types/auth';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshUser = async (): Promise<UserProfile | null> => {
    if (!authService.hasToken()) {
      setUser(null);
      setIsLoading(false);
      return null;
    }

    try {
      const profile = await authService.getCurrentUser();
      setUser(profile);
      return profile;
    } catch {
      setUser(null);
      authService.logout();
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const login = async (payload: LoginPayload): Promise<UserProfile> => {
    setIsLoading(true);
    try {
      await authService.login(payload);
      const profile = await authService.getCurrentUser();
      setUser(profile);
      return profile;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (payload: RegisterPayload): Promise<UserProfile> => {
    setIsLoading(true);
    try {
      return await authService.register(payload);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = (): void => {
    authService.logout();
    setUser(null);
  };

  const role = user?.role || null;
  const isAuthenticated = Boolean(user);

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        isAuthenticated,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
