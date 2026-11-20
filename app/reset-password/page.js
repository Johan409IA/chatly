import AuthCard from "../auth-card";
import ResetPasswordForm from "./reset-form";

export const metadata = {
  title: "Restablecer contraseña | Chatly",
};

export default async function ResetPasswordPage({ searchParams }) {
  const { token_hash: tokenHash = "" } = await searchParams;
  return (
    <AuthCard
      title="Crea una nueva contraseña"
      subtitle="Usa una contraseña segura para proteger tu cuenta."
    >
      <ResetPasswordForm tokenHash={tokenHash} />
    </AuthCard>
  );
}
