import AuthCard from "../auth-card";
import ForgotPasswordForm from "./forgot-form";

export const metadata = {
  title: "Recuperar contraseña | Chatly",
};

export default function ForgotPasswordPage() {
  return (
    <AuthCard
      title="Recupera tu contraseña"
      subtitle="Te enviaremos un enlace si encontramos una cuenta con ese correo."
    >
      <ForgotPasswordForm />
    </AuthCard>
  );
}
