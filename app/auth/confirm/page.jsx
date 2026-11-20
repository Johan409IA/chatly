import AuthCard from "../../auth-card";
import ConfirmStatus from "./confirm-status";

export const metadata = {
  title: "Confirma tu correo | Chatly",
};

export default async function ConfirmPage({ searchParams }) {
  const search = await searchParams;
  return (
    <AuthCard title="Confirma tu correo" subtitle="">
      <ConfirmStatus
        tokenHash={search.token_hash || ""}
        code={search.code || ""}
        type={search.type || "signup"}
      />
    </AuthCard>
  );
}
