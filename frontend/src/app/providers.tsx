"use client";

import { GoogleOAuthProvider } from "@react-oauth/google";

type ProvidersProps = {
    children: React.ReactNode;
};

export default function Providers({ children }: ProvidersProps) {
    // Keep OAuth context available during SSR/prerender even when env is missing.
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "__MISSING_GOOGLE_CLIENT_ID__";

    return <GoogleOAuthProvider clientId={clientId}>{children}</GoogleOAuthProvider>;
}
