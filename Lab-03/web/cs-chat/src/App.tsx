import { Navigate, Route, Routes } from "react-router-dom";
import Login from "@/routes/Login";
import Chat from "@/routes/Chat";
import { getCurrentUser } from "@/lib/auth";

function RequireAuth({ children }: { children: JSX.Element }) {
  const user = getCurrentUser();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/chat"
        element={
          <RequireAuth>
            <Chat />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
