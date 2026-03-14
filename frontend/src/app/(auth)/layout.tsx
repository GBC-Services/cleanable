/**
 * Auth layout — centered card on a clean background.
 * Used for /login, /register, /forgot-password.
 */
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-brand-500">
            Cleanable
          </h1>
        </div>
        {children}
      </div>
    </div>
  );
}
