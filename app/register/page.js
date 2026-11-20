import RegisterForm from "./register-form";
import AuthCard from "../auth-card";

export const metadata = {
  title: "Crear cuenta | Chatly",
};

export default function RegisterPage() {
  return (
    <AuthCard
      title="Crea tu cuenta en Chatly"
      subtitle="Completa tus datos para empezar a conversar."
    >
      <RegisterForm />
    </AuthCard>
  );
}
