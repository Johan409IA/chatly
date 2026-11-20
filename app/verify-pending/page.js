import AuthCard from "../auth-card";
import ResendForm from "./resend-form";

export const metadata = {
  title: "Confirma tu correo | Chatly",
};

export default async function VerifyPendingPage({ searchParams }) {
  const { email = "" } = await searchParams;
  return (
    <AuthCard
      title="Confirma tu correo"
      subtitle="Abre el enlace que te enviamos para activar tu cuenta."
    >
      <ResendForm initialEmail={email} />
    </AuthCard>
  );
}
