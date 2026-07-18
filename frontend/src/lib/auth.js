import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("surginote_token");
    const stored = localStorage.getItem("surginote_user");
    if (token && stored) {
      setUser(JSON.parse(stored));
      // background verify
      api.me().then((u) => {
        setUser(u);
        localStorage.setItem("surginote_user", JSON.stringify(u));
      }).catch(() => {});
    }
    setReady(true);
  }, []);

  const login = async (email, password) => {
    const { token, user: u } = await api.login({ email, password });
    localStorage.setItem("surginote_token", token);
    localStorage.setItem("surginote_user", JSON.stringify(u));
    setUser(u);
    return u;
  };

  const register = async (email, password, name) => {
    const { token, user: u } = await api.register({ email, password, name });
    localStorage.setItem("surginote_token", token);
    localStorage.setItem("surginote_user", JSON.stringify(u));
    setUser(u);
    return u;
  };

  const logout = () => {
    localStorage.removeItem("surginote_token");
    localStorage.removeItem("surginote_user");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, ready, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
